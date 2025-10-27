"""A heat, the molds it filled, and the castings that came out.

The unit of production is the heat: one melt, tapped and poured into a set of
molds over the twenty minutes or so before it goes too cold. Everything that
gets charged back to the sand is charged through a heat, because the heat is the
only record that ties a batch of sand to a batch of castings.

Two things about the shape are decisions rather than conveniences.

**A mold belongs to exactly one heat and carries its own pattern class.** A heat
usually runs one pattern, and "usually" is doing a lot of work: a jobbing shop
will fill the tail of a ladle with whatever is on the floor. So the class is on
the mold. Putting it on the heat would be right most days and wrong on exactly
the days somebody is trying to work out why a third of a heat scrapped.

**The disposition is on the casting and it is a closed set.** Shipped, scrapped,
or still being decided. There is no "probably fine": a casting that has not been
judged is ``PENDING``, and a shift report that counts pending as good is a
report that improves when the inspector falls behind.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum

from mullerbox.errors import BadInputError, RuleError
from mullerbox.spec.pattern import PatternClass
from mullerbox.units.bulk import Pounds


class Disposition(Enum):
    """What happened to a casting."""

    PENDING = "pending"
    SHIPPED = "shipped"
    SCRAPPED = "scrapped"

    @property
    def is_decided(self) -> bool:
        return self is not Disposition.PENDING

    @property
    def label(self) -> str:
        return self.value


@dataclass(frozen=True)
class Casting:
    """One piece out of one mold."""

    casting_id: str
    weight: Pounds
    disposition: Disposition = Disposition.PENDING

    def __post_init__(self) -> None:
        if not self.casting_id.strip():
            raise BadInputError("a casting needs an identifier")
        if not isinstance(self.weight, Pounds):
            raise BadInputError("a casting weight is a bulk mass")
        if self.weight.is_zero:
            raise BadInputError("a casting with no weight is not a casting")
        if not isinstance(self.disposition, Disposition):
            raise BadInputError("a casting has a disposition")

    @property
    def is_scrap(self) -> bool:
        return self.disposition is Disposition.SCRAPPED


@dataclass(frozen=True)
class Mold:
    """One mold, its pattern class, and what came out of it."""

    mold_id: str
    pattern: PatternClass
    sand: Pounds
    castings: tuple[Casting, ...] = ()

    def __post_init__(self) -> None:
        if not self.mold_id.strip():
            raise BadInputError("a mold needs an identifier")
        if not isinstance(self.pattern, PatternClass):
            raise BadInputError("a mold names the pattern class it ran")
        if not isinstance(self.sand, Pounds):
            raise BadInputError("the sand in a mold is a bulk mass")
        if self.sand.is_zero:
            raise BadInputError("a mold with no sand in it is not a mold")
        ids = [c.casting_id for c in self.castings]
        if len(set(ids)) != len(ids):
            raise RuleError(f"mold {self.mold_id} has two castings with one number")

    @property
    def metal(self) -> Pounds:
        """What went in, which is the sum of what came out."""
        running = Pounds.zero()
        for casting in self.castings:
            running = running + casting.weight
        return running

    @property
    def scrapped(self) -> tuple[Casting, ...]:
        return tuple(c for c in self.castings if c.is_scrap)

    @property
    def is_fully_judged(self) -> bool:
        return all(c.disposition.is_decided for c in self.castings)


@dataclass(frozen=True)
class Heat:
    """One melt into one set of molds."""

    heat_number: str
    poured_on: date
    molds: tuple[Mold, ...] = ()

    def __post_init__(self) -> None:
        if not self.heat_number.strip():
            raise BadInputError("a heat needs a number")
        if not isinstance(self.poured_on, date):
            raise BadInputError("a heat is dated")
        ids = [m.mold_id for m in self.molds]
        if len(set(ids)) != len(ids):
            raise RuleError(f"heat {self.heat_number} has two molds with one number")

    @property
    def metal(self) -> Pounds:
        """What the heat poured, summed from what came out of its molds."""
        running = Pounds.zero()
        for mold in self.molds:
            running = running + mold.metal
        return running

    @property
    def sand(self) -> Pounds:
        """The sand in this heat's molds, which the pour ratio is taken against."""
        running = Pounds.zero()
        for mold in self.molds:
            running = running + mold.sand
        return running

    @property
    def castings(self) -> tuple[Casting, ...]:
        return tuple(c for mold in self.molds for c in mold.castings)

    @property
    def patterns(self) -> frozenset[PatternClass]:
        """Every class this heat ran, which is more than one more often than expected."""
        return frozenset(m.pattern for m in self.molds)

    @property
    def is_single_pattern(self) -> bool:
        return len(self.patterns) == 1

    def molds_of(self, pattern: PatternClass) -> tuple[Mold, ...]:
        if not isinstance(pattern, PatternClass):
            raise BadInputError("a pattern class is expected")
        return tuple(m for m in self.molds if m.pattern is pattern)

    @property
    def scrap_rate(self) -> Decimal:
        """Scrapped weight over poured weight, to four places.

        By weight rather than by count, because a shop that scraps one heavy
        casting and ships forty small ones has had a bad day and a count says
        it had a good one.
        """
        poured = self.metal
        if poured.is_zero:
            raise RuleError(f"heat {self.heat_number} poured no metal")
        scrapped = Pounds.zero()
        for casting in self.castings:
            if casting.is_scrap:
                scrapped = scrapped + casting.weight
        return scrapped.fraction_of(poured).quantize(Decimal("0.0001"))

    @property
    def is_fully_judged(self) -> bool:
        return all(m.is_fully_judged for m in self.molds)

    def __str__(self) -> str:
        return f"heat {self.heat_number} on {self.poured_on}, {len(self.molds)} molds"


__all__ = ["Casting", "Disposition", "Heat", "Mold"]
