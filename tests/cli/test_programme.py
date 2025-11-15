from __future__ import annotations

from pathlib import Path

import pytest

from mullerbox.analysis.control import MIN_POINTS
from mullerbox.cli.context import EXIT_RULE
from tests.cli.helpers import initialised, run

WHEN = "2025-11-17"


@pytest.fixture
def book(tmp_path: Path) -> Path:
    target = initialised(tmp_path)
    run("catalogue", "instrument-add", "RAM-1", "compactability", book=target)
    run("catalogue", "instrument-add", "MUF-1", "muffle", book=target)
    run(
        "catalogue", "calibrate", "RAM-1", "C-1", "--on", "2025-01-06", "--days", "400", book=target
    )
    run(
        "catalogue", "calibrate", "MUF-1", "C-2", "--on", "2025-01-06", "--days", "400", book=target
    )
    run(
        "programme",
        "set",
        "comp",
        "every_shift",
        "--on",
        "2025-01-06",
        "--because",
        "the line feels it",
        book=target,
    )
    run(
        "programme",
        "set",
        "loi",
        "monthly",
        "--on",
        "2025-01-06",
        "--because",
        "slow to move",
        book=target,
    )
    return target


def add_loi_run(book: Path, count: int, reading: str = "2.5") -> None:
    for n in range(count):
        sample = f"L-{n:03d}"
        run(
            "lab",
            "sample-add",
            sample,
            "--on",
            WHEN,
            "--point",
            "muller",
            "--system",
            "two",
            book=book,
        )
        value = reading if n % 2 else str(float(reading) + 0.02)
        run(
            "lab",
            "result-add",
            sample,
            "loi",
            value,
            "--instrument",
            "MUF-1",
            "--on",
            WHEN,
            book=book,
        )


class TestSetting:
    def test_a_property_goes_on_the_programme(self, book: Path) -> None:
        result = run(
            "programme", "set", "perm", "weekly", "--on", WHEN, "--because", "stable", book=book
        )
        assert result.exit_code == 0
        assert "tested weekly" in result.output

    def test_a_reason_is_required(self, book: Path) -> None:
        result = run("programme", "set", "perm", "weekly", "--on", WHEN, book=book)
        assert result.exit_code != 0

    def test_an_unknown_frequency_lists_the_real_ones(self, book: Path) -> None:
        result = run(
            "programme", "set", "perm", "fortnightly", "--on", WHEN, "--because", "x", book=book
        )
        assert result.exit_code == EXIT_RULE
        assert "is not a frequency" in result.output

    def test_an_unknown_property_is_refused(self, book: Path) -> None:
        result = run(
            "programme", "set", "stickiness", "weekly", "--on", WHEN, "--because", "x", book=book
        )
        assert result.exit_code == EXIT_RULE


class TestDue:
    def test_a_property_never_tested_is_due(self, book: Path) -> None:
        result = run("programme", "due", "--on", WHEN, book=book)
        assert result.exit_code == 0
        assert "never" in result.output

    def test_a_property_tested_today_is_not(self, book: Path) -> None:
        run(
            "lab",
            "sample-add",
            "S-1",
            "--on",
            WHEN,
            "--point",
            "muller",
            "--system",
            "two",
            book=book,
        )
        run(
            "lab",
            "result-add",
            "S-1",
            "comp",
            "42",
            "--instrument",
            "RAM-1",
            "--on",
            WHEN,
            book=book,
        )
        result = run("programme", "due", "--on", WHEN, book=book)
        assert "compactability" not in result.output

    def test_an_empty_programme_is_refused(self, tmp_path: Path) -> None:
        target = initialised(tmp_path)
        result = run("programme", "due", "--on", WHEN, book=target)
        assert result.exit_code == EXIT_RULE
        assert "testing programme" in result.output

    def test_nothing_due_says_so(self, book: Path) -> None:
        for kind, tag in (("comp", "RAM-1"), ("loi", "MUF-1")):
            sample = f"S-{kind}"
            run(
                "lab",
                "sample-add",
                sample,
                "--on",
                WHEN,
                "--point",
                "muller",
                "--system",
                "two",
                book=book,
            )
            run(
                "lab",
                "result-add",
                sample,
                kind,
                "2.5",
                "--instrument",
                tag,
                "--on",
                WHEN,
                book=book,
            )
        assert "nothing is due" in run("programme", "due", "--on", WHEN, book=book).output


class TestReviewRecommendsAndChangesNothing:
    def test_too_few_readings_says_leave_it(self, book: Path) -> None:
        result = run("programme", "review", book=book)
        assert result.exit_code == 0
        assert "too few" in result.output
        assert "leave it" in result.output

    def test_a_stable_run_recommends_relaxing(self, book: Path) -> None:
        add_loi_run(book, MIN_POINTS + 5)
        result = run("programme", "review", book=book)
        assert "move to quarterly" in result.output

    def test_the_recommendation_does_not_move_it(self, book: Path) -> None:
        add_loi_run(book, MIN_POINTS + 5)
        run("programme", "review", book=book)
        assert (
            run("programme", "history", "loi", book=book)
            .output.strip()
            .endswith("never had its interval moved")
        )

    def test_a_pinned_property_says_pinned(self, book: Path) -> None:
        result = run("programme", "review", book=book)
        assert "pinned" in result.output

    def test_it_shows_the_chart_state(self, book: Path) -> None:
        add_loi_run(book, MIN_POINTS + 5)
        result = run("programme", "review", book=book)
        assert "in control" in result.output


class TestHistory:
    def test_a_property_never_moved(self, book: Path) -> None:
        assert (
            "never had its interval moved" in run("programme", "history", "loi", book=book).output
        )

    def test_a_move_is_recorded_with_its_reason(self, book: Path) -> None:
        run(
            "programme",
            "set",
            "loi",
            "quarterly",
            "--on",
            WHEN,
            "--because",
            "in control all year",
            book=book,
        )
        result = run("programme", "history", "loi", book=book)
        assert "monthly" in result.output
        assert "quarterly" in result.output
        assert "in control all year" in result.output

    def test_an_unknown_property_is_refused(self, book: Path) -> None:
        result = run("programme", "history", "stickiness", book=book)
        assert result.exit_code == EXIT_RULE
