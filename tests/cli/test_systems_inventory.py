from __future__ import annotations

from pathlib import Path

import pytest

from tests.cli.helpers import initialised, run

FIGURE = [
    "--mass",
    "80000",
    "--inventoried",
    "2026-01-05",
    "--batch",
    "2000",
    "--return-f",
    "120",
    "--dust-rate",
    "1.5",
]


@pytest.fixture
def book(tmp_path: Path) -> Path:
    return initialised(tmp_path)


def take(book: Path, *extra: str, save: bool = True) -> object:
    args = [
        "system",
        "inventory",
        "--name",
        "two",
        "--on",
        "2026-07-15",
        "--vessel",
        "silo:1000:0.80:95",
        *extra,
    ]
    if not save:
        args.append("--no-save")
    return run(*args, book=book)


class TestTakingACount:
    def test_it_prints_the_total(self, book: Path) -> None:
        result = take(book)
        assert result.exit_code == 0, result.output  # type: ignore[attr-defined]
        assert "total 38.000 t" in result.output  # type: ignore[attr-defined]

    def test_the_floor_is_added_and_flagged(self, book: Path) -> None:
        result = take(book, "--moulds", "40", "--sand-per-mould", "300")
        assert "on the floor 6.000 t" in result.output  # type: ignore[attr-defined]
        assert "13.6% of that is the floor estimate" in result.output  # type: ignore[attr-defined]

    def test_no_moulds_means_no_floor_line(self, book: Path) -> None:
        assert "floor estimate" not in take(book).output  # type: ignore[attr-defined]

    def test_a_vessel_with_no_density_makes_it_partial(self, book: Path) -> None:
        result = take(book, "--vessel", "hopper:400:0.50")
        assert "did not reach hopper" in result.output  # type: ignore[attr-defined]
        assert "not counted" in result.output  # type: ignore[attr-defined]

    def test_an_empty_density_field_means_the_same(self, book: Path) -> None:
        result = take(book, "--vessel", "hopper:400:0.50:")
        assert "did not reach hopper" in result.output  # type: ignore[attr-defined]

    def test_it_is_kept_on_the_book(self, book: Path) -> None:
        take(book)
        listed = run("system", "counts", "--name", "two", book=book)
        assert "2026-07-15" in listed.output
        assert "complete" in listed.output

    def test_no_save_leaves_the_book_alone(self, book: Path) -> None:
        take(book, save=False)
        listed = run("system", "counts", "--name", "two", book=book)
        assert "never been inventoried" in listed.output

    def test_a_malformed_vessel_is_refused(self, book: Path) -> None:
        result = run(
            "system",
            "inventory",
            "--name",
            "two",
            "--on",
            "2026-07-15",
            "--vessel",
            "silo:1000",
            book=book,
        )
        assert result.exit_code != 0
        assert "is not name:capacity:fill" in result.output

    def test_a_capacity_that_is_not_a_number(self, book: Path) -> None:
        result = run(
            "system",
            "inventory",
            "--name",
            "two",
            "--on",
            "2026-07-15",
            "--vessel",
            "silo:big:0.8:95",
            book=book,
        )
        assert result.exit_code != 0
        assert "vessel capacity" in result.output


class TestReconciling:
    def test_it_reports_the_drift(self, book: Path) -> None:
        take(book)
        result = run(
            "system", "reconcile", "--name", "two", "--on", "2026-07-15", *FIGURE, book=book
        )
        assert result.exit_code == 0, result.output
        assert "-5.0%" in result.output

    def test_adopting_a_complete_count_names_the_new_figure(self, book: Path) -> None:
        take(book)
        result = run(
            "system",
            "reconcile",
            "--name",
            "two",
            "--on",
            "2026-07-15",
            "--adopt",
            *FIGURE,
            book=book,
        )
        assert "--basis measured" in result.output
        assert "adopt 38.000 t" in result.output

    def test_adopting_a_partial_count_is_refused(self, book: Path) -> None:
        take(book, "--vessel", "hopper:400:0.50")
        result = run(
            "system",
            "reconcile",
            "--name",
            "two",
            "--on",
            "2026-07-15",
            "--adopt",
            *FIGURE,
            book=book,
        )
        assert result.exit_code != 0
        assert "did not reach hopper" in result.output

    def test_reading_a_partial_count_without_adopting_is_fine(self, book: Path) -> None:
        take(book, "--vessel", "hopper:400:0.50")
        result = run(
            "system", "reconcile", "--name", "two", "--on", "2026-07-15", *FIGURE, book=book
        )
        assert result.exit_code == 0
        assert "no measured density" in result.output

    def test_a_count_that_is_not_there(self, book: Path) -> None:
        result = run(
            "system", "reconcile", "--name", "two", "--on", "2026-07-15", *FIGURE, book=book
        )
        assert result.exit_code != 0


