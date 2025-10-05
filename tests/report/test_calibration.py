from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest

from mullerbox.cal.instrument import Instrument, InstrumentKind
from mullerbox.cal.window import CalibrationWindow
from mullerbox.errors import BadInputError
from mullerbox.props.kind import PropertyKind
from mullerbox.props.result import Result
from mullerbox.report.calibration import NOTICE_DAYS, calibration_report
from mullerbox.units.percent import Percent

AS_OF = date(2025, 10, 1)
GOOD = CalibrationWindow(date(2025, 1, 6), date(2026, 1, 6), "C-1")
EXPIRED = CalibrationWindow(date(2025, 1, 6), date(2025, 8, 1), "C-2")
SOON = CalibrationWindow(date(2025, 1, 6), AS_OF + timedelta(days=10), "C-3")


def rammer(*windows: CalibrationWindow, tag: str = "RAM-1") -> Instrument:
    return Instrument(tag=tag, kind=InstrumentKind.COMPACTABILITY, windows=windows)


def result(when: date, tag: str = "RAM-1", sample: str = "S-1") -> Result:
    return Result(
        kind=PropertyKind.COMPACTABILITY,
        reading=Percent(41),
        instrument_tag=tag,
        tested_on=when,
        sample_id=sample,
    )


class TestLapses:
    def test_an_instrument_with_no_cover_is_lapsed(self) -> None:
        report = calibration_report({"RAM-1": rammer(EXPIRED)}, [], AS_OF)
        assert len(report.lapsed) == 1
        assert report.lapsed[0].instrument.tag == "RAM-1"

    def test_it_counts_the_readings_it_invalidated(self) -> None:
        results = [
            result(date(2025, 8, 15), sample="S-1"),
            result(date(2025, 9, 15), sample="S-2"),
            result(date(2025, 5, 1), sample="S-3"),
        ]
        report = calibration_report({"RAM-1": rammer(EXPIRED)}, results, AS_OF)
        assert report.lapsed[0].count == 2
        assert report.results_invalidated == 2

    def test_it_names_the_earliest_one(self) -> None:
        results = [result(date(2025, 9, 15), sample="S-1"), result(date(2025, 8, 15), sample="S-2")]
        report = calibration_report({"RAM-1": rammer(EXPIRED)}, results, AS_OF)
        assert report.lapsed[0].earliest == date(2025, 8, 15)

    def test_a_lapse_with_no_readings_behind_it_has_none(self) -> None:
        report = calibration_report({"RAM-1": rammer(EXPIRED)}, [], AS_OF)
        assert report.lapsed[0].earliest is None
        assert report.lapsed[0].count == 0

    def test_readings_from_another_instrument_are_not_counted(self) -> None:
        results = [result(date(2025, 9, 1), tag="RAM-2")]
        report = calibration_report({"RAM-1": rammer(EXPIRED)}, results, AS_OF)
        assert report.lapsed[0].count == 0

    def test_the_worst_lapse_sorts_first(self) -> None:
        instruments = {
            "RAM-1": rammer(EXPIRED),
            "RAM-2": rammer(EXPIRED, tag="RAM-2"),
        }
        results = [
            result(date(2025, 9, 1), tag="RAM-2", sample="S-1"),
            result(date(2025, 9, 2), tag="RAM-2", sample="S-2"),
            result(date(2025, 9, 3), tag="RAM-1", sample="S-3"),
        ]
        report = calibration_report(instruments, results, AS_OF)
        assert report.lapsed[0].instrument.tag == "RAM-2"

    def test_an_instrument_with_no_certificate_at_all_is_lapsed(self) -> None:
        report = calibration_report({"RAM-1": rammer()}, [], AS_OF)
        assert len(report.lapsed) == 1


class TestFallingDue:
    def test_something_due_inside_the_window_is_listed(self) -> None:
        report = calibration_report({"RAM-1": rammer(SOON)}, [], AS_OF)
        assert len(report.falling_due) == 1
        assert report.falling_due[0].days_left == 10

    def test_something_due_far_out_is_not(self) -> None:
        report = calibration_report({"RAM-1": rammer(GOOD)}, [], AS_OF)
        assert report.falling_due == ()
        assert report.is_clean

    def test_exactly_on_the_notice_window_is_listed(self) -> None:
        edge = CalibrationWindow(date(2025, 1, 6), AS_OF + timedelta(days=NOTICE_DAYS), "C-9")
        report = calibration_report({"RAM-1": rammer(edge)}, [], AS_OF)
        assert len(report.falling_due) == 1

    def test_the_soonest_sorts_first(self) -> None:
        later = CalibrationWindow(date(2025, 1, 6), AS_OF + timedelta(days=30), "C-9")
        instruments = {"RAM-1": rammer(SOON), "RAM-2": rammer(later, tag="RAM-2")}
        report = calibration_report(instruments, [], AS_OF)
        assert report.falling_due[0].instrument.tag == "RAM-1"

    def test_a_lapsed_instrument_is_not_also_falling_due(self) -> None:
        report = calibration_report({"RAM-1": rammer(EXPIRED)}, [], AS_OF)
        assert report.falling_due == ()


class TestRendering:
    def test_the_lapse_section_comes_first(self) -> None:
        instruments = {"RAM-1": rammer(EXPIRED), "RAM-2": rammer(SOON, tag="RAM-2")}
        lines = calibration_report(instruments, [], AS_OF).render()
        lapsed_at = next(i for i, x in enumerate(lines) if "LAPSED" in x)
        falling_at = next(i for i, x in enumerate(lines) if "falling due" in x)
        assert lapsed_at < falling_at

    def test_it_says_readings_do_not_count(self) -> None:
        text = str(calibration_report({"RAM-1": rammer(EXPIRED)}, [], AS_OF))
        assert "do not count" in text

    def test_a_clean_book_says_so(self) -> None:
        text = str(calibration_report({"RAM-1": rammer(GOOD)}, [], AS_OF))
        assert "room to spare" in text

    def test_an_empty_book_is_clean(self) -> None:
        assert calibration_report({}, [], AS_OF).is_clean

    def test_no_line_has_trailing_space(self) -> None:
        instruments = {"RAM-1": rammer(EXPIRED), "RAM-2": rammer(SOON, tag="RAM-2")}
        for line in calibration_report(instruments, [], AS_OF).render():
            assert line == line.rstrip()

    def test_it_wants_a_date(self) -> None:
        bad: Any = "2025-10-01"
        with pytest.raises(BadInputError, match="a date is expected"):
            calibration_report({}, [], bad)
