"""Whether the testing programme covers the work the shop actually runs.

A programme is a set of intervals. What it does not say, and what nobody checks,
is whether it covers the properties the pattern classes on the floor are judged
by. Those two lists drift apart quietly: a class gets added, a property gets
controlled, and the programme is never revisited, so a property that decides
whether castings scrap is never scheduled to be tested at all.

The gap has two halves and they are different problems.

**Controlled and not on the programme.** The band exists, the shift report will
judge against it, and nothing ensures there is ever a reading. The report shows
a dash and looks tidy.

**On the programme and controlled by nothing.** The lab is spending bench time
on a property no class is judged by. Not wrong, and worth knowing, because bench
time is the constraint in every sand lab.
"""

from __future__ import annotations

from dataclasses import dataclass

from mullerbox.errors import BadInputError
from mullerbox.programme.schedule import Schedule
from mullerbox.props.kind import PropertyKind
from mullerbox.spec.pattern import PatternClass
from mullerbox.spec.sheet import SpecSheet


@dataclass(frozen=True)
class Coverage:
    """The programme against the work, both gaps named."""

    classes: frozenset[PatternClass]
    controlled: frozenset[PropertyKind]
    scheduled: frozenset[PropertyKind]
    published: frozenset[PropertyKind]

    @property
    def unscheduled(self) -> tuple[PropertyKind, ...]:
        """Controlled by some class, and never scheduled to be tested."""
        return tuple(sorted(self.controlled - self.scheduled, key=lambda k: k.name))

    @property
    def unused(self) -> tuple[PropertyKind, ...]:
        """Scheduled, and no class in the shop is judged by it."""
        return tuple(sorted(self.scheduled - self.controlled, key=lambda k: k.name))

    @property
    def unbanded(self) -> tuple[PropertyKind, ...]:
        """Controlled by a class and not published on the sheet."""
        return tuple(sorted(self.controlled - self.published, key=lambda k: k.name))

    @property
    def is_complete(self) -> bool:
        return not self.unscheduled and not self.unbanded

    def findings(self) -> list[str]:
        """The gaps, with the costly one first."""
        lines: list[str] = []
        if self.unbanded:
            named = ", ".join(k.label for k in self.unbanded)
            lines.append(
                f"controlled by a class and not on the spec sheet, so never judged at all: {named}"
            )
        if self.unscheduled:
            named = ", ".join(k.label for k in self.unscheduled)
            lines.append(
                f"judged against a band and never scheduled to be tested, so the "
                f"shift report shows a dash and looks tidy: {named}"
            )
        if self.unused:
            named = ", ".join(k.label for k in self.unused)
            lines.append(
                f"tested on the programme and no class is judged by it, which is "
                f"bench time in a lab where bench time is the constraint: {named}"
            )
        if not lines:
            lines.append(
                f"the programme covers every property the {len(self.classes)} "
                "classes on the floor are judged by"
            )
        return lines


def coverage_of(schedule: Schedule, sheet: SpecSheet, classes: list[PatternClass]) -> Coverage:
    """Compare the programme against the classes the shop actually runs.

    Takes the classes explicitly rather than assuming all of them, because a
    shop that never runs cored work should not be told it is missing friability
    coverage.
    """
    if not isinstance(schedule, Schedule):
        raise BadInputError("a schedule is expected")
    if not isinstance(sheet, SpecSheet):
        raise BadInputError("a spec sheet is expected")
    if not classes:
        raise BadInputError("no pattern classes to check against")
    for cls in classes:
        if not isinstance(cls, PatternClass):
            raise BadInputError("only pattern classes can be checked against")
    controlled: set[PropertyKind] = set()
    for cls in classes:
        controlled |= cls.controlled
    return Coverage(
        classes=frozenset(classes),
        controlled=frozenset(controlled),
        scheduled=schedule.covers,
        published=sheet.covers,
    )


__all__ = ["Coverage", "coverage_of"]
