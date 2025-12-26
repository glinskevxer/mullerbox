"""Reading and writing the testing programme, with a trail of why it moved.

The schedule is a small table and the change log beside it is the point. An
interval that moved is a decision the lab made about how much it trusts a
property, and six months later "why is loss on ignition only tested quarterly"
is a question somebody will ask. Without the trail the answer is a shrug, and
the usual response to a shrug is to put it back on the short interval, which
throws away whatever the relaxation earned.

So every change records what it was, what it became, when, and the reason. The
reason is required. A change with no reason is exactly the change nobody can
defend later.
"""

from __future__ import annotations

from datetime import date

from mullerbox.errors import BadInputError, NotFoundError
from mullerbox.programme.schedule import Frequency, Schedule
from mullerbox.props.kind import PropertyKind
from mullerbox.store.coding import decode
from mullerbox.store.connection import Book


def set_interval(
    book: Book,
    kind: PropertyKind,
    frequency: Frequency,
    when: date,
    because: str,
) -> None:
    """Set or move one property's interval, logging the change if it moved."""
    if not isinstance(kind, PropertyKind):
        raise BadInputError("a property kind is expected")
    if not isinstance(frequency, Frequency):
        raise BadInputError("a frequency is expected")
    if not isinstance(when, date):
        raise BadInputError("a date is expected")
    if not because.strip():
        raise BadInputError("a change to the programme records why it was made")
    row = book.one("SELECT frequency FROM test_interval WHERE property = ?", (kind.name,))
    with book.write():
        if row is None:
            book.execute(
                "INSERT INTO test_interval (property, frequency, set_on, because)"
                " VALUES (?, ?, ?, ?)",
                (kind.name, frequency.name, when.isoformat(), because),
            )
            return
        was = str(row["frequency"])
        if was == frequency.name:
            return
        book.execute(
            "UPDATE test_interval SET frequency = ?, set_on = ?, because = ? WHERE property = ?",
            (frequency.name, when.isoformat(), because, kind.name),
        )
        book.execute(
            "INSERT OR REPLACE INTO interval_change"
            " (property, changed_on, was, became, because) VALUES (?, ?, ?, ?, ?)",
            (kind.name, when.isoformat(), was, frequency.name, because),
        )


def load_schedule(book: Book) -> Schedule:
    """Rebuild the whole programme, refusing an empty one."""
    rows = book.all("SELECT property, frequency FROM test_interval ORDER BY property")
    if not rows:
        raise NotFoundError("testing programme", "any property")
    intervals: dict[PropertyKind, Frequency] = {}
    for row in rows:
        kind = decode(str(row["property"]), PropertyKind, "a property")
        intervals[kind] = decode(str(row["frequency"]), Frequency, "a testing frequency")
    return Schedule(intervals=intervals)


def changes(book: Book, kind: PropertyKind) -> list[tuple[date, str, str, str]]:
    """Every interval change for one property, oldest first."""
    if not isinstance(kind, PropertyKind):
        raise BadInputError("a property kind is expected")
    rows = book.all(
        "SELECT changed_on, was, became, because FROM interval_change"
        " WHERE property = ? ORDER BY changed_on",
        (kind.name,),
    )
    return [
        (
            date.fromisoformat(str(r["changed_on"])),
            str(r["was"]),
            str(r["became"]),
            str(r["because"]),
        )
        for r in rows
    ]


def last_tested(book: Book) -> dict[PropertyKind, date]:
    """When each property was last tested, from the results on the book."""
    rows = book.all("SELECT property, max(tested_on) AS last FROM result GROUP BY property")
    found: dict[PropertyKind, date] = {}
    for row in rows:
        name = str(row["property"])
        if name not in PropertyKind.__members__:
            continue
        found[PropertyKind[name]] = date.fromisoformat(str(row["last"]))
    return found


def is_on_programme(book: Book, kind: PropertyKind) -> bool:
    if not isinstance(kind, PropertyKind):
        raise BadInputError("a property kind is expected")
    return (
        book.one("SELECT property FROM test_interval WHERE property = ?", (kind.name,)) is not None
    )


__all__ = [
    "changes",
    "is_on_programme",
    "last_tested",
    "load_schedule",
    "set_interval",
]
