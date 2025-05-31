"""Reading the lab's bench sheet export into property results.

The bench sheet is the file the lab's own equipment writes: one row per test,
with the sample, the property in whatever shorthand the technician typed, the
reading, the instrument tag and the date.

Two things this reader does that a naive one would not.

**It builds the reading through the property's own scale.** The file has a bare
number in it and nothing else; the scale comes from the property. That is the
only way to get a permeability back as a ``Permeability`` and a hardness back as
a ``Hardness`` when both are written ``88``.

**It does not check calibration.** Whether a result counts is a question about
the instrument's history at the test date, and the history is on the book, not
in the file. Answering it here would mean the same result loaded on two
different days gives two different answers about whether it is usable, which is
exactly the confusion ``props.result`` exists to prevent. The file gives facts;
validity is asked later.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from mullerbox.errors import BadInputError
from mullerbox.ingest.reader import Problem, Row, Sheet, collect
from mullerbox.props.kind import PropertyKind, Reading, parse_property
from mullerbox.props.result import Result

COLUMNS = ("sample", "property", "reading", "instrument", "tested")


def _read_date(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise BadInputError(f"{text!r} is not a date in yyyy-mm-dd form") from None


def _read_reading(kind: PropertyKind, text: str) -> Reading:
    """Turn the bare number in the file into the property's own scale."""
    return kind.reading_type(text)


def result_from(row: Row) -> Result:
    """Build one result from one bench sheet row."""
    kind = parse_property(row.text("property"))
    return Result(
        kind=kind,
        reading=_read_reading(kind, row.text("reading")),
        instrument_tag=row.text("instrument"),
        tested_on=_read_date(row.text("tested")),
        sample_id=row.text("sample"),
    )


@dataclass(frozen=True)
class BenchLoad:
    """What came off a bench sheet, and what would not."""

    results: tuple[Result, ...]
    problems: tuple[Problem, ...]

    @property
    def is_clean(self) -> bool:
        return not self.problems

    @property
    def samples(self) -> tuple[str, ...]:
        """Every sample mentioned, in first appearance order."""
        seen: list[str] = []
        for result in self.results:
            if result.sample_id not in seen:
                seen.append(result.sample_id)
        return tuple(seen)

    def for_sample(self, sample_id: str) -> tuple[Result, ...]:
        return tuple(r for r in self.results if r.sample_id == sample_id)

    def of_property(self, kind: PropertyKind) -> tuple[Result, ...]:
        if not isinstance(kind, PropertyKind):
            raise BadInputError("a property kind is expected")
        return tuple(r for r in self.results if r.kind is kind)

    def __str__(self) -> str:
        return (
            f"{len(self.results)} results over {len(self.samples)} samples, "
            f"{len(self.problems)} problems"
        )


def load_bench(sheet: Sheet) -> BenchLoad:
    """Read a whole bench sheet, keeping the rows that would not parse."""
    if not isinstance(sheet, Sheet):
        raise BadInputError("a parsed sheet is expected")
    sheet.require_columns(*COLUMNS)
    built, problems = collect(sheet, result_from)
    results = [r for r in built if isinstance(r, Result)]
    return BenchLoad(results=tuple(results), problems=tuple(problems))


__all__ = ["BenchLoad", "COLUMNS", "load_bench", "result_from"]
