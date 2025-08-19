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
