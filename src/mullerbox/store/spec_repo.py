"""Reading and writing published spec sheets.

Only the **published** sheet is stored. The resolution against a pattern class
is not, and that is the point of the module rather than an omission.

A resolved spec is derived from a sheet and a class, and it is derived cheaply.
Storing it would create a second copy that can disagree with the first, and the
way it disagrees is the worst kind: metallurgy revises the sheet, the stored
resolutions keep the old numbers, and every line that was resolved before the
revision carries on being judged against a spec nobody publishes any more. There
is no error, no warning, and nothing on any report that says which of the two
was used.

So resolution happens at the point of judgement, every time, and this module
declines to help with anything else.

A one ended band stores NULL in the end it does not have. That distinguishes it
from a band whose limit happens to be zero, which is a real and different thing
for a property like friability.
"""

from __future__ import annotations

from datetime import date

from mullerbox.errors import BadInputError, DuplicateError, NotFoundError
from mullerbox.props.kind import PropertyKind, Reading
from mullerbox.spec.band import Band
from mullerbox.spec.sheet import SpecSheet
from mullerbox.store.connection import Book
from mullerbox.units.percent import Percent
from mullerbox.units.pressure import Psi, WetTensile
from mullerbox.units.scales import Hardness, Permeability

_SCALES: dict[str, type[Percent | Psi | WetTensile | Permeability | Hardness]] = {
    "Percent": Percent,
    "Psi": Psi,
    "WetTensile": WetTensile,
    "Permeability": Permeability,
    "Hardness": Hardness,
}


def _limit_text(limit: Reading | None) -> str | None:
    return None if limit is None else str(limit.value)


def _limit_from(text: object, scale: str) -> Reading | None:
    if text is None:
        return None
    builder = _SCALES.get(scale)
    if builder is None:
        raise BadInputError(f"the book carries a band on scale {scale!r}")
    return builder(str(text))


def sheet_exists(book: Book, name: str) -> bool:
    return book.one("SELECT name FROM spec_sheet WHERE name = ?", (name,)) is not None


def save_sheet(book: Book, sheet: SpecSheet, published_on: date) -> None:
    """Write a published sheet and every band on it."""
    if not isinstance(sheet, SpecSheet):
        raise BadInputError("a spec sheet is expected")
    if not isinstance(published_on, date):
        raise BadInputError("a spec sheet is published on a date")
    if sheet_exists(book, sheet.name):
        raise DuplicateError("spec sheet", sheet.name)
    with book.write():
        book.execute(
            "INSERT INTO spec_sheet (name, published_on) VALUES (?, ?)",
            (sheet.name, published_on.isoformat()),
        )
        for kind, band in sheet.bands.items():
            reference = band.low if band.low is not None else band.high
            assert reference is not None
            book.execute(
                "INSERT INTO spec_band"
                " (sheet_name, property, low, high, scale) VALUES (?, ?, ?, ?, ?)",
                (
                    sheet.name,
                    kind.name,
                    _limit_text(band.low),
                    _limit_text(band.high),
                    type(reference).__name__,
                ),
            )


def load_sheet(book: Book, name: str) -> SpecSheet:
    """Rebuild a published sheet, through the type's own checks."""
    if not sheet_exists(book, name):
        raise NotFoundError("spec sheet", name)
    rows = book.all(
        "SELECT property, low, high, scale FROM spec_band WHERE sheet_name = ? ORDER BY property",
        (name,),
    )
    bands: dict[PropertyKind, Band] = {}
    for row in rows:
        property_name = str(row["property"])
        try:
            kind = PropertyKind[property_name]
        except KeyError:
            raise BadInputError(
                f"the book carries a band for {property_name!r}, which is not a property"
            ) from None
        scale = str(row["scale"])
        bands[kind] = Band(
            kind=kind,
            low=_limit_from(row["low"], scale),
            high=_limit_from(row["high"], scale),
        )
    return SpecSheet(name=name, bands=bands)


def published_on(book: Book, name: str) -> date:
    row = book.one("SELECT published_on FROM spec_sheet WHERE name = ?", (name,))
    if row is None:
        raise NotFoundError("spec sheet", name)
    return date.fromisoformat(str(row["published_on"]))


def list_sheets(book: Book) -> list[str]:
    rows = book.all("SELECT name FROM spec_sheet ORDER BY published_on DESC, name")
    return [str(r["name"]) for r in rows]


def current_sheet(book: Book, on_or_before: date) -> SpecSheet:
    """The newest sheet published on or before a date.

    Which sheet applied to a shift is a question about when the shift happened,
    not about which sheet is newest now. A shift in March is judged against the
    sheet that was published in January even after a June revision lands.
    """
    if not isinstance(on_or_before, date):
        raise BadInputError("a date is expected")
    row = book.one(
        "SELECT name FROM spec_sheet WHERE published_on <= ?"
        " ORDER BY published_on DESC, name LIMIT 1",
        (on_or_before.isoformat(),),
    )
    if row is None:
        raise NotFoundError("spec sheet published on or before", on_or_before.isoformat())
    return load_sheet(book, str(row["name"]))


__all__ = [
    "current_sheet",
    "list_sheets",
    "load_sheet",
    "published_on",
    "save_sheet",
    "sheet_exists",
]
