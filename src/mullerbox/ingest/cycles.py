"""Reading the muller controller's own log.

This file comes off a machine rather than off a person, which changes what the
reader has to tolerate. Controllers write what they have: a column that is blank
because that batch took no water, a discharge flag spelled differently by two
firmware versions, and a run of rows for one shift with no header repeat.

**A blank mass is zero, not an error.** On a hand written sheet a blank is a
technician who did not fill it in and is worth flagging. On a controller export
it is the machine saying nothing was charged, which is a fact, and refusing the
row would throw away the cycles that took no bentonite.

**A blank discharge flag is not assumed.** That is the one field where absence
is ambiguous: it means either "not discharged" or "this firmware does not report
it", and guessing turns a missing feature into a count of abandoned batches. So
a blank there is a problem row, and it is read through ``optional`` rather than
``text`` so the refusal can say *why* the blank cannot be filled in, rather than
the generic "this column is empty" that every other blank field gets.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from mullerbox.errors import BadInputError
from mullerbox.ingest.reader import Problem, Row, Sheet, collect
from mullerbox.muller.history import History, RecordedCycle
from mullerbox.units.bulk import Pounds
from mullerbox.units.duration import Seconds

COLUMNS = ("batch", "run", "dry", "wet", "discharged")

_YES = {"yes", "y", "1", "true", "t", "discharged"}
_NO = {"no", "n", "0", "false", "f", "held", "left"}


def _read_date(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise BadInputError(f"{text!r} is not a date in yyyy-mm-dd form") from None


def _read_flag(text: str) -> bool:
    key = text.strip().lower()
    if not key:
        raise BadInputError(
            "the discharge flag is blank, which could mean not discharged or "
            "could mean this controller does not report it"
        )
    if key in _YES:
        return True
    if key in _NO:
        return False
    raise BadInputError(f"{text!r} is not a discharge flag")


def _read_mass(row: Row, column: str) -> Pounds:
    """A blank mass on a controller export is zero, not a missing value."""
    return Pounds(row.optional(column, "0"))


@dataclass(frozen=True)
class LoggedCycle:
    """One cycle off the log, with the day it ran."""

    cycle: RecordedCycle
    run_on: date


def logged_from(row: Row) -> LoggedCycle:
    """Build one cycle from one log row."""
    return LoggedCycle(
        cycle=RecordedCycle(
            batch_id=row.text("batch"),
            dry_mull=Seconds(row.text("dry")),
            wet_mull=Seconds(row.text("wet")),
            bentonite=_read_mass(row, "bentonite"),
            water=_read_mass(row, "water"),
            discharged=_read_flag(row.optional("discharged")),
        ),
        run_on=_read_date(row.text("run")),
    )


@dataclass(frozen=True)
class CycleLoad:
    """What came off the controller, and what would not read."""

    cycles: tuple[LoggedCycle, ...]
    problems: tuple[Problem, ...]

    @property
    def is_clean(self) -> bool:
        return not self.problems

    @property
    def days(self) -> tuple[date, ...]:
        return tuple(sorted({c.run_on for c in self.cycles}))

    def on(self, when: date) -> History:
        """The day's cycles as a history, ready to be read for findings."""
        if not isinstance(when, date):
            raise BadInputError("a date is expected")
        return History(cycles=tuple(c.cycle for c in self.cycles if c.run_on == when))

    @property
    def history(self) -> History:
        """Everything loaded, as one history."""
        return History(cycles=tuple(c.cycle for c in self.cycles))

    def __str__(self) -> str:
        return (
            f"{len(self.cycles)} cycles over {len(self.days)} days, {len(self.problems)} problems"
        )


def load_cycles(sheet: Sheet) -> CycleLoad:
    """Read a controller export, keeping the rows that would not parse."""
    if not isinstance(sheet, Sheet):
        raise BadInputError("a parsed sheet is expected")
    sheet.require_columns(*COLUMNS)
    built, problems = collect(sheet, logged_from)
    return CycleLoad(
        cycles=tuple(c for c in built if isinstance(c, LoggedCycle)),
        problems=tuple(problems),
    )


__all__ = ["COLUMNS", "CycleLoad", "LoggedCycle", "load_cycles", "logged_from"]
