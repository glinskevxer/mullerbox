"""Reading and writing samples, property results and sieve analyses.

A reading is stored as text alongside the name of the scale it is on, rather
than as a number. Two reasons, and the second is the real one.

Text keeps the exact value. Compactability 42.00 and 42 are the same reading and
the same Decimal, and a REAL column turns both into a float that is neither.

Naming the scale means the row can be turned back into the right type without
consulting anything else. A bare number cannot: 88 is a plausible mold hardness
and a plausible permeability, and a loader that guesses from the property name
is a loader that silently produces the wrong type the first time a property is
moved from one scale to another. The scale is written down because it is part of
the reading, not part of the schema.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from mullerbox.errors import BadInputError, DuplicateError, NotFoundError
from mullerbox.props.kind import PropertyKind, Reading
from mullerbox.props.result import Result
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


@dataclass(frozen=True)
class Sample:
    """A pull of sand, and where it came from."""

    sample_id: str
    taken_on: date
    point: str
    system_name: str

    def __post_init__(self) -> None:
        if not self.sample_id.strip():
            raise BadInputError("a sample needs an identifier")
        if not isinstance(self.taken_on, date):
            raise BadInputError("a sample is dated")
        if not self.point.strip():
            raise BadInputError("a sample names where it was pulled")
        if not self.system_name.strip():
            raise BadInputError("a sample names its sand system")


def _reading_text(reading: Reading) -> tuple[str, str]:
    scale = type(reading).__name__
    if scale not in _SCALES:
        raise BadInputError(f"{scale} is not a scale this book stores")
    if isinstance(reading, Permeability):
        return str(reading.value), scale
    return str(reading.value), scale


def _reading_from(text: str, scale: str) -> Reading:
    builder = _SCALES.get(scale)
    if builder is None:
        raise BadInputError(f"the book carries a reading on scale {scale!r}")
    return builder(text)


def save_sample(book: Book, sample: Sample) -> None:
    if sample_exists(book, sample.sample_id):
        raise DuplicateError("sample", sample.sample_id)
    with book.write():
        book.execute(
            "INSERT INTO sample (sample_id, taken_on, point, system_name) VALUES (?, ?, ?, ?)",
            (
                sample.sample_id,
                sample.taken_on.isoformat(),
                sample.point,
                sample.system_name,
            ),
        )


def sample_exists(book: Book, sample_id: str) -> bool:
    return book.one("SELECT sample_id FROM sample WHERE sample_id = ?", (sample_id,)) is not None


def load_sample(book: Book, sample_id: str) -> Sample:
    row = book.one(
        "SELECT sample_id, taken_on, point, system_name FROM sample WHERE sample_id = ?",
        (sample_id,),
    )
    if row is None:
        raise NotFoundError("sample", sample_id)
    return Sample(
        sample_id=str(row["sample_id"]),
        taken_on=date.fromisoformat(str(row["taken_on"])),
        point=str(row["point"]),
        system_name=str(row["system_name"]),
    )


def save_result(book: Book, result: Result) -> None:
    """Write one property result against an existing sample."""
    if not sample_exists(book, result.sample_id):
        raise NotFoundError("sample", result.sample_id)
    existing = book.one(
        "SELECT property FROM result WHERE sample_id = ? AND property = ?",
        (result.sample_id, result.kind.name),
    )
    if existing is not None:
        raise DuplicateError(f"{result.kind.label} on sample", result.sample_id)
    text, scale = _reading_text(result.reading)
    with book.write():
        book.execute(
            "INSERT INTO result"
            " (sample_id, property, reading, scale, instrument_tag, tested_on)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                result.sample_id,
                result.kind.name,
                text,
                scale,
                result.instrument_tag,
                result.tested_on.isoformat(),
            ),
        )


def load_results(book: Book, sample_id: str) -> list[Result]:
    """Every result on one sample, in property order."""
    rows = book.all(
        "SELECT property, reading, scale, instrument_tag, tested_on FROM result"
        " WHERE sample_id = ? ORDER BY property",
        (sample_id,),
    )
    return [_result_from(row, sample_id) for row in rows]


def results_of(book: Book, kind: PropertyKind) -> list[Result]:
    """Every result for one property across the book, oldest first."""
    if not isinstance(kind, PropertyKind):
        raise BadInputError("a property kind is expected")
    rows = book.all(
        "SELECT sample_id, property, reading, scale, instrument_tag, tested_on"
        " FROM result WHERE property = ? ORDER BY tested_on, sample_id",
        (kind.name,),
    )
    return [_result_from(row, str(row["sample_id"])) for row in rows]


def _result_from(row: object, sample_id: str) -> Result:
    mapping = row  # sqlite3.Row supports mapping access
    property_name = str(mapping["property"])  # type: ignore[index]
    try:
        kind = PropertyKind[property_name]
    except KeyError:
        raise BadInputError(
            f"the book carries a result for {property_name!r}, which is not a property"
        ) from None
    return Result(
        kind=kind,
        reading=_reading_from(
            str(mapping["reading"]),  # type: ignore[index]
            str(mapping["scale"]),  # type: ignore[index]
        ),
        instrument_tag=str(mapping["instrument_tag"]),  # type: ignore[index]
        tested_on=date.fromisoformat(str(mapping["tested_on"])),  # type: ignore[index]
        sample_id=sample_id,
    )


__all__ = [
    "Sample",
    "load_results",
    "load_sample",
    "results_of",
    "sample_exists",
    "save_result",
    "save_sample",
]
