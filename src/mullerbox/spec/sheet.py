"""The published bands, and the bands actually in force on a given line.

Two documents, and confusing them is the mistake this module exists to prevent.

The **spec sheet** is what metallurgy published. It is one set of bands for the
sand system, written without reference to any particular job, and it is what
gets argued over once a year and then left alone.

The **resolved spec** is what the sand is actually judged against this shift. It
is the sheet narrowed to the properties the pattern class on the line controls,
with each remaining band rescaled by that class's tolerance factor. It is
derived, it is different for every class, and it is never stored, because
storing it means a spec sheet revision silently fails to reach the lines that
were resolved before it.

So resolution runs at the point of judgement and takes the class as an argument.
A reading is never in band or out of band on its own; it is in band *for the
work that was on the line when it was taken*.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from mullerbox.errors import BadInputError, NotFoundError
from mullerbox.props.kind import PropertyKind
from mullerbox.spec.band import Band, Verdict
from mullerbox.spec.pattern import PatternClass


@dataclass(frozen=True)
class SpecSheet:
    """What metallurgy published, before any job is considered."""

    name: str
    bands: Mapping[PropertyKind, Band]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise BadInputError("a spec sheet needs a name")
        if not self.bands:
            raise BadInputError("a spec sheet with no bands is not a spec sheet")
        for kind, band in self.bands.items():
            if not isinstance(kind, PropertyKind):
                raise BadInputError("a spec sheet is keyed by property")
            if not isinstance(band, Band):
                raise BadInputError("a spec sheet holds bands")
            if band.kind is not kind:
                raise BadInputError(f"the {kind.label} entry holds a {band.kind.label} band")

    @property
    def covers(self) -> frozenset[PropertyKind]:
        return frozenset(self.bands)

    def band_for(self, kind: PropertyKind) -> Band:
        if not isinstance(kind, PropertyKind):
            raise BadInputError("a property kind is expected")
        if kind not in self.bands:
            raise NotFoundError("published band", kind.label)
        return self.bands[kind]

    def missing_for(self, pattern: PatternClass) -> frozenset[PropertyKind]:
        """Properties a class controls that this sheet does not publish."""
        if not isinstance(pattern, PatternClass):
            raise BadInputError("a pattern class is expected")
        return frozenset(pattern.controlled - self.covers)


@dataclass(frozen=True)
class ResolvedSpec:
    """The bands in force for one pattern class, derived from a sheet."""

    sheet_name: str
    pattern: PatternClass
    bands: Mapping[PropertyKind, Band]

    @property
    def covers(self) -> frozenset[PropertyKind]:
        return frozenset(self.bands)

    def band_for(self, kind: PropertyKind) -> Band:
        if not isinstance(kind, PropertyKind):
            raise BadInputError("a property kind is expected")
        if kind not in self.bands:
            raise NotFoundError(f"band in force for {self.pattern.label}", kind.label)
        return self.bands[kind]

    def verdict(self, kind: PropertyKind, reading: object) -> Verdict:
        return self.band_for(kind).verdict(reading)

    def holds(self, kind: PropertyKind, reading: object) -> bool:
        return self.band_for(kind).holds(reading)

    def judges(self, kind: object) -> bool:
        """Whether this resolution has anything to say about a property."""
        if not isinstance(kind, PropertyKind):
            raise BadInputError("a property kind is expected")
        return kind in self.bands


def resolve(sheet: SpecSheet, pattern: PatternClass) -> ResolvedSpec:
    """Narrow a published sheet to one pattern class and rescale what is left.

    A property the class controls but the sheet does not publish is left out
    rather than defaulted. There is no honest default for a missing band, and a
    resolution that quietly omits it lets the caller ask ``judges`` and get a
    truthful no, where a fabricated band would produce a verdict nobody wrote.

    A one ended band is carried through unscaled. Its aim is the limit itself
    rather than a midpoint, so there is nothing for the tolerance factor to move
    it around.
    """
    if not isinstance(sheet, SpecSheet):
        raise BadInputError("a resolution starts from a spec sheet")
    if not isinstance(pattern, PatternClass):
        raise BadInputError("a resolution is against a pattern class")
    factor = pattern.tolerance_factor
    in_force: dict[PropertyKind, Band] = {}
    for kind in sorted(pattern.controlled, key=lambda k: k.name):
        band = sheet.bands.get(kind)
        if band is None:
            continue
        in_force[kind] = band.scaled(factor) if band.is_two_ended else band
    return ResolvedSpec(sheet_name=sheet.name, pattern=pattern, bands=in_force)


__all__ = ["ResolvedSpec", "SpecSheet", "resolve"]
