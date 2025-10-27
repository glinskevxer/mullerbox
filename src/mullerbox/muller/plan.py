"""Planning one batch: the four additions worked out together, in order.

Each addition has its own module and its own arithmetic. This is where they meet,
and the meeting has an order that is not negotiable.

**Bond first.** The bentonite call depends on the measured methylene blue clay
and on how hard the last shift poured. Nothing upstream of it.

**Then carbon**, which depends on the loss on ignition and on the same burnout.
Independent of the bond call, but it goes in the same dry mull, so it is worked
out with it.

**Then new sand**, which depends on the dead clay and on what left the system.
Independent of both, and it dilutes what they just added, which is why the shop
adds it with them rather than after: sand added later dilutes bond that has
already been paid for.

**Water last, and only last.** The water response depends on the bond level, and
the bond level is what the bentonite call just changed. Working the water out
against the *measured* clay rather than the clay after the addition is the
single most common error in a sand system, and it is always in the same
direction: the system gets wetter than intended, because the extra bond takes up
water the calculation did not know about.

So the plan carries the projected bond level and hands that to the water call,
and the projection is visible on the plan rather than hidden inside it.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from mullerbox.addition.bond import BondCall, bentonite_for
from mullerbox.addition.carbon import CarbonCall, seacoal_for
from mullerbox.addition.material import Addition, Material, dry_total
from mullerbox.addition.sand import SandCall, dead_clay, new_sand_for
from mullerbox.addition.water import WaterCall, water_for
from mullerbox.burnout.loss import Burnout
from mullerbox.errors import BadInputError
from mullerbox.units.bulk import Pounds
from mullerbox.units.percent import Percent
from mullerbox.units.thermal import Temperature


@dataclass(frozen=True)
class BatchPlan:
    """The four calls for one batch, and the projection that links two of them."""

    bond: BondCall
    carbon: CarbonCall
    sand: SandCall
    water: WaterCall
    projected_clay: Percent
    batch_size: Pounds

    @property
    def additions(self) -> tuple[Addition, ...]:
        """In charging order: the dry three, then the water."""
        return (
            self.bond.addition,
            self.carbon.addition,
            self.sand.addition,
            self.water.addition,
        )

    @property
    def real_additions(self) -> tuple[Addition, ...]:
        return tuple(a for a in self.additions if not a.is_nothing)

    @property
    def dry_charge(self) -> Pounds:
        return dry_total(list(self.additions))

    @property
    def adds_bond(self) -> bool:
        return not self.bond.addition.is_nothing

    def addition_of(self, material: Material) -> Addition:
        for addition in self.additions:
            if addition.material is material:
                return addition
        raise BadInputError(f"no {material.label} on this plan")

    def render(self) -> list[str]:
        """The plan as lines, with a star against every addition that is not zero."""
        lines = [f"batch of {self.batch_size}"]
        for addition in self.additions:
            mark = "  " if addition.is_nothing else "* "
            lines.append(f"{mark}{addition}")
        lines.append(
            f"  bond projected from {self.bond.measured} to {self.projected_clay} "
            f"before the water was sized"
        )
        return lines

    def __str__(self) -> str:
        return "\n".join(self.render())


def project_clay(measured: Percent, addition: Addition, system_mass: Pounds) -> Percent:
    """Where the live clay lands once a bentonite addition has been mulled in.

    The addition is a mass of bentonite; what it is worth in methylene blue
    points is that mass times the material's yield, over the system mass. This
    is the inverse of the sizing calculation and it is written out separately so
    the two can be checked against each other rather than trusted.
    """
    if not isinstance(measured, Percent):
        raise BadInputError("the measured clay is a percentage")
    if not isinstance(addition, Addition):
        raise BadInputError("an addition is expected")
    if addition.material is not Material.BENTONITE:
        raise BadInputError("only bentonite moves the live clay")
    if not isinstance(system_mass, Pounds):
        raise BadInputError("the system mass is a bulk mass")
    if system_mass.is_zero:
        raise BadInputError("a system with no sand in it has no clay level")
    gained = (
        addition.mass.value * Material.BENTONITE.yield_factor / system_mass.value * 100
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return Percent(measured.value + gained)


def plan_batch(
    *,
    burnout: Burnout,
    system_mass: Pounds,
    batch_size: Pounds,
    measured_clay: Percent,
    clay_target: Percent,
    measured_loi: Percent,
    loi_ceiling: Percent,
    measured_total_clay: Percent,
    dead_clay_target: Percent,
    losses: Pounds,
    measured_compactability: Percent,
    compactability_target: Percent,
    return_temperature: Temperature,
) -> BatchPlan:
    """Work out one batch's four additions, in the order they depend on each other."""
    if not isinstance(batch_size, Pounds):
        raise BadInputError("the batch size is a bulk mass")
    if batch_size.is_zero:
        raise BadInputError("a batch with no sand in it is not a batch")

    bond = bentonite_for(measured_clay, clay_target, burnout, system_mass)
    carbon = seacoal_for(measured_loi, loi_ceiling, burnout, system_mass)
    sand = new_sand_for(
        losses,
        dead_clay(measured_total_clay, measured_clay),
        dead_clay_target,
        system_mass,
    )
    projected = project_clay(measured_clay, bond.addition, system_mass)
    water = water_for(
        measured_compactability,
        compactability_target,
        projected,
        batch_size,
        return_temperature,
    )
    return BatchPlan(
        bond=bond,
        carbon=carbon,
        sand=sand,
        water=water,
        projected_clay=projected,
        batch_size=batch_size,
    )


__all__ = ["BatchPlan", "plan_batch", "project_clay"]
