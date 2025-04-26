"""Money, in whole cents, and a price per ton to get there.

Sand and bentonite are bought by the ton and consumed by the pound, so every
cost in this package is a rate times a mass. Doing that in floating point puts
a fraction of a cent on every line and a visible error on the month, so the
amount is an integer number of cents and the rate carries enough places to
survive the division.

The type refuses to be built from another currency's habits. There is no
rounding mode argument and no way to get a half cent: everything rounds half up
at the cent on the way in, once, and stays there.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from functools import total_ordering
from typing import Any

from mullerbox.errors import BadInputError
from mullerbox.units.bulk import POUNDS_PER_TON, Pounds
from mullerbox.units.coerce import to_decimal

CENTS = Decimal("0.01")
RATE_PLACES = Decimal("0.0001")


@total_ordering
@dataclass(frozen=True, init=False, eq=False)
class Money:
    """A non negative amount in whole cents."""

    cents: int

    def __init__(self, value: object = 0) -> None:
        if isinstance(value, Money):
            object.__setattr__(self, "cents", value.cents)
            return
        amount = to_decimal(
            value, "an amount", prefixes=("$",), suffixes=("usd",), strip_commas=True
        )
        if amount < 0:
            raise BadInputError("a cost cannot be negative")
        object.__setattr__(
            self, "cents", int((amount * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))
        )

    @classmethod
    def zero(cls) -> Money:
        return cls(0)

    @classmethod
    def from_cents(cls, cents: int) -> Money:
        if isinstance(cents, bool) or not isinstance(cents, int):
            raise BadInputError("cents are a whole number")
        if cents < 0:
            raise BadInputError("a cost cannot be negative")
        money = cls.__new__(cls)
        object.__setattr__(money, "cents", cents)
        return money

    @property
    def dollars(self) -> Decimal:
        return (Decimal(self.cents) / 100).quantize(CENTS)

    @property
    def is_zero(self) -> bool:
        return self.cents == 0

    def __add__(self, other: object) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        return Money.from_cents(self.cents + other.cents)

    def __sub__(self, other: object) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        if other.cents > self.cents:
            raise BadInputError("subtracting that leaves a negative cost")
        return Money.from_cents(self.cents - other.cents)

    def __str__(self) -> str:
        whole, part = divmod(self.cents, 100)
        return f"${whole:,}.{part:02d}"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Money):
            return self.cents == other.cents
        return NotImplemented

    def __hash__(self) -> int:
        return hash(("Money", self.cents))

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Money):
            return bool(self.cents < other.cents)
        return NotImplemented


@dataclass(frozen=True, init=False, eq=False)
class PricePerTon:
    """What a material costs by the ton, carried to four places.

    Four places on the rate rather than two, because the rate gets divided by
    two thousand before it multiplies a mass, and a rate rounded to the cent
    loses a visible amount over a month of additions.
    """

    dollars: Decimal

    def __init__(self, value: object) -> None:
        rate = to_decimal(value, "a price", prefixes=("$",), suffixes=("usd",), strip_commas=True)
        if rate < 0:
            raise BadInputError("a price cannot be negative")
        object.__setattr__(self, "dollars", rate.quantize(RATE_PLACES, rounding=ROUND_HALF_UP))

    def cost_of(self, mass: Pounds) -> Money:
        """What a mass of this material costs, rounded once at the end."""
        if not isinstance(mass, Pounds):
            raise BadInputError("a cost is taken of a bulk mass")
        exact = self.dollars * mass.value / POUNDS_PER_TON
        return Money.from_cents(int((exact * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP)))

    def __str__(self) -> str:
        return f"${self.dollars.normalize():f}/t"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, PricePerTon):
            return self.dollars == other.dollars
        return NotImplemented

    def __hash__(self) -> int:
        return hash(("PricePerTon", self.dollars))


def total_money(amounts: list[Money]) -> Money:
    running = 0
    for amount in amounts:
        if not isinstance(amount, Money):
            raise BadInputError("only amounts can be totalled")
        running += amount.cents
    return Money.from_cents(running)


__all__ = ["CENTS", "Money", "PricePerTon", "RATE_PLACES", "total_money"]
