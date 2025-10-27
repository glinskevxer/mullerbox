"""Mass in grams, which is what every balance in the sand lab reads in.

Sieve analysis is the reason this is its own type. A specimen is charged onto
the top screen at a known mass, the stack is shaken, and the mass retained on
each screen is weighed back. Those retained masses have to close against the
charge within a tolerance, and closing is a comparison between a sum of many
small numbers and one larger one. Doing that in float loses the argument at the
fourth screen, so mass is held as an integer number of centigrams and the sum
is exact.

Centigrams rather than grams because the lab's balances read to 0.01 g and the
tenth screen of a stack can retain well under a gram.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from functools import total_ordering
from typing import Any

from mullerbox.errors import BadInputError
from mullerbox.units.coerce import to_decimal

CENTIGRAM = Decimal("0.01")

# A sand specimen is 50 g to 200 g depending on the test. Anything past this is
# a units mistake, usually kilograms typed into a grams field.
IMPLAUSIBLE_GRAMS = Decimal("100000")


def _centigrams_from(value: object) -> int:
    if isinstance(value, Grams):
        return value.centigrams
    amount = to_decimal(value, "a mass", suffixes=("g",))
    return int(amount.quantize(CENTIGRAM, rounding=ROUND_HALF_UP) * 100)


@total_ordering
@dataclass(frozen=True, init=False, eq=False)
class Grams:
    """A mass in whole centigrams.

    Negative is refused. A sieve stack that weighs back heavier than it was
    charged is a real thing and it is reported as a closure failure, not as a
    negative retained mass, so nothing in the lab needs a signed mass.
    """

    centigrams: int

    def __init__(self, value: object = 0) -> None:
        cg = _centigrams_from(value)
        if cg < 0:
            raise BadInputError("a mass cannot be negative")
        if cg > IMPLAUSIBLE_GRAMS * 100:
            raise BadInputError(f"{cg / 100} g is not a sand lab quantity")
        object.__setattr__(self, "centigrams", cg)

    @classmethod
    def zero(cls) -> Grams:
        return cls(0)

    @classmethod
    def from_centigrams(cls, centigrams: int) -> Grams:
        """Build from a raw centigram count, skipping the coercion."""
        if not isinstance(centigrams, int):
            raise BadInputError("centigrams have to be a whole number")
        if centigrams < 0:
            raise BadInputError("a mass cannot be negative")
        mass = cls.__new__(cls)
        object.__setattr__(mass, "centigrams", centigrams)
        return mass

    @property
    def grams(self) -> Decimal:
        return (Decimal(self.centigrams) / 100).quantize(CENTIGRAM)

    @property
    def is_zero(self) -> bool:
        return self.centigrams == 0

    def __add__(self, other: object) -> Grams:
        if not isinstance(other, Grams):
            return NotImplemented
        return Grams.from_centigrams(self.centigrams + other.centigrams)

    def __sub__(self, other: object) -> Grams:
        """Subtract, refusing to go below zero rather than wrapping to a signed mass."""
        if not isinstance(other, Grams):
            return NotImplemented
        if other.centigrams > self.centigrams:
            raise BadInputError("subtracting that leaves a negative mass")
        return Grams.from_centigrams(self.centigrams - other.centigrams)

    def difference(self, other: Grams) -> Grams:
        """The gap between two masses, whichever way round they are."""
        if not isinstance(other, Grams):
            raise BadInputError("a mass can only be compared against a mass")
        return Grams.from_centigrams(abs(self.centigrams - other.centigrams))

    def scaled(self, factor: object) -> Grams:
        """Multiply by a ratio, rounding half up at the centigram."""
        if isinstance(factor, Grams):
            raise BadInputError("mass times mass is not a mass")
        if isinstance(factor, str | int | Decimal | float):
            ratio = factor if isinstance(factor, Decimal) else Decimal(str(factor))
        else:
            raise BadInputError(f"cannot scale a mass by {type(factor).__name__}")
        if ratio < 0:
            raise BadInputError("cannot scale a mass by a negative ratio")
        exact = Decimal(self.centigrams) * ratio
        return Grams.from_centigrams(int(exact.quantize(Decimal(1), rounding=ROUND_HALF_UP)))

    def ratio_to(self, whole: Grams) -> Decimal:
        """This mass as a fraction of a larger one, to six places.

        Six because a sieve fraction gets multiplied by a three digit screen
        weight and then summed across eleven screens, and rounding the fraction
        early moves the grain fineness number by a whole point.
        """
        if not isinstance(whole, Grams):
            raise BadInputError("a mass can only be taken as a fraction of a mass")
        if whole.is_zero:
            raise BadInputError("cannot take a fraction of nothing")
        return (Decimal(self.centigrams) / Decimal(whole.centigrams)).quantize(Decimal("0.000001"))

    def __str__(self) -> str:
        return f"{self.grams} g"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Grams):
            return self.centigrams == other.centigrams
        return NotImplemented

    def __hash__(self) -> int:
        return hash(("Grams", self.centigrams))

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Grams):
            return bool(self.centigrams < other.centigrams)
        return NotImplemented


def total(masses: list[Grams]) -> Grams:
    """Add a list of masses exactly.

    Worth having as a function rather than a ``sum`` call because ``sum`` starts
    at the integer zero and ``Grams.__add__`` refuses that, and because the
    empty stack has to come back as zero grams rather than as an error.
    """
    running = 0
    for mass in masses:
        if not isinstance(mass, Grams):
            raise BadInputError("only masses can be totalled")
        running += mass.centigrams
    return Grams.from_centigrams(running)


__all__ = ["CENTIGRAM", "Grams", "IMPLAUSIBLE_GRAMS", "total"]
