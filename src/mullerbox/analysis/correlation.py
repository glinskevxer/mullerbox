"""Whether two properties move together, and what that does and does not mean.

The lab's standing question is which of two readings to chase. Moisture and
compactability move together, so a shift where both are low is one problem
rather than two, and treating it as two produces a sand that is corrected twice
and ends up wet.

The arithmetic is a Pearson coefficient over paired readings, and three things
about using it are worth writing down because the number invites misuse.

**Only paired readings count.** Two properties measured on different samples are
not paired, however close in time. Pairing by sample is the only pairing that
means anything, and it is why this takes a mapping per sample rather than two
lists.

**A coefficient is not a mechanism.** Moisture and compactability are causally
linked; moisture and permeability move together too, and mostly because both
follow the clay. So a strong coefficient says look, never says why, and the
strength is reported without any claim about direction of cause.

**A coefficient needs a spread to be computed at all.** If either property was
flat across the run there is no covariance to divide, and the honest answer is
that the run cannot say, not zero. Zero would read as "these are unrelated",
which is a different and much stronger claim.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

from mullerbox.errors import BadInputError, RuleError
from mullerbox.props.kind import PropertyKind

# Fewer pairs than this and a coefficient is noise with a decimal point.
MIN_PAIRS = 10

STRONG = Decimal("0.70")
MODERATE = Decimal("0.40")

_PLACES = Decimal("0.001")


class Strength(Enum):
    """How much of a relationship the coefficient shows."""

    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"

    @property
    def label(self) -> str:
        return self.value


@dataclass(frozen=True)
class Correlation:
    """Two properties over a set of paired readings."""

    first: PropertyKind
    second: PropertyKind
    pairs: int
    coefficient: Decimal

    @property
    def strength(self) -> Strength:
        """How much of a relationship this is, on magnitude alone."""
        magnitude = abs(self.coefficient)
        if magnitude >= STRONG:
            return Strength.STRONG
        if magnitude >= MODERATE:
            return Strength.MODERATE
        return Strength.WEAK

    @property
    def moves_together(self) -> bool:
        return self.coefficient > 0

    def finding(self) -> str:
        """What the coefficient says, with no claim about cause."""
        direction = "together" if self.moves_together else "against each other"
        return (
            f"{self.first.label} and {self.second.label} move {direction}, "
            f"{self.strength.label} at {self.coefficient} over {self.pairs} pairs. "
            "This says where to look and nothing about why"
        )

    def __str__(self) -> str:
        return self.finding()


def paired(
    readings: Mapping[str, Mapping[PropertyKind, Decimal]],
    first: PropertyKind,
    second: PropertyKind,
) -> list[tuple[Decimal, Decimal]]:
    """Every sample that carries both properties, as pairs.

    Keyed by sample, so two readings from different samples never pair up
    however close together they were taken.
    """
    if not isinstance(first, PropertyKind) or not isinstance(second, PropertyKind):
        raise BadInputError("two property kinds are expected")
    if first is second:
        raise BadInputError("a property is perfectly correlated with itself")
    found: list[tuple[Decimal, Decimal]] = []
    for sample_id in sorted(readings):
        values = readings[sample_id]
        one = values.get(first)
        other = values.get(second)
        if one is None or other is None:
            continue
        if not isinstance(one, Decimal) or not isinstance(other, Decimal):
            raise BadInputError(f"sample {sample_id} carries a reading that is not a decimal")
        found.append((one, other))
    return found


def correlate(
    readings: Mapping[str, Mapping[PropertyKind, Decimal]],
    first: PropertyKind,
    second: PropertyKind,
) -> Correlation:
    """Work out how strongly two properties move together across paired samples."""
    pairs = paired(readings, first, second)
    if len(pairs) < MIN_PAIRS:
        raise RuleError(
            f"{len(pairs)} samples carry both readings, and {MIN_PAIRS} is the "
            "fewest that will carry a coefficient"
        )
    count = Decimal(len(pairs))
    mean_one = sum((a for a, _ in pairs), Decimal(0)) / count
    mean_two = sum((b for _, b in pairs), Decimal(0)) / count
    covariance = sum(((a - mean_one) * (b - mean_two) for a, b in pairs), Decimal(0))
    spread_one = sum(((a - mean_one) ** 2 for a, _ in pairs), Decimal(0))
    spread_two = sum(((b - mean_two) ** 2 for _, b in pairs), Decimal(0))
    if spread_one == 0 or spread_two == 0:
        flat = first.label if spread_one == 0 else second.label
        raise RuleError(
            f"{flat} did not move across these samples, so the run cannot say "
            "whether the two are related"
        )
    coefficient = covariance / (spread_one * spread_two).sqrt()
    return Correlation(
        first=first,
        second=second,
        pairs=len(pairs),
        coefficient=coefficient.quantize(_PLACES, rounding=ROUND_HALF_UP),
    )


__all__ = [
    "Correlation",
    "MIN_PAIRS",
    "MODERATE",
    "STRONG",
    "Strength",
    "correlate",
    "paired",
]
