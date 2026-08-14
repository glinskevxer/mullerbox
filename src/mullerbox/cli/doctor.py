"""One command that walks the whole book and says what is wrong with it.

Every other command answers a question. This one asks them, in the order a
person would if they had an hour and knew where to look, and prints only what it
found. On a healthy book it prints one line.

The findings are ranked, and the ranking is the useful part. A calibration lapse
is above an unpriced material because the lapse is silently invalidating
readings right now while the missing price only bites the next time somebody
costs a shift. A book with twelve findings is not twelve equal problems and a
flat list would read like it is.

Nothing here changes anything. A doctor that fixed what it found would be a
doctor nobody could run on a book they were unsure about.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

import click

from mullerbox.addition.material import Material
from mullerbox.cli.context import Context, handle, pass_context
from mullerbox.cli.main import main
from mullerbox.cli.parsing import date_or_today
from mullerbox.errors import NotFoundError, SandError
from mullerbox.props.kind import PropertyKind
from mullerbox.report.calibration import calibration_report
from mullerbox.report.layout import Column, Table
from mullerbox.store import (
    instrument_repo,
    inventory_repo,
    price_repo,
    programme_repo,
    reading_repo,
    result_repo,
    series_repo,
    spec_repo,
)
from mullerbox.store.connection import Book
from mullerbox.store.migrations import MIGRATIONS, current_version
from mullerbox.system.state import INVENTORY_STALE_DAYS


class Severity(Enum):
    """How much a finding is costing right now."""

    COSTING_NOW = "costing now"
    WILL_BITE = "will bite"
    WORTH_KNOWING = "worth knowing"

    @property
    def rank(self) -> int:
        return _RANK[self]

    @property
    def label(self) -> str:
        return self.value


_RANK: dict[Severity, int] = {
    Severity.COSTING_NOW: 0,
    Severity.WILL_BITE: 1,
    Severity.WORTH_KNOWING: 2,
}


@dataclass(frozen=True)
class Finding:
    """One thing wrong with the book."""

    severity: Severity
    area: str
    detail: str

    def __str__(self) -> str:
        return f"{self.severity.label}: {self.area} - {self.detail}"


def examine(book: Book, as_of: date) -> list[Finding]:
    """Walk the book and collect everything worth saying, worst first."""
    found: list[Finding] = []
    at = current_version(book)
    if at < len(MIGRATIONS):
        # Nothing else can be asked. A book behind the code is missing tables,
        # and every check below would raise an OperationalError rather than
        # producing a finding. One finding that names the fix is the whole
        # useful answer here.
        return [
            Finding(
                Severity.WILL_BITE,
                "schema",
                f"the book is at migration {at} of {len(MIGRATIONS)}, run init",
            )
        ]
    instruments = instrument_repo.load_all(book)
    if not instruments:
        found.append(Finding(Severity.WILL_BITE, "instruments", "none are on the book"))
    else:
        every_result: list[object] = []
        for kind in PropertyKind:
            every_result.extend(result_repo.results_of(book, kind))
        report = calibration_report(instruments, every_result, as_of)  # type: ignore[arg-type]
        for lapse in report.lapsed:
            detail = f"{lapse.instrument.tag} has no calibration covering {as_of}"
            if lapse.count:
                detail += f", invalidating {lapse.count} readings"
            found.append(
                Finding(
                    Severity.COSTING_NOW if lapse.count else Severity.WILL_BITE,
                    "calibration",
                    detail,
                )
            )
        for falling in report.falling_due:
            found.append(
                Finding(
                    Severity.WILL_BITE,
                    "calibration",
                    f"{falling.instrument.tag} falls due in {falling.days_left} days",
                )
            )
    uncounted = reading_repo.uncounted(book, as_of)
    if uncounted:
        found.append(
            Finding(
                Severity.COSTING_NOW,
                "readings",
                f"{len(uncounted)} results on or before {as_of} do not count",
            )
        )
    if not series_repo.list_series(book):
        found.append(Finding(Severity.WILL_BITE, "screens", "no screen series is on the book"))
    try:
        spec_repo.current_sheet(book, as_of)
    except SandError:
        found.append(
            Finding(
                Severity.COSTING_NOW,
                "spec",
                f"no spec sheet was published on or before {as_of}",
            )
        )
    priced = set(price_repo.priced_materials(book, as_of))
    missing = [m for m in Material if m not in priced]
    if missing:
        found.append(
            Finding(
                Severity.WORTH_KNOWING,
                "prices",
                f"no price for {', '.join(m.label for m in missing)}",
            )
        )
    try:
        schedule = programme_repo.load_schedule(book)
    except NotFoundError:
        found.append(
            Finding(
                Severity.WORTH_KNOWING,
                "programme",
                "no property is on the testing programme",
            )
        )
    else:
        overdue = schedule.due_on(as_of, programme_repo.last_tested(book))
        if overdue:
            found.append(
                Finding(
                    Severity.WILL_BITE,
                    "programme",
                    f"{len(overdue)} tests are due, worst is {overdue[0].kind.label}",
                )
            )
    found.extend(_inventory_findings(book, as_of))
    found.sort(key=lambda f: (f.severity.rank, f.area, f.detail))
    return found


def _inventory_findings(book: Book, as_of: date) -> list[Finding]:
    """What the inventory counts on the book say about the mass everything uses.

    The doctor has no system record to read, because a system is passed on the
    command line rather than kept. What it does have is the counts, and a system
    nobody has counted in six months is the finding whether or not the record
    says measured; every addition sized against that figure is wrong by the same
    proportion and no reading on the book will show it.
    """
    found: list[Finding] = []
    systems = inventory_repo.counted_systems(book)
    if not systems:
        return [
            Finding(
                Severity.WILL_BITE,
                "inventory",
                "no sand system has ever been inventoried",
            )
        ]
    for name in systems:
        latest = inventory_repo.latest_count(book, name, as_of)
        if latest is None:
            found.append(
                Finding(
                    Severity.WORTH_KNOWING,
                    "inventory",
                    f"{name} has no count on or before {as_of}",
                )
            )
            continue
        days = (as_of - latest.counted_on).days
        if days > INVENTORY_STALE_DAYS:
            found.append(
                Finding(
                    Severity.COSTING_NOW,
                    "inventory",
                    f"{name} was last counted {days} days ago, past the "
                    f"{INVENTORY_STALE_DAYS} day limit",
                )
            )
        if not latest.is_complete:
            missed = ", ".join(v.name for v in latest.uncounted_vessels)
            found.append(
                Finding(
                    Severity.WILL_BITE,
                    "inventory",
                    f"the latest count of {name} did not reach {missed}",
                )
            )
    return found


@main.command("doctor")
@click.option("--on", "as_of", default=None, help="As at a date, yyyy-mm-dd.")
@pass_context
@handle
def doctor(context: Context, as_of: str | None) -> None:
    """Walk the book and print what is wrong with it. Changes nothing."""
    when = date_or_today(as_of)
    with context.book(migrated=False) as book:
        found = examine(book, when)
    if not found:
        context.say(f"the book is sound as at {when}")
        return
    table = Table(columns=(Column("severity"), Column("area"), Column("finding")))
    for finding in found:
        table.add(finding.severity.label, finding.area, finding.detail)
    for line in table.render():
        context.say(line)
    context.say("")
    worst = found[0].severity
    context.say(f"{len(found)} findings, worst is {worst.label}")


__all__ = ["Finding", "Severity", "doctor", "examine"]
