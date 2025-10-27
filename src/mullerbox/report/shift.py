"""The shift report: what the sand did, judged against the work that was on.

This is the first thing in the package that pulls the layers together, and the
shape it takes says something about all of them.

It takes readings, a spec sheet and a pattern class, and it resolves the bands
at the point of rendering. That means the same shift's readings render as two
different reports for two different classes, and both are correct. There is no
"the" verdict on a shift's sand; there is a verdict per class of work, and a
report that prints one number is hiding which question it answered. So the class
is on the report's own heading line.

The report never says a property is in band when it has no band for it. A
property the class does not control is printed with its reading and a dash where
the verdict goes, which is different from a tick and is meant to be.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from mullerbox.errors import BadInputError
from mullerbox.props.kind import PropertyKind, Reading
from mullerbox.report.layout import Column, Table, heading
from mullerbox.spec.band import Verdict
from mullerbox.spec.sheet import ResolvedSpec

VERDICT_MARK: dict[Verdict, str] = {
    Verdict.INSIDE: "ok",
    Verdict.BELOW: "low",
    Verdict.ABOVE: "high",
}

NOT_JUDGED = "-"


@dataclass(frozen=True)
class Line:
    """One property on the report."""

    kind: PropertyKind
    reading: Reading | None
    verdict: Verdict | None
    band_text: str

    @property
    def is_out(self) -> bool:
        return self.verdict is not None and self.verdict.is_out

    @property
    def is_judged(self) -> bool:
        return self.verdict is not None

    @property
    def mark(self) -> str:
        return NOT_JUDGED if self.verdict is None else VERDICT_MARK[self.verdict]


@dataclass(frozen=True)
class ShiftReport:
    """One shift's sand, against one class of work."""

    shift_on: date
    system_name: str
    resolved: ResolvedSpec
    lines: tuple[Line, ...]

    @property
    def out_of_band(self) -> tuple[Line, ...]:
        return tuple(line for line in self.lines if line.is_out)

    @property
    def unjudged(self) -> tuple[Line, ...]:
        return tuple(line for line in self.lines if not line.is_judged)

    @property
    def is_clean(self) -> bool:
        return not self.out_of_band

    def table(self) -> Table:
        """One row per reading, with the band in force and a verdict mark."""
        built = Table(
            columns=(
                Column("property"),
                Column.number("reading"),
                Column("band in force"),
                Column("verdict"),
            )
        )
        for line in self.lines:
            built.add(
                line.kind.label,
                "" if line.reading is None else str(line.reading),
                line.band_text,
                line.mark,
            )
        return built

    def render(self) -> list[str]:
        """The report as lines, with the excursions named under the table."""
        title = f"{self.system_name} on {self.shift_on}, judged as {self.resolved.pattern.label}"
        lines = heading(title)
        lines.extend(self.table().render())
        lines.append("")
        if self.is_clean:
            lines.append("every controlled property is in band")
        else:
            named = ", ".join(f"{n.kind.label} {n.mark}" for n in self.out_of_band)
            lines.append(f"out of band: {named}")
        if self.unjudged:
            names = ", ".join(n.kind.label for n in self.unjudged)
            lines.append(f"not controlled for this work: {names}")
        return lines

    def __str__(self) -> str:
        return "\n".join(self.render())


def shift_report(
    shift_on: date,
    system_name: str,
    resolved: ResolvedSpec,
    readings: Mapping[PropertyKind, Reading],
) -> ShiftReport:
    """Build a shift report from readings and the spec resolved for the work.

    Every property with a reading appears, whether or not it is controlled.
    Leaving the uncontrolled ones off would make the report shorter and would
    hide the case the lab most needs to see: a property drifting badly while
    the class in force happens not to hold it, which is fine today and is not
    fine the next time that class is scheduled.
    """
    if not isinstance(resolved, ResolvedSpec):
        raise BadInputError("a shift report needs a resolved spec")
    if not isinstance(shift_on, date):
        raise BadInputError("a shift report is dated")
    if not system_name.strip():
        raise BadInputError("a shift report names its system")
    lines: list[Line] = []
    for kind in sorted(readings, key=lambda k: k.name):
        reading = readings[kind]
        if resolved.judges(kind):
            band = resolved.band_for(kind)
            lines.append(
                Line(
                    kind=kind,
                    reading=reading,
                    verdict=band.verdict(reading),
                    band_text=str(band).removeprefix(f"{kind.label} "),
                )
            )
        else:
            lines.append(Line(kind=kind, reading=reading, verdict=None, band_text=NOT_JUDGED))
    return ShiftReport(
        shift_on=shift_on,
        system_name=system_name,
        resolved=resolved,
        lines=tuple(lines),
    )


__all__ = ["Line", "NOT_JUDGED", "ShiftReport", "VERDICT_MARK", "shift_report"]
