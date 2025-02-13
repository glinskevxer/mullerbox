"""What the lab measures, on what, and in what.

Each property is tied to the instrument kind that measures it and to the type
its reading comes back in. Both links are load bearing.

The instrument link is what lets a result be refused before it is stored: a
green compression figure attributed to the permeability meter is not a reading
that needs checking against a band, it is a data entry fault, and catching it at
the point of entry is the difference between one bad number and a month of
control charts built on one.

The reading type link is what stops a band comparison from silently succeeding
against the wrong scale. Compactability and moisture are both percentages and
are interchangeable to a type checker; permeability and mold hardness are both
small whole numbers and are not interchangeable at all. Naming the type per
property lets the band check refuse a mismatch instead of comparing whatever it
was handed.
"""

from __future__ import annotations

from enum import Enum

from mullerbox.cal.instrument import InstrumentKind
from mullerbox.errors import BadInputError
from mullerbox.units.percent import Percent
from mullerbox.units.pressure import Psi, WetTensile
from mullerbox.units.scales import Hardness, Permeability

# Everything a result may carry. Kept as a union rather than a common base so
# that adding a scale is a change the type checker points at.
Reading = Percent | Psi | WetTensile | Permeability | Hardness


class Direction(Enum):
    """Which way a property being out of band hurts.

    Most sand properties are two sided: too much bond is as bad as too little.
    A few are one sided, and the difference matters when a band is being
    resolved from a partial specification, because a one sided property with
    only one limit given is fully specified and a two sided one is not.
    """

    TWO_SIDED = "two sided"
    HIGHER_IS_WORSE = "higher is worse"
    LOWER_IS_WORSE = "lower is worse"


class PropertyKind(Enum):
    """One measurable property of the sand."""

    COMPACTABILITY = "compactability"
    GREEN_COMPRESSION = "green compression strength"
    PERMEABILITY = "permeability"
    MOISTURE = "moisture"
    MB_CLAY = "methylene blue clay"
    TOTAL_CLAY = "total clay"
    LOI = "loss on ignition"
    VOLATILES = "volatiles"
    FRIABILITY = "friability"
    WET_TENSILE = "wet tensile strength"
    MOLD_HARDNESS = "mold hardness"
    SHATTER_INDEX = "shatter index"

    @property
    def label(self) -> str:
        return self.value

    @property
    def measured_by(self) -> InstrumentKind:
        return _INSTRUMENT[self]

    @property
    def reading_type(self) -> type[Percent | Psi | WetTensile | Permeability | Hardness]:
        return _READING[self]

    @property
    def direction(self) -> Direction:
        return _DIRECTION[self]

    def accepts(self, reading: object) -> bool:
        """Whether a value is the right kind of number for this property."""
        return isinstance(reading, self.reading_type)

    def require_reading(self, reading: object) -> Reading:
        """The reading, or a refusal naming both scales."""
        if not self.accepts(reading):
            raise BadInputError(
                f"{self.label} is measured in {self.reading_type.__name__}, "
                f"not {type(reading).__name__}"
            )
        assert isinstance(reading, Percent | Psi | WetTensile | Permeability | Hardness)
        return reading

    def require_instrument_kind(self, kind: object) -> InstrumentKind:
        """The instrument kind, or a refusal naming the one that should have been used."""
        if not isinstance(kind, InstrumentKind):
            raise BadInputError("an instrument kind is expected")
        if kind is not self.measured_by:
            raise BadInputError(
                f"{self.label} is measured on the {self.measured_by.label}, not the {kind.label}"
            )
        return kind


_INSTRUMENT: dict[PropertyKind, InstrumentKind] = {
    PropertyKind.COMPACTABILITY: InstrumentKind.COMPACTABILITY,
    PropertyKind.GREEN_COMPRESSION: InstrumentKind.STRENGTH,
    PropertyKind.PERMEABILITY: InstrumentKind.PERMEABILITY,
    PropertyKind.MOISTURE: InstrumentKind.MOISTURE,
    PropertyKind.MB_CLAY: InstrumentKind.CLAY,
    PropertyKind.TOTAL_CLAY: InstrumentKind.BALANCE,
    PropertyKind.LOI: InstrumentKind.MUFFLE,
    PropertyKind.VOLATILES: InstrumentKind.MUFFLE,
    PropertyKind.FRIABILITY: InstrumentKind.BALANCE,
    PropertyKind.WET_TENSILE: InstrumentKind.STRENGTH,
    PropertyKind.MOLD_HARDNESS: InstrumentKind.STRENGTH,
    PropertyKind.SHATTER_INDEX: InstrumentKind.BALANCE,
}

