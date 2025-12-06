"""Writing csv back out, in the shape the readers expect.

The exports and the imports share their column names, and that is a deliberate
constraint rather than a coincidence: an export that cannot be read back by the
matching reader is an export nobody can check. So the writers name their columns
from the reader modules, and a round trip through both is what the tests assert.

Two details that make the round trip actually hold.

**Every value goes out as the string the type prints for storage**, not as the
one it prints for a person. ``42.00`` rather than ``42.00%``, because the reader
takes a bare number and applies the scale. A friendly export is one the reader
refuses.

**The line ending is written explicitly.** ``csv.writer`` defaults to platform
line endings, which on the wrong machine produces a file with blank rows between
every line when read back on another. Newline is set at both ends.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

from mullerbox.errors import BadInputError, ConfigError

LINE_ENDING = "\n"


@dataclass(frozen=True)
class Sheet:
    """A table on its way out: its columns and its rows."""

    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]

    def __post_init__(self) -> None:
        if not self.columns:
            raise BadInputError("an export needs at least one column")
        if len(set(self.columns)) != len(self.columns):
            raise BadInputError("an export cannot have two columns with one name")
        for row in self.rows:
            if len(row) != len(self.columns):
                raise BadInputError(
                    f"this export has {len(self.columns)} columns and a row has {len(row)}"
                )

    def __len__(self) -> int:
        return len(self.rows)


def write_rows(columns: Sequence[str], rows: Iterable[Sequence[object]]) -> str:
    """Render a table as csv text.

    Values are stringified here rather than by the caller so that ``None``
    becomes an empty field once, in one place, instead of at every call site
    with a slightly different idea of what empty means.
    """
    built = Sheet(
        columns=tuple(columns),
        rows=tuple(tuple("" if value is None else str(value) for value in row) for row in rows),
    )
    buffer = StringIO()
    writer = csv.writer(buffer, lineterminator=LINE_ENDING)
    writer.writerow(built.columns)
    writer.writerows(built.rows)
    return buffer.getvalue()


def write_sheet(path: str | Path, columns: Sequence[str], rows: Iterable[Sequence[object]]) -> int:
    """Write a table to a file, returning how many rows went out.

    Refuses to write over a directory and refuses a path whose parent is not
    there, because both produce a confusing traceback out of the standard
    library and neither is worth one.
    """
    target = Path(path)
    if target.is_dir():
        raise ConfigError(f"{target} is a directory")
    parent = target.expanduser().parent
    if not parent.exists():
        raise ConfigError(f"there is no directory at {parent}")
    text = write_rows(columns, rows)
    target.expanduser().write_text(text, encoding="utf-8", newline="")
    return max(text.count(LINE_ENDING) - 1, 0)


__all__ = ["LINE_ENDING", "Sheet", "write_rows", "write_sheet"]
