from __future__ import annotations

from pathlib import Path

import pytest

from mullerbox.cli.context import EXIT_RULE
from tests.cli.helpers import initialised, run


@pytest.fixture
def book(tmp_path: Path) -> Path:
    target = initialised(tmp_path)
    assert run("catalogue", "load-afs", book=target).exit_code == 0
    return target


class TestScreenSeries:
    def test_the_afs_series_loads(self, tmp_path: Path) -> None:
        target = initialised(tmp_path)
        result = run("catalogue", "load-afs", book=target)
        assert result.exit_code == 0
        assert "12 screens" in result.output

    def test_loading_it_twice_is_refused_rather_than_overwriting(self, book: Path) -> None:
        result = run("catalogue", "load-afs", book=book)
        assert result.exit_code == EXIT_RULE
        assert "already on the book" in result.output

    def test_listing(self, book: Path) -> None:
        result = run("catalogue", "series", book=book)
        assert "AFS US 11 screen" in result.output
        assert "12" in result.output

    def test_an_empty_book_says_so(self, tmp_path: Path) -> None:
        target = initialised(tmp_path)
        assert "no screen series" in run("catalogue", "series", book=target).output


class TestInstruments:
    def test_adding_one(self, book: Path) -> None:
        result = run("catalogue", "instrument-add", "USM-1", "strength", book=book)
        assert result.exit_code == 0
        assert "added instrument USM-1" in result.output

    def test_the_kind_is_read_in_several_spellings(self, book: Path) -> None:
        for tag, kind in (
            ("A-1", "STRENGTH"),
            ("A-2", "sieve_shaker"),
            ("A-3", "sieve-shaker"),
            ("A-4", "muffle"),
        ):
            assert run("catalogue", "instrument-add", tag, kind, book=book).exit_code == 0

    def test_an_unknown_kind_lists_the_real_ones(self, book: Path) -> None:
        result = run("catalogue", "instrument-add", "X-1", "dowsing rod", book=book)
        assert result.exit_code == EXIT_RULE
        assert "is not an instrument kind" in result.output
        assert "permeability" in result.output

    def test_adding_the_same_tag_twice_is_refused(self, book: Path) -> None:
        run("catalogue", "instrument-add", "USM-1", "strength", book=book)
        result = run("catalogue", "instrument-add", "USM-1", "strength", book=book)
        assert result.exit_code == EXIT_RULE

    def test_an_empty_book_says_so(self, book: Path) -> None:
        assert "no instruments" in run("catalogue", "instruments", book=book).output


class TestCalibration:
    def test_recording_a_certificate(self, book: Path) -> None:
        run("catalogue", "instrument-add", "USM-1", "strength", book=book)
        result = run(
            "catalogue",
            "calibrate",
            "USM-1",
            "C-1",
            "--on",
            "2025-01-06",
            "--days",
            "90",
            book=book,
        )
        assert result.exit_code == 0
        assert "good to 2025-04-05" in result.output

    def test_calibrating_something_absent_is_refused(self, book: Path) -> None:
        result = run(
            "catalogue",
            "calibrate",
            "USM-9",
            "C-1",
            "--on",
            "2025-01-06",
            "--days",
            "90",
            book=book,
        )
        assert result.exit_code == EXIT_RULE
        assert "no instrument on the book" in result.output

    def test_a_bad_date_names_the_format(self, book: Path) -> None:
        result = run(
            "catalogue",
            "calibrate",
            "USM-1",
            "C-1",
            "--on",
            "06/01/2025",
            "--days",
            "90",
            book=book,
        )
        assert result.exit_code == EXIT_RULE
        assert "yyyy-mm-dd" in result.output

    def test_an_overlapping_certificate_is_refused(self, book: Path) -> None:
        run("catalogue", "instrument-add", "USM-1", "strength", book=book)
        run(
            "catalogue",
            "calibrate",
            "USM-1",
            "C-1",
            "--on",
            "2025-01-06",
            "--days",
            "90",
            book=book,
        )
        result = run(
            "catalogue",
            "calibrate",
            "USM-1",
            "C-2",
            "--on",
            "2025-02-06",
            "--days",
            "90",
            book=book,
        )
        assert result.exit_code == EXIT_RULE
        assert "both cover" in result.output


class TestListingWithCalibration:
    def test_it_says_who_was_in_calibration_on_a_day(self, book: Path) -> None:
        run("catalogue", "instrument-add", "USM-1", "strength", book=book)
        run(
            "catalogue",
            "calibrate",
            "USM-1",
            "C-1",
            "--on",
            "2025-01-06",
            "--days",
            "90",
            book=book,
        )
        result = run("catalogue", "instruments", "--on", "2025-02-01", book=book)
        assert "in calibration" in result.output
        assert "C-1" in result.output

    def test_it_says_who_had_lapsed(self, book: Path) -> None:
        run("catalogue", "instrument-add", "USM-1", "strength", book=book)
        run(
            "catalogue",
            "calibrate",
            "USM-1",
            "C-1",
            "--on",
            "2025-01-06",
            "--days",
            "90",
            book=book,
        )
        result = run("catalogue", "instruments", "--on", "2025-06-01", book=book)
        assert "LAPSED" in result.output

    def test_without_the_option_it_just_counts_certificates(self, book: Path) -> None:
        run("catalogue", "instrument-add", "USM-1", "strength", book=book)
        result = run("catalogue", "instruments", book=book)
        assert "certificates" in result.output
        assert "LAPSED" not in result.output
