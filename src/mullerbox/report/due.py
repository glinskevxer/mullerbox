"""Everything the shop owes, on one sheet, ranked by what it costs to be late.

Three things fall due independently and each has its own report: calibrations,
scheduled tests, and sieve wear checks. A shop reading three sheets reads them
on three different days, so the one that matters is the one nobody opened.

Ranking them together needs a common scale, and days overdue is the wrong one.
A calibration a day past due has already stopped every reading off that
instrument counting; a test a week past due has cost nothing yet. So the rank is
by consequence rather than by lateness, and lateness only breaks ties inside a
consequence.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from enum import Enum

from mullerbox.cal.instrument import Instrument
from mullerbox.errors import BadInputError
from mullerbox.programme.schedule import Due, Schedule
from mullerbox.props.kind import PropertyKind
from mullerbox.report.layout import Column, Table, heading
from mullerbox.screens.series import ScreenSeries
from mullerbox.screens.wear import Check
from mullerbox.units.mesh import Mesh


class Consequence(Enum):
    """What being late on this actually costs."""

    READINGS_VOID = "readings are not counting"
    READINGS_SUSPECT = "readings may be wrong and nothing shows it"
    NOTHING_YET = "nothing yet"

    @property
    def label(self) -> str:
        return self.value

    @property
    def rank(self) -> int:
        return _RANK[self]


_RANK: dict[Consequence, int] = {
    Consequence.READINGS_VOID: 0,
    Consequence.READINGS_SUSPECT: 1,
    Consequence.NOTHING_YET: 2,
}


@dataclass(frozen=True)
class Item:
    """One thing that is due or overdue."""

    what: str
    detail: str
    days_over: int
    consequence: Consequence

    def __str__(self) -> str:
        when = "never done" if self.days_over >= 10**5 else f"{self.days_over} days over"
        return f"{self.what}: {self.detail}, {when}"


@dataclass(frozen=True)
class DueSheet:
    """Everything owed, worst consequence first."""

    as_of: date
    items: tuple[Item, ...]

    @property
    def is_clear(self) -> bool:
        return not self.items

    @property
    def costing_now(self) -> tuple[Item, ...]:
        return tuple(item for item in self.items if item.consequence is not Consequence.NOTHING_YET)

    def render(self) -> list[str]:
        """The sheet as lines, worst consequence first."""
        lines = heading(f"what is due as at {self.as_of}")
        if self.is_clear:
            lines.append("nothing is due")
            return lines
        table = Table(
            columns=(
                Column("what"),
                Column("detail"),
                Column.number("days over"),
                Column("consequence"),
            )
        )
        for item in self.items:
            table.add(
                item.what,
                item.detail,
                "never" if item.days_over >= 10**5 else str(item.days_over),
                item.consequence.label,
            )
        lines.extend(table.render())
        lines.append("")
        costing = len(self.costing_now)
        lines.append(f"{len(self.items)} due, {costing} of them costing something now")
        return lines

    def __str__(self) -> str:
        return "\n".join(self.render())


def due_sheet(
    as_of: date,
    instruments: dict[str, Instrument],
    schedule: Schedule | None,
    last_tested: Mapping[PropertyKind, date],
    series: ScreenSeries | None = None,
    wear_checks: dict[Mesh, Check] | None = None,
) -> DueSheet:
    """Gather everything owed and rank it by what being late costs.

    Each source is optional, because a shop that has not set up a testing
    programme still wants its calibrations listed. A missing source contributes
    nothing rather than an error.
    """
    if not isinstance(as_of, date):
        raise BadInputError("a date is expected")
    items: list[Item] = []
    for tag in sorted(instruments):
        instrument = instruments[tag]
        covering = instrument.window_covering(as_of)
        if covering is None:
            latest = instrument.latest
            over = (as_of - latest.due_on).days if latest else 10**5
            items.append(
                Item(
                    what="calibration",
                    detail=f"{tag} ({instrument.kind.label})",
                    days_over=max(over, 0),
                    consequence=Consequence.READINGS_VOID,
                )
            )
    if schedule is not None:
        for entry in schedule.due_on(as_of, last_tested):
            items.append(_from_test(entry))
    if series is not None:
        for step in series.working_steps:
            found = (wear_checks or {}).get(step.mesh)
            if found is None:
                items.append(
                    Item(
                        what="sieve wear",
                        detail=f"screen {step.label} has never been measured",
                        days_over=10**5,
                        consequence=Consequence.READINGS_SUSPECT,
                    )
                )
            elif found.is_worn or found.is_wrong_screen:
                items.append(
                    Item(
                        what="sieve wear",
                        detail=f"screen {step.label} is {found.drift:+.1%} off nominal",
                        days_over=(as_of - found.checked_on).days,
                        consequence=Consequence.READINGS_SUSPECT,
                    )
                )
    items.sort(key=lambda i: (i.consequence.rank, -i.days_over, i.what, i.detail))
    return DueSheet(as_of=as_of, items=tuple(items))


def _from_test(entry: Due) -> Item:
    return Item(
        what="test",
        detail=f"{entry.kind.label} ({entry.frequency.label})",
        days_over=entry.days_over,
        consequence=Consequence.NOTHING_YET,
    )


__all__ = ["Consequence", "DueSheet", "Item", "due_sheet"]
