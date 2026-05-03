"""Plain text tables, because that is what gets printed and pinned up.

Every report in this package renders to fixed width text. Not because anything
here is against richer output, but because these reports are read three ways:
in a terminal over ssh from the shop office, printed on a dot matrix printer
that is older than the software, and pasted into an email. Fixed width survives
all three and nothing else survives the second.

The alignment rule is the only judgement in here and it matters more than it
looks. **Numbers right, text left, always.** A column of right aligned numbers
can be scanned for an outlier at a glance because the digits line up by place
value; the same column left aligned cannot, and a foundry manager scanning a
scrap report for the row that is ten times the others will miss it. The
alignment is therefore a property of the column and is declared once, not
decided per cell.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from mullerbox.errors import BadInputError

GUTTER = "  "
RULE_CHARACTER = "-"


class Align(Enum):
    """Which way a column's cells sit against its width."""

    LEFT = "left"
    RIGHT = "right"

    @property
    def label(self) -> str:
        return self.value

    def pad(self, text: str, width: int) -> str:
        return text.rjust(width) if self is Align.RIGHT else text.ljust(width)


@dataclass(frozen=True)
class Column:
    """One column, and how its cells line up."""

    heading: str
    align: Align = Align.LEFT

    def __post_init__(self) -> None:
        if not self.heading.strip():
            raise BadInputError("a column needs a heading")
        if not isinstance(self.align, Align):
            raise BadInputError("a column needs an alignment")

    @classmethod
    def number(cls, heading: str) -> Column:
        return cls(heading=heading, align=Align.RIGHT)


@dataclass
class Table:
    """A fixed width table that knows its own column widths."""

    columns: tuple[Column, ...]
    rows: list[tuple[str, ...]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.columns:
            raise BadInputError("a table needs at least one column")
        for column in self.columns:
            if not isinstance(column, Column):
                raise BadInputError("a table is built from columns")

    def add(self, *cells: object) -> None:
        """Append a row, refusing one of the wrong width."""
        if len(cells) != len(self.columns):
            raise BadInputError(
                f"this table has {len(self.columns)} columns and the row has {len(cells)}"
            )
        self.rows.append(tuple("" if c is None else str(c) for c in cells))

    @property
    def widths(self) -> tuple[int, ...]:
        return tuple(
            max(
                len(column.heading),
                *(len(row[index]) for row in self.rows),
            )
            if self.rows
            else len(column.heading)
            for index, column in enumerate(self.columns)
        )

    @property
    def width(self) -> int:
        return sum(self.widths) + len(GUTTER) * (len(self.columns) - 1)

    def render(self) -> list[str]:
        """The table as lines, with no trailing spaces on any of them."""
        widths = self.widths
        lines = [
            GUTTER.join(
                column.align.pad(column.heading, widths[index])
                for index, column in enumerate(self.columns)
            ).rstrip(),
            GUTTER.join(RULE_CHARACTER * w for w in widths),
        ]
        for row in self.rows:
            lines.append(
                GUTTER.join(
                    self.columns[index].align.pad(cell, widths[index])
                    for index, cell in enumerate(row)
                ).rstrip()
            )
        return lines

    def __str__(self) -> str:
        return "\n".join(self.render())

    def __len__(self) -> int:
        return len(self.rows)


def rule(width: int, character: str = RULE_CHARACTER) -> str:
    """A horizontal rule of one repeated character."""
    if width < 0:
        raise BadInputError("a rule cannot be shorter than nothing")
    if len(character) != 1:
        raise BadInputError("a rule is drawn with one character")
    return character * width


def wrap(text: str, width: int, indent: str = "") -> list[str]:
    """Break a paragraph to a width without splitting a word.

    A word longer than the width goes on its own line and overruns, rather than
    being cut. A cut word in a defect reason is worse than a long line: the
    reader cannot tell whether the cut is real.
    """
    if width <= 0:
        raise BadInputError("a wrap needs a width above zero")
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current = indent
    for word in words:
        candidate = word if current == indent else f"{current} {word}"
        if current != indent and len(candidate) > width:
            lines.append(current)
            current = indent + word
        else:
            current = candidate if current != indent else indent + word
    lines.append(current)
    return lines


def heading(title: str, width: int = 72) -> list[str]:
    """A title with a rule under it, sized to the wider of the two."""
    if not title.strip():
        raise BadInputError("a heading needs a title")
    span = max(len(title), width)
    return [title, rule(span)]


__all__ = ["Align", "Column", "GUTTER", "RULE_CHARACTER", "Table", "heading", "rule", "wrap"]
