"""What each material cost, and when.

Prices are kept as a history rather than as a current value, and every lookup
takes a date. A shift in March is costed at March's bentonite price even after a
June increase, because the alternative is a cost report whose past changes every
time purchasing renegotiates. A report that will not sit still is a report
nobody can act on.

That makes the primary key material and effective date together, and it makes
"the price list" a derived thing: it is the newest price for each material on or
before a given day, assembled at the point of asking.

A material with no price on or before the day being costed is an error rather
than a zero. A zero is a real price for water and a wrong one for bentonite, and
a costing that silently treats a missing price as free understates a shift by
whatever the missing material cost.
"""

from __future__ import annotations

from datetime import date

from mullerbox.addition.material import Material
from mullerbox.charge.cost import PriceList
from mullerbox.errors import BadInputError, DuplicateError, NotFoundError
from mullerbox.store.connection import Book
from mullerbox.units.money import PricePerTon


def set_price(book: Book, material: Material, per_ton: PricePerTon, effective: date) -> None:
    """Record what a material costs from a date, refusing a repeat for that day."""
    if not isinstance(material, Material):
        raise BadInputError("a material is expected")
    if not isinstance(per_ton, PricePerTon):
        raise BadInputError("a price per ton is expected")
    if not isinstance(effective, date):
        raise BadInputError("a price is effective from a date")
    existing = book.one(
        "SELECT per_ton FROM material_price WHERE material = ? AND effective = ?",
        (material.name, effective.isoformat()),
    )
    if existing is not None:
        raise DuplicateError(f"{material.label} price effective", effective.isoformat())
    with book.write():
        book.execute(
            "INSERT INTO material_price (material, effective, per_ton) VALUES (?, ?, ?)",
            (material.name, effective.isoformat(), str(per_ton.dollars)),
        )


def price_on(book: Book, material: Material, when: date) -> PricePerTon:
    """The price in force for one material on a date."""
    if not isinstance(material, Material):
        raise BadInputError("a material is expected")
    if not isinstance(when, date):
        raise BadInputError("a date is expected")
    row = book.one(
        "SELECT per_ton FROM material_price WHERE material = ? AND effective <= ?"
        " ORDER BY effective DESC LIMIT 1",
        (material.name, when.isoformat()),
    )
    if row is None:
        raise NotFoundError(f"{material.label} price on or before", when.isoformat())
    return PricePerTon(str(row["per_ton"]))


def price_list_on(book: Book, when: date) -> PriceList:
    """Assemble the whole price list as it stood on a date.

    Every material has to have a price. ``PriceList`` refuses a partial one, and
    that refusal is left to propagate rather than being softened here: a costing
    run against a list with a hole in it is a costing run that understates, and
    the operator needs to be told which material is missing.
    """
    if not isinstance(when, date):
        raise BadInputError("a date is expected")
    return PriceList(prices={material: price_on(book, material, when) for material in Material})


def history(book: Book, material: Material) -> list[tuple[date, PricePerTon]]:
    """Every price ever recorded for one material, oldest first."""
    if not isinstance(material, Material):
        raise BadInputError("a material is expected")
    rows = book.all(
        "SELECT effective, per_ton FROM material_price WHERE material = ? ORDER BY effective",
        (material.name,),
    )
    return [(date.fromisoformat(str(r["effective"])), PricePerTon(str(r["per_ton"]))) for r in rows]


def priced_materials(book: Book, when: date) -> list[Material]:
    """Which materials have a price on a date, for reporting the holes."""
    if not isinstance(when, date):
        raise BadInputError("a date is expected")
    found: list[Material] = []
    for material in Material:
        row = book.one(
            "SELECT per_ton FROM material_price WHERE material = ? AND effective <= ? LIMIT 1",
            (material.name, when.isoformat()),
        )
        if row is not None:
            found.append(material)
    return found


__all__ = ["history", "price_list_on", "price_on", "priced_materials", "set_price"]
