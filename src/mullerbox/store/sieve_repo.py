"""Reading and writing sieve analyses.

Retained masses are stored as whole centigrams rather than as text, because
``Grams`` is already an integer count of centigrams and an INTEGER column round
trips it exactly with no parsing. That is the one place in this schema where a
numeric column is the right call, and it is right for a reason that does not
generalise: the value is an integer in the domain, not a decimal that happens to
look like one.

The series name is stored on every row rather than once per analysis. It is
denormalised on purpose. A sieve analysis is meaningless without knowing which
stack it ran on, and a schema that lets the two drift apart will eventually let
them, usually during a restore.
"""

from __future__ import annotations

from mullerbox.errors import BadInputError, DuplicateError, NotFoundError, RuleError
from mullerbox.screens.analysis import Retained, SieveAnalysis
from mullerbox.screens.series import ScreenSeries
from mullerbox.store.connection import Book
from mullerbox.store.result_repo import sample_exists
from mullerbox.store.series_repo import load_series
from mullerbox.units.mass import Grams


def analysis_exists(book: Book, sample_id: str) -> bool:
    return (
        book.one(
            "SELECT sample_id FROM sieve_reading WHERE sample_id = ? LIMIT 1",
            (sample_id,),
        )
        is not None
    )


def save_analysis(book: Book, sample_id: str, analysis: SieveAnalysis) -> None:
    """Write one analysis against an existing sample."""
    if not isinstance(analysis, SieveAnalysis):
        raise BadInputError("a sieve analysis is expected")
    if not sample_exists(book, sample_id):
        raise NotFoundError("sample", sample_id)
    if analysis_exists(book, sample_id):
        raise DuplicateError("sieve analysis on sample", sample_id)
    series_name = analysis.series.name
    known = book.one("SELECT name FROM screen_series WHERE name = ?", (series_name,))
    if known is None:
        raise RuleError(f"the analysis ran on series {series_name!r}, which is not on the book")
    with book.write():
        book.executemany(
            "INSERT INTO sieve_reading"
            " (sample_id, series_name, charged_cg, mesh_number, retained_cg)"
            " VALUES (?, ?, ?, ?, ?)",
            [
                (
                    sample_id,
                    series_name,
                    analysis.charged.centigrams,
                    reading.mesh.number,
                    reading.mass.centigrams,
                )
                for reading in analysis.ordered
            ],
        )


def load_analysis(book: Book, sample_id: str) -> SieveAnalysis:
    """Rebuild an analysis, through the type's own closure and coverage checks."""
    rows = book.all(
        "SELECT series_name, charged_cg, mesh_number, retained_cg FROM sieve_reading"
        " WHERE sample_id = ?",
        (sample_id,),
    )
    if not rows:
        raise NotFoundError("sieve analysis on sample", sample_id)
    names = {str(r["series_name"]) for r in rows}
    if len(names) > 1:
        raise RuleError(f"sample {sample_id} has readings against {len(names)} different series")
    charges = {int(r["charged_cg"]) for r in rows}
    if len(charges) > 1:
        raise RuleError(f"sample {sample_id} has readings against {len(charges)} charged masses")
    series: ScreenSeries = load_series(book, names.pop())
    by_number = {mesh.number: mesh for mesh in series.meshes}
    readings: list[Retained] = []
    for row in rows:
        number = int(row["mesh_number"])
        mesh = by_number.get(number)
        if mesh is None:
            raise RuleError(
                f"sample {sample_id} has a reading on screen {number}, "
                f"which is not on series {series.name}"
            )
        readings.append(Retained(mesh=mesh, mass=Grams.from_centigrams(int(row["retained_cg"]))))
    return SieveAnalysis(
        series=series,
        charged=Grams.from_centigrams(charges.pop()),
        readings=tuple(readings),
    )


def delete_analysis(book: Book, sample_id: str) -> None:
    if not analysis_exists(book, sample_id):
        raise NotFoundError("sieve analysis on sample", sample_id)
    with book.write():
        book.execute("DELETE FROM sieve_reading WHERE sample_id = ?", (sample_id,))


def samples_with_analyses(book: Book) -> list[str]:
    rows = book.all("SELECT DISTINCT sample_id FROM sieve_reading ORDER BY sample_id")
    return [str(r["sample_id"]) for r in rows]


__all__ = [
    "analysis_exists",
    "delete_analysis",
    "load_analysis",
    "samples_with_analyses",
    "save_analysis",
]
