"""Seacoal, and why its target is a ceiling rather than an aim.

Seacoal is finely ground bituminous coal. It does one job: as the metal comes
in, the coal at the mold face pyrolyses and lays down a film of lustrous carbon
between the metal and the sand, which is what gives an iron casting a clean
peel. Too little and the casting comes out with sand fused to it. Too much and
the same volatiles that make the film also make gas, and gas makes blowholes.

That asymmetry runs all the way through the arithmetic and it is why this module
does not look like the bond one. Bentonite has an aim and you climb towards it
from either side. Seacoal has a working range with a hard ceiling, the ceiling
is a gas defect rather than a quality drift, and the addition is sized to land
below it rather than on it.

Loss on ignition is the measurement, and it is a poor proxy. It burns off
everything carbonaceous, which includes the seacoal, the lustrous carbon already
made, any core binder that came in on the return sand, and the cereal if the
shop runs any. So LOI overstates the live seacoal, by more on a shop running a
lot of cored work. The overstatement is not corrected here, because correcting
it needs a number nobody measures; it is left visible in the headroom instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from mullerbox.addition.material import Addition, Material
from mullerbox.burnout.loss import Burnout
from mullerbox.errors import BadInputError
from mullerbox.units.bulk import Pounds
from mullerbox.units.percent import Percent, Points

# The addition aims here inside the ceiling rather than at it, because the next
# shift's own lustrous carbon will push LOI up on its own.
HEADROOM = Decimal("0.85")

_PLACES = Decimal("0.01")


@dataclass(frozen=True)
class CarbonCall:
    """The seacoal decision."""

    measured: Percent
    ceiling: Percent
    aim: Percent
    shortfall: Points
    burnt: Points
    addition: Addition

    @property
    def is_over_ceiling(self) -> bool:
        return self.measured > self.ceiling

    def __str__(self) -> str:
        return f"LOI {self.measured} under a ceiling of {self.ceiling}: {self.addition}"


def aim_under(ceiling: Percent) -> Percent:
    """Where to land, given a ceiling you must not reach."""
    if not isinstance(ceiling, Percent):
        raise BadInputError("an LOI ceiling is a percentage")
    return Percent((ceiling.value * HEADROOM).quantize(_PLACES, rounding=ROUND_HALF_UP))


def seacoal_for(
    measured: Percent,
    ceiling: Percent,
    burnout: Burnout,
    system_mass: Pounds,
) -> CarbonCall:
    """Work out the seacoal addition for the next batch.

    A system already over the ceiling gets nothing, and the reason says so
    plainly, because the operator's instinct when castings are peeling badly is
    to add coal and the reading that matters is telling them not to.
    """
    if not isinstance(measured, Percent):
        raise BadInputError("the loss on ignition reading is a percentage")
    if not isinstance(ceiling, Percent):
        raise BadInputError("an LOI ceiling is a percentage")
    if not isinstance(burnout, Burnout):
        raise BadInputError("a carbon call needs the shift's burnout")
    if not isinstance(system_mass, Pounds):
        raise BadInputError("the system mass is a bulk mass")
    if system_mass.is_zero:
        raise BadInputError("a system with no sand in it needs no seacoal")

    aim = aim_under(ceiling)
    shortfall = aim - measured
    if measured > ceiling:
        return CarbonCall(
            measured=measured,
            ceiling=ceiling,
            aim=aim,
            shortfall=shortfall,
            burnt=burnout.carbon_lost,
            addition=Addition.nothing(
                Material.SEACOAL,
                f"LOI {measured} is already over the ceiling of {ceiling}",
            ),
        )
    if not shortfall.is_high:
        return CarbonCall(
            measured=measured,
            ceiling=ceiling,
            aim=aim,
            shortfall=shortfall,
            burnt=burnout.carbon_lost,
            addition=Addition.nothing(
                Material.SEACOAL, f"LOI {measured} is at or above the aim of {aim}"
            ),
        )
    charged = system_mass.scaled(shortfall.value / Decimal(100) / Material.SEACOAL.yield_factor)
    return CarbonCall(
        measured=measured,
        ceiling=ceiling,
        aim=aim,
        shortfall=shortfall,
        burnt=burnout.carbon_lost,
        addition=Addition(
            material=Material.SEACOAL,
            mass=charged,
            reason=(
                f"LOI {measured} is {shortfall} under the aim of {aim}, "
                f"after losing {burnout.carbon_lost} to the pour"
            ),
        ),
    )


__all__ = ["CarbonCall", "HEADROOM", "aim_under", "seacoal_for"]
