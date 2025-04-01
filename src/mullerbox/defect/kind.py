"""The defects a grey iron casting comes back with, and what each one means.

Two separate questions live here and keeping them apart is the whole point.

**Which sand properties could plausibly cause this defect.** A blow is a gas
defect, so it is reachable from low permeability, high moisture and high loss on
ignition. It is not reachable from green compression strength, and a scrap
report that charges a blow to a strength excursion has found a coincidence.

**Whether this pattern class allows the charge at all.** Veining is a core
defect. On uncored work there is no core to vein, so a veining call on a light
jobbing pattern is a misclassification by the inspector rather than a sand
problem, however far out of band the sand was that shift. The same reasoning
runs the other way: penetration on heavy section work is a real sand call, and
on thin wall work the metal is gone before it can penetrate anything.

Those two are independent and both have to hold. Collapsing them into one table
is the mistake that makes a scrap report useless, because it turns "the sand was
out and this defect can be caused by sand" into "the sand did it", which is a
different claim and often a false one.

Some defects are never the sand's. Misruns, cold shuts, shrinkage and slag come
off the melt or the gating, and no sand property appears against them. They are
carried here rather than left out so that a report can account for a whole
heat's scrap without the sand-attributable ones being the only rows on it.
"""

from __future__ import annotations

from enum import Enum

from mullerbox.errors import BadInputError
from mullerbox.props.kind import PropertyKind
from mullerbox.spec.pattern import PatternClass


class Family(Enum):
    """The mechanism behind a defect, which is how a foundry groups them."""

    EXPANSION = "expansion"
    GAS = "gas"
    METAL_PENETRATION = "penetration"
    MOLD_BREAKAGE = "mold breakage"
    MELT = "melt"

    @property
    def label(self) -> str:
        return self.value


class Culprit(Enum):
    """Where a defect is charged once the question has been settled."""

    SAND = "sand"
    PATTERN = "pattern"
    MELT = "melt"

    @property
    def label(self) -> str:
        return self.value


class DefectKind(Enum):
    """One named casting defect."""

    SCAB = "scab"
    RAT_TAIL = "rat tail"
    BUCKLE = "buckle"
    VEINING = "veining"
    BLOW = "blow"
    PINHOLE = "pinhole"
    PENETRATION = "penetration"
    SAND_INCLUSION = "sand inclusion"
    CUT_AND_WASH = "cut and wash"
    EROSION = "erosion"
    MISRUN = "misrun"
    COLD_SHUT = "cold shut"
    SHRINKAGE = "shrinkage"
    SLAG = "slag"

    @property
    def label(self) -> str:
        return self.value

    @property
    def family(self) -> Family:
        return _FAMILY[self]

    @property
    def candidate_properties(self) -> frozenset[PropertyKind]:
        """Sand properties that could plausibly cause this defect."""
        return _CANDIDATES[self]

    @property
    def can_ever_be_sand(self) -> bool:
        return bool(self.candidate_properties)

    @property
    def fallback(self) -> Culprit:
        """Where it goes when the sand is not to blame."""
        return _FALLBACK[self]

    def attributable_on(self, pattern: object) -> bool:
        """Whether this class of work can produce this defect from the sand."""
        if not isinstance(pattern, PatternClass):
            raise BadInputError("a pattern class is expected")
        return pattern in _ATTRIBUTABLE[self]

    def classes_that_allow_it(self) -> frozenset[PatternClass]:
        return _ATTRIBUTABLE[self]


_FAMILY: dict[DefectKind, Family] = {
    DefectKind.SCAB: Family.EXPANSION,
    DefectKind.RAT_TAIL: Family.EXPANSION,
    DefectKind.BUCKLE: Family.EXPANSION,
    DefectKind.VEINING: Family.EXPANSION,
    DefectKind.BLOW: Family.GAS,
    DefectKind.PINHOLE: Family.GAS,
    DefectKind.PENETRATION: Family.METAL_PENETRATION,
    DefectKind.SAND_INCLUSION: Family.MOLD_BREAKAGE,
    DefectKind.CUT_AND_WASH: Family.MOLD_BREAKAGE,
    DefectKind.EROSION: Family.MOLD_BREAKAGE,
    DefectKind.MISRUN: Family.MELT,
    DefectKind.COLD_SHUT: Family.MELT,
    DefectKind.SHRINKAGE: Family.MELT,
    DefectKind.SLAG: Family.MELT,
}

# Expansion defects come from silica expanding faster than the mold can give.
# Carbon cushions it, water makes it worse, and a hot strong mold has nowhere
# to move.
_EXPANSION = frozenset({PropertyKind.LOI, PropertyKind.MOISTURE, PropertyKind.COMPACTABILITY})