class TestListing:
    def test_a_system_never_counted(self, book: Path) -> None:
        assert (
            "never been inventoried" in run("system", "counts", "--name", "two", book=book).output
        )

    def test_a_partial_count_shows_as_partial(self, book: Path) -> None:
        take(book, "--vessel", "hopper:400:0.50")
        assert "partial" in run("system", "counts", "--name", "two", book=book).output


class TestTheCountsRun:
    def take_on(self, book: Path, when: str, fill: str) -> None:
        run(
            "system",
            "inventory",
            "--name",
            "two",
            "--on",
            when,
            "--vessel",
            f"silo:1000:{fill}:95",
            book=book,
        )

    def test_two_counts_are_not_a_trend(self, book: Path) -> None:
        self.take_on(book, "2025-01-06", "0.80")
        self.take_on(book, "2025-07-06", "0.75")
        shown = run("system", "counts", "--name", "two", book=book)
        assert "is not a trend" in shown.output

    def test_three_counts_read_as_a_loss(self, book: Path) -> None:
        self.take_on(book, "2025-01-06", "0.80")
        self.take_on(book, "2025-07-06", "0.75")
        self.take_on(book, "2026-01-05", "0.70")
        shown = run("system", "counts", "--name", "two", book=book)
        assert "losing" in shown.output
        assert "new sand a year" in shown.output

    def test_a_gaining_system_is_offered_no_figure(self, book: Path) -> None:
        self.take_on(book, "2025-01-06", "0.70")
        self.take_on(book, "2025-07-06", "0.75")
        self.take_on(book, "2026-01-05", "0.80")
        shown = run("system", "counts", "--name", "two", book=book)
        assert "gaining" in shown.output
        assert "new sand a year" not in shown.output

    def test_the_change_column_is_there(self, book: Path) -> None:
        self.take_on(book, "2025-01-06", "0.80")
        self.take_on(book, "2025-07-06", "0.75")
        assert "change" in run("system", "counts", "--name", "two", book=book).output

    def test_a_system_never_counted_still_says_so(self, book: Path) -> None:
        assert (
            "never been inventoried" in run("system", "counts", "--name", "two", book=book).output
        )

    def test_a_partial_count_is_still_plotted(self, book: Path) -> None:
        run(
            "system",
            "inventory",
            "--name",
            "two",
            "--on",
            "2025-01-06",
            "--vessel",
            "silo:1000:0.80:95",
            "--vessel",
            "hopper:400:0.50",
            book=book,
        )
        shown = run("system", "counts", "--name", "two", book=book)
        assert "partial" in shown.output
        assert "2025-01-06" in shown.output


class TestRemovingACount:
    def test_it_comes_off_the_run(self, book: Path) -> None:
        take(book)
        removed = run("system", "count-delete", "--name", "two", "--on", "2026-07-15", book=book)
        assert removed.exit_code == 0, removed.output
        assert (
            "never been inventoried" in run("system", "counts", "--name", "two", book=book).output
        )

    def test_the_day_can_be_counted_again(self, book: Path) -> None:
        take(book)
        run("system", "count-delete", "--name", "two", "--on", "2026-07-15", book=book)
        assert take(book).exit_code == 0  # type: ignore[attr-defined]

    def test_removing_one_that_is_not_there(self, book: Path) -> None:
        result = run("system", "count-delete", "--name", "two", "--on", "2026-07-15", book=book)
        assert result.exit_code != 0
