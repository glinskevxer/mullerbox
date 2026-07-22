"""What order the additions go into the muller, and why the order changes them.

Every module in this package sizes one addition on its own. The muller takes
them all at once, and the order is not a preference. Three of the four change
the base the next one is sized against, so a batch charged in the wrong order is
not the batch anybody calculated.

**New sand first, and everything else is sized after it.** New sand dilutes: it
lowers the clay percentage, the carbon percentage and the moisture, all at once
and all by the same share. Sizing the bentonite against the pre dilution reading
and then adding new sand underdoses the bond by exactly the dilution. The shop
version of this mistake is a bond that never comes up on a shift where new sand
went in, and it gets blamed on the bentonite.

**Water last, and never at the same time as the dry materials.** Bentonite that
meets water before it meets the sand balls up, and a ball of wet clay in a
muller is bond that is in the batch and not on the sand. So the dry charge goes
in, gets its dry mull, and the water follows.

**Seacoal rides with the bentonite** because neither one changes the other's
base, and splitting them costs a mull the shop does not have.

The one thing this module refuses to do is size anything against a nameplate
system mass. `mullerbox.system.state` says why that figure is a guess, and a
charge order built on a guess is four wrong numbers rather than one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from mullerbox.addition.material import Addition, Material, dry_total
from mullerbox.errors import BadInputError, RuleError
from mullerbox.system.state import SandSystem
from mullerbox.units.bulk import Pounds
from mullerbox.units.percent import Percent

_PLACES = Decimal("0.01")

# The order the muller sees, and the order dilution has to be applied in.
CHARGE_ORDER: tuple[Material, ...] = (
    Material.NEW_SAND,
    Material.BENTONITE,
    Material.SEACOAL,
    Material.WATER,
)

# Materials that go in together and get one dry mull between them.
DRY_CHARGE: frozenset[Material] = frozenset(
    {Material.NEW_SAND, Material.BENTONITE, Material.SEACOAL}
)


def dilution_factor(new_sand: Pounds, system_mass: Pounds) -> Decimal:
    """What a percentage reading becomes once new sand is folded in.

    A fraction, at or below one. Multiply any percentage measured before the new
    sand went in and you have what it will read after, before anything else is
    added. Six places, because the number is used to scale a target and the
    rounding compounds across the three dry materials.
    """
    if not isinstance(new_sand, Pounds):
        raise BadInputError("new sand is a bulk mass")
    if not isinstance(system_mass, Pounds):
        raise BadInputError("the system mass is a bulk mass")
    if system_mass.is_zero:
        raise BadInputError("nothing can be diluted into a system with no sand")
    after = system_mass + new_sand
    return (system_mass.value / after.value).quantize(Decimal("0.000001"))


def diluted(reading: Percent, factor: Decimal) -> Percent:
    """A percentage after dilution, which is the reading the bond should chase."""
    if not isinstance(reading, Percent):
        raise BadInputError("a diluted reading is a percentage")
    if not isinstance(factor, Decimal):
        raise BadInputError("a dilution factor is a decimal")
    if not Decimal(0) < factor <= Decimal(1):
        raise BadInputError("a dilution factor is above zero and at most one")
    return Percent((reading.value * factor).quantize(_PLACES, rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class Step:
    """One addition and where it falls in the charge."""

    position: int
    addition: Addition
    wait_for_mull: bool

    def __post_init__(self) -> None:
        if not isinstance(self.addition, Addition):
            raise BadInputError("a charge step holds an addition")
        if isinstance(self.position, bool) or not isinstance(self.position, int):
            raise BadInputError("a charge position is a whole number")
        if self.position < 1:
            raise BadInputError("the charge starts at position one")

    def __str__(self) -> str:
        tail = ", after the dry mull" if self.wait_for_mull else ""
        return f"{self.position}. {self.addition}{tail}"


@dataclass(frozen=True)
class ChargeOrder:
    """A whole batch's additions, in the order they go in."""

    system: SandSystem
    steps: tuple[Step, ...]
    dilution: Decimal

    @property
    def dry(self) -> Pounds:
        return dry_total([step.addition for step in self.steps])

    @property
    def water(self) -> Pounds:
        for step in self.steps:
            if step.addition.material is Material.WATER:
                return step.addition.mass
        return Pounds.zero()

    @property
    def is_dilutive(self) -> bool:
        """Whether new sand went in, which is what makes the order matter."""
        return self.dilution < Decimal(1)

    @property
    def acting(self) -> tuple[Step, ...]:
        """The steps that actually put something in the muller."""
        return tuple(step for step in self.steps if not step.addition.is_nothing)

    def render(self) -> list[str]:
        """The charge sheet the muller operator works from."""
        lines = [str(step) for step in self.steps]
        if self.is_dilutive:
            lines.append(
                f"the new sand dilutes every reading to {self.dilution:.4f} of what "
                "the lab measured, and the bond above is sized against that"
            )
        return lines

    def __str__(self) -> str:
        return f"{len(self.acting)} additions, {self.dry} dry and {self.water} water"


def charge_order(
    system: SandSystem,
    when: date,
    new_sand: Addition,
    bentonite: Addition,
    seacoal: Addition,
    water: Addition,
) -> ChargeOrder:
    """Put a batch's four additions in the order the muller takes them.

    The system has to carry a mass anybody actually counted. Every addition here
    was sized as a share of that mass, so charging against a nameplate figure
    puts the same proportional error on all four at once and leaves no reading
    that could catch it.
    """
    if not isinstance(system, SandSystem):
        raise BadInputError("a charge order is against a sand system")
    if not isinstance(when, date):
        raise BadInputError("a charge order is dated")
    given = {
        Material.NEW_SAND: new_sand,
        Material.BENTONITE: bentonite,
        Material.SEACOAL: seacoal,
        Material.WATER: water,
    }
    for material, addition in given.items():
        if not isinstance(addition, Addition):
            raise BadInputError(f"the {material.label} addition is missing")
        if addition.material is not material:
            raise RuleError(
                f"a {addition.material.label} addition was given as the {material.label} one"
            )
    system.require_trustworthy(when)
    steps = tuple(
        Step(
            position=index,
            addition=given[material],
            wait_for_mull=material not in DRY_CHARGE,
        )
        for index, material in enumerate(CHARGE_ORDER, start=1)
    )
    return ChargeOrder(
        system=system,
        steps=steps,
        dilution=dilution_factor(new_sand.mass, system.mass),
    )


__all__ = [
    "CHARGE_ORDER",
    "ChargeOrder",
    "DRY_CHARGE",
    "Step",
    "charge_order",
    "diluted",
    "dilution_factor",
]
