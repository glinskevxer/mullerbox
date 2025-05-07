"""Reading and writing heats, and the pour records derived from them.

Masses go in as text for the same reason readings do: a Decimal round trips
through TEXT exactly and does not through REAL. A hundred and twenty pound
casting stored as a float and summed forty times is not a four thousand eight
hundred pound heat, it is four thousand seven hundred and ninety nine point nine
nine nine, and the scrap rate computed from it is wrong in the fourth place
forever.

A heat is written whole and read whole. Its molds and castings are its parts,
not independent records, and there is no way through this module to add a
casting to a heat that has already been written. Production records are not
edited after the fact; a heat that was recorded wrong is corrected by a
correcting entry, which is a thing the shop already understands.
"""

from __future__ import annotations

from datetime import date

from mullerbox.burnout.pour import Pour
from mullerbox.errors import BadInputError, DuplicateError, NotFoundError
from mullerbox.heat.heat import Casting, Disposition, Heat, Mold
from mullerbox.spec.pattern import PatternClass
from mullerbox.store.connection import Book
from mullerbox.units.bulk import Pounds


def heat_exists(book: Book, heat_number: str) -> bool:
    return (
        book.one("SELECT heat_number FROM heat WHERE heat_number = ?", (heat_number,)) is not None
    )


def save_heat(book: Book, heat: Heat) -> None:
    """Write a heat and everything under it in one transaction."""
    if not isinstance(heat, Heat):
        raise BadInputError("a heat is expected")
    if heat_exists(book, heat.heat_number):
        raise DuplicateError("heat", heat.heat_number)
    with book.write():
        book.execute(
            "INSERT INTO heat (heat_number, poured_on) VALUES (?, ?)",
            (heat.heat_number, heat.poured_on.isoformat()),
        )
        for mold in heat.molds:
            book.execute(
                "INSERT INTO mold (mold_id, heat_number, pattern, sand_lb) VALUES (?, ?, ?, ?)",
                (
                    mold.mold_id,
                    heat.heat_number,
                    mold.pattern.name,
                    str(mold.sand.value),
                ),
            )
            for casting in mold.castings:
                book.execute(
                    "INSERT INTO casting"
                    " (casting_id, mold_id, weight_lb, disposition)"
                    " VALUES (?, ?, ?, ?)",
                    (
                        casting.casting_id,
                        mold.mold_id,
                        str(casting.weight.value),
                        casting.disposition.name,
                    ),
                )


def load_heat(book: Book, heat_number: str) -> Heat:
    """Rebuild a heat and everything under it, through the types' own checks."""
    row = book.one(
        "SELECT heat_number, poured_on FROM heat WHERE heat_number = ?",
        (heat_number,),
    )
    if row is None:
        raise NotFoundError("heat", heat_number)
    mold_rows = book.all(
        "SELECT mold_id, pattern, sand_lb FROM mold WHERE heat_number = ? ORDER BY mold_id",
        (heat_number,),
    )
    molds: list[Mold] = []
    for mold_row in mold_rows:
        mold_id = str(mold_row["mold_id"])
        casting_rows = book.all(
            "SELECT casting_id, weight_lb, disposition FROM casting"
            " WHERE mold_id = ? ORDER BY casting_id",
            (mold_id,),
        )
        molds.append(
            Mold(
                mold_id=mold_id,
                pattern=_pattern_from(str(mold_row["pattern"])),
                sand=Pounds(str(mold_row["sand_lb"])),
                castings=tuple(
                    Casting(
                        casting_id=str(c["casting_id"]),
                        weight=Pounds(str(c["weight_lb"])),
                        disposition=_disposition_from(str(c["disposition"])),
                    )
                    for c in casting_rows
                ),
            )
        )
    return Heat(
        heat_number=str(row["heat_number"]),
        poured_on=date.fromisoformat(str(row["poured_on"])),
        molds=tuple(molds),
    )


def list_heats(book: Book, on: date | None = None) -> list[str]:
    """Heat numbers, optionally narrowed to one day."""
    if on is None:
        rows = book.all("SELECT heat_number FROM heat ORDER BY poured_on, heat_number")
    else:
        if not isinstance(on, date):
            raise BadInputError("a date is expected")
        rows = book.all(
            "SELECT heat_number FROM heat WHERE poured_on = ? ORDER BY heat_number",
            (on.isoformat(),),
        )
    return [str(r["heat_number"]) for r in rows]


def save_pour(book: Book, pour: Pour) -> None:
    if not isinstance(pour, Pour):
        raise BadInputError("a pour is expected")
    existing = book.one(
        "SELECT poured_on FROM pour WHERE poured_on = ? AND pattern = ?",
        (pour.poured_on.isoformat(), pour.pattern.name),
    )
    if existing is not None:
        raise DuplicateError("pour", f"{pour.poured_on} {pour.pattern.label}")
    with book.write():
        book.execute(
            "INSERT INTO pour (poured_on, pattern, metal_lb, sand_lb) VALUES (?, ?, ?, ?)",
            (
                pour.poured_on.isoformat(),
                pour.pattern.name,
                str(pour.metal.value),
                str(pour.sand.value),
            ),
        )


def load_pours(book: Book, on: date) -> list[Pour]:
    """Every pour record for one day, in pattern order."""
    if not isinstance(on, date):
        raise BadInputError("a date is expected")
    rows = book.all(
        "SELECT poured_on, pattern, metal_lb, sand_lb FROM pour"
        " WHERE poured_on = ? ORDER BY pattern",
        (on.isoformat(),),
    )
    return [
        Pour(
            poured_on=date.fromisoformat(str(r["poured_on"])),
            pattern=_pattern_from(str(r["pattern"])),
            metal=Pounds(str(r["metal_lb"])),
            sand=Pounds(str(r["sand_lb"])),
        )
        for r in rows
    ]


def pour_from_heat(book: Book, heat_number: str, pattern: PatternClass) -> Pour:
    """Derive a pour record from what a heat actually did.

    Only the molds of the named class are counted, so a heat that ran two
    classes yields two pour records with two different ratios, which is the
    honest reading of it.
    """
    if not isinstance(pattern, PatternClass):
        raise BadInputError("a pattern class is expected")
    heat = load_heat(book, heat_number)
    molds = heat.molds_of(pattern)
    if not molds:
        raise NotFoundError(f"{pattern.label} molds on heat", heat_number)
    metal = Pounds.zero()
    sand = Pounds.zero()
    for mold in molds:
        metal = metal + mold.metal
        sand = sand + mold.sand
    return Pour(poured_on=heat.poured_on, pattern=pattern, metal=metal, sand=sand)


def _pattern_from(name: str) -> PatternClass:
    try:
        return PatternClass[name]
    except KeyError:
        raise BadInputError(f"the book carries pattern class {name!r}, which is not one") from None


def _disposition_from(name: str) -> Disposition:
    try:
        return Disposition[name]
    except KeyError:
        raise BadInputError(f"the book carries disposition {name!r}, which is not one") from None


__all__ = [
    "heat_exists",
    "list_heats",
    "load_heat",
    "load_pours",
    "pour_from_heat",
    "save_heat",
    "save_pour",
]
