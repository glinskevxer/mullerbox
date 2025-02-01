from __future__ import annotations

from decimal import Decimal

import pytest

from mullerbox.errors import BadInputError
from mullerbox.gfn.distribution import (
    Distribution,
    Grading,
    _sliding_best,
    grade,
)
from mullerbox.gfn.fineness import fineness_of
from mullerbox.units.percent import Percent
from tests.gfn.helpers import analysis_of, sheet


def graded(**held: str) -> Distribution:
    return grade(fineness_of(analysis_of(sheet(**held), "50.00")))


class TestThreeScreenSand:
    def test_everything_on_three_adjacent_screens(self) -> None:
        result = graded(**{"50": "15.00", "70": "20.00", "100": "15.00"})
        assert result.grading is Grading.THREE_SCREEN
        assert result.best_three.share == Percent(100)
        assert result.best_three.labels == ("50", "70", "100")

    def test_exactly_at_the_threshold_counts(self) -> None:
        result = graded(
            **{"50": "10.00", "70": "15.00", "100": "10.00", "20": "7.50", "200": "7.50"}
        )
        assert result.best_three.share.value == Decimal("70.00")
        assert result.grading is Grading.THREE_SCREEN

    def test_just_under_the_threshold_does_not(self) -> None:
        result = graded(
            **{"50": "10.00", "70": "14.00", "100": "10.00", "20": "8.00", "200": "8.00"}
        )
        assert result.best_three.share.value == Decimal("68.00")
        assert result.grading is not Grading.THREE_SCREEN

    def test_a_uniform_sand_reports_uniform(self) -> None:
        assert graded(**{"50": "15.00", "70": "20.00", "100": "15.00"}).is_uniform


class TestTheScreensHaveToBeAdjacent:
    def test_a_gap_graded_sand_is_not_a_three_screen_sand(self) -> None:
        # The same seventy percent, but on the 20, the 70 and the 270.
        result = graded(
            **{"20": "12.00", "70": "11.00", "270": "12.00", "50": "7.50", "100": "7.50"}
        )
        assert result.grading is Grading.SPREAD

    def test_the_window_only_ever_reports_adjacent_screens(self) -> None:
        result = graded(**{"20": "20.00", "270": "30.00"})
        labels = result.best_three.labels
        assert labels in {
            ("20", "30", "40"),
            ("140", "200", "270"),
        }


class TestFourScreenSand:
    def test_four_adjacent_screens_over_eighty(self) -> None:
        result = graded(
            **{"40": "10.00", "50": "12.00", "70": "12.00", "100": "10.00", "200": "6.00"}
        )
        assert result.best_three.share.value < Decimal("70")
        assert result.best_four.share.value >= Decimal("80")
        assert result.grading is Grading.FOUR_SCREEN
        assert result.is_uniform

    def test_three_screen_wins_when_both_would_hold(self) -> None:
        result = graded(**{"50": "15.00", "70": "20.00", "100": "15.00"})
        assert result.best_four.share == Percent(100)
        assert result.grading is Grading.THREE_SCREEN


class TestSpreadSand:
    def test_an_even_spread_across_the_stack(self) -> None:
        result = graded(
            **{
                "20": "6.00",
                "30": "6.00",
                "40": "6.00",
                "50": "7.00",
                "70": "7.00",
                "100": "6.00",
                "140": "6.00",
                "200": "6.00",
            }
        )
        assert result.grading is Grading.SPREAD
        assert not result.is_uniform


class TestFines:
    def test_the_fines_are_the_two_finest_screens(self) -> None:
        result = graded(**{"70": "40.00", "200": "6.00", "270": "4.00"})
        assert result.fines == Percent(20)

    def test_the_pan_is_not_counted_as_a_screen(self) -> None:
        result = graded(**{"70": "45.00", "PAN": "5.00"})
        assert result.fines == Percent.zero()
        assert "PAN" not in result.best_three.labels


class TestGuards:
    def test_grading_wants_a_fineness(self) -> None:
        with pytest.raises(BadInputError, match="read off a fineness result"):
            grade("60")  # type: ignore[arg-type]

    def test_a_window_covers_at_least_one_screen(self) -> None:
        with pytest.raises(BadInputError, match="at least one screen"):
            _sliding_best([], 0)

    def test_a_window_wider_than_the_series_is_refused(self) -> None:
        result = fineness_of(analysis_of(sheet(**{"70": "50.00"}), "50.00"))
        working = [(m, p) for m, p in result.spread if not m.is_pan]
        with pytest.raises(BadInputError, match="needs 20 working screens"):
            _sliding_best(working, 20)

    def test_ties_go_to_the_coarse_end(self) -> None:
        # Both the 6-12-20 window and the 140-200-270 window hold fifty
        # percent. The coarse one is reported.
        result = graded(**{"20": "25.00", "270": "25.00"})
        assert result.best_three.labels == ("6", "12", "20")

    def test_str_carries_both_readings(self) -> None:
        result = graded(**{"50": "15.00", "70": "20.00", "100": "15.00"})
        assert str(result) == "GFN 53.00 three screen"
