"""The calibration report, which is really two reports about different risks.

**What falls due soon** is a planning problem. An instrument going out of
calibration next month needs a slot booking, and the report exists so somebody
books it.

**What has already lapsed** is not a planning problem, it is a data problem, and
it is worse than it looks. Every result taken on a lapsed instrument since the
lapse began has stopped counting, and nobody noticed at the time because the
instrument kept working perfectly. So the lapse section counts the results it
has invalidated rather than just naming the instrument, because "PERM-1 is out
of calibration" and "PERM-1 is out of calibration and forty readings since
August do not count" are different conversations.

The two sections are separated in the output and the lapse one comes first, for
the same reason the pending line comes before the totals on a scrap sheet.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from mullerbox.cal.instrument import Instrument
from mullerbox.errors import BadInputError
from mullerbox.props.result import Result
from mullerbox.report.layout import Column, Table, heading

# Anything falling due inside this window is on the planning list.
NOTICE_DAYS = 45


@dataclass(frozen=True)
class Lapse:
    """An instrument with no calibration covering a date, and what it cost."""

    instrument: Instrument
    invalidated: tuple[Result, ...]

    @property
    def count(self) -> int:
        return len(self.invalidated)

    @property
    def earliest(self) -> date | None:
        if not self.invalidated:
            return None
        return min(r.tested_on for r in self.invalidated)


@dataclass(frozen=True)
class Falling:
    """An instrument still good but not for much longer."""

    instrument: Instrument
    due_on: date
    days_left: int


@dataclass(frozen=True)
class CalibrationReport:
    """What has lapsed and what is about to."""

    as_of: date
    lapsed: tuple[Lapse, ...]
    falling_due: tuple[Falling, ...]

    @property
    def is_clean(self) -> bool:
        return not self.lapsed and not self.falling_due

    @property
    def results_invalidated(self) -> int:
        return sum(lapse.count for lapse in self.lapsed)

    def render(self) -> list[str]:
        lines = heading(f"calibration as at {self.as_of}")
        if self.lapsed:
            lines.append("LAPSED - readings taken on these do not count")
            table = Table(
                columns=(
                    Column("instrument"),
                    Column("kind"),
                    Column.number("readings lost"),
                    Column("earliest"),
                )
            )
            for lapse in self.lapsed:
                table.add(
                    lapse.instrument.tag,
                    lapse.instrument.kind.label,
                    str(lapse.count),
                    str(lapse.earliest) if lapse.earliest else "",
                )
            lines.extend(table.render())
            lines.append("")
        if self.falling_due:
            lines.append(f"falling due inside {NOTICE_DAYS} days")
            table = Table(
                columns=(
                    Column("instrument"),
                    Column("kind"),
                    Column("due"),
                    Column.number("days left"),
                )
            )
            for falling in self.falling_due:
                table.add(
                    falling.instrument.tag,
                    falling.instrument.kind.label,
                    str(falling.due_on),
                    str(falling.days_left),
                )
            lines.extend(table.render())
        if self.is_clean:
            lines.append("every instrument is in calibration with room to spare")
        return lines

    def __str__(self) -> str:
        return "\n".join(self.render())


def calibration_report(
    instruments: dict[str, Instrument], results: list[Result], as_of: date
) -> CalibrationReport:
    """Build the report from the instruments on the book and every result taken.

    Results are attributed to the instrument they name. A result naming an
    instrument that is not on the book is not counted against any lapse: it has
    a different problem and belongs on the exceptions report, not this one.
    """
    if not isinstance(as_of, date):
        raise BadInputError("a date is expected")
    lapsed: list[Lapse] = []
    falling: list[Falling] = []
    for tag in sorted(instruments):
        instrument = instruments[tag]
        covering = instrument.window_covering(as_of)
        if covering is None:
            hit = tuple(
                r
                for r in results
                if r.instrument_tag == tag
                and r.kind.measured_by is instrument.kind
                and r.tested_on <= as_of
                and not instrument.was_calibrated_on(r.tested_on)
            )
            lapsed.append(Lapse(instrument=instrument, invalidated=hit))
            continue
        left = covering.days_left_on(as_of)
        if left <= NOTICE_DAYS:
            falling.append(Falling(instrument=instrument, due_on=covering.due_on, days_left=left))
    lapsed.sort(key=lambda x: (-x.count, x.instrument.tag))
    falling.sort(key=lambda x: (x.days_left, x.instrument.tag))
    return CalibrationReport(as_of=as_of, lapsed=tuple(lapsed), falling_due=tuple(falling))


__all__ = [
    "CalibrationReport",
    "Falling",
    "Lapse",
    "NOTICE_DAYS",
    "calibration_report",
]
