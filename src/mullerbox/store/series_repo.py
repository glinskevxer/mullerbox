"""Reading and writing screen series.

A series is a composite: the row that names it and the ordered steps under it.
It is stored across two tables and it is only ever handed out whole, because a
series missing a step is not a smaller series, it is a wrong one. Every fineness
number ever computed against it would be quietly wrong, and nothing downstream
could tell.

So loading rebuilds the full object and lets ``ScreenSeries`` re-run its own
construction checks. Storage is not trusted to have kept the ordering or the
multiplier monotonicity that the type guarantees; the file could have been
edited, restored from an older schema, or written by an earlier version of this
code. The type is the authority and the round trip goes back through it.
"""

from __future__ import annotations

from mullerbox.errors import DuplicateError, NotFoundError
from mullerbox.screens.series import ScreenSeries, Step
from mullerbox.store.connection import Book
from mullerbox.units.mesh import Mesh


def save_series(book: Book, series: ScreenSeries) -> None:
    """Write a series and its steps, refusing to overwrite an existing one."""
    if exists(book, series.name):
        raise DuplicateError("screen series", series.name)
    with book.write():
        book.execute("INSERT INTO screen_series (name) VALUES (?)", (series.name,))
        book.executemany(
            "INSERT INTO screen_step"
            " (series_name, position, mesh_number, micrometres, multiplier)"
            " VALUES (?, ?, ?, ?, ?)",
            [
                (
                    series.name,
                    position,
                    step.mesh.number,
                    step.mesh.micrometres,
                    step.multiplier,
                )
                for position, step in enumerate(series.steps)
            ],
        )


def exists(book: Book, name: str) -> bool:
    return book.one("SELECT name FROM screen_series WHERE name = ?", (name,)) is not None


def load_series(book: Book, name: str) -> ScreenSeries:
    """Rebuild a series from the book, through the type's own checks."""
    if not exists(book, name):
        raise NotFoundError("screen series", name)
    rows = book.all(
        "SELECT mesh_number, micrometres, multiplier FROM screen_step"
        " WHERE series_name = ? ORDER BY position",
        (name,),
    )
    steps = tuple(
        Step(
            mesh=Mesh(int(row["mesh_number"]), int(row["micrometres"])),
            multiplier=int(row["multiplier"]),
        )
        for row in rows
    )
    return ScreenSeries(name=name, steps=steps)


def list_series(book: Book) -> list[str]:
    rows = book.all("SELECT name FROM screen_series ORDER BY name")
    return [str(row["name"]) for row in rows]


def delete_series(book: Book, name: str) -> None:
    """Remove a series and its steps."""
    if not exists(book, name):
        raise NotFoundError("screen series", name)
    with book.write():
        book.execute("DELETE FROM screen_step WHERE series_name = ?", (name,))
        book.execute("DELETE FROM screen_series WHERE name = ?", (name,))


__all__ = ["delete_series", "exists", "list_series", "load_series", "save_series"]
