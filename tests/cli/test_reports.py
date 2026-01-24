from __future__ import annotations

from pathlib import Path

import pytest

from mullerbox.analysis.control import MIN_POINTS
from mullerbox.cli.context import EXIT_RULE
from tests.cli.helpers import initialised, run

WHEN = "2025-08-04"


@pytest.fixture
def book(tmp_path: Path) -> Path:
    target = initialised(tmp_path)
    run("spec", "load-default", "--on", "2025-01-06", book=target)
    for tag, kind in (("RAM-1", "compactability"), ("PERM-1", "permeability")):
        run("catalogue", "instrument-add", tag, kind, book=target)
    run(
        "catalogue", "calibrate", "RAM-1", "C-1", "--on", "2025-01-06", "--days", "300", book=target
    )
    run(
        "lab",
        "sample-add",
        "S-100",
        "--on",
        WHEN,
        "--point",
        "muller",
        "--system",
        "two",
        book=target,
    )
    run(
        "lab",
        "result-add",
        "S-100",
        "comp",
        "42",
        "--instrument",
        "RAM-1",
        "--on",
        WHEN,
        book=target,
    )
    return target


class TestShift:
    def test_it_names_the_class_it_judged_as(self, book: Path) -> None:
        result = run("report", "shift", "heavy jobbing", "--on", WHEN, book=book)
        assert result.exit_code == 0
        assert "judged as heavy jobbing" in result.output

    def test_the_class_is_required(self, book: Path) -> None:
        result = run("report", "shift", "--on", WHEN, book=book)
        assert result.exit_code != 0

    def test_one_shift_reads_two_ways(self, book: Path) -> None:
        run(
            "lab",
            "sample-add",
            "S-101",
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
            "S-101",
            "comp",
            "44.5",
            "--instrument",
            "RAM-1",
            "--on",
            WHEN,
            book=book,
        )
        heavy = run("report", "shift", "heavy jobbing", "--on", WHEN, book=book)
        thin = run("report", "shift", "thin wall", "--on", WHEN, book=book)
        assert "in band" in heavy.output
        assert "out of band" in thin.output

    def test_it_names_the_system(self, book: Path) -> None:
        result = run(
            "report", "shift", "heavy jobbing", "--on", WHEN, "--system", "number two", book=book
        )
        assert "number two on 2025-08-04" in result.output

    def test_a_stale_reading_is_called_out(self, book: Path) -> None:
        result = run("report", "shift", "heavy jobbing", "--on", "2025-09-01", book=book)
        assert "over a week old" in result.output

    def test_an_unknown_class_is_refused(self, book: Path) -> None:
        result = run("report", "shift", "prototype", "--on", WHEN, book=book)
        assert result.exit_code == EXIT_RULE


class TestExceptions:
    def test_a_clean_book_says_so(self, book: Path) -> None:
        result = run("report", "exceptions", "--on", WHEN, book=book)
        assert result.exit_code == 0
        assert "every reading" in result.output

    def test_a_reading_with_no_calibration_is_listed(self, book: Path) -> None:
        run(
            "lab",
            "sample-add",
            "S-102",
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
            "S-102",
            "perm",
            "110",
            "--instrument",
            "PERM-1",
            "--on",
            WHEN,
            book=book,
        )
        result = run("report", "exceptions", "--on", WHEN, book=book)
        assert "no calibration covering" in result.output
        assert "1 readings do not count" in result.output

    def test_it_does_not_appear_on_the_shift_report(self, book: Path) -> None:
        run(
            "lab",
            "sample-add",
            "S-102",
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
            "S-102",
            "perm",
            "110",
            "--instrument",
            "PERM-1",
            "--on",
            WHEN,
            book=book,
        )
        shift = run("report", "shift", "heavy jobbing", "--on", WHEN, book=book)
        assert "no calibration covering" not in shift.output