_READING: dict[PropertyKind, type[Percent | Psi | WetTensile | Permeability | Hardness]] = {
    PropertyKind.COMPACTABILITY: Percent,
    PropertyKind.GREEN_COMPRESSION: Psi,
    PropertyKind.PERMEABILITY: Permeability,
    PropertyKind.MOISTURE: Percent,
    PropertyKind.MB_CLAY: Percent,
    PropertyKind.TOTAL_CLAY: Percent,
    PropertyKind.LOI: Percent,
    PropertyKind.VOLATILES: Percent,
    PropertyKind.FRIABILITY: Percent,
    PropertyKind.WET_TENSILE: WetTensile,
    PropertyKind.MOLD_HARDNESS: Hardness,
    PropertyKind.SHATTER_INDEX: Percent,
}

_DIRECTION: dict[PropertyKind, Direction] = {
    PropertyKind.COMPACTABILITY: Direction.TWO_SIDED,
    PropertyKind.GREEN_COMPRESSION: Direction.TWO_SIDED,
    PropertyKind.PERMEABILITY: Direction.TWO_SIDED,
    PropertyKind.MOISTURE: Direction.TWO_SIDED,
    PropertyKind.MB_CLAY: Direction.TWO_SIDED,
    PropertyKind.TOTAL_CLAY: Direction.TWO_SIDED,
    PropertyKind.LOI: Direction.HIGHER_IS_WORSE,
    PropertyKind.VOLATILES: Direction.HIGHER_IS_WORSE,
    PropertyKind.FRIABILITY: Direction.HIGHER_IS_WORSE,
    PropertyKind.WET_TENSILE: Direction.LOWER_IS_WORSE,
    PropertyKind.MOLD_HARDNESS: Direction.TWO_SIDED,
    PropertyKind.SHATTER_INDEX: Direction.LOWER_IS_WORSE,
}


def parse_property(text: str) -> PropertyKind:
    """Read a property off a bench sheet, where the lab uses its own shorthand."""
    key = text.strip().lower().replace("_", " ").replace("-", " ")
    key = " ".join(key.split())
    shorthand = {
        "comp": PropertyKind.COMPACTABILITY,
        "compactability": PropertyKind.COMPACTABILITY,
        "gcs": PropertyKind.GREEN_COMPRESSION,
        "green compression": PropertyKind.GREEN_COMPRESSION,
        "green compression strength": PropertyKind.GREEN_COMPRESSION,
        "perm": PropertyKind.PERMEABILITY,
        "permeability": PropertyKind.PERMEABILITY,
        "moisture": PropertyKind.MOISTURE,
        "h2o": PropertyKind.MOISTURE,
        "mb": PropertyKind.MB_CLAY,
        "mb clay": PropertyKind.MB_CLAY,
        "methylene blue clay": PropertyKind.MB_CLAY,
        "afs clay": PropertyKind.TOTAL_CLAY,
        "total clay": PropertyKind.TOTAL_CLAY,
        "loi": PropertyKind.LOI,
        "loss on ignition": PropertyKind.LOI,
        "volatiles": PropertyKind.VOLATILES,
        "friability": PropertyKind.FRIABILITY,
        "wet tensile": PropertyKind.WET_TENSILE,
        "wet tensile strength": PropertyKind.WET_TENSILE,
        "hardness": PropertyKind.MOLD_HARDNESS,
        "mold hardness": PropertyKind.MOLD_HARDNESS,
        "shatter": PropertyKind.SHATTER_INDEX,
        "shatter index": PropertyKind.SHATTER_INDEX,
    }
    if key not in shorthand:
        raise BadInputError(f"{text!r} is not a sand property")
    return shorthand[key]


__all__ = ["Direction", "PropertyKind", "Reading", "parse_property"]
