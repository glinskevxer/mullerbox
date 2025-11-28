"""Ranking scrap so the shop works on the right thing.

A month of scrap is forty defect calls across nine kinds and the useful question
is which two to fix. Sorting by count answers it wrong: a foundry that scraps
thirty small castings for pinholes and two large ones for penetration has lost
more weight to penetration, and weight is what it sells.

So the ranking is by weight and the count comes along beside it, because the two
disagreeing is itself the finding. A defect that is high on count and low on
weight is a nuisance on the small work; the reverse is a problem on the heavy
work that nobody has noticed because it happens twice a month.

**The cumulative share is carried and the eighty percent line is marked**,
because that is what a Pareto is for: it says where to stop reading. Everything
below the line is real and is not where the next month goes.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from mullerbox.defect.kind import Culprit, DefectKind
from mullerbox.defect.scrap import ScrapReport
from mullerbox.errors import BadInputError
from mullerbox.units.bulk import Pounds

# The share of the total that the "vital few" are taken to cover.
VITAL_SHARE = Decimal("0.80")


@dataclass(frozen=True)
class Band:
    """One defect's contribution to the scrap."""

    defect: DefectKind
    weight: Pounds
    count: int
    share: Decimal
    cumulative: Decimal

    @property
    def is_vital(self) -> bool:
        """Whether this band is inside the eighty percent.

        Measured on the cumulative *before* this band rather than after it, so
        the band that carries the total across the line is inside it. Testing
        the cumulative after is the obvious reading and it is wrong at both
        ends: a single defect making all of the scrap has a cumulative of one
        and would fall outside its own vital few, and the first band of any
        set that is over eighty percent on its own would too.
        """
        return self.cumulative - self.share < VITAL_SHARE

    def __str__(self) -> str:
        return f"{self.defect.label}: {self.weight} over {self.count} castings, {self.share:.1%}"


@dataclass(frozen=True)
class Pareto:
    """Scrap ranked by weight, with the vital few marked."""

    total: Pounds
    bands: tuple[Band, ...]

    @property
    def vital_few(self) -> tuple[Band, ...]:
        return tuple(band for band in self.bands if band.is_vital)

    @property
    def by_count(self) -> tuple[Band, ...]:
        """The same bands ranked the wrong way, for comparison."""
        return tuple(sorted(self.bands, key=lambda b: (-b.count, b.defect.name)))

    @property
    def ranking_disagrees(self) -> bool:
        """True when weight and count do not put the same defect first.

        Worth reporting on its own. It means the shop's impression of what it
        scraps, which comes from counting, is not what its scrap actually costs.
        """
        if not self.bands:
            return False
        return self.bands[0].defect is not self.by_count[0].defect

    def band_for(self, defect: DefectKind) -> Band | None:
        for band in self.bands:
            if band.defect is defect:
                return band
        return None

    def __str__(self) -> str:
        if not self.bands:
            return "no scrap to rank"
        named = ", ".join(b.defect.label for b in self.vital_few)
        return f"{self.total} of scrap, {VITAL_SHARE:.0%} of it in: {named}"


def pareto_of(reports: list[ScrapReport], *, sand_only: bool = False) -> Pareto:
    """Rank the defects across several heats by the weight they scrapped.

    A casting carrying two defects contributes its whole weight to each. That
    over-counts the total on purpose: the question a Pareto answers is "which
    defect, if it went away, would save the most weight", and for that question
    a casting with a blow and a scab really is saved by fixing either. The total
    is therefore a sum of contributions rather than a scrap weight, and it is
    named that way so nobody reconciles it against the scrap sheet.
    """
    contributions: dict[DefectKind, list[Pounds]] = {}
    for report in reports:
        if not isinstance(report, ScrapReport):
            raise BadInputError("a pareto is built from scrap reports")
        for charge in report.charges:
            if sand_only and charge.culprit is not Culprit.SAND:
                continue
            for attribution in charge.attributions:
                contributions.setdefault(attribution.defect, []).append(charge.weight)
    if not contributions:
        return Pareto(total=Pounds.zero(), bands=())
    totals = {
        defect: sum((w.value for w in weights), Decimal(0))
        for defect, weights in contributions.items()
    }
    grand = sum(totals.values(), Decimal(0))
    ordered = sorted(totals, key=lambda d: (-totals[d], d.name))
    bands: list[Band] = []
    running = Decimal(0)
    for defect in ordered:
        share = (totals[defect] / grand).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        running += share
        bands.append(
            Band(
                defect=defect,
                weight=Pounds(totals[defect]),
                count=len(contributions[defect]),
                share=share,
                cumulative=running,
            )
        )
    return Pareto(total=Pounds(grand), bands=tuple(bands))


__all__ = ["Band", "Pareto", "VITAL_SHARE", "pareto_of"]
