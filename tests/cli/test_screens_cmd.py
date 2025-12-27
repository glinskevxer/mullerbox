from __future__ import annotations

from pathlib import Path

import pytest

from mullerbox.cli.context import EXIT_RULE
from tests.cli.helpers import initialised, run

SERIES = "AFS US 11 screen"
WHEN = "2026-01-05"
WORKING = [6, 12, 20, 30, 40, 50, 70, 100, 140, 200, 270]
NOMINAL = {
    6: 3350,
    12: 1700,
    20: 850,
    30: 600,
    40: 425,
    50: 300,
    70: 212,
    100: 150,
    140: 106,
    200: 75,
    270: 53,
}


@pytest.fixture
def book(tmp_path: Path) -> Path:
    target = initialised(tmp_path)
    assert run("catalogue", "load-afs", book=target).exit_code == 0
    return target


def measure_all(book: Path, when: str = WHEN, **overrides: int) -> None:
    for number in WORKING:
        value = overrides.get(f"m{number}", NOMINAL[number])
        run("screens", "measure", SERIES, str(number), str(value), "--on", when, book=book)


class TestMeasuring:
    def test_a_good_screen(self, book: Path) -> None:
        result = run("screens", "measure", SERIES, "50", "300", "--on", WHEN, book=book)
        assert result.exit_code == 0
        assert "within" in result.output

    def test_a_worn_screen_says_retire_it(self, book: Path) -> None:
        result = run("screens", "measure", SERIES, "50", "320", "--on", WHEN, book=book)
        assert "retire it" in result.output

    def test_the_wrong_screen_says_check_the_frame(self, book: Path) -> None:
        result = run("screens", "measure", SERIES, "50", "400", "--on", WHEN, book=book)
        assert "right cloth" in result.output

    def test_a_screen_off_the_series_lists_the_real_ones(self, book: Path) -> None:
        result = run("screens", "measure", SERIES, "325", "45", "--on", WHEN, book=book)
        assert result.exit_code == EXIT_RULE
        assert "is not on series" in result.output
        assert "270" in result.output

    def test_the_same_screen_and_day_twice_is_refused(self, book: Path) -> None:
        run("screens", "measure", SERIES, "50", "300", "--on", WHEN, book=book)
        result = run("screens", "measure", SERIES, "50", "301", "--on", WHEN, book=book)
        assert result.exit_code == EXIT_RULE

    def test_an_unknown_series_is_refused(self, book: Path) -> None:
        result = run("screens", "measure", "nothing", "50", "300", "--on", WHEN, book=book)
        assert result.exit_code == EXIT_RULE


class TestAnUnmeasuredScreenIsNotAPass:
    def test_a_partly_measured_stack_is_not_fit(self, book: Path) -> None:
        run("screens", "measure", SERIES, "50", "300", "--on", WHEN, book=book)
        result = run("screens", "stack", SERIES, "--on", WHEN, book=book)
        assert result.exit_code == 0
        assert "UNCHECKED" in result.output
        assert "NOT FIT" in result.output
        assert "were not measured" in result.output

    def test_a_fully_measured_good_stack_is_fit(self, book: Path) -> None:
        measure_all(book)
        result = run("screens", "stack", SERIES, "--on", WHEN, book=book)
        assert "fit to use" in result.output
        assert "UNCHECKED" not in result.output

    def test_an_unmeasured_book_is_not_fit(self, book: Path) -> None:
        result = run("screens", "stack", SERIES, "--on", WHEN, book=book)
        assert "NOT FIT" in result.output

    def test_a_worn_screen_fails_a_fully_measured_stack(self, book: Path) -> None:
        measure_all(book, m50=320)
        result = run("screens", "stack", SERIES, "--on", WHEN, book=book)
        assert "NOT FIT" in result.output
        assert "retire it" in result.output

    def test_the_oldest_check_is_named_on_a_fit_stack(self, book: Path) -> None:
        measure_all(book)
        result = run("screens", "stack", SERIES, "--on", WHEN, book=book)
        assert "the oldest check is screen" in result.output

    def test_the_table_shows_the_drift(self, book: Path) -> None:
        measure_all(book, m50=306)
        result = run("screens", "stack", SERIES, "--on", WHEN, book=book)
        assert "+2.00%" in result.output


class TestHistory:
    def test_a_screen_never_measured(self, book: Path) -> None:
        result = run("screens", "wear-history", SERIES, "50", book=book)
        assert result.exit_code == 0
        assert "has never been measured" in result.output

    def test_it_shows_the_wear_over_time(self, book: Path) -> None:
        run("screens", "measure", SERIES, "50", "300", "--on", "2025-01-06", book=book)
        run("screens", "measure", SERIES, "50", "312", "--on", WHEN, book=book)
        result = run("screens", "wear-history", SERIES, "50", book=book)
        assert "+0.00%" in result.output
        assert "+4.00%" in result.output

    def test_a_screen_off_the_series_is_refused(self, book: Path) -> None:
        result = run("screens", "wear-history", SERIES, "325", book=book)
        assert result.exit_code == EXIT_RULE
