"""Reading and writing sieve wear checks.

A wear check is kept per screen per date rather than per stack, because that is
how they actually happen: somebody measures three screens this month and the
other eight next month, and a schema that demanded a whole stack at once would
push the lab into recording a stack it did not measure.

What that costs is that "was this stack fit on that day" becomes a query rather
than a row, and the query has to decide what to do about a screen last measured
six months ago. It takes the most recent check on or before the date and lets
the caller see how old it is, which is the same shape as everything else in this
package that deals in things measured at a moment.
"""

from __future__ import annotations

from datetime import date

from mullerbox.errors import BadInputError, DuplicateError, NotFoundError
from mullerbox.screens.series import ScreenSeries
from mullerbox.screens.wear import Check, StackCheck
from mullerbox.store.connection import Book
from mullerbox.units.mesh import Mesh


def record_check(book: Book, series_name: str, check: Check) -> None:
    """Write one screen's measurement."""
    if not isinstance(check, Check):
        raise BadInputError("a wear check is expected")
    known = book.one("SELECT name FROM screen_series WHERE name = ?", (series_name,))
    if known is None:
        raise NotFoundError("screen series", series_name)
    existing = book.one(
        "SELECT measured_um FROM wear_check"
        " WHERE series_name = ? AND mesh_number = ? AND checked_on = ?",
        (series_name, check.mesh.number, check.checked_on.isoformat()),
    )
    if existing is not None:
        raise DuplicateError(
            f"wear check on screen {check.mesh.label}", check.checked_on.isoformat()
        )
    with book.write():
        book.execute(
            "INSERT INTO wear_check"
            " (series_name, mesh_number, checked_on, measured_um)"
            " VALUES (?, ?, ?, ?)",
            (
                series_name,
                check.mesh.number,
                check.checked_on.isoformat(),
                check.measured_micrometres,
            ),
        )


def latest_checks(book: Book, series: ScreenSeries, as_of: date) -> dict[Mesh, Check]:
    """The most recent check for each screen on or before a date."""
    if not isinstance(series, ScreenSeries):
        raise BadInputError("a screen series is expected")
    if not isinstance(as_of, date):
        raise BadInputError("a date is expected")
    found: dict[Mesh, Check] = {}
    for step in series.working_steps:
        row = book.one(
            "SELECT checked_on, measured_um FROM wear_check"
            " WHERE series_name = ? AND mesh_number = ? AND checked_on <= ?"
            " ORDER BY checked_on DESC LIMIT 1",
            (series.name, step.mesh.number, as_of.isoformat()),
        )
        if row is None:
            continue
        found[step.mesh] = Check(
            mesh=step.mesh,
            measured_micrometres=int(row["measured_um"]),
            checked_on=date.fromisoformat(str(row["checked_on"])),
        )
    return found


def stack_as_of(book: Book, series: ScreenSeries, as_of: date) -> StackCheck:
    """Assemble the stack's state on a date from whatever has been measured."""
    checks = latest_checks(book, series, as_of)
    return StackCheck(
        series=series,
        checks=tuple(checks[mesh] for mesh in sorted(checks)),
        checked_on=as_of,
    )


def oldest_check(book: Book, series: ScreenSeries, as_of: date) -> tuple[Mesh, date] | None:
    """The screen whose measurement is the most out of date, if any."""
    checks = latest_checks(book, series, as_of)
    if not checks:
        return None
    mesh = min(checks, key=lambda m: (checks[m].checked_on, m.micrometres))
    return mesh, checks[mesh].checked_on


def history(book: Book, series_name: str, mesh: Mesh) -> list[tuple[date, int]]:
    """Every measurement of one screen, oldest first, to see the wear rate."""
    if not isinstance(mesh, Mesh):
        raise BadInputError("a screen is expected")
    rows = book.all(
        "SELECT checked_on, measured_um FROM wear_check"
        " WHERE series_name = ? AND mesh_number = ? ORDER BY checked_on",
        (series_name, mesh.number),
    )
    return [(date.fromisoformat(str(r["checked_on"])), int(r["measured_um"])) for r in rows]


__all__ = ["history", "latest_checks", "oldest_check", "record_check", "stack_as_of"]
