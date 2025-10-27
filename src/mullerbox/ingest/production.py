"""Reading the pour log and the inspection sheet.

These two files come from opposite ends of the plant and they disagree, which is
the point of reading them together.

The **pour log** is written at the ladle: date, pattern class, metal poured,
sand in the molds. It is the source of the sand to metal ratio, and it is the
one number in this package that nothing in the lab can check.

The **inspection sheet** is written at the grinding bench, days later: casting,
disposition, and whatever defects were found. One casting can carry several
defects and usually does.

The readers stay separate because the files arrive separately and one is often
days behind the other. What they share is that neither is allowed to invent the
other's facts: the pour log does not know what scrapped, and the inspection
sheet does not know what the ratio was.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from mullerbox.burnout.pour import Pour
from mullerbox.defect.kind import DefectKind, parse_defect
from mullerbox.errors import BadInputError
from mullerbox.heat.heat import Disposition
from mullerbox.ingest.reader import Problem, Row, Sheet, collect
from mullerbox.spec.pattern import PatternClass, parse_pattern_class
from mullerbox.units.bulk import Pounds

POUR_COLUMNS = ("poured", "pattern", "metal", "sand")
INSPECTION_COLUMNS = ("casting", "disposition", "defects")


def _read_date(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise BadInputError(f"{text!r} is not a date in yyyy-mm-dd form") from None


def pour_from(row: Row) -> Pour:
    return Pour(
        poured_on=_read_date(row.text("poured")),
        pattern=parse_pattern_class(row.text("pattern")),
        metal=Pounds(row.text("metal")),
        sand=Pounds(row.text("sand")),
    )


@dataclass(frozen=True)
class Inspection:
    """One casting's verdict and the defects written against it."""

    casting_id: str
    disposition: Disposition
    defects: tuple[DefectKind, ...]

    def __post_init__(self) -> None:
        if not self.casting_id.strip():
            raise BadInputError("an inspection names a casting")
        if not isinstance(self.disposition, Disposition):
            raise BadInputError("an inspection carries a disposition")
        if self.disposition is Disposition.SHIPPED and self.defects:
            raise BadInputError(
                f"casting {self.casting_id} shipped with {len(self.defects)} "
                "defects written against it"
            )

    @property
    def is_scrap(self) -> bool:
        return self.disposition is Disposition.SCRAPPED


def _read_disposition(text: str) -> Disposition:
    key = text.strip().lower()
    table = {
        "shipped": Disposition.SHIPPED,
        "ship": Disposition.SHIPPED,
        "ok": Disposition.SHIPPED,
        "scrapped": Disposition.SCRAPPED,
        "scrap": Disposition.SCRAPPED,
        "pending": Disposition.PENDING,
        "held": Disposition.PENDING,
        "": Disposition.PENDING,
    }
    if key not in table:
        raise BadInputError(f"{text!r} is not a disposition")
    return table[key]


def inspection_from(row: Row) -> Inspection:
    """Build one inspection. Several defects come semicolon separated."""
    raw = row.optional("defects")
    defects = tuple(parse_defect(part) for part in (p.strip() for p in raw.split(";")) if part)
    return Inspection(
        casting_id=row.text("casting"),
        disposition=_read_disposition(row.optional("disposition")),
        defects=defects,
    )


@dataclass(frozen=True)
class PourLoad:
    """Pour records that read, and the rows that did not."""

    pours: tuple[Pour, ...]
    problems: tuple[Problem, ...]

    @property
    def is_clean(self) -> bool:
        return not self.problems

    def on(self, when: date) -> tuple[Pour, ...]:
        if not isinstance(when, date):
            raise BadInputError("a date is expected")
        return tuple(p for p in self.pours if p.poured_on == when)

    def of(self, pattern: PatternClass) -> tuple[Pour, ...]:
        if not isinstance(pattern, PatternClass):
            raise BadInputError("a pattern class is expected")
        return tuple(p for p in self.pours if p.pattern is pattern)


@dataclass(frozen=True)
class InspectionLoad:
    """Inspections that read, and the rows that did not."""

    inspections: tuple[Inspection, ...]
    problems: tuple[Problem, ...]

    @property
    def is_clean(self) -> bool:
        return not self.problems

    @property
    def scrapped(self) -> tuple[Inspection, ...]:
        return tuple(i for i in self.inspections if i.is_scrap)

    @property
    def defects_by_casting(self) -> dict[str, tuple[DefectKind, ...]]:
        """The mapping the scrap report wants."""
        return {i.casting_id: i.defects for i in self.inspections if i.defects}


def load_pours(sheet: Sheet) -> PourLoad:
    """Read a pour log, keeping the rows that would not parse."""
    if not isinstance(sheet, Sheet):
        raise BadInputError("a parsed sheet is expected")
    sheet.require_columns(*POUR_COLUMNS)
    built, problems = collect(sheet, pour_from)
    return PourLoad(
        pours=tuple(p for p in built if isinstance(p, Pour)),
        problems=tuple(problems),
    )


def load_inspections(sheet: Sheet) -> InspectionLoad:
    """Read an inspection sheet, keeping the rows that would not parse."""
    if not isinstance(sheet, Sheet):
        raise BadInputError("a parsed sheet is expected")
    sheet.require_columns(*INSPECTION_COLUMNS)
    built, problems = collect(sheet, inspection_from)
    return InspectionLoad(
        inspections=tuple(i for i in built if isinstance(i, Inspection)),
        problems=tuple(problems),
    )


__all__ = [
    "INSPECTION_COLUMNS",
    "Inspection",
    "InspectionLoad",
    "POUR_COLUMNS",
    "PourLoad",
    "inspection_from",
    "load_inspections",
    "load_pours",
    "pour_from",
]
