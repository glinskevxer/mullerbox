"""Sizing a core sand mix, where making too much is worse than making too little.

Green sand that is not used goes round again. Core sand that is not used is
scrap: past bench life it is inert, it cannot go back in the hopper, and it
cannot go into the green sand system either without carrying its binder in
there. So the asymmetry runs the other way from every other addition in this
package, and the arithmetic has to reflect it.

**The allowance is for spillage, not for spare.** A blow loses a little sand
round the box every time, and that is real and has to be mixed. What is not
allowed for is "a bit extra in case", because a bit extra is a bit of scrap
every single mix and it adds up to a material line nobody can explain.

**Both catalyst conventions are already on the binder system** and this module
deliberately does not add a third. ``BinderSystem.catalyst`` is the share of the
*sand*, which is what the operator sets the pump against; ``catalyst_ratio`` is
the share of the *resin*, which is how the supplier quotes it. A conversion
helper was written here first and turned out to return the field it started
from, which is the useful kind of mistake: it means the two conventions were
already both available and nobody had to convert anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from mullerbox.core.binder import BinderSystem
from mullerbox.errors import BadInputError, RuleError
from mullerbox.units.bulk import Pounds

# What a blow loses round the box, as a share of the core weight.
SPILLAGE = Decimal("0.04")

# A mix bigger than this cannot be blown inside bench life on one machine.
MAX_PRACTICAL_MIX = Pounds(2000)

_PLACES = Decimal("0.01")


@dataclass(frozen=True)
class Mix:
    """What to charge into the core mixer, and what it will make."""

    system: BinderSystem
    cores_wanted: Pounds
    sand: Pounds
    resin: Pounds
    catalyst: Pounds
    spillage: Pounds

    @property
    def total_charge(self) -> Pounds:
        return self.sand + self.resin + self.catalyst

    @property
    def waste_if_unused(self) -> Pounds:
        """What is scrapped if none of it gets blown.

        The whole charge. There is no partial recovery from a core sand mix and
        saying so beside the number is the point of the property.
        """
        return self.total_charge

    def scrap_from_blowing(self, blown: Pounds) -> Pounds:
        """What is scrapped when only part of the mix gets used."""
        if not isinstance(blown, Pounds):
            raise BadInputError("a blown mass is a bulk mass")
        if blown > self.total_charge:
            raise RuleError(f"{blown} cannot be blown from a {self.total_charge} charge")
        return self.total_charge - blown

    def __str__(self) -> str:
        return (
            f"{self.total_charge} charge for {self.cores_wanted} of cores "
            f"on {self.system.binder.label}"
        )


def mix_for(system: BinderSystem, cores_wanted: Pounds) -> Mix:
    """Size a mix for a known weight of cores, allowing only for spillage."""
    if not isinstance(system, BinderSystem):
        raise BadInputError("a binder system is expected")
    if not isinstance(cores_wanted, Pounds):
        raise BadInputError("the cores wanted is a bulk mass")
    if cores_wanted.is_zero:
        raise BadInputError("a mix for no cores is not a mix")
    spillage = cores_wanted.scaled(SPILLAGE)
    sand = cores_wanted + spillage
    if sand > MAX_PRACTICAL_MIX:
        raise RuleError(
            f"{sand} of sand will not be blown inside a "
            f"{system.bench_life} bench life; split the mix"
        )
    resin = sand.scaled(system.resin.fraction)
    catalyst = resin.scaled(system.catalyst_ratio)
    return Mix(
        system=system,
        cores_wanted=cores_wanted,
        sand=sand,
        resin=resin,
        catalyst=catalyst,
        spillage=spillage,
    )


def cores_from(system: BinderSystem, sand: Pounds) -> Pounds:
    """How many cores a given weight of sand will make, after spillage.

    The inverse, for the case the operator has a fixed mixer and wants to know
    what it yields rather than what to charge for a target.
    """
    if not isinstance(system, BinderSystem):
        raise BadInputError("a binder system is expected")
    if not isinstance(sand, Pounds):
        raise BadInputError("the sand available is a bulk mass")
    if sand.is_zero:
        return Pounds.zero()
    return Pounds((sand.value / (Decimal(1) + SPILLAGE)).quantize(_PLACES, rounding=ROUND_HALF_UP))


__all__ = ["MAX_PRACTICAL_MIX", "Mix", "SPILLAGE", "cores_from", "mix_for"]
