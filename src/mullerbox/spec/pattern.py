"""What is being molded, which is what decides how the sand is judged.

A jobbing foundry runs several kinds of work through one sand system, and the
sand is not right or wrong in the abstract. It is right or wrong *for what is on
the line*. A compactability of forty five is comfortable under a heavy plain
casting and is too wet under a thin walled one, where the extra water flashes to
steam faster than the mold can vent it. Same sand, same number, opposite verdict.

Two things come off the pattern class and they are separate. The first is which
properties are controlled at all: nobody runs a wet tensile on plain heavy work,
because the failure it predicts does not happen there. The second is how tightly
the controlled ones are held, which is the tolerance factor.

The third thing that comes off it lives in ``defect``: whether a given casting
defect can be charged to the sand at all. That one is kept apart deliberately,
because a class that controls a property is not the same as a class where that
property can take the blame, and collapsing the two is how a scrap report starts
charging vent defects to a sand system that was never asked to vent.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum

from mullerbox.errors import BadInputError
from mullerbox.props.kind import PropertyKind


class Section(Enum):
    """How heavy the casting is, in the only sense the sand cares about.

    Section thickness governs how long metal stays liquid against the mold wall,
    which governs how much gas the sand has to pass and how long it has to hold
    its strength. It is the single biggest driver of what the sand has to do.
    """

    THIN = "thin section"
    MEDIUM = "medium section"
    HEAVY = "heavy section"

    @property
    def label(self) -> str:
        return self.value


class PatternClass(Enum):
    """A family of work with one set of sand demands."""

    LIGHT_JOBBING = "light jobbing"
    MEDIUM_JOBBING = "medium jobbing"
    HEAVY_JOBBING = "heavy jobbing"
    CORED_LIGHT = "cored light"
    CORED_HEAVY = "cored heavy"
    THIN_WALL = "thin wall"

    @property
    def label(self) -> str:
        return self.value

    @property
    def section(self) -> Section:
        return _SECTION[self]

    @property
    def is_cored(self) -> bool:
        return self in {PatternClass.CORED_LIGHT, PatternClass.CORED_HEAVY}

    @property
    def controlled(self) -> frozenset[PropertyKind]:
        """The properties held to a band for this class."""
        return _CONTROLLED[self]

    @property
    def tolerance_factor(self) -> Decimal:
        """How much a published band is widened or narrowed for this class.

        Below one narrows the band, above one widens it. Thin wall work is held
        to seventy percent of the published width because it has the least
        margin; heavy plain work gets a fifth more because it has the most.
        """
        return _TOLERANCE[self]

    def controls(self, kind: object) -> bool:
        if not isinstance(kind, PropertyKind):
            raise BadInputError("a property kind is expected")
        return kind in self.controlled

    def require_controls(self, kind: object) -> PropertyKind:
        """The property, or a refusal saying this class does not hold it."""
        if not isinstance(kind, PropertyKind):
            raise BadInputError("a property kind is expected")
        if kind not in self.controlled:
            raise BadInputError(f"{self.label} work does not control {kind.label}")
        return kind


_SECTION: dict[PatternClass, Section] = {
    PatternClass.LIGHT_JOBBING: Section.THIN,
    PatternClass.MEDIUM_JOBBING: Section.MEDIUM,
    PatternClass.HEAVY_JOBBING: Section.HEAVY,
    PatternClass.CORED_LIGHT: Section.THIN,
    PatternClass.CORED_HEAVY: Section.HEAVY,
    PatternClass.THIN_WALL: Section.THIN,
}

# Everything controls the four that decide whether a mold stands up at all.
_CORE_FOUR = frozenset(
    {
        PropertyKind.COMPACTABILITY,
        PropertyKind.GREEN_COMPRESSION,
        PropertyKind.MOISTURE,
        PropertyKind.MB_CLAY,
    }
)

_CONTROLLED: dict[PatternClass, frozenset[PropertyKind]] = {
    PatternClass.LIGHT_JOBBING: _CORE_FOUR | {PropertyKind.PERMEABILITY},
    PatternClass.MEDIUM_JOBBING: _CORE_FOUR | {PropertyKind.PERMEABILITY, PropertyKind.LOI},
    PatternClass.HEAVY_JOBBING: _CORE_FOUR
    | {PropertyKind.PERMEABILITY, PropertyKind.LOI, PropertyKind.VOLATILES},
    # Cored work adds the friability that decides whether the core prints
    # survive closing, and the wet tensile that predicts a scab at the core.
    PatternClass.CORED_LIGHT: _CORE_FOUR
    | {PropertyKind.PERMEABILITY, PropertyKind.FRIABILITY, PropertyKind.WET_TENSILE},
    PatternClass.CORED_HEAVY: _CORE_FOUR
    | {
        PropertyKind.PERMEABILITY,
        PropertyKind.FRIABILITY,
        PropertyKind.WET_TENSILE,
        PropertyKind.LOI,
        PropertyKind.VOLATILES,
    },
    # Thin wall work vents through the sand or it does not fill, so it controls
    # everything that touches gas, and the hardness the squeeze delivers.
    PatternClass.THIN_WALL: _CORE_FOUR
    | {
        PropertyKind.PERMEABILITY,
        PropertyKind.LOI,
        PropertyKind.VOLATILES,
        PropertyKind.WET_TENSILE,
        PropertyKind.MOLD_HARDNESS,
    },
}

_TOLERANCE: dict[PatternClass, Decimal] = {
    PatternClass.LIGHT_JOBBING: Decimal("1.00"),
    PatternClass.MEDIUM_JOBBING: Decimal("1.00"),
    PatternClass.HEAVY_JOBBING: Decimal("1.20"),
    PatternClass.CORED_LIGHT: Decimal("0.90"),
    PatternClass.CORED_HEAVY: Decimal("1.00"),
    PatternClass.THIN_WALL: Decimal("0.70"),
}


def parse_pattern_class(text: str) -> PatternClass:
    """Read a class off a schedule, where it is written with any separator."""
    key = " ".join(text.strip().lower().replace("_", " ").replace("-", " ").split())
    for member in PatternClass:
        if member.value == key:
            return member
    raise BadInputError(f"{text!r} is not a pattern class")


__all__ = ["PatternClass", "Section", "parse_pattern_class"]
