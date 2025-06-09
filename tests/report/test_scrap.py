from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from mullerbox.defect.kind import Culprit, DefectKind
from mullerbox.defect.scrap import report_on
from mullerbox.errors import BadInputError
from mullerbox.heat.heat import Disposition
from mullerbox.report.scrap import (
    combined_sand_share,
    scrap_sheet,
    totals_line,
)
from mullerbox.spec.pattern import PatternClass
from mullerbox.units.scales import Permeability
from tests.defect.helpers import readings, spec_for
from tests.heat.helpers import casting, heat, mold

HEAVY = PatternClass.HEAVY_JOBBING
SPECS = {cls: spec_for(cls) for cls in PatternClass}
BAD_SAND = readings(PERMEABILITY=Permeability(40))


def built(pending: bool = False):  # type: ignore[no-untyped-def]
    castings = [
        casting("C-1", "100", Disposition.SCRAPPED),
        casting("C-2", "300", Disposition.SHIPPED),
    ]
    if pending:
        castings.append(casting("C-3", "200", Disposition.PENDING))
    the_heat = heat(mold("M-1", pattern=HEAVY, castings=tuple(castings)))
    return report_on(the_heat, {"C-1": (DefectKind.BLOW,)}, SPECS, BAD_SAND)


class TestTheSheet:
    def test_it_names_the_heat(self) -> None:
        assert "scrap on heat H-1001" in scrap_sheet(built()).render()[0]

    def test_every_culprit_gets_a_row(self) -> None:
        table = scrap_sheet(built()).culprit_table()
        assert len(table) == len(Culprit)

    def test_the_shares_are_shown_as_percentages(self) -> None:
        rendered = str(scrap_sheet(built()))
        assert "25.00%" in rendered

    def test_a_casting_row_names_its_class_and_properties(self) -> None:
        rendered = str(scrap_sheet(built()))
        assert "heavy jobbing" in rendered
        assert "permeability" in rendered

    def test_the_implicated_properties_are_listed(self) -> None:
        assert "most cited first" in str(scrap_sheet(built()))

    def test_a_clean_heat_has_no_casting_table(self) -> None:
        clean = report_on(heat(mold("M-1", pattern=HEAVY)), {}, SPECS, readings())
        rendered = str(scrap_sheet(clean))
        assert "charged to" in rendered
        assert "casting  " not in rendered

    def test_no_rendered_line_has_trailing_space(self) -> None:
        for line in scrap_sheet(built(pending=True)).render():
            assert line == line.rstrip()


class TestPendingIsImpossibleToMiss:
    def test_it_is_called_out(self) -> None:
        sheet = scrap_sheet(built(pending=True))
        assert sheet.has_pending
        assert "NOT YET JUDGED" in str(sheet)

    def test_it_says_the_shares_will_move(self) -> None:
        assert "the shares below will move" in str(scrap_sheet(built(pending=True)))

    def test_it_sits_above_the_totals(self) -> None:
        lines = scrap_sheet(built(pending=True)).render()
        pending_at = next(i for i, x in enumerate(lines) if "NOT YET JUDGED" in x)
        scrapped_at = next(i for i, x in enumerate(lines) if x.startswith("scrapped"))
        assert pending_at < scrapped_at

    def test_a_fully_judged_heat_says_nothing_about_it(self) -> None:
        sheet = scrap_sheet(built())
        assert not sheet.has_pending
        assert "NOT YET JUDGED" not in str(sheet)


class TestTotalsLine:
    def test_it_is_one_line(self) -> None:
        assert "\n" not in totals_line(built())

    def test_it_names_the_sand_share(self) -> None:
        assert "to sand" in totals_line(built())

    def test_it_flags_unjudged_weight(self) -> None:
        assert "unjudged" in totals_line(built(pending=True))
        assert "unjudged" not in totals_line(built())

    def test_it_wants_a_report(self) -> None:
        bad: Any = "H-1001"
        with pytest.raises(BadInputError, match="scrap report is expected"):
            totals_line(bad)


class TestCombining:
    def test_it_weights_by_what_each_heat_poured(self) -> None:
        assert combined_sand_share([built(), built()]) == Decimal("0.2500")

    def test_one_heat_is_its_own_share(self) -> None:
        assert combined_sand_share([built()]) == built().sand_share

    def test_nothing_to_combine_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="no heats to combine"):
            combined_sand_share([])

    def test_it_wants_reports(self) -> None:
        bad: Any = ["H-1001"]
        with pytest.raises(BadInputError, match="only scrap reports"):
            combined_sand_share(bad)


def test_the_sheet_wants_a_report() -> None:
    bad: Any = "H-1001"
    with pytest.raises(BadInputError, match="rendered from a scrap report"):
        scrap_sheet(bad)
