"""The sand cooler, which is the only thing standing between shakeout and the muller.

Sand comes off shakeout at two hundred Fahrenheit and has to reach the muller
under about a hundred and twenty, or the temper water flashes off before the
bentonite can take it up. The cooler gets it there by evaporating water into the
sand stream: every pound evaporated carries away roughly a thousand BTU, and
sand takes about a fifth of a BTU per pound per degree, so a pound of water
cools five thousand pounds of sand by one degree.

Two things about this are worth stating because they are where the intuition
fails.

**Cooling water and temper water are not the same water.** The cooler's water
leaves as steam and is gone. The muller's water stays in the sand and becomes
the moisture reading. A shop that meters one total and calls it "water added"
cannot tell an evaporative loss from a moisture addition, and its moisture
control never works.

**There is a floor and it is not ambient.** Evaporative cooling cannot take the
sand below the wet bulb temperature of the air passing through it, because at
the wet bulb the air will not take up any more water. For an ordinary target
around a hundred and fifteen Fahrenheit the floor is nowhere near, and it is
tempting to leave it out. It binds on the aggressive targets: a high density
line asking for ninety degree sand on a humid day is asking for something below
the wet bulb, and no amount of water gets there. The arithmetic says so rather
than returning a number the cooler cannot reach.

**Fahrenheit is the shop's scale and Celsius is the stored one**, and the round
trip costs a tenth of a degree. So the drop this module works from is taken from
the stored temperatures rather than from what the operator typed, and a caller
comparing against a round number will be out by a tenth. That is the price of
one canonical scale and it is cheaper than carrying two.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from mullerbox.errors import BadInputError, RuleError
from mullerbox.units.bulk import Pounds
from mullerbox.units.thermal import Temperature

# BTU carried away by evaporating one pound of water, and BTU to move one pound
# of silica sand one degree Fahrenheit.
LATENT_HEAT = Decimal("970")
SAND_SPECIFIC_HEAT = Decimal("0.19")

# A cooler cannot approach the wet bulb exactly. Two degrees is as close as a
# real one gets.
APPROACH_F = Decimal("2")

_PLACES = Decimal("0.01")


@dataclass(frozen=True)
class CoolingCall:
    """What the cooler is being asked to do and whether it can."""

    sand: Pounds
    entering: Temperature
    wanted: Temperature
    wet_bulb: Temperature
    water: Pounds
    floor: Temperature
    reachable: bool

    @property
    def drop_wanted(self) -> Decimal:
        """Degrees Fahrenheit the sand has to lose."""
        return self.entering.fahrenheit_value - self.wanted.fahrenheit_value

    def __str__(self) -> str:
        if not self.reachable:
            return (
                f"{self.wanted} is below the {self.floor} floor set by a {self.wet_bulb} wet bulb"
            )
        return f"{self.water} of water to take {self.sand} to {self.wanted}"


def floor_temperature(wet_bulb: Temperature) -> Temperature:
    """The coldest the sand can get, which is the wet bulb plus the approach."""
    if not isinstance(wet_bulb, Temperature):
        raise BadInputError("a wet bulb temperature is expected")
    return Temperature.fahrenheit(wet_bulb.fahrenheit_value + APPROACH_F)


def cooling_water_for(
    sand: Pounds,
    entering: Temperature,
    wanted: Temperature,
    wet_bulb: Temperature,
) -> CoolingCall:
    """How much water the cooler has to evaporate, and whether it can get there.

    A call for a temperature below the floor comes back unreachable with the
    water it would have taken left at zero, rather than raising. The operator
    needs to see that the request was impossible and by how much, which is a
    different thing from the command failing.
    """
    if not isinstance(sand, Pounds):
        raise BadInputError("the sand stream is a bulk mass")
    if sand.is_zero:
        raise BadInputError("a cooler with no sand through it has nothing to do")
    for name, value in (
        ("entering", entering),
        ("wanted", wanted),
        ("wet bulb", wet_bulb),
    ):
        if not isinstance(value, Temperature):
            raise BadInputError(f"the {name} temperature is a temperature")
    if wanted.warmer_than(entering):
        raise RuleError(
            f"the sand enters at {entering} and {wanted} is warmer, a cooler does not heat"
        )
    floor = floor_temperature(wet_bulb)
    if floor.warmer_than(wanted):
        return CoolingCall(
            sand=sand,
            entering=entering,
            wanted=wanted,
            wet_bulb=wet_bulb,
            water=Pounds.zero(),
            floor=floor,
            reachable=False,
        )
    drop = entering.fahrenheit_value - wanted.fahrenheit_value
    btu = sand.value * SAND_SPECIFIC_HEAT * drop
    pounds = (btu / LATENT_HEAT).quantize(_PLACES, rounding=ROUND_HALF_UP)
    return CoolingCall(
        sand=sand,
        entering=entering,
        wanted=wanted,
        wet_bulb=wet_bulb,
        water=Pounds(pounds),
        floor=floor,
        reachable=True,
    )


def reachable_temperature(
    sand: Pounds, entering: Temperature, water: Pounds, wet_bulb: Temperature
) -> Temperature:
    """Where the sand actually lands with the water the cooler has.

    The inverse of the above, and it is the one the operator uses: the cooler
    has a fixed spray rate and the question is what comes out of it.
    """
    if not isinstance(sand, Pounds):
        raise BadInputError("the sand stream is a bulk mass")
    if sand.is_zero:
        raise BadInputError("a cooler with no sand through it has nothing to do")
    if not isinstance(water, Pounds):
        raise BadInputError("the cooling water is a bulk mass")
    if not isinstance(entering, Temperature):
        raise BadInputError("the entering temperature is a temperature")
    drop = (water.value * LATENT_HEAT) / (sand.value * SAND_SPECIFIC_HEAT)
    landed = entering.fahrenheit_value - drop
    floor = floor_temperature(wet_bulb)
    if landed < floor.fahrenheit_value:
        return floor
    return Temperature.fahrenheit(landed.quantize(_PLACES, rounding=ROUND_HALF_UP))


__all__ = [
    "APPROACH_F",
    "CoolingCall",
    "LATENT_HEAT",
    "SAND_SPECIFIC_HEAT",
    "cooling_water_for",
    "floor_temperature",
    "reachable_temperature",
]
