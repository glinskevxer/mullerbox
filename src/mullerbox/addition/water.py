"""Temper water, which is the addition everything else is judged through.

Compactability is the number the molding line actually feels, and water is what
moves it. But the relationship between the two is not a constant, and treating
it as one is the single most common way a sand system is mismanaged.

**The response depends on the bond.** Bentonite holds water. A system at ten
percent clay absorbs more of each pound of water into the clay and delivers less
of it to the compactability reading than a system at six. So the same water
addition moves compactability by different amounts on the same day, and the
difference is the bond level that the bentonite calculation just changed. Water
is downstream of bond, always, which is why the muller adds bentonite first and
mulls dry before the water goes in.

**Hot return sand takes more.** Sand off shakeout above about fifty Celsius
flashes part of the addition to steam before the clay can take it up. The
allowance for that is a straight uplift on the calculated mass, and it is an
allowance rather than a correction because none of it ends up in the sand: it
leaves as steam and the moisture reading afterwards is unaffected by it.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from mullerbox.addition.material import Addition, Material
from mullerbox.errors import BadInputError
from mullerbox.units.bulk import Pounds
from mullerbox.units.percent import Percent, Points
from mullerbox.units.thermal import Temperature

# Compactability points delivered by one point of moisture, at the reference
# bond level. Measured off the shop's own water response curve.
BASE_RESPONSE = Decimal("12")
REFERENCE_CLAY = Decimal("8.0")

# Return sand warmer than this starts losing the addition to steam, and the
# allowance grows with every degree over.
EVAPORATION_ONSET_C = Decimal("50")
ALLOWANCE_PER_DEGREE = Decimal("0.015")
MAX_ALLOWANCE = Decimal("0.30")

_PLACES = Decimal("0.0001")


@dataclass(frozen=True)
class WaterCall:
    """The temper water decision, with the two things that shaped it."""

    measured: Percent
    target: Percent
    shortfall: Points
    response: Decimal
    moisture_needed: Decimal
    allowance: Decimal
    addition: Addition

    @property
    def was_allowed_for_heat(self) -> bool:
        return self.allowance > 0

    def __str__(self) -> str:
        return f"compactability {self.measured} against {self.target}: {self.addition}"


def response_at(clay: Percent) -> Decimal:
    """Compactability points per point of moisture, at a given bond level.

    Inverse in the clay: twice the bond, half the response. Crude against the
    real curve and right in the direction that matters, which is that a rich
    system needs more water for the same movement and a lean one needs less.
    """
    if not isinstance(clay, Percent):
        raise BadInputError("a bond level is a percentage")
    if clay.value <= 0:
        raise BadInputError("a system with no bond has no water response")
    return (BASE_RESPONSE * REFERENCE_CLAY / clay.value).quantize(
        Decimal("0.001"), rounding=ROUND_HALF_UP
    )


def evaporation_allowance(return_temperature: Temperature) -> Decimal:
    """The uplift on a water addition for sand that is too hot to hold it."""
    if not isinstance(return_temperature, Temperature):
        raise BadInputError("a return sand temperature is expected")
    over = return_temperature.celsius - EVAPORATION_ONSET_C
    if over <= 0:
        return Decimal(0)
    allowance = over * ALLOWANCE_PER_DEGREE
    if allowance > MAX_ALLOWANCE:
        allowance = MAX_ALLOWANCE
    return allowance.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def water_for(
    measured: Percent,
    target: Percent,
    clay: Percent,
    system_mass: Pounds,
    return_temperature: Temperature,
) -> WaterCall:
    """Work out the temper water for the next batch.

    A system already at or above target gets nothing. Water cannot be taken back
    out of a batch; a wet system is corrected by mulling longer, by running the
    cooler, or by waiting, and none of those is an addition.
    """
    if not isinstance(measured, Percent):
        raise BadInputError("the compactability reading is a percentage")
    if not isinstance(target, Percent):
        raise BadInputError("a compactability target is a percentage")
    if not isinstance(system_mass, Pounds):
        raise BadInputError("the batch mass is a bulk mass")
    if system_mass.is_zero:
        raise BadInputError("a batch with no sand in it needs no water")
    response = response_at(clay)
    allowance = evaporation_allowance(return_temperature)
    shortfall = target - measured
    if not shortfall.is_high:
        return WaterCall(
            measured=measured,
            target=target,
            shortfall=shortfall,
            response=response,
            moisture_needed=Decimal(0),
            allowance=allowance,
            addition=Addition.nothing(
                Material.WATER,
                f"compactability {measured} is at or above the target of {target}",
            ),
        )
    moisture_needed = (shortfall.value / response).quantize(_PLACES, rounding=ROUND_HALF_UP)
    charged = system_mass.scaled(moisture_needed / Decimal(100) * (Decimal(1) + allowance))
    return WaterCall(
        measured=measured,
        target=target,
        shortfall=shortfall,
        response=response,
        moisture_needed=moisture_needed,
        allowance=allowance,
        addition=Addition(
            material=Material.WATER,
            mass=charged,
            reason=(
                f"compactability {measured} is {shortfall} under {target}, "
                f"needing {moisture_needed}% moisture at a response of {response}"
            ),
        ),
    )


__all__ = [
    "ALLOWANCE_PER_DEGREE",
    "BASE_RESPONSE",
    "EVAPORATION_ONSET_C",
    "MAX_ALLOWANCE",
    "REFERENCE_CLAY",
    "WaterCall",
    "evaporation_allowance",
    "response_at",
    "water_for",
]
