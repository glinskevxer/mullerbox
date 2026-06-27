"""Reading a sieve calibration sheet.

Screens are measured with an optical comparator and the result arrives as a
short sheet: a screen, a measured aperture, a date. It is the smallest file this
package reads and it carries the one thing nothing else can detect, which is why
it is worth a reader of its own rather than a hand entry per screen.

**The series is not on the sheet and cannot be guessed.** The comparator knows a
mesh number and not which stack the frame came out of, and two series can carry
different apertures behind the same number. So the series comes in as an
argument and every row is checked against it, which turns a frame from the wrong
drawer into a named refusal rather than a silently wrong nominal.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from mullerbox.errors import BadInputError
from mullerbox.ingest.reader import Problem, Row, Sheet, collect
from mullerbox.screens.series import ScreenSeries
from mullerbox.screens.wear import Check, StackCheck
from mullerbox.units.mesh import Mesh

COLUMNS = ("screen", "measured", "checked")


@dataclass(frozen=True)
class MeasuredRow:
    """One screen off the calibration sheet, before it is matched to a series."""

    mesh_number: int
    measured: int
    checked_on: date
    line: int


def measured_from(row: Row) -> MeasuredRow:
    """Build one measurement from one sheet row."""
    label = row.text("screen").strip().upper()
    if label in {"PAN", "PAN.", "P"}:
        raise BadInputError("the pan has no aperture to measure")
    try:
        number = int(label)
    except ValueError:
        raise BadInputError(f"{label!r} is not a screen number") from None
    try:
        measured = int(row.text("measured"))
    except ValueError:
        raise BadInputError(f"{row.text('measured')!r} is not an aperture in micrometres") from None
    try:
        checked = date.fromisoformat(row.text("checked"))
    except ValueError:
        raise BadInputError(f"{row.text('checked')!r} is not a date in yyyy-mm-dd form") from None
    return MeasuredRow(mesh_number=number, measured=measured, checked_on=checked, line=row.line)


@dataclass(frozen=True)
class WearLoad:
    """The checks that matched the series, and the rows that did not."""

    checks: tuple[Check, ...]
    problems: tuple[Problem, ...]

    @property
    def is_clean(self) -> bool:
        return not self.problems

    def stack(self, series: ScreenSeries, as_of: date) -> StackCheck:
        """Assemble what was loaded into a stack, which will say what is missing."""
        return StackCheck(series=series, checks=self.checks, checked_on=as_of)

    @property
    def worn(self) -> tuple[Check, ...]:
        return tuple(c for c in self.checks if c.is_worn or c.is_wrong_screen)

    def __str__(self) -> str:
        return f"{len(self.checks)} screens measured, {len(self.problems)} problems"


def load_wear(sheet: Sheet, series: ScreenSeries) -> WearLoad:
    """Read a calibration sheet against the series the frames belong to."""
    if not isinstance(sheet, Sheet):
        raise BadInputError("a parsed sheet is expected")
    if not isinstance(series, ScreenSeries):
        raise BadInputError("a screen series is expected")
    sheet.require_columns(*COLUMNS)
    built, problems = collect(sheet, measured_from)
    by_number = {mesh.number: mesh for mesh in series.meshes}
    checks: list[Check] = []
    kept = list(problems)
    seen: set[int] = set()
    for row in built:
        if not isinstance(row, MeasuredRow):
            continue
        mesh = by_number.get(row.mesh_number)
        if mesh is None:
            kept.append(
                Problem(
                    line=row.line,
                    reason=(
                        f"screen {row.mesh_number} is not on series {series.name}, "
                        "so this frame came out of the wrong drawer"
                    ),
                    raw={"screen": str(row.mesh_number)},
                )
            )
            continue
        if row.mesh_number in seen:
            kept.append(
                Problem(
                    line=row.line,
                    reason=f"screen {row.mesh_number} was measured twice",
                    raw={"screen": str(row.mesh_number)},
                )
            )
            continue
        seen.add(row.mesh_number)
        checks.append(
            Check(
                mesh=mesh,
                measured_micrometres=row.measured,
                checked_on=row.checked_on,
            )
        )
    kept.sort(key=lambda p: p.line)
    return WearLoad(checks=tuple(checks), problems=tuple(kept))


def unmeasured(load: WearLoad, series: ScreenSeries) -> tuple[Mesh, ...]:
    """Working screens the sheet did not cover."""
    if not isinstance(series, ScreenSeries):
        raise BadInputError("a screen series is expected")
    measured = {check.mesh for check in load.checks}
    return tuple(step.mesh for step in series.working_steps if step.mesh not in measured)


__all__ = ["COLUMNS", "MeasuredRow", "WearLoad", "load_wear", "measured_from", "unmeasured"]