class TestChart:
    def test_too_few_readings_says_how_many_are_needed(self, book: Path) -> None:
        result = run("report", "chart", "comp", book=book)
        assert result.exit_code == 0
        assert f"{MIN_POINTS} are needed" in result.output

    def test_enough_readings_gives_limits(self, book: Path) -> None:
        for n in range(MIN_POINTS):
            sample = f"S-2{n:02d}"
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
            reading = "41.0" if n % 2 else "41.2"
            run(
                "lab",
                "result-add",
                sample,
                "comp",
                reading,
                "--instrument",
                "RAM-1",
                "--on",
                WHEN,
                book=book,
            )
        result = run("report", "chart", "comp", book=book)
        assert result.exit_code == 0
        assert "centre" in result.output
        assert "average moving range" in result.output

    def test_an_unknown_property_is_refused(self, book: Path) -> None:
        result = run("report", "chart", "stickiness", book=book)
        assert result.exit_code == EXIT_RULE
        assert "not a sand property" in result.output


class TestAnalyse:
    """Its own book, with no stray readings from the shared fixture.

    A single leftover reading two points away from a run is an outlier the
    control chart correctly flags, which would make every state in here read
    as drifting for a reason that has nothing to do with what is being tested.
    """

    @pytest.fixture
    def clean(self, tmp_path: Path) -> Path:
        target = initialised(tmp_path)
        run("spec", "load-default", "--on", "2025-01-06", book=target)
        run("catalogue", "instrument-add", "RAM-1", "compactability", book=target)
        run(
            "catalogue",
            "calibrate",
            "RAM-1",
            "C-1",
            "--on",
            "2025-01-06",
            "--days",
            "400",
            book=target,
        )
        return target

    def _long_run(self, book: Path, low: str, high: str, count: int = 20) -> None:
        for n in range(count):
            sample = f"A-{n:03d}"
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
                "comp",
                high if n % 2 else low,
                "--instrument",
                "RAM-1",
                "--on",
                WHEN,
                book=book,
            )

    def test_too_little_history_is_named_rather_than_guessed(self, clean: Path) -> None:
        result = run("report", "analyse", "heavy jobbing", "--on", WHEN, book=clean)
        assert result.exit_code == 0
        assert "not enough history" in result.output
        assert "run more tests" in result.output

    def test_a_settled_property_says_leave_it_alone(self, clean: Path) -> None:
        self._long_run(clean, "40.9", "41.1")
        result = run("report", "analyse", "heavy jobbing", "--on", WHEN, book=clean)
        assert "stable and capable" in result.output
        assert "leave it alone" in result.output

    def test_a_consistently_wrong_property_says_move_the_recipe(self, clean: Path) -> None:
        self._long_run(clean, "49.9", "50.1")
        result = run("report", "analyse", "heavy jobbing", "--on", WHEN, book=clean)
        assert "stable and not capable" in result.output
        assert "move the recipe" in result.output

    def test_the_class_changes_the_answer(self, clean: Path) -> None:
        self._long_run(clean, "43.9", "44.1")
        heavy = run("report", "analyse", "heavy jobbing", "--on", WHEN, book=clean)
        thin = run("report", "analyse", "thin wall", "--on", WHEN, book=clean)
        assert heavy.output != thin.output

    def test_only_action_hides_the_settled_ones(self, clean: Path) -> None:
        self._long_run(clean, "40.9", "41.1")
        everything = run("report", "analyse", "heavy jobbing", "--on", WHEN, book=clean)
        filtered = run(
            "report", "analyse", "heavy jobbing", "--on", WHEN, "--only-action", book=clean
        )
        assert "compactability" in everything.output
        assert "nothing needs doing" in filtered.output

    def test_the_summary_counts_what_needs_action(self, clean: Path) -> None:
        self._long_run(clean, "40.9", "41.1")
        result = run("report", "analyse", "heavy jobbing", "--on", WHEN, book=clean)
        assert "controlled properties need action" in result.output

    def test_an_unknown_class_is_refused(self, clean: Path) -> None:
        result = run("report", "analyse", "prototype", "--on", WHEN, book=clean)
        assert result.exit_code == EXIT_RULE

    def test_a_date_before_any_spec_is_refused(self, clean: Path) -> None:
        result = run("report", "analyse", "heavy jobbing", "--on", "2024-01-01", book=clean)
        assert result.exit_code == EXIT_RULE
