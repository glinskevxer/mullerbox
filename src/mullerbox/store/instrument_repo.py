"""Reading and writing instruments and their calibration history.

Same shape as the series repository and for the same reason: an instrument is
the tag row plus every certificate under it, and a partially loaded history is
worse than none. The whole point of the history is answering "was this covered
on that day", and a load that dropped a certificate answers that question wrong
while looking like it worked.

Certificates are unique across the whole book rather than per instrument. A
certificate number identifies a piece of paper in a filing cabinet, and the same
number appearing against two devices means somebody copied a row.
"""

from __future__ import annotations

from datetime import date

from mullerbox.cal.instrument import Instrument, InstrumentKind
from mullerbox.cal.window import CalibrationWindow
from mullerbox.errors import DuplicateError, NotFoundError
from mullerbox.store.coding import decode
from mullerbox.store.connection import Book


def _as_date(text: object) -> date:
    return date.fromisoformat(str(text))


def exists(book: Book, tag: str) -> bool:
    return book.one("SELECT tag FROM instrument WHERE tag = ?", (tag,)) is not None


def save_instrument(book: Book, instrument: Instrument) -> None:
    """Write an instrument and every certificate it carries."""
    if exists(book, instrument.tag):
        raise DuplicateError("instrument", instrument.tag)
    with book.write():
        book.execute(
            "INSERT INTO instrument (tag, kind) VALUES (?, ?)",
            (instrument.tag, instrument.kind.name),
        )
        for window in instrument.windows:
            _insert_window(book, instrument.tag, window)


def add_calibration(book: Book, tag: str, window: CalibrationWindow) -> Instrument:
    """Record one more certificate, through the type's own overlap check."""
    instrument = load_instrument(book, tag)
    updated = instrument.with_window(window)
    with book.write():
        _insert_window(book, tag, window)
    return updated


def _insert_window(book: Book, tag: str, window: CalibrationWindow) -> None:
    clash = book.one(
        "SELECT instrument_tag FROM calibration WHERE certificate = ?",
        (window.certificate,),
    )
    if clash is not None:
        raise DuplicateError("certificate", window.certificate)
    book.execute(
        "INSERT INTO calibration"
        " (certificate, instrument_tag, calibrated_on, due_on) VALUES (?, ?, ?, ?)",
        (
            window.certificate,
            tag,
            window.calibrated_on.isoformat(),
            window.due_on.isoformat(),
        ),
    )


def load_instrument(book: Book, tag: str) -> Instrument:
    """Rebuild an instrument and its whole history."""
    row = book.one("SELECT tag, kind FROM instrument WHERE tag = ?", (tag,))
    if row is None:
        raise NotFoundError("instrument", tag)
    kind = decode(str(row["kind"]), InstrumentKind, "an instrument kind")
    windows = book.all(
        "SELECT certificate, calibrated_on, due_on FROM calibration"
        " WHERE instrument_tag = ? ORDER BY calibrated_on, certificate",
        (tag,),
    )
    return Instrument(
        tag=str(row["tag"]),
        kind=kind,
        windows=tuple(
            CalibrationWindow(
                calibrated_on=_as_date(w["calibrated_on"]),
                due_on=_as_date(w["due_on"]),
                certificate=str(w["certificate"]),
            )
            for w in windows
        ),
    )


def list_instruments(book: Book) -> list[str]:
    rows = book.all("SELECT tag FROM instrument ORDER BY tag")
    return [str(row["tag"]) for row in rows]


def load_all(book: Book) -> dict[str, Instrument]:
    """Every instrument on the book, keyed by tag, ready for a validity sweep."""
    return {tag: load_instrument(book, tag) for tag in list_instruments(book)}


__all__ = [
    "add_calibration",
    "exists",
    "list_instruments",
    "load_all",
    "load_instrument",
    "save_instrument",
]
