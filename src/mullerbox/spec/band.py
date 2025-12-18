"""A property band: the low limit, the high limit, and what a reading does to it.

A band is not simply a pair of numbers. Three things about it are decisions.

The ends are **inclusive**. A reading exactly on the limit is in band. The lab
argued about this once and settled it in the only direction that survives
rounding: readings are quantised on the way in, so an exclusive limit would put
a reading that rounded onto the limit out of band because of the rounding rather
than because of the sand.

A band may be **one ended**. Loss on ignition has a ceiling and no floor, and
inventing a floor of zero so that every band has two ends turns "no lower limit"
into "a lower limit that is never hit", which reads the same until somebody
computes a midpoint from it.

**Widening keeps the midpoint fixed.** A pattern class narrows or widens a
published band by a factor, and doing that by scaling the endpoints would move
the target as well as the width. It is the tolerance that changes with the work,
not the aim, so the midpoint is held and the half width is scaled around it. A
one ended band has no midpoint, so scaling it is refused rather than guessed at.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

from mullerbox.errors import BadInputError
from mullerbox.props.kind import PropertyKind, Reading
from mullerbox.units.reading import scalar_of
from mullerbox.units.scales import Permeability

# The scales that only take whole numbers, and therefore have to be rounded
# rather than quantised when a band is rescaled.
_WHOLE_NUMBER_SCALES = (Permeability,)


class Verdict(Enum):
    """Where a reading sits against a band."""

    BELOW = "below"
    INSIDE = "inside"
    ABOVE = "above"

    @property
    def is_out(self) -> bool:
        return self is not Verdict.INSIDE


def _rebuild(sample: Reading, value: Decimal) -> Reading:
    """A new reading of the same scale carrying a computed number."""
    scale = type(sample)
    if isinstance(sample, _WHOLE_NUMBER_SCALES):
        return scale(int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP)))
    return scale(value)


@dataclass(frozen=True)
class Band:
    """The limits one property is held to."""

    kind: PropertyKind
    low: Reading | None
    high: Reading | None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, PropertyKind):
            raise BadInputError("a band is a band for a property")
        if self.low is None and self.high is None:
            raise BadInputError("a band needs at least one limit")
        for end in (self.low, self.high):
            if end is not None:
                self.kind.require_reading(end)
        two_ended = self.low is not None and self.high is not None
        if two_ended and scalar_of(self.low) > scalar_of(self.high):
            raise BadInputError(f"the {self.kind.label} band runs from {self.low} to {self.high}")

    @classmethod
    def between(cls, kind: PropertyKind, low: Reading, high: Reading) -> Band:
        return cls(kind=kind, low=low, high=high)

    @classmethod
    def at_most(cls, kind: PropertyKind, high: Reading) -> Band:
        return cls(kind=kind, low=None, high=high)

    @classmethod
    def at_least(cls, kind: PropertyKind, low: Reading) -> Band:
        return cls(kind=kind, low=low, high=None)

    @property
    def is_two_ended(self) -> bool:
        return self.low is not None and self.high is not None

    @property
    def floor(self) -> Reading:
        """The low limit of a band that has one.

        Worth having next to ``low`` because most callers already know the band
        is two ended and only want the number. Reaching through ``low`` forces
        every one of them to write the same None check, and a caller that writes
        it once carelessly gets a comparison against None rather than a refusal.
        """
        if self.low is None:
            raise BadInputError(f"the {self.kind.label} band has no lower limit")
        return self.low

    @property
    def ceiling(self) -> Reading:
        """The high limit of a band that has one."""
        if self.high is None:
            raise BadInputError(f"the {self.kind.label} band has no upper limit")
        return self.high

    @property
    def midpoint(self) -> Reading:
        """The aim, which only exists when the band has two ends."""
        if self.low is None or self.high is None:
            raise BadInputError(f"a one ended {self.kind.label} band has no midpoint")
        return _rebuild(self.low, (scalar_of(self.low) + scalar_of(self.high)) / 2)

    @property
    def width(self) -> Decimal:
        if self.low is None or self.high is None:
            raise BadInputError(f"a one ended {self.kind.label} band has no width")
        return scalar_of(self.high) - scalar_of(self.low)

    def verdict(self, reading: object) -> Verdict:
        """Where a reading sits, with both limits inclusive."""
        checked = self.kind.require_reading(reading)
        value = scalar_of(checked)
        if self.low is not None and value < scalar_of(self.low):
            return Verdict.BELOW
        if self.high is not None and value > scalar_of(self.high):
            return Verdict.ABOVE
        return Verdict.INSIDE

    def holds(self, reading: object) -> bool:
        return self.verdict(reading) is Verdict.INSIDE

    def scaled(self, factor: object) -> Band:
        """The same aim, held to a wider or narrower tolerance."""
        if not isinstance(factor, str | int | Decimal | float) or isinstance(factor, bool):
            raise BadInputError("a band is scaled by a ratio")
        ratio = factor if isinstance(factor, Decimal) else Decimal(str(factor))
        if ratio <= 0:
            raise BadInputError("a band cannot be scaled to nothing")
        if not self.is_two_ended:
            raise BadInputError(
                f"a one ended {self.kind.label} band cannot be rescaled around a midpoint"
            )
        assert self.low is not None
        assert self.high is not None
        centre = (scalar_of(self.low) + scalar_of(self.high)) / 2
        half = (scalar_of(self.high) - scalar_of(self.low)) / 2 * ratio
        return Band(
            kind=self.kind,
            low=_rebuild(self.low, centre - half),
            high=_rebuild(self.high, centre + half),
        )

    def __str__(self) -> str:
        if self.low is None:
            return f"{self.kind.label} at most {self.high}"
        if self.high is None:
            return f"{self.kind.label} at least {self.low}"
        return f"{self.kind.label} {self.low} to {self.high}"


__all__ = ["Band", "Verdict"]
