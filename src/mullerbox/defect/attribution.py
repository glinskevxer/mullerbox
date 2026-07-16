"""Deciding whether a scrapped casting is the sand's fault.

Three conditions, all of which have to hold, and the order they are checked in
is the order that produces a useful answer.

**One: the pattern class has to allow the charge.** Asked first because it is
the cheapest and because it settles the misclassified cases without looking at
any readings. A veining call on uncored work is not a sand question with a
negative answer, it is a question that should not have been asked.

**Two: the property has to be one this defect could come from.** A blow reaches
permeability, moisture and volatiles. That the green compression strength was
also out that shift is true and irrelevant, and a report that lists it under the
blow has invented a mechanism.

**Three: the property has to have actually been out of band, in the band that
applied to that work.** This is where the pattern class comes back in a second
and different way: it set the band. A compactability that was in band for heavy
jobbing and out for thin wall is out only for the thin wall molds, and the same
shift's sand is therefore guilty on one line of the scrap report and innocent on
the next. That is not an inconsistency, it is the point.

What comes back names every excursion that supports the charge rather than the
first one found. A blow with both permeability and moisture out is a different
conversation from a blow with only moisture out, and the muller does different
things about them.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from mullerbox.defect.kind import Culprit, DefectKind
from mullerbox.errors import BadInputError
from mullerbox.gfn.distribution import Distribution
from mullerbox.props.kind import PropertyKind, Reading
from mullerbox.spec.band import Band, Verdict
from mullerbox.spec.pattern import PatternClass
from mullerbox.spec.permeability import expected_permeability
from mullerbox.spec.sheet import ResolvedSpec


@dataclass(frozen=True)
class Excursion:
    """One property that was out of the band in force."""

    kind: PropertyKind
    reading: Reading
    verdict: Verdict
    band: Band

    def __post_init__(self) -> None:
        if self.verdict is Verdict.INSIDE:
            raise BadInputError("a reading inside its band is not an excursion")

    def __str__(self) -> str:
        return f"{self.kind.label} {self.reading} {self.verdict.value} {self.band}"


@dataclass(frozen=True)
class Attribution:
    """Where one defect is charged, and what carried the decision."""

    defect: DefectKind
    pattern: PatternClass
    culprit: Culprit
    excursions: tuple[Excursion, ...]
    reason: str

    @property
    def is_sand(self) -> bool:
        return self.culprit is Culprit.SAND

    @property
    def properties(self) -> tuple[PropertyKind, ...]:
        return tuple(e.kind for e in self.excursions)

    def __str__(self) -> str:
        return f"{self.defect.label} on {self.pattern.label}: {self.culprit.label}, {self.reason}"


def band_in_force(
    resolved: ResolvedSpec,
    kind: PropertyKind,
    distribution: Distribution | None = None,
) -> Band:
    """The band a reading is actually judged against.

    For every property but one this is the band off the sheet. Permeability is
    the exception, and `mullerbox.spec.permeability` says why: the published
    figure is an anchor for the reference sand, and the sand in the system is
    not the reference sand. Given a sieve analysis, the anchor is shifted to
    what this sand should read, and the shifted band is what judges.

    Without a distribution the anchor is used unshifted. That is not a silent
    default so much as the honest one: nothing here can invent a sieve analysis
    the lab did not run, and the caller that has one should pass it.
    """
    if not isinstance(resolved, ResolvedSpec):
        raise BadInputError("a resolved spec is expected")
    if not isinstance(kind, PropertyKind):
        raise BadInputError("a property kind is expected")
    band = resolved.band_for(kind)
    if kind is not PropertyKind.PERMEABILITY or distribution is None:
        return band
    if not isinstance(distribution, Distribution):
        raise BadInputError("a graded distribution is expected")
    if not band.is_two_ended:
        # A one ended permeability limit is a floor or a ceiling and not an
        # anchor, so there is nothing to shift and nothing to correct.
        return band
    return expected_permeability(resolved, distribution).band


def excursions_for(
    defect: DefectKind,
    resolved: ResolvedSpec,
    readings: Mapping[PropertyKind, Reading],
    distribution: Distribution | None = None,
) -> tuple[Excursion, ...]:
    """Every candidate property of this defect that was out of the band in force.

    A candidate the resolved spec does not judge is skipped rather than treated
    as passing. There is no band, so there is no excursion, and saying so is not
    the same as saying the property was fine.

    The band in force is not always the band on the sheet. Pass the sieve
    analysis and permeability is judged against the shifted band, which is the
    whole point of publishing an anchor; without it a coarse sand reads high
    against a band written for finer sand and every blow gets charged to
    permeability that was never out.
    """
    if not isinstance(defect, DefectKind):
        raise BadInputError("a defect kind is expected")
    if not isinstance(resolved, ResolvedSpec):
        raise BadInputError("a resolved spec is expected")
    found: list[Excursion] = []
    for kind in sorted(defect.candidate_properties, key=lambda k: k.name):
        if not resolved.judges(kind):
            continue
        reading = readings.get(kind)
        if reading is None:
            continue
        band = band_in_force(resolved, kind, distribution)
        verdict = band.verdict(reading)
        if verdict is not Verdict.INSIDE:
            found.append(Excursion(kind=kind, reading=reading, verdict=verdict, band=band))
    return tuple(found)


def attribute(
    defect: DefectKind,
    resolved: ResolvedSpec,
    readings: Mapping[PropertyKind, Reading],
    distribution: Distribution | None = None,
) -> Attribution:
    """Charge one defect, given the spec in force and the sand at molding time."""
    if not isinstance(defect, DefectKind):
        raise BadInputError("a defect kind is expected")
    if not isinstance(resolved, ResolvedSpec):
        raise BadInputError("a resolved spec is expected")
    pattern = resolved.pattern
    if not defect.attributable_on(pattern):
        why = (
            "no sand property can cause it"
            if not defect.can_ever_be_sand
            else f"{pattern.label} work does not produce it from the sand"
        )
        return Attribution(
            defect=defect,
            pattern=pattern,
            culprit=defect.fallback,
            excursions=(),
            reason=why,
        )
    found = excursions_for(defect, resolved, readings, distribution)
    if not found:
        return Attribution(
            defect=defect,
            pattern=pattern,
            culprit=defect.fallback,
            excursions=(),
            reason="every property that could have caused it was in band",
        )
    named = ", ".join(str(e) for e in found)
    return Attribution(
        defect=defect,
        pattern=pattern,
        culprit=Culprit.SAND,
        excursions=found,
        reason=f"out of band at molding time: {named}",
    )


def charged_to_sand(
    defects: list[DefectKind],
    resolved: ResolvedSpec,
    readings: Mapping[PropertyKind, Reading],
    distribution: Distribution | None = None,
) -> list[Attribution]:
    """Every defect in a list that lands on the sand."""
    attributed = (attribute(d, resolved, readings, distribution) for d in defects)
    return [a for a in attributed if a.is_sand]


__all__ = [
    "Attribution",
    "Excursion",
    "attribute",
    "band_in_force",
    "charged_to_sand",
    "excursions_for",
]
