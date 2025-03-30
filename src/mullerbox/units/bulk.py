"""Shop scale mass, which is a different problem from lab scale mass.

The lab weighs specimens in grams to a hundredth. The muller charges sand in
tons and the additions come off a scale in pounds. Those are not the same
quantity at different magnitudes, they are numbers with different provenance and
different precision, and a package that carries both in one type ends up
comparing a fifty gram specimen against a fifty ton batch and finding them
equal.

So ``Grams`` stays in the lab and ``Pounds`` runs the shop. There is no
conversion between them, not because one is impossible but because the shop
never does it: nothing in the muller is dosed off a lab specimen and nothing in
the lab is weighed off the batch scale. A conversion would exist only to be
called by mistake.

Pounds is the base because that is what every scale on the floor reads. Tons are
a presentation of pounds and a short ton at that, two thousand pounds, since
this is an American foundry and the long ton has never been in the building.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from functools import total_ordering
from typing import Any

from mullerbox.errors import BadInputError
from mullerbox.units.coerce import to_decimal

POUNDS_PER_TON = Decimal("2000")
PLACES = Decimal("0.01")

# A jobbing system holds a few hundred tons at most. A million pounds is a
# steel mill, and on this book it is a decimal point.
MAX_POUNDS = Decimal("1000000")


_SUFFIXES = ("pounds", "lbs", "lb", "#")


def _decimal_from(value: object) -> Decimal:
    return to_decimal(value, "a bulk mass", suffixes=_SUFFIXES, strip_commas=True)


@total_ordering
@dataclass(frozen=True, init=False, eq=False)
class Pounds:
    """A shop scale mass, to a hundredth of a pound."""

    value: Decimal

    def __init__(self, value: object = 0) -> None:
        mass = _decimal_from(value).quantize(PLACES, rounding=ROUND_HALF_UP)
        if mass < 0:
            raise BadInputError("a bulk mass cannot be negative")
        if mass > MAX_POUNDS:
            raise BadInputError(f"{mass} lb is not a foundry sand quantity")
        object.__setattr__(self, "value", mass)

    @classmethod
    def zero(cls) -> Pounds:
        return cls(0)

    @classmethod
    def of_tons(cls, tons: object) -> Pounds:
        return cls(_decimal_from(tons) * POUNDS_PER_TON)

    @property
    def tons(self) -> Decimal:
        return (self.value / POUNDS_PER_TON).quantize(Decimal("0.001"))

    @property
    def is_zero(self) -> bool:
        return self.value == 0

    def __add__(self, other: object) -> Pounds:
        if not isinstance(other, Pounds):
            return NotImplemented
        return Pounds(self.value + other.value)

    def __sub__(self, other: object) -> Pounds:
        if not isinstance(other, Pounds):
            return NotImplemented
        if other.value > self.value:
            raise BadInputError("subtracting that leaves a negative bulk mass")
        return Pounds(self.value - other.value)

    def scaled(self, factor: object) -> Pounds:
        if isinstance(factor, Pounds):
            raise BadInputError("a mass times a mass is not a mass")
        if not isinstance(factor, str | int | Decimal | float) or isinstance(factor, bool):
            raise BadInputError(f"cannot scale a bulk mass by {type(factor).__name__}")
        ratio = factor if isinstance(factor, Decimal) else Decimal(str(factor))
        if ratio < 0:
            raise BadInputError("cannot scale a bulk mass by a negative ratio")
        return Pounds(self.value * ratio)

    def fraction_of(self, whole: Pounds) -> Decimal:
        """This mass as a fraction of a larger one, to six places."""
        if not isinstance(whole, Pounds):
            raise BadInputError("a bulk mass is a fraction of a bulk mass")
        if whole.is_zero:
            raise BadInputError("cannot take a fraction of nothing")
        return (self.value / whole.value).quantize(Decimal("0.000001"))

    def ratio_to(self, other: Pounds) -> Decimal:
        """How many of ``other`` this is, to two places. The sand to metal ratio."""
        if not isinstance(other, Pounds):
            raise BadInputError("a bulk mass is a ratio against a bulk mass")
        if other.is_zero:
            raise BadInputError("cannot take a ratio against nothing")
        return (self.value / other.value).quantize(PLACES)

    def __str__(self) -> str:
        if self.value >= POUNDS_PER_TON:
            return f"{self.tons} t"
        return f"{self.value} lb"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Pounds):
            return self.value == other.value
        return NotImplemented

    def __hash__(self) -> int:
        return hash(("Pounds", self.value))

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Pounds):
            return bool(self.value < other.value)
        return NotImplemented


def total_pounds(masses: list[Pounds]) -> Pounds:
    """Add a list of bulk masses. Empty comes back as zero, not as an error."""
    running = Decimal(0)
    for mass in masses:
        if not isinstance(mass, Pounds):
            raise BadInputError("only bulk masses can be totalled")
        running += mass.value
    return Pounds(running)


__all__ = ["MAX_POUNDS", "PLACES", "POUNDS_PER_TON", "Pounds", "total_pounds"]
