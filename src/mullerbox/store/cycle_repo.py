"""Reading and writing what the muller actually did.

These rows come off the machine's log rather than out of a plan, so the
repository does as little as possible to them. It refuses a duplicate batch
number and it decodes the types, and that is all: a cycle with a five second wet
mull is written exactly as recorded, because the whole reason for keeping them
is to count the ones the plan would have refused.

The discharged flag is stored as an integer because sqlite has no boolean and
storing "yes"/"no" invites a third value. Zero and one, decoded on the way back.
"""

from __future__ import annotations

from datetime import date

from mullerbox.errors import BadInputError, DuplicateError, NotFoundError
from mullerbox.muller.history import History, RecordedCycle
from mullerbox.store.connection import Book
from mullerbox.units.bulk import Pounds
from mullerbox.units.duration import Seconds


def cycle_exists(book: Book, batch_id: str) -> bool:
    return (
        book.one("SELECT batch_id FROM recorded_cycle WHERE batch_id = ?", (batch_id,)) is not None
    )


def record_cycle(book: Book, cycle: RecordedCycle, run_on: date) -> None:
    """Write one cycle as the machine reported it."""
    if not isinstance(cycle, RecordedCycle):
        raise BadInputError("a recorded cycle is expected")
    if not isinstance(run_on, date):
        raise BadInputError("a cycle is dated")
    if cycle_exists(book, cycle.batch_id):
        raise DuplicateError("recorded cycle", cycle.batch_id)
    with book.write():
        book.execute(
            "INSERT INTO recorded_cycle (batch_id, run_on, dry_mull_s, wet_mull_s,"
            " bentonite_lb, water_lb, discharged) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                cycle.batch_id,
                run_on.isoformat(),
                cycle.dry_mull.value,
                cycle.wet_mull.value,
                str(cycle.bentonite.value),
                str(cycle.water.value),
                1 if cycle.discharged else 0,
            ),
        )


def load_cycle(book: Book, batch_id: str) -> RecordedCycle:
    """Rebuild one recorded cycle."""
    row = book.one(
        "SELECT batch_id, dry_mull_s, wet_mull_s, bentonite_lb, water_lb,"
        " discharged FROM recorded_cycle WHERE batch_id = ?",
        (batch_id,),
    )
    if row is None:
        raise NotFoundError("recorded cycle", batch_id)
    return _from_row(row)


def history_on(book: Book, run_on: date) -> History:
    """Every cycle recorded on one day, in batch order."""
    if not isinstance(run_on, date):
        raise BadInputError("a date is expected")
    rows = book.all(
        "SELECT batch_id, dry_mull_s, wet_mull_s, bentonite_lb, water_lb,"
        " discharged FROM recorded_cycle WHERE run_on = ? ORDER BY batch_id",
        (run_on.isoformat(),),
    )
    return History(cycles=tuple(_from_row(row) for row in rows))


def history_between(book: Book, start: date, end: date) -> History:
    """Every cycle over a span, which is where the machine's wear shows."""
    if not isinstance(start, date) or not isinstance(end, date):
        raise BadInputError("two dates are expected")
    if end < start:
        raise BadInputError(f"the span runs from {start} to {end}, which is backwards")
    rows = book.all(
        "SELECT batch_id, dry_mull_s, wet_mull_s, bentonite_lb, water_lb,"
        " discharged FROM recorded_cycle WHERE run_on BETWEEN ? AND ?"
        " ORDER BY run_on, batch_id",
        (start.isoformat(), end.isoformat()),
    )
    return History(cycles=tuple(_from_row(row) for row in rows))


def _from_row(row: object) -> RecordedCycle:
    mapping = row
    return RecordedCycle(
        batch_id=str(mapping["batch_id"]),  # type: ignore[index]
        dry_mull=Seconds(int(mapping["dry_mull_s"])),  # type: ignore[index]
        wet_mull=Seconds(int(mapping["wet_mull_s"])),  # type: ignore[index]
        bentonite=Pounds(str(mapping["bentonite_lb"])),  # type: ignore[index]
        water=Pounds(str(mapping["water_lb"])),  # type: ignore[index]
        discharged=bool(int(mapping["discharged"])),  # type: ignore[index]
    )


__all__ = [
    "cycle_exists",
    "history_between",
    "history_on",
    "load_cycle",
    "record_cycle",
]
