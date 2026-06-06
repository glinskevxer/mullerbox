from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from mullerbox.cal.instrument import Instrument, InstrumentKind
from mullerbox.cal.window import CalibrationWindow
from mullerbox.errors import BadInputError
from mullerbox.programme.schedule import Frequency, Schedule
from mullerbox.props.kind import PropertyKind
from mullerbox.report.due import Consequence, due_sheet
from mullerbox.screens.series import ScreenSeries, Step
from mullerbox.screens.wear import Check
from mullerbox.units.mesh import Mesh

AS_OF = date(2026, 6, 8)
GOOD = CalibrationWindow(date(2026, 1, 6), date(2027, 1, 6), "C-1")
EXPIRED = CalibrationWindow(date(2025, 1, 6), date(2026, 1, 6), "C-2")
COARSE = Mesh(30, 600)
FINE = Mesh(70, 212)
SMALL = ScreenSeries(name="rig", steps=(Step(COARSE, 20), Step(FINE, 50), Step(Mesh.pan(), 300)))


def rammer(*windows: CalibrationWindow) -> Instrument:
    return Instrument(tag="RAM-1", kind=InstrumentKind.COMPACTABILITY, windows=windows)


def schedule() -> Schedule:
    return Schedule(intervals={PropertyKind.LOI: Frequency.MONTHLY})


class TestRankingIsByConsequence:
    def test_a_lapsed_calibration_outranks_an_overdue_test(self) -> None:
        sheet = due_sheet(AS_OF, {"RAM-1": rammer(EXPIRED)}, schedule(), {})
        assert sheet.items[0].what == "calibration"
        assert sheet.items[0].consequence is Consequence.READINGS_VOID

    def test_an_overdue_test_costs_nothing_yet(self) -> None:
        sheet = due_sheet(AS_OF, {}, schedule(), {})
        assert sheet.items[0].consequence is Consequence.NOTHING_YET

    def test_lateness_only_breaks_ties_inside_a_consequence(self) -> None:
        older = Instrument(
            tag="A-1",
            kind=InstrumentKind.MUFFLE,
            windows=(CalibrationWindow(date(2024, 1, 6), date(2025, 1, 6), "C-9"),),
        )
        sheet = due_sheet(AS_OF, {"RAM-1": rammer(EXPIRED), "A-1": older}, None, {})
        assert sheet.items[0].detail.startswith("A-1")

    def test_a_sound_book_is_clear(self) -> None:
        sheet = due_sheet(AS_OF, {"RAM-1": rammer(GOOD)}, None, {})
        assert sheet.is_clear
        assert "nothing is due" in str(sheet)


class TestEachSourceIsOptional:
    def test_no_programme_still_lists_calibrations(self) -> None:
        sheet = due_sheet(AS_OF, {"RAM-1": rammer(EXPIRED)}, None, {})
        assert len(sheet.items) == 1

    def test_no_instruments_still_lists_tests(self) -> None:
        sheet = due_sheet(AS_OF, {}, schedule(), {})
        assert sheet.items[0].what == "test"

    def test_no_series_means_no_wear_items(self) -> None:
        sheet = due_sheet(AS_OF, {}, None, {})
        assert sheet.is_clear


class TestSieveWear:
    def test_a_screen_never_measured_is_suspect(self) -> None:
        sheet = due_sheet(AS_OF, {}, None, {}, SMALL, {})
        assert len(sheet.items) == 2
        assert all(i.consequence is Consequence.READINGS_SUSPECT for i in sheet.items)
        assert "never been measured" in sheet.items[0].detail

    def test_a_good_screen_is_not_listed(self) -> None:
        checks = {
            COARSE: Check(mesh=COARSE, measured_micrometres=600, checked_on=AS_OF),
            FINE: Check(mesh=FINE, measured_micrometres=212, checked_on=AS_OF),
        }
        assert due_sheet(AS_OF, {}, None, {}, SMALL, checks).is_clear

    def test_a_worn_screen_is(self) -> None:
        checks = {
            COARSE: Check(mesh=COARSE, measured_micrometres=660, checked_on=AS_OF),
            FINE: Check(mesh=FINE, measured_micrometres=212, checked_on=AS_OF),
        }
        sheet = due_sheet(AS_OF, {}, None, {}, SMALL, checks)
        assert len(sheet.items) == 1
        assert "off nominal" in sheet.items[0].detail

    def test_the_pan_is_never_listed(self) -> None:
        sheet = due_sheet(AS_OF, {}, None, {}, SMALL, {})
        assert not any("PAN" in i.detail for i in sheet.items)


class TestRendering:
    def test_it_counts_what_is_costing_something(self) -> None:
        sheet = due_sheet(AS_OF, {"RAM-1": rammer(EXPIRED)}, schedule(), {})
        assert len(sheet.costing_now) == 1
        assert "1 of them costing something now" in str(sheet)

    def test_never_done_reads_as_never(self) -> None:
        sheet = due_sheet(AS_OF, {}, schedule(), {})
        assert "never" in str(sheet)

    def test_no_line_has_trailing_space(self) -> None:
        sheet = due_sheet(AS_OF, {"RAM-1": rammer(EXPIRED)}, schedule(), {})
        for line in sheet.render():
            assert line == line.rstrip()

    def test_it_wants_a_date(self) -> None:
        bad: Any = "2026-06-08"
        with pytest.raises(BadInputError, match="a date is expected"):
            due_sheet(bad, {}, None, {})

    def test_every_consequence_has_a_label(self) -> None:
        assert all(c.label for c in Consequence)
