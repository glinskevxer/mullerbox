"""Reading a sieve shaker's export into an analysis.

The shaker writes one row per screen, which means one analysis is spread across
twelve rows and the reader has to group before it can build anything. That
grouping is where the interesting failure lives: a file with eleven rows for one
sample is not eleven screens' worth of information, it is a broken analysis, and
the missing screen has to surface as one problem against the sample rather than
as a silently short stack.

So this reader works in two passes. The first turns rows into readings and keeps
the row level problems. The second assembles each sample's readings into a
``SieveAnalysis``, which runs the coverage and closure checks, and turns any
refusal into one problem naming the sample. A sample that fails assembly does
not take the other samples with it.
"""

from __future__ import annotations

from dataclasses import dataclass

from mullerbox.errors import BadInputError, SandError
from mullerbox.ingest.reader import Problem, Row, Sheet, collect
from mullerbox.screens.analysis import Retained, SieveAnalysis
from mullerbox.screens.series import ScreenSeries
from mullerbox.units.mass import Grams
from mullerbox.units.mesh import PAN_LABEL

COLUMNS = ("sample", "screen", "retained", "charged")


@dataclass(frozen=True)
class ScreenRow:
    """One weighed screen off the export."""

    sample_id: str
    label: str
    retained: Grams
    charged: Grams
    line: int


def screen_row_from(row: Row) -> ScreenRow:
    label = row.text("screen").strip().upper()
    return ScreenRow(
        sample_id=row.text("sample"),
        label=PAN_LABEL if label in {"PAN", "PAN.", "P"} else label,
        retained=Grams(row.text("retained")),
        charged=Grams(row.text("charged")),
        line=row.line,
    )


@dataclass(frozen=True)
class SieveLoad:
    """The analyses that assembled, and everything that did not."""

    analyses: dict[str, SieveAnalysis]
    problems: tuple[Problem, ...]

    @property
    def is_clean(self) -> bool:
        return not self.problems

    @property
    def samples(self) -> tuple[str, ...]:
        return tuple(sorted(self.analyses))

    def __str__(self) -> str:
        return f"{len(self.analyses)} analyses, {len(self.problems)} problems"


def load_sieve(sheet: Sheet, series: ScreenSeries) -> SieveLoad:
    """Read a shaker export against one screen series."""
    if not isinstance(sheet, Sheet):
        raise BadInputError("a parsed sheet is expected")
    if not isinstance(series, ScreenSeries):
        raise BadInputError("a screen series is expected")
    sheet.require_columns(*COLUMNS)
    built, problems = collect(sheet, screen_row_from)
    rows = [r for r in built if isinstance(r, ScreenRow)]

    by_label = {step.label: step.mesh for step in series.steps}
    grouped: dict[str, list[ScreenRow]] = {}
    kept_problems = list(problems)
    for row in rows:
        if row.label not in by_label:
            kept_problems.append(
                Problem(
                    line=row.line,
                    reason=f"screen {row.label} is not on series {series.name}",
                    raw={"sample": row.sample_id, "screen": row.label},
                )
            )
            continue
        grouped.setdefault(row.sample_id, []).append(row)

    analyses: dict[str, SieveAnalysis] = {}
    for sample_id in sorted(grouped):
        group = grouped[sample_id]
        charges = {r.charged for r in group}
        first_line = min(r.line for r in group)
        if len(charges) > 1:
            kept_problems.append(
                Problem(
                    line=first_line,
                    reason=(f"sample {sample_id} carries {len(charges)} different charged masses"),
                    raw={"sample": sample_id},
                )
            )
            continue
        try:
            analysis = SieveAnalysis(
                series=series,
                charged=charges.pop(),
                readings=tuple(Retained(mesh=by_label[r.label], mass=r.retained) for r in group),
            )
            # Closure is lazy on the type, because a caller that only wants the
            # raw masses is entitled to them. A loader is not that caller: an
            # analysis that will not close is not fit to derive anything from,
            # so it is asked here and refused here rather than being handed on
            # to fail at whatever happens to touch it first.
            analysis.require_closure()
            analyses[sample_id] = analysis
        except SandError as exc:
            kept_problems.append(
                Problem(
                    line=first_line,
                    reason=f"sample {sample_id}: {exc}",
                    raw={"sample": sample_id},
                )
            )
    kept_problems.sort(key=lambda p: p.line)
    return SieveLoad(analyses=analyses, problems=tuple(kept_problems))


__all__ = ["COLUMNS", "ScreenRow", "SieveLoad", "load_sieve", "screen_row_from"]
