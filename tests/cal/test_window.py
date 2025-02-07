from __future__ import annotations

from datetime import date

import pytest

from mullerbox.cal.window import CalibrationWindow
from mullerbox.errors import BadInputError

JAN = date(2025, 1, 6)
APR = date(2025, 4, 6)


def window(calibrated: date = JAN, due: date = APR, cert: str = "C-1188") -> CalibrationWindow:
    return CalibrationWindow(calibrated_on=calibrated, due_on=due, certificate=cert)


class TestConstruction:
    def test_a_window_runs_forward(self) -> None:
        with pytest.raises(BadInputError, match="due after it was done"):
            window(calibrated=APR, due=JAN)

    def test_a_zero_length_window_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="due after it was done"):
            window(calibrated=JAN, due=JAN)

    def test_a_forgotten_instrument_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="not a calibration interval"):
            window(calibrated=date(2023, 1, 1), due=date(2025, 6, 1))

    def test_dates_have_to_be_dates(self) -> None:
        with pytest.raises(BadInputError, match="calibration date is a date"):
            window(calibrated="2025-01-06")  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="due date is a date"):
            window(due="2025-04-06")  # type: ignore[arg-type]

    def test_a_certificate_number_is_required(self) -> None:
        with pytest.raises(BadInputError, match="certificate number"):
            window(cert="   ")

    def test_opened_from_an_interval(self) -> None:
        opened = CalibrationWindow.opened(JAN, 90, "C-1188")
        assert opened.due_on == date(2025, 4, 6)
        assert opened.interval_days == 90

    def test_an_interval_has_to_be_a_whole_positive_number_of_days(self) -> None:
        with pytest.raises(BadInputError, match="whole number of days"):
            CalibrationWindow.opened(JAN, 90.0, "C-1188")  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="whole number of days"):
            CalibrationWindow.opened(JAN, True, "C-1188")
        with pytest.raises(BadInputError, match="at least a day"):
            CalibrationWindow.opened(JAN, 0, "C-1188")


class TestTheDueDateIsTheFirstBadDay:
    def test_good_on_the_day_it_was_calibrated(self) -> None:
        assert window().covers(JAN)

    def test_good_on_the_day_before_it_falls_due(self) -> None:
        assert window().covers(date(2025, 4, 5))

    def test_not_good_on_the_day_it_falls_due(self) -> None:
        assert not window().covers(APR)

    def test_not_good_before_it_was_calibrated(self) -> None:
        assert not window().covers(date(2025, 1, 5))

    def test_the_last_good_day_is_the_day_before_due(self) -> None:
        assert window().last_good_day == date(2025, 4, 5)

    def test_covers_wants_a_date(self) -> None:
        with pytest.raises(BadInputError, match="checked against a date"):
            window().covers("2025-02-01")  # type: ignore[arg-type]


class TestDaysLeft:
    def test_counts_down_to_the_due_date(self) -> None:
        assert window().days_left_on(date(2025, 4, 5)) == 1
        assert window().days_left_on(APR) == 0

    def test_goes_negative_past_due(self) -> None:
        assert window().days_left_on(date(2025, 4, 16)) == -10

    def test_wants_a_date(self) -> None:
        with pytest.raises(BadInputError, match="checked against a date"):
            window().days_left_on("2025-04-01")  # type: ignore[arg-type]


class TestOverlap:
    def test_two_windows_meeting_end_to_end_do_not_overlap(self) -> None:
        first = window(JAN, APR)
        second = window(APR, date(2025, 7, 6))
        assert not first.overlaps(second)
        assert not second.overlaps(first)

    def test_a_recalibration_before_due_does_overlap(self) -> None:
        first = window(JAN, APR)
        second = window(date(2025, 3, 1), date(2025, 6, 1))
        assert first.overlaps(second)

    def test_overlap_wants_a_window(self) -> None:
        with pytest.raises(BadInputError, match="only compares against a window"):
            window().overlaps(APR)  # type: ignore[arg-type]


def test_str_reads_as_the_certificate_and_its_good_span() -> None:
    assert str(window()) == "C-1188 2025-01-06 to 2025-04-05"
