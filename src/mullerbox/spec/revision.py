"""Comparing two published spec sheets, and saying what a revision changed.

A spec revision is a small diff with large consequences and it arrives as a new
sheet rather than as a list of changes. So the diff has to be computed, and the
useful shape of it is not "what is different" but "what does this do to the sand
we are already making".

Three kinds of change, and they are not equally interesting.

**A band that moved its aim** is the one that matters. Sand sitting comfortably
in the old band can be out of the new one on the day it is published, with no
change to the sand at all, and the shift report will say so without explaining
why. So a moved aim is reported with the direction and the size.

**A band that only changed width** is a tolerance decision. Nothing is
immediately out that was not out before if it widened; if it narrowed, readings
near the edge move outside. Reported, and separately.

**A band added or dropped** changes what is controlled at all. Dropping one is
the quiet case: a property stops being judged and nothing on any report says it
used to be.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from mullerbox.errors import BadInputError
from mullerbox.props.kind import PropertyKind
from mullerbox.spec.band import Band, _scalar
from mullerbox.spec.sheet import SpecSheet


@dataclass(frozen=True)
class Change:
    """What a revision did to one property's band."""

    kind: PropertyKind
    was: Band | None
    now: Band | None

    @property
    def is_added(self) -> bool:
        return self.was is None and self.now is not None

    @property
    def is_dropped(self) -> bool:
        return self.was is not None and self.now is None

    @property
    def aim_moved(self) -> Decimal | None:
        """How far the midpoint moved, when both bands have one."""
        if self.was is None or self.now is None:
            return None
        if not (self.was.is_two_ended and self.now.is_two_ended):
            return None
        return _scalar(self.now.midpoint) - _scalar(self.was.midpoint)

    @property
    def width_changed(self) -> Decimal | None:
        """How much wider the band got, when both bands have a width."""
        if self.was is None or self.now is None:
            return None
        if not (self.was.is_two_ended and self.now.is_two_ended):
            return None
        return self.now.width - self.was.width

    @property
    def is_material(self) -> bool:
        """Whether this change can put in-band sand out of band on publication."""
        if self.is_added:
            return True
        moved = self.aim_moved
        narrowed = self.width_changed
        if moved is not None and moved != 0:
            return True
        return narrowed is not None and narrowed < 0

    def __str__(self) -> str:
        if self.is_added:
            return f"{self.kind.label} is now controlled: {self.now}"
        if self.is_dropped:
            return f"{self.kind.label} is no longer controlled, was {self.was}"
        moved = self.aim_moved
        width = self.width_changed
        parts: list[str] = []
        if moved is not None and moved != 0:
            parts.append(f"aim moved {moved:+}")
        if width is not None and width != 0:
            parts.append(f"width {width:+}")
        if not parts:
            parts.append("limits changed")
        return f"{self.kind.label}: {', '.join(parts)}"


@dataclass(frozen=True)
class Revision:
    """Everything one sheet changed against another."""

    was: str
    now: str
    changes: tuple[Change, ...]

    @property
    def is_empty(self) -> bool:
        return not self.changes

    @property
    def material(self) -> tuple[Change, ...]:
        return tuple(c for c in self.changes if c.is_material)

    @property
    def added(self) -> tuple[Change, ...]:
        return tuple(c for c in self.changes if c.is_added)

    @property
    def dropped(self) -> tuple[Change, ...]:
        return tuple(c for c in self.changes if c.is_dropped)

    def change_for(self, kind: PropertyKind) -> Change | None:
        for change in self.changes:
            if change.kind is kind:
                return change
        return None

    def render(self) -> list[str]:
        """The revision as lines, material changes first."""
        if self.is_empty:
            return [f"{self.now} changes nothing against {self.was}"]
        lines = [f"{self.now} against {self.was}"]
        for change in self.material:
            lines.append(f"  MATERIAL  {change}")
        for change in self.changes:
            if change.is_material:
                continue
            lines.append(f"            {change}")
        return lines

    def __str__(self) -> str:
        return "\n".join(self.render())


def compare(was: SpecSheet, now: SpecSheet) -> Revision:
    """Diff two published sheets, property by property."""
    if not isinstance(was, SpecSheet) or not isinstance(now, SpecSheet):
        raise BadInputError("two spec sheets are expected")
    touched = sorted(was.covers | now.covers, key=lambda k: k.name)
    changes: list[Change] = []
    for kind in touched:
        before = was.bands.get(kind)
        after = now.bands.get(kind)
        if before == after:
            continue
        changes.append(Change(kind=kind, was=before, now=after))
    return Revision(was=was.name, now=now.name, changes=tuple(changes))


__all__ = ["Change", "Revision", "compare"]
