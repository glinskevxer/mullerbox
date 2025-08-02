"""Gathering the readings that count, as at a date.

This is the query the reports are built on and it is the one place where the
three ideas the package keeps apart finally meet: a result is a fact, a
calibration history decides whether it counts, and a date decides which history
applies.

The gather runs per property and takes the most recent countable reading on or
before the cutoff. That means a property whose only recent test was run during a
calibration lapse falls back to an older reading rather than disappearing, and
the report is built on stale-but-valid rather than fresh-but-void. Which of
those is worse is a judgement, and the shop's judgement is that a number nobody
can stand behind is worse than an old one, because the old one can at least be
argued with.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from mullerbox.errors import BadInputError
from mullerbox.props.kind import PropertyKind, Reading
from mullerbox.props.result import Result, latest_countable
from mullerbox.store import instrument_repo
from mullerbox.store.connection import Book


@dataclass(frozen=True)
class Gathered:
    """The readings in force at a date, and how old each one is."""

    as_of: date
    results: dict[PropertyKind, Result]

    @property
    def readings(self) -> dict[PropertyKind, Reading]:
        """The plain mapping the reports and the attribution want."""
        return {kind: result.reading for kind, result in self.results.items()}

    def age_of(self, kind: PropertyKind) -> int:
        """How many days old the reading in force is."""
        if kind not in self.results:
            raise BadInputError(f"there is no {kind.label} reading in force")
        return (self.as_of - self.results[kind].tested_on).days

    @property
    def stale(self) -> tuple[PropertyKind, ...]:
        """Anything older than a week, which is a shift's worth of drift."""
        return tuple(
            kind for kind in sorted(self.results, key=lambda k: k.name) if self.age_of(kind) > 7
        )

    def __len__(self) -> int:
        return len(self.results)


def gather(book: Book, as_of: date) -> Gathered:
    """Every property's most recent countable reading, as at a date."""
    if not isinstance(as_of, date):
        raise BadInputError("a date is expected")
    instruments = instrument_repo.load_all(book)
    found: dict[PropertyKind, Result] = {}
    for kind in PropertyKind:
        rows = book.all(
            "SELECT sample_id, property, reading, scale, instrument_tag, tested_on"
            " FROM result WHERE property = ? AND tested_on <= ?"
            " ORDER BY tested_on, sample_id",
            (kind.name, as_of.isoformat()),
        )
        if not rows:
            continue
        from mullerbox.store.result_repo import _result_from

        candidates = [_result_from(row, str(row["sample_id"])) for row in rows]
        latest = latest_countable(candidates, instruments, kind, as_of)
        if latest is not None:
            found[kind] = latest
    return Gathered(as_of=as_of, results=found)


def uncounted(book: Book, as_of: date) -> list[Result]:
    """Results on or before a date that do not count, for the exception report."""
    if not isinstance(as_of, date):
        raise BadInputError("a date is expected")
    instruments = instrument_repo.load_all(book)
    from mullerbox.store.result_repo import _result_from

    rows = book.all(
        "SELECT sample_id, property, reading, scale, instrument_tag, tested_on"
        " FROM result WHERE tested_on <= ? ORDER BY tested_on, sample_id, property",
        (as_of.isoformat(),),
    )
    found: list[Result] = []
    for row in rows:
        result = _result_from(row, str(row["sample_id"]))
        instrument = instruments.get(result.instrument_tag)
        if instrument is None:
            found.append(result)
            continue
        if instrument.kind is not result.kind.measured_by:
            found.append(result)
            continue
        if not result.counts_for(instrument):
            found.append(result)
    return found


__all__ = ["Gathered", "gather", "uncounted"]
