"""Percentages, which is what most of the sand lab's answers come back as.

Compactability, moisture, methylene blue clay, total clay, loss on ignition,
volatiles and friability are all percentages, and they are all compared against
a band and subtracted from a target. Two of those operations look the same and
are not: the difference between two percentages is a number of *points*, not a
percentage, and treating it as one is how a moisture correction ends up an order
of magnitude out. The type keeps them apart by giving the subtraction a
different return type from the operands.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from functools import total_ordering
from typing import Any

from mullerbox.errors import BadInputError
from mullerbox.units.coerce import to_decimal

PLACES = Decimal("0.01")
POINT_PLACES = Decimal("0.01")


def _decimal_from(value: object) -> Decimal:
    return to_decimal(value, "a percentage", suffixes=("%",))


@total_ordering
@dataclass(frozen=True, init=False, eq=False)
class Points:
    """A signed difference between two percentages.

    Compactability 42 against a target of 38 is four points high, and four
    points is not four percent of anything. The lab says "points" out loud for
    exactly this reason and the code says it too.
    """

    value: Decimal

    def __init__(self, value: object = 0) -> None:
        pts = _decimal_from(value).quantize(POINT_PLACES, rounding=ROUND_HALF_UP)
        object.__setattr__(self, "value", pts)

    @classmethod
    def zero(cls) -> Points:
        return cls(0)

    @property
    def is_zero(self) -> bool:
        return self.value == 0

    @property
    def is_high(self) -> bool:
        return self.value > 0

    @property
    def is_low(self) -> bool:
        return self.value < 0

    def __abs__(self) -> Points:
        return Points(abs(self.value))

    def __neg__(self) -> Points:
        return Points(-self.value)

    def __add__(self, other: object) -> Points:
        if not isinstance(other, Points):
            return NotImplemented
        return Points(self.value + other.value)

    def __sub__(self, other: object) -> Points:
        if not isinstance(other, Points):
            return NotImplemented
        return Points(self.value - other.value)

    def scaled(self, factor: object) -> Points:
        if isinstance(factor, Points):
            raise BadInputError("points times points is not points")
        if not isinstance(factor, str | int | Decimal | float):
            raise BadInputError(f"cannot scale points by {type(factor).__name__}")
        ratio = factor if isinstance(factor, Decimal) else Decimal(str(factor))
        return Points(self.value * ratio)

    def __str__(self) -> str:
        return f"{self.value:+} pt"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Points):
            return self.value == other.value
        return NotImplemented

    def __hash__(self) -> int:
        return hash(("Points", self.value))

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Points):
            return bool(self.value < other.value)
        return NotImplemented


@total_ordering
@dataclass(frozen=True, init=False, eq=False)
class Percent:
    """A percentage between zero and one hundred, held to two places.

    The upper bound is real rather than defensive. Every percentage in this
    package is a fraction of a specimen: the clay in it, the water in it, the
    mass it lost on ignition, the height it lost under a squeeze. None of them
    can exceed the specimen, so a reading above 100 is an instrument or a
    transcription fault and the lab wants to hear about it at the point of
    entry rather than three derivations later.
    """

    value: Decimal

    def __init__(self, value: object) -> None:
        pct = _decimal_from(value).quantize(PLACES, rounding=ROUND_HALF_UP)
        if pct < 0:
            raise BadInputError("a percentage of a specimen cannot be negative")
        if pct > 100:
            raise BadInputError(f"{pct}% is more than the whole specimen")
        object.__setattr__(self, "value", pct)

    @classmethod
    def zero(cls) -> Percent:
        return cls(0)

    @classmethod
    def of(cls, part: object, whole: object) -> Percent:
        """Build from a part and a whole in any consistent unit."""
        top = _decimal_from(part)
        bottom = _decimal_from(whole)
        if bottom <= 0:
            raise BadInputError("the whole has to be above zero")
        if top < 0:
            raise BadInputError("the part cannot be negative")
        return cls(top / bottom * 100)

    @property
    def fraction(self) -> Decimal:
        """The same number as a fraction of one, to six places."""
        return (self.value / 100).quantize(Decimal("0.000001"))

    def __sub__(self, other: object) -> Points:
        """Two percentages differ by a number of points, not by a percentage."""
        if not isinstance(other, Percent):
            return NotImplemented
        return Points(self.value - other.value)

    def moved(self, points: Points) -> Percent:
        """This percentage shifted by a number of points, clamped at the ends."""
        if not isinstance(points, Points):
            raise BadInputError("a percentage moves by points")
        moved = self.value + points.value
        if moved < 0:
            moved = Decimal(0)
        if moved > 100:
            moved = Decimal(100)
        return Percent(moved)

    def __str__(self) -> str:
        return f"{self.value}%"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Percent):
            return self.value == other.value
        return NotImplemented

    def __hash__(self) -> int:
        return hash(("Percent", self.value))

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Percent):
            return bool(self.value < other.value)
        return NotImplemented


__all__ = ["PLACES", "POINT_PLACES", "Percent", "Points"]
