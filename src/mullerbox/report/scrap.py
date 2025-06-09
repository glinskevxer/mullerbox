"""Rendering a heat's scrap for the morning meeting.

The report leads with the sand's share because that is the number the sand
department is asked about, and it prints the other shares beside it because a
sand share of eight percent means nothing without knowing whether the total was
nine or forty.

Pending weight gets its own line, above the totals rather than below them. A
heat that is half inspected has a sand share computed on half a heat, and the
share will move when the rest is judged. Putting the pending line where it
cannot be missed is the difference between a number that gets quoted with a
caveat and one that gets quoted.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from mullerbox.defect.kind import Culprit
from mullerbox.defect.scrap import ScrapReport
from mullerbox.errors import BadInputError
from mullerbox.report.layout import Column, Table, heading
from mullerbox.units.bulk import Pounds


@dataclass(frozen=True)
class ScrapSheet:
    """A rendered view of one heat's scrap."""

    report: ScrapReport

    def __post_init__(self) -> None:
        if not isinstance(self.report, ScrapReport):
            raise BadInputError("a scrap sheet is rendered from a scrap report")

    @property
    def has_pending(self) -> bool:
        return not self.report.pending.is_zero

    def share_of(self, culprit: Culprit) -> Decimal:
        return self.report.share_charged_to(culprit)

    def culprit_table(self) -> Table:
        built = Table(
            columns=(
                Column("charged to"),
                Column.number("weight"),
                Column.number("share of pour"),
            )
        )
        for culprit in Culprit:
            weight = self.report.weight_charged_to(culprit)
            built.add(culprit.label, str(weight), f"{self.share_of(culprit):.2%}")
        return built

    def casting_table(self) -> Table:
        built = Table(
            columns=(
                Column("casting"),
                Column("mold"),
                Column("class"),
                Column.number("weight"),
                Column("charged to"),
                Column("properties"),
            )
        )
        for charge in sorted(self.report.charges, key=lambda c: c.casting.casting_id):
            built.add(
                charge.casting.casting_id,
                charge.mold_id,
                charge.pattern.label,
                str(charge.weight),
                charge.culprit.label,
                ", ".join(k.label for k in charge.sand_properties),
            )
        return built

    def render(self) -> list[str]:
        lines = heading(f"scrap on heat {self.report.heat_number}")
        lines.append(f"poured {self.report.poured}")
        if self.has_pending:
            lines.append(f"NOT YET JUDGED {self.report.pending} - the shares below will move")
        lines.append(f"scrapped {self.report.scrapped}")
        lines.append("")
        lines.extend(self.culprit_table().render())
        if self.report.charges:
            lines.append("")
            lines.extend(self.casting_table().render())
        implicated = self.report.properties_implicated
        if implicated:
            lines.append("")
            named = ", ".join(k.label for k in implicated)
            lines.append(f"sand properties implicated, most cited first: {named}")
        return lines

    def __str__(self) -> str:
        return "\n".join(self.render())


def scrap_sheet(report: ScrapReport) -> ScrapSheet:
    return ScrapSheet(report=report)


def totals_line(report: ScrapReport) -> str:
    """One line for a shift roll up, where a whole sheet is too much."""
    if not isinstance(report, ScrapReport):
        raise BadInputError("a scrap report is expected")
    sand = report.weight_charged_to(Culprit.SAND)
    pending = "" if report.pending.is_zero else f", {report.pending} unjudged"
    return (
        f"heat {report.heat_number}: {report.scrapped} scrapped of {report.poured}, "
        f"{sand} to sand{pending}"
    )


def combined_sand_share(reports: list[ScrapReport]) -> Decimal:
    """The sand's share across several heats, weighted by what each poured."""
    if not reports:
        raise BadInputError("no heats to combine")
    poured = Pounds.zero()
    charged = Pounds.zero()
    for report in reports:
        if not isinstance(report, ScrapReport):
            raise BadInputError("only scrap reports can be combined")
        poured = poured + report.poured
        charged = charged + report.weight_charged_to(Culprit.SAND)
    if poured.is_zero:
        raise BadInputError("the heats poured no metal between them")
    return charged.fraction_of(poured).quantize(Decimal("0.0001"))


__all__ = ["ScrapSheet", "combined_sand_share", "scrap_sheet", "totals_line"]
