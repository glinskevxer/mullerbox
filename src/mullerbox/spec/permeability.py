"""Why a permeability band cannot be published as one pair of numbers.

Permeability is the odd property. Every other band on the sheet is a target the
sand is supposed to hit. Permeability is a *consequence*: it falls out of the
grain size and the grain distribution, and the sand cannot be adjusted to it
directly. Adding water or bond moves it a little; nothing in the muller moves it
much. What moves it is the sand grains themselves.

So a fixed band judges the wrong thing. A 55 GFN three screen sand and a 75 GFN
spread sand will read a hundred AFS apart, and both may be exactly the sand the
foundry bought. Judging both against one band flags the second one every shift
until somebody turns the alarm off, which is worse than not having it.

The band published on the sheet is therefore an anchor: what to expect from the
reference sand at the reference fineness. This module shifts that anchor by what
the sieve analysis actually says, and the shifted band is what the reading is
judged against. Two corrections, in this order:

**Fineness.** Finer sand packs tighter and vents worse, so permeability falls as
the grain fineness number rises. About one and four fifths AFS points per GFN
point over the range foundry sands live in. Linear is not the physics, but it is
close enough over 45 to 90 GFN and it is what the shop's own chart does.

**Distribution.** At equal fineness, a sand piled on three adjacent screens
vents better than one spread across six, because the spread one has fines
filling the voids between the coarse grains. The correction is a step per
grading class rather than a curve, because the grading itself is a step.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from mullerbox.errors import BadInputError
from mullerbox.gfn.distribution import Distribution, Grading
from mullerbox.props.kind import PropertyKind
from mullerbox.spec.band import Band
from mullerbox.spec.sheet import ResolvedSpec
from mullerbox.units.scales import Permeability

# The fineness the published band assumes.
REFERENCE_GFN = Decimal("65")

# AFS permeability points lost per grain fineness point gained.
AFS_PER_GFN = Decimal("1.8")

# What the grading is worth at equal fineness.
GRADING_SHIFT: dict[Grading, Decimal] = {
    Grading.THREE_SCREEN: Decimal("8"),
    Grading.FOUR_SCREEN: Decimal("0"),
    Grading.SPREAD: Decimal("-10"),
}


@dataclass(frozen=True)
class Expectation:
    """The permeability band actually in force, and how it got there."""

    band: Band
    anchor: Band
    fineness_shift: Decimal
    grading_shift: Decimal

    @property
    def total_shift(self) -> Decimal:
        return self.fineness_shift + self.grading_shift

    def __str__(self) -> str:
        return f"{self.band} (anchor {self.anchor}, shifted {self.total_shift:+})"


def _shifted(band: Band, by: Decimal) -> Band:
    """Move both ends of a permeability band, floored at zero."""
    if band.low is None or band.high is None:
        raise BadInputError("a permeability anchor needs both limits")
    low = _to_permeability(Decimal(band.low.value) + by)
    high = _to_permeability(Decimal(band.high.value) + by)
    return Band.between(PropertyKind.PERMEABILITY, low, high)


def _to_permeability(value: Decimal) -> Permeability:
    rounded = int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return Permeability(max(rounded, 0))


def expected_permeability(resolved: ResolvedSpec, distribution: Distribution) -> Expectation:
    """Shift the published permeability band by what the sieve analysis says.

    Both corrections are applied to the band rather than to the reading. Moving
    the reading would produce a "corrected permeability" that is not a number
    anybody measured and that would then get plotted on a control chart beside
    numbers that were. Moving the band leaves the measurement alone and puts the
    derivation where it belongs, in the judgement.
    """
    if not isinstance(resolved, ResolvedSpec):
        raise BadInputError("a permeability expectation starts from a resolved spec")
    if not isinstance(distribution, Distribution):
        raise BadInputError("a permeability expectation needs a graded distribution")
    anchor = resolved.band_for(PropertyKind.PERMEABILITY)
    if not anchor.is_two_ended:
        raise BadInputError("a permeability anchor needs both limits")
    fineness_shift = (REFERENCE_GFN - distribution.fineness.value) * AFS_PER_GFN
    grading_shift = GRADING_SHIFT[distribution.grading]
    return Expectation(
        band=_shifted(anchor, fineness_shift + grading_shift),
        anchor=anchor,
        fineness_shift=fineness_shift,
        grading_shift=grading_shift,
    )


__all__ = [
    "AFS_PER_GFN",
    "Expectation",
    "GRADING_SHIFT",
    "REFERENCE_GFN",
    "expected_permeability",
]
