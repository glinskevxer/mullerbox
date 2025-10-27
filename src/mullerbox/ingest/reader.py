"""Reading a csv the shop exported, and keeping what went wrong with it.

Every ingest in this package accumulates rather than raising. That is the one
design decision here and it comes from how these files are actually used: a
bench export is thirty rows and one of them has a typo, and the useful outcome
is twenty nine rows loaded and one row named. Raising on the first bad row gives
the operator a file that will not load, no idea how many other problems it has,
and a fix-and-retry loop that takes as many rounds as there are typos.

So a read gives back both halves: the rows that parsed and a problem per row
that did not, each carrying its line number so it can be pointed at. The caller
decides whether a file with problems is usable. Nothing here decides that,
because it depends on what the file is for: a spec sheet with one bad row should
not load at all, and a shift's bench sheets should load what they can.

Headers are matched case insensitively with surrounding space stripped, because
the exports come out of four different pieces of equipment and each spells them
differently. Unknown columns are ignored rather than refused, because the
equipment vendors add columns without telling anybody.
"""

from __future__ import annotations

import csv
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

from mullerbox.errors import BadInputError, ConfigError


@dataclass(frozen=True)
class Problem:
    """One row that could not be read, and why."""

    line: int
    reason: str
    raw: Mapping[str, str]

    def __str__(self) -> str:
        return f"line {self.line}: {self.reason}"


@dataclass(frozen=True)
class Row:
    """One csv row, addressed by normalised header."""

    line: int
    fields: Mapping[str, str]

    def text(self, column: str) -> str:
        """A required column, stripped."""
        key = column.strip().lower()
        if key not in self.fields:
            raise BadInputError(f"there is no {column!r} column")
        value = self.fields[key].strip()
        if not value:
            raise BadInputError(f"{column!r} is empty")
        return value

    def optional(self, column: str, fallback: str = "") -> str:
        """A column that may be absent or blank, with a fallback for either."""
        key = column.strip().lower()
        value = self.fields.get(key, "").strip()
        return value or fallback

    def has(self, column: str) -> bool:
        return column.strip().lower() in self.fields


@dataclass(frozen=True)
class Sheet:
    """A parsed csv: its rows, its columns, and whatever it could not read."""

    columns: tuple[str, ...]
    rows: tuple[Row, ...]
    problems: tuple[Problem, ...]

    @property
    def is_clean(self) -> bool:
        return not self.problems

    def require_clean(self, what: str) -> None:
        """Refuse a file with any problem in it, naming the first."""
        if self.problems:
            raise ConfigError(
                f"{what} will not load: {len(self.problems)} bad rows, first is {self.problems[0]}"
            )

    def require_columns(self, *needed: str) -> None:
        missing = [c for c in needed if c.strip().lower() not in self.columns]
        if missing:
            raise ConfigError(f"the file has no {missing[0]!r} column; it has {list(self.columns)}")

    def __len__(self) -> int:
        return len(self.rows)

    def __iter__(self) -> Iterator[Row]:
        return iter(self.rows)


def _normalise(name: str | None) -> str:
    return (name or "").strip().lower()


def read_text(text: str) -> Sheet:
    """Parse csv already in memory."""
    if not isinstance(text, str):
        raise BadInputError("a sheet is parsed from text")
    reader = csv.DictReader(StringIO(text))
    if reader.fieldnames is None:
        return Sheet(columns=(), rows=(), problems=())
    columns = tuple(_normalise(name) for name in reader.fieldnames)
    if len(set(columns)) != len(columns):
        raise ConfigError("the file has two columns with the same name")
    rows: list[Row] = []
    problems: list[Problem] = []
    for offset, raw in enumerate(reader, start=2):
        fields = {_normalise(k): (v if v is not None else "") for k, v in raw.items()}
        if None in raw:
            problems.append(
                Problem(
                    line=offset,
                    reason="more values than there are columns",
                    raw={k: v for k, v in fields.items() if k},
                )
            )
            continue
        if all(not value.strip() for value in fields.values()):
            continue
        rows.append(Row(line=offset, fields=fields))
    return Sheet(columns=columns, rows=tuple(rows), problems=tuple(problems))


def read_sheet(path: str | Path) -> Sheet:
    """Parse a csv off disk."""
    target = Path(path)
    if not target.exists():
        raise ConfigError(f"there is no file at {target}")
    if target.is_dir():
        raise ConfigError(f"{target} is a directory")
    try:
        text = target.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ConfigError(f"{target} is not utf-8 text: {exc}") from exc
    return read_text(text)


def collect(sheet: Sheet, build: object) -> tuple[list[object], list[Problem]]:
    """Run a builder over every row, keeping the failures rather than raising.

    ``build`` takes a ``Row`` and returns whatever the caller wants. Anything it
    raises that descends from the package's own error base becomes a problem;
    anything else escapes, because a ``KeyError`` out of a builder is a bug in
    the builder and swallowing it into a row problem hides it behind a message
    about the operator's data.
    """
    if not callable(build):
        raise BadInputError("a builder is expected")
    built: list[object] = []
    problems: list[Problem] = list(sheet.problems)
    for row in sheet.rows:
        try:
            built.append(build(row))
        except (BadInputError, ConfigError) as exc:
            problems.append(Problem(line=row.line, reason=str(exc), raw=row.fields))
    problems.sort(key=lambda p: p.line)
    return built, problems


def problem_lines(problems: Sequence[Problem]) -> list[str]:
    return [str(p) for p in problems]


__all__ = [
    "Problem",
    "Row",
    "Sheet",
    "collect",
    "problem_lines",
    "read_sheet",
    "read_text",
]
