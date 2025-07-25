from __future__ import annotations

from pathlib import Path

import pytest

from mullerbox.cli.context import EXIT_RULE
from tests.cli.helpers import initialised, run


@pytest.fixture
def book(tmp_path: Path) -> Path:
    target = initialised(tmp_path)
    run("catalogue", "load-afs", book=target)
    for tag, kind in (
        ("RAM-1", "compactability"),
        ("PERM-1", "permeability"),
        ("USM-1", "strength"),
    ):
        run("catalogue", "instrument-add", tag, kind, book=target)
    run(
        "catalogue", "calibrate", "RAM-1", "C-1", "--on", "2025-01-06", "--days", "300", book=target
    )
    run(
        "lab",
        "sample-add",
        "S-100",
        "--on",
        "2025-07-21",
        "--point",
        "muller discharge",
        "--system",
        "number two",
        book=target,
    )
    return target


class TestSamples:
    def test_adding_one(self, book: Path) -> None:
        result = run(
            "lab",
            "sample-add",
            "S-101",
            "--on",
            "2025-07-21",
            "--point",
            "shakeout",
            "--system",
            "number two",
            book=book,
        )
        assert result.exit_code == 0
        assert "added sample S-101" in result.output

    def test_the_same_id_twice_is_refused(self, book: Path) -> None:
        result = run(
            "lab",
            "sample-add",
            "S-100",
            "--on",
            "2025-07-21",
            "--point",
            "shakeout",
            "--system",
            "number two",
            book=book,
        )
        assert result.exit_code == EXIT_RULE
        assert "already on the book" in result.output

    def test_a_bad_date_names_the_format(self, book: Path) -> None:
        result = run(
            "lab",
            "sample-add",
            "S-102",
            "--on",
            "21/07/2025",
            "--point",
            "shakeout",
            "--system",
            "number two",
            book=book,
        )
        assert result.exit_code == EXIT_RULE
        assert "yyyy-mm-dd" in result.output

    def test_showing_a_sample_with_no_readings(self, book: Path) -> None:
        result = run("lab", "sample", "S-100", book=book)
        assert "pulled 2025-07-21 at muller discharge" in result.output
        assert "no readings" in result.output

    def test_showing_something_absent(self, book: Path) -> None:
        result = run("lab", "sample", "S-999", book=book)
        assert result.exit_code == EXIT_RULE
        assert "no sample on the book" in result.output


class TestTheScaleComesFromTheProperty:
    def test_a_percentage_reading(self, book: Path) -> None:
        result = run(
            "lab",
            "result-add",
            "S-100",
            "comp",
            "42",
            "--instrument",
            "RAM-1",
            "--on",
            "2025-07-21",
            book=book,
        )
        assert result.exit_code == 0
        assert "42.00%" in result.output

    def test_a_permeability_reading(self, book: Path) -> None:
        result = run(
            "lab",
            "result-add",
            "S-100",
            "perm",
            "110",
            "--instrument",
            "PERM-1",
            "--on",
            "2025-07-21",
            book=book,
        )
        assert "110 AFS" in result.output

    def test_the_same_bare_number_on_two_scales(self, book: Path) -> None:
        perm = run(
            "lab",
            "result-add",
            "S-100",
            "perm",
            "88",
            "--instrument",
            "PERM-1",
            "--on",
            "2025-07-21",
            book=book,
        )
        hard = run(
            "lab",
            "result-add",
            "S-100",
            "hardness",
            "88",
            "--instrument",
            "USM-1",
            "--on",
            "2025-07-21",
            book=book,
        )
        assert "88 AFS" in perm.output
        assert "88.0 B" in hard.output

    def test_a_reading_off_its_scale_is_refused(self, book: Path) -> None:
        result = run(
            "lab",
            "result-add",
            "S-100",
            "perm",
            "110.5",
            "--instrument",
            "PERM-1",
            "--on",
            "2025-07-21",
            book=book,
        )
        assert result.exit_code == EXIT_RULE

    def test_an_unknown_property_is_refused(self, book: Path) -> None:
        result = run(
            "lab",
            "result-add",
            "S-100",
            "stickiness",
            "4",
            "--instrument",
            "RAM-1",
            "--on",
            "2025-07-21",
            book=book,
        )
        assert result.exit_code == EXIT_RULE
        assert "not a sand property" in result.output


class TestValidityIsShownNotEnforced:
    def test_a_reading_in_a_lapse_is_still_recorded(self, book: Path) -> None:
        result = run(
            "lab",
            "result-add",
            "S-100",
            "perm",
            "110",
            "--instrument",
            "PERM-1",
            "--on",
            "2025-07-21",
            book=book,
        )
        assert result.exit_code == 0

    def test_the_sample_view_says_which_readings_count(self, book: Path) -> None:
        run(
            "lab",
            "result-add",
            "S-100",
            "comp",
            "42",
            "--instrument",
            "RAM-1",
            "--on",
            "2025-07-21",
            book=book,
        )
        run(
            "lab",
            "result-add",
            "S-100",
            "perm",
            "110",
            "--instrument",
            "PERM-1",
            "--on",
            "2025-07-21",
            book=book,
        )
        result = run("lab", "sample", "S-100", book=book)
        assert "C-1" in result.output
        assert "NO" in result.output

    def test_a_late_certificate_changes_the_answer(self, book: Path) -> None:
        run(
            "lab",
            "result-add",
            "S-100",
            "perm",
            "110",
            "--instrument",
            "PERM-1",
            "--on",
            "2025-07-21",
            book=book,
        )
        assert "NO" in run("lab", "sample", "S-100", book=book).output
        run(
            "catalogue",
            "calibrate",
            "PERM-1",
            "C-9",
            "--on",
            "2025-07-01",
            "--days",
            "90",
            book=book,
        )
        assert "C-9" in run("lab", "sample", "S-100", book=book).output


class TestSeriesCheck:
    def test_it_reloads_through_the_type(self, book: Path) -> None:
        result = run("lab", "series-check", "AFS US 11 screen", book=book)
        assert result.exit_code == 0
        assert "12 steps, 11 screens" in result.output
        assert "PAN" in result.output
        assert "300" in result.output

    def test_a_series_that_is_not_there(self, book: Path) -> None:
        result = run("lab", "series-check", "nothing", book=book)
        assert result.exit_code == EXIT_RULE


class TestFineness:
    def test_a_sample_with_no_analysis(self, book: Path) -> None:
        result = run("lab", "fineness", "S-100", book=book)
        assert result.exit_code == EXIT_RULE
        assert "no sieve analysis on sample" in result.output
