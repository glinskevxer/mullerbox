"""Reading and writing the pattern register.

The register is reference data, not production data: it changes when a pattern
is made or scrapped, which is a few times a year. So the repository allows an
update where the production ones do not, because a flask measured wrong is
corrected rather than superseded.

What it does not allow is changing a pattern's class silently. The class decides
how every mold off that pattern is judged, so moving one reaches back over every
scrap charge ever made against it. The update refuses a class change and says to
retire the pattern and register a new one, which leaves the old charges pointing
at the old class where they belong.
"""

from __future__ import annotations

from decimal import Decimal

from mullerbox.errors import BadInputError, DuplicateError, NotFoundError, RuleError
from mullerbox.heat.pattern import Pattern, Register
from mullerbox.spec.pattern import PatternClass
from mullerbox.store.coding import decode, encode
from mullerbox.store.connection import Book
from mullerbox.units.bulk import Pounds


def pattern_exists(book: Book, pattern_id: str) -> bool:
    return (
        book.one("SELECT pattern_id FROM pattern WHERE pattern_id = ?", (pattern_id,)) is not None
    )


def save_pattern(book: Book, pattern: Pattern) -> None:
    """Put a pattern on the register."""
    if not isinstance(pattern, Pattern):
        raise BadInputError("a pattern is expected")
    if pattern_exists(book, pattern.pattern_id):
        raise DuplicateError("pattern", pattern.pattern_id)
    with book.write():
        book.execute(
            "INSERT INTO pattern (pattern_id, name, pattern_class, flask_cu_ft,"
            " cavities, casting_lb) VALUES (?, ?, ?, ?, ?, ?)",
            (
                pattern.pattern_id,
                pattern.name,
                encode(pattern.pattern_class),
                str(pattern.flask_cubic_feet),
                pattern.cavities,
                str(pattern.casting_weight.value),
            ),
        )


def update_pattern(book: Book, pattern: Pattern) -> None:
    """Correct a pattern's measurements, refusing a change of class."""
    if not isinstance(pattern, Pattern):
        raise BadInputError("a pattern is expected")
    existing = load_pattern(book, pattern.pattern_id)
    if existing.pattern_class is not pattern.pattern_class:
        raise RuleError(
            f"pattern {pattern.pattern_id} is registered as "
            f"{existing.pattern_class.label} and every mold off it has been judged "
            "that way; retire it and register a new one rather than moving it"
        )
    with book.write():
        book.execute(
            "UPDATE pattern SET name = ?, flask_cu_ft = ?, cavities = ?,"
            " casting_lb = ? WHERE pattern_id = ?",
            (
                pattern.name,
                str(pattern.flask_cubic_feet),
                pattern.cavities,
                str(pattern.casting_weight.value),
                pattern.pattern_id,
            ),
        )


def load_pattern(book: Book, pattern_id: str) -> Pattern:
    """Rebuild one pattern, through the type's own checks."""
    row = book.one(
        "SELECT pattern_id, name, pattern_class, flask_cu_ft, cavities, casting_lb"
        " FROM pattern WHERE pattern_id = ?",
        (pattern_id,),
    )
    if row is None:
        raise NotFoundError("pattern", pattern_id)
    return Pattern(
        pattern_id=str(row["pattern_id"]),
        name=str(row["name"]),
        pattern_class=decode(str(row["pattern_class"]), PatternClass, "a pattern class"),
        flask_cubic_feet=Decimal(str(row["flask_cu_ft"])),
        cavities=int(row["cavities"]),
        casting_weight=Pounds(str(row["casting_lb"])),
    )


def load_register(book: Book) -> Register:
    """The whole register, in identifier order."""
    rows = book.all("SELECT pattern_id FROM pattern ORDER BY pattern_id")
    return Register(patterns=tuple(load_pattern(book, str(r["pattern_id"])) for r in rows))


def retire(book: Book, pattern_id: str) -> None:
    """Take a pattern off the register."""
    if not pattern_exists(book, pattern_id):
        raise NotFoundError("pattern", pattern_id)
    with book.write():
        book.execute("DELETE FROM pattern WHERE pattern_id = ?", (pattern_id,))


__all__ = [
    "load_pattern",
    "load_register",
    "pattern_exists",
    "retire",
    "save_pattern",
    "update_pattern",
]
