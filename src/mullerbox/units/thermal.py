"""Temperature, in the two scales the foundry actually uses side by side.

Return sand temperature is the number that governs whether the muller can do
anything useful. Sand coming back off shakeout above about 120 F will flash off
the temper water before the bentonite has taken it up, so the batch mulls dry
whatever the water addition says, and every property downstream reads wrong.

The shop floor reads Fahrenheit off the sand cooler and the lab reads Celsius
off everything else, and both numbers appear on the same shift sheet. So the
type holds one canonical scale and converts, rather than making the caller
remember which column it read.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from functools import total_ordering
from typing import Any

from mullerbox.errors import BadInputError

PLACES = Decimal("0.1")
ABSOLUTE_ZERO_C = Decimal("-273.15")

# Molten grey iron is tapped around 2600 F. Anything past that on a sand sheet
# is a thermocouple fault or a metal reading in a sand column.
MAX_CELSIUS = Decimal("1500")


def _decimal_from(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise BadInputError("cannot read a temperature from a boolean")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(repr(value))
    if isinstance(value, str):
        text = value.strip().upper().removesuffix("C").removesuffix("F").strip()
        text = text.removesuffix("DEG").strip()
        try:
            return Decimal(text)
        except InvalidOperation:
            raise BadInputError(f"{value!r} is not a temperature") from None
    raise BadInputError(f"cannot read a temperature from {type(value).__name__}")


@total_ordering
@dataclass(frozen=True, init=False, eq=False)
class Temperature:
    """A temperature, held in Celsius to a tenth.

    Construct through the named constructors rather than the initialiser so the
    scale is written down at the call site. ``Temperature.fahrenheit(120)`` says
    what it is; ``Temperature(120)`` would not.
    """

    celsius: Decimal

    def __init__(self, celsius: object) -> None:
        degrees = _decimal_from(celsius).quantize(PLACES, rounding=ROUND_HALF_UP)
        if degrees < ABSOLUTE_ZERO_C:
            raise BadInputError("that is below absolute zero")
        if degrees > MAX_CELSIUS:
            raise BadInputError(f"{degrees} C is not a sand or a metal reading")
        object.__setattr__(self, "celsius", degrees)

    @classmethod
    def celsius_of(cls, value: object) -> Temperature:
        return cls(value)

    @classmethod
    def fahrenheit(cls, value: object) -> Temperature:
        degrees = _decimal_from(value)
        return cls((degrees - 32) * 5 / 9)

    @property
    def fahrenheit_value(self) -> Decimal:
        return (self.celsius * 9 / 5 + 32).quantize(PLACES, rounding=ROUND_HALF_UP)

    def warmer_than(self, other: Temperature) -> bool:
        if not isinstance(other, Temperature):
            raise BadInputError("a temperature only compares against a temperature")
        return self.celsius > other.celsius

    def difference(self, other: Temperature) -> Decimal:
        """Degrees Celsius between two readings, always positive."""
        if not isinstance(other, Temperature):
            raise BadInputError("a temperature only compares against a temperature")
        return abs(self.celsius - other.celsius)

    def __str__(self) -> str:
        return f"{self.celsius} C"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Temperature):
            return self.celsius == other.celsius
        return NotImplemented

    def __hash__(self) -> int:
        return hash(("Temperature", self.celsius))

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Temperature):
            return bool(self.celsius < other.celsius)
        return NotImplemented


__all__ = ["ABSOLUTE_ZERO_C", "MAX_CELSIUS", "PLACES", "Temperature"]
