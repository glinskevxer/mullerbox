"""Reading and writing sand system inventory counts.

A count is two tables because a vessel with no measured density is still part of
the count. Flattening the vessels into the count row would force the writer to
either drop them or invent a density for them, and dropping them is exactly the
mistake `mullerbox.system.inventory` exists to prevent: an incomplete count that
comes back looking complete.

The density column is nullable and that is deliberate. Null here means "nobody
measured it", which is a different fact from zero, and the count reads it back
as the same hole it was written with.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from mullerbox.errors import BadInputError, DuplicateError, NotFoundError
from mullerbox.store.connection import Book
from mullerbox.system.inventory import Count, Vessel
from mullerbox.units.bulk import Pounds


def save_count(book: Book, count: Count) -> None:
    """Write one inventory, vessels and all."""
    if not isinstance(count, Count):
        raise BadInputError("an inventory count is expected")
    key = count.counted_on.isoformat()
    existing = book.one(
        "SELECT system_name FROM inventory_count WHERE system_name = ? AND counted_on = ?",
        (count.system_name, key),
    )
    if existing is not None:
        raise DuplicateError(f"inventory of {count.system_name}", key)
    with book.write():
        book.execute(
            "INSERT INTO inventory_count"
            " (system_name, counted_on, moulds, sand_per_mould)"
            " VALUES (?, ?, ?, ?)",
            (count.system_name, key, count.moulds_standing, str(count.sand_per_mould.value)),
        )
        for vessel in count.vessels:
            density = vessel.density_pounds_per_cubic_foot
            book.execute(
                "INSERT INTO inventory_vessel"
                " (system_name, counted_on, name, capacity_cf, filled, density)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    count.system_name,
                    key,
                    vessel.name,
                    str(vessel.capacity_cubic_feet),
                    str(vessel.filled_fraction),
                    None if density is None else str(density),
                ),
            )


def load_count(book: Book, system_name: str, counted_on: date) -> Count:
    """One inventory, or a refusal naming what was asked for."""
    if not isinstance(counted_on, date):
        raise BadInputError("an inventory is looked up by date")
    key = counted_on.isoformat()
    head = book.one(
        "SELECT moulds, sand_per_mould FROM inventory_count"
        " WHERE system_name = ? AND counted_on = ?",
        (system_name, key),
    )
    if head is None:
        raise NotFoundError(f"inventory of {system_name}", key)
    rows = book.all(
        "SELECT name, capacity_cf, filled, density FROM inventory_vessel"
        " WHERE system_name = ? AND counted_on = ? ORDER BY name",
        (system_name, key),
    )
    vessels = tuple(
        Vessel(
            name=str(row["name"]),
            capacity_cubic_feet=Decimal(str(row["capacity_cf"])),
            filled_fraction=Decimal(str(row["filled"])),
            density_pounds_per_cubic_foot=(
                None if row["density"] is None else Decimal(str(row["density"]))
            ),
        )
        for row in rows
    )
    return Count(
        system_name=system_name,
        counted_on=counted_on,
        vessels=vessels,
        moulds_standing=int(str(head["moulds"])),
        sand_per_mould=Pounds(str(head["sand_per_mould"])),
    )


def count_dates(book: Book, system_name: str) -> list[date]:
    """Every day this system was counted, oldest first."""
    rows = book.all(
        "SELECT counted_on FROM inventory_count WHERE system_name = ? ORDER BY counted_on",
        (system_name,),
    )
    return [date.fromisoformat(str(row["counted_on"])) for row in rows]


def latest_count(book: Book, system_name: str, as_of: date) -> Count | None:
    """The most recent inventory on or before a date, or nothing."""
    if not isinstance(as_of, date):
        raise BadInputError("an inventory is looked up by date")
    row = book.one(
        "SELECT counted_on FROM inventory_count"
        " WHERE system_name = ? AND counted_on <= ?"
        " ORDER BY counted_on DESC LIMIT 1",
        (system_name, as_of.isoformat()),
    )
    if row is None:
        return None
    return load_count(book, system_name, date.fromisoformat(str(row["counted_on"])))


def delete_count(book: Book, system_name: str, counted_on: date) -> None:
    """Remove one inventory and the vessels under it."""
    if not isinstance(counted_on, date):
        raise BadInputError("an inventory is looked up by date")
    key = counted_on.isoformat()
    with book.write():
        cursor = book.execute(
            "DELETE FROM inventory_count WHERE system_name = ? AND counted_on = ?",
            (system_name, key),
        )
        if cursor.rowcount == 0:
            raise NotFoundError(f"inventory of {system_name}", key)


__all__ = ["count_dates", "delete_count", "latest_count", "load_count", "save_count"]
