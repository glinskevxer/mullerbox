"""How often each property is tested, and why that is not a fixed answer.

A sand lab cannot run every test every shift. Compactability and moisture are
quick and go on the hourly sheet; a methylene blue titration takes half an hour
and a loss on ignition needs a muffle furnace and an hour of cooling. So the
programme is a set of intervals, one per property, and the intervals are not all
the same.

The part worth stating is that the interval is **earned**. A property that has
been in control for a long run does not need testing as often as one that is
wandering, and a property that has just signalled needs testing more often until
it settles. That makes the schedule a function of the control chart, which is a
function of the readings, which are produced by the schedule. The loop is real
and it is the point: a stable system costs less to run, and a system that has
gone off pays for itself in extra testing until it comes back.

Two guards on that loop, both learned the hard way by shops that automated it.

**Nothing relaxes past the floor.** Compactability and moisture stay on the
hourly sheet however stable they look, because they are what the molding line
feels and because they are cheap. A programme that relaxed them into a weekly
test would save nothing and lose the only fast signal there is.

**Tightening is immediate and relaxing is slow.** One signal moves a property to
the shortest interval at once. Coming back out takes a full run of clean points,
because the alternative is a schedule that oscillates every time a chart blinks.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum

from mullerbox.analysis.control import ControlChart
from mullerbox.errors import BadInputError
from mullerbox.props.kind import PropertyKind


class Frequency(Enum):
    """How often a test comes round."""

    EVERY_SHIFT = "every shift"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"

    @property
    def label(self) -> str:
        return self.value

    @property
    def days(self) -> int:
        return _DAYS[self]

    @property
    def rank(self) -> int:
        """Position in the ladder, tightest first."""
        return _LADDER.index(self)

    def tighter(self) -> Frequency:
        """One step shorter, or itself at the tightest."""
        return _LADDER[max(self.rank - 1, 0)]

    def looser(self) -> Frequency:
        """One step longer, or itself at the loosest."""
        return _LADDER[min(self.rank + 1, len(_LADDER) - 1)]


_DAYS: dict[Frequency, int] = {
    Frequency.EVERY_SHIFT: 1,
    Frequency.DAILY: 1,
    Frequency.WEEKLY: 7,
    Frequency.MONTHLY: 30,
    Frequency.QUARTERLY: 91,
}

_LADDER: tuple[Frequency, ...] = (
    Frequency.EVERY_SHIFT,
    Frequency.DAILY,
    Frequency.WEEKLY,
    Frequency.MONTHLY,
    Frequency.QUARTERLY,
)

# Properties that never relax, whatever the chart says.
PINNED: frozenset[PropertyKind] = frozenset({PropertyKind.COMPACTABILITY, PropertyKind.MOISTURE})

# How many consecutive in-control readings buy one step of relaxation.
CLEAN_RUN_TO_RELAX = 20


@dataclass(frozen=True)
class Due:
    """One property that wants testing, and how overdue it is."""

    kind: PropertyKind
    frequency: Frequency
    last_tested: date | None
    days_over: int

    @property
    def never_tested(self) -> bool:
        return self.last_tested is None

    def __str__(self) -> str:
        if self.never_tested:
            return f"{self.kind.label}: never tested, wanted {self.frequency.label}"
        return f"{self.kind.label}: {self.days_over} days over its {self.frequency.label} interval"


@dataclass(frozen=True)
class Schedule:
    """One interval per property."""

    intervals: Mapping[PropertyKind, Frequency]

    def __post_init__(self) -> None:
        if not self.intervals:
            raise BadInputError("a schedule with no properties on it is not a schedule")
        for kind, frequency in self.intervals.items():
            if not isinstance(kind, PropertyKind):
                raise BadInputError("a schedule is keyed by property")
            if not isinstance(frequency, Frequency):
                raise BadInputError("a schedule holds frequencies")

    @property
    def covers(self) -> frozenset[PropertyKind]:
        return frozenset(self.intervals)

    def frequency_of(self, kind: PropertyKind) -> Frequency:
        if not isinstance(kind, PropertyKind):
            raise BadInputError("a property kind is expected")
        if kind not in self.intervals:
            raise BadInputError(f"{kind.label} is not on the programme")
        return self.intervals[kind]

    def due_on(self, as_of: date, last_tested: Mapping[PropertyKind, date]) -> tuple[Due, ...]:
        """Everything wanting a test, most overdue first.

        A property never tested is maximally overdue and sorts to the top, which
        is where a shop that has just started running a programme needs it.
        """
        if not isinstance(as_of, date):
            raise BadInputError("a date is expected")
        found: list[Due] = []
        for kind in sorted(self.intervals, key=lambda k: k.name):
            frequency = self.intervals[kind]
            when = last_tested.get(kind)
            if when is None:
                found.append(Due(kind=kind, frequency=frequency, last_tested=None, days_over=10**6))
                continue
            if when > as_of:
                raise BadInputError(f"{kind.label} was last tested {when}, which is after {as_of}")
            over = (as_of - when).days - frequency.days
            if over >= 0:
                found.append(
                    Due(
                        kind=kind,
                        frequency=frequency,
                        last_tested=when,
                        days_over=over,
                    )
                )
        found.sort(key=lambda d: (-d.days_over, d.kind.name))
        return tuple(found)

    def next_due(self, kind: PropertyKind, last_tested: date) -> date:
        if not isinstance(last_tested, date):
            raise BadInputError("a date is expected")
        return last_tested + timedelta(days=self.frequency_of(kind).days)

    def with_frequency(self, kind: PropertyKind, frequency: Frequency) -> Schedule:
        if not isinstance(frequency, Frequency):
            raise BadInputError("a frequency is expected")
        if not isinstance(kind, PropertyKind):
            raise BadInputError("a property kind is expected")
        return Schedule(intervals={**self.intervals, kind: frequency})


def adjusted(schedule: Schedule, kind: PropertyKind, chart: ControlChart) -> Schedule:
    """Move one property's interval according to what its chart is doing.

    Out of control tightens to the shortest interval in one step. In control
    relaxes by one step, and only once the run is long enough to mean anything.
    A pinned property never moves.
    """
    if not isinstance(schedule, Schedule):
        raise BadInputError("a schedule is expected")
    if not isinstance(chart, ControlChart):
        raise BadInputError("a control chart is expected")
    current = schedule.frequency_of(kind)
    if kind in PINNED:
        return schedule
    if not chart.in_control:
        return schedule.with_frequency(kind, _LADDER[0])
    if len(chart.values) < CLEAN_RUN_TO_RELAX:
        return schedule
    return schedule.with_frequency(kind, current.looser())


__all__ = ["CLEAN_RUN_TO_RELAX", "Due", "Frequency", "PINNED", "Schedule", "adjusted"]