# Gas defects come from more gas than the mold can pass.
_GAS = frozenset({PropertyKind.PERMEABILITY, PropertyKind.MOISTURE, PropertyKind.VOLATILES})

# Breakage comes from a mold that will not hold together under the stream.
_BREAKAGE = frozenset(
    {
        PropertyKind.GREEN_COMPRESSION,
        PropertyKind.FRIABILITY,
        PropertyKind.COMPACTABILITY,
    }
)

_CANDIDATES: dict[DefectKind, frozenset[PropertyKind]] = {
    DefectKind.SCAB: _EXPANSION,
    DefectKind.RAT_TAIL: _EXPANSION,
    DefectKind.BUCKLE: _EXPANSION,
    DefectKind.VEINING: _EXPANSION,
    DefectKind.BLOW: _GAS,
    DefectKind.PINHOLE: _GAS,
    DefectKind.PENETRATION: frozenset(
        {
            PropertyKind.PERMEABILITY,
            PropertyKind.GREEN_COMPRESSION,
            PropertyKind.MOLD_HARDNESS,
        }
    ),
    DefectKind.SAND_INCLUSION: _BREAKAGE,
    DefectKind.CUT_AND_WASH: _BREAKAGE,
    DefectKind.EROSION: _BREAKAGE,
    DefectKind.MISRUN: frozenset(),
    DefectKind.COLD_SHUT: frozenset(),
    DefectKind.SHRINKAGE: frozenset(),
    DefectKind.SLAG: frozenset(),
}

_FALLBACK: dict[DefectKind, Culprit] = {
    DefectKind.SCAB: Culprit.PATTERN,
    DefectKind.RAT_TAIL: Culprit.PATTERN,
    DefectKind.BUCKLE: Culprit.PATTERN,
    DefectKind.VEINING: Culprit.PATTERN,
    DefectKind.BLOW: Culprit.MELT,
    DefectKind.PINHOLE: Culprit.MELT,
    DefectKind.PENETRATION: Culprit.MELT,
    DefectKind.SAND_INCLUSION: Culprit.PATTERN,
    DefectKind.CUT_AND_WASH: Culprit.PATTERN,
    DefectKind.EROSION: Culprit.PATTERN,
    DefectKind.MISRUN: Culprit.MELT,
    DefectKind.COLD_SHUT: Culprit.MELT,
    DefectKind.SHRINKAGE: Culprit.MELT,
    DefectKind.SLAG: Culprit.MELT,
}

_EVERY_CLASS = frozenset(PatternClass)
_CORED = frozenset({PatternClass.CORED_LIGHT, PatternClass.CORED_HEAVY})
_HEAVY = frozenset({PatternClass.HEAVY_JOBBING, PatternClass.CORED_HEAVY})
_NOT_THIN_WALL = _EVERY_CLASS - {PatternClass.THIN_WALL}

_ATTRIBUTABLE: dict[DefectKind, frozenset[PatternClass]] = {
    # Expansion needs a hot face held long enough, so not on thin wall work.
    DefectKind.SCAB: _NOT_THIN_WALL,
    DefectKind.RAT_TAIL: _NOT_THIN_WALL,
    DefectKind.BUCKLE: _NOT_THIN_WALL,
    # There is no core to vein on uncored work.
    DefectKind.VEINING: _CORED,
    # Gas is everybody's problem.
    DefectKind.BLOW: _EVERY_CLASS,
    DefectKind.PINHOLE: _EVERY_CLASS,
    # Metal has to stay liquid against the wall long enough to push in.
    DefectKind.PENETRATION: _HEAVY,
    DefectKind.SAND_INCLUSION: _EVERY_CLASS,
    DefectKind.CUT_AND_WASH: _EVERY_CLASS,
    DefectKind.EROSION: _EVERY_CLASS,
    DefectKind.MISRUN: frozenset(),
    DefectKind.COLD_SHUT: frozenset(),
    DefectKind.SHRINKAGE: frozenset(),
    DefectKind.SLAG: frozenset(),
}


def parse_defect(text: str) -> DefectKind:
    """Read a defect off an inspection sheet, whatever separator was used."""
    key = " ".join(text.strip().lower().replace("_", " ").replace("-", " ").split())
    for member in DefectKind:
        if member.value == key:
            return member
    raise BadInputError(f"{text!r} is not a defect on the shop's list")


__all__ = ["Culprit", "DefectKind", "Family", "parse_defect"]
