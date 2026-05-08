from __future__ import annotations

from pathlib import Path

import pytest

from mullerbox.bench.specimen import NOMINAL_HEIGHT
from mullerbox.cli.context import EXIT_RULE
from mullerbox.props.kind import PropertyKind
from tests.cli.helpers import initialised, run


@pytest.fixture
def book(tmp_path: Path) -> Path:
    return initialised(tmp_path)


class TestNeeds:
    def test_it_lists_what_one_test_takes(self, book: Path) -> None:
        result = run("bench", "needs", "gcs", book=book)
        assert result.exit_code == 0
        assert "rammed specimen" in result.output
        assert "universal strength machine" in result.output
        assert "in calibration" in result.output

    def test_it_totals_the_sand_for_several(self, book: Path) -> None:
        result = run("bench", "needs", "gcs", "mb", book=book)
        assert "of sand between them" in result.output

    def test_it_says_which_tests_share_a_specimen(self, book: Path) -> None:
        result = run("bench", "needs", "perm", "hardness", book=book)
        assert "share one rammed specimen" in result.output

    def test_two_destructive_specimen_tests_are_refused(self, book: Path) -> None:
        result = run("bench", "needs", "gcs", "wet tensile", book=book)
        assert result.exit_code == EXIT_RULE
        assert "need 2 specimens and not one" in result.output

    def test_the_titration_names_bench_temperature(self, book: Path) -> None:
        result = run("bench", "needs", "mb", book=book)
        assert "bench temperature" in result.output

    def test_an_unknown_property_is_refused(self, book: Path) -> None:
        result = run("bench", "needs", "stickiness", book=book)
        assert result.exit_code == EXIT_RULE

    def test_it_needs_at_least_one_property(self, book: Path) -> None:
        assert run("bench", "needs", book=book).exit_code != 0


class TestMethods:
    def test_every_property_is_listed(self, book: Path) -> None:
        result = run("bench", "methods", book=book)
        assert result.exit_code == 0
        for kind in PropertyKind:
            assert kind.label in result.output

    def test_it_says_which_destroy_the_specimen(self, book: Path) -> None:
        result = run("bench", "methods", book=book)
        assert "destroys it" in result.output

    def test_it_works_on_an_empty_book(self, tmp_path: Path) -> None:
        assert run("bench", "methods", book=initialised(tmp_path)).exit_code == 0


class TestSpecimen:
    def test_a_good_specimen_may_carry_readings(self, book: Path) -> None:
        result = run("bench", "specimen", "SP-1", "3400", str(NOMINAL_HEIGHT), book=book)
        assert result.exit_code == 0
        assert "good" in result.output
        assert "readings may be taken" in result.output

    def test_it_reports_the_compactability(self, book: Path) -> None:
        result = run("bench", "specimen", "SP-1", "3400", str(NOMINAL_HEIGHT), book=book)
        assert "compactability" in result.output

    def test_a_short_specimen_is_refused_before_any_reading(self, book: Path) -> None:
        result = run("bench", "specimen", "SP-1", "3400", "1900", book=book)
        assert result.exit_code == EXIT_RULE
        assert "thousandths short" in result.output

    def test_a_tall_one_too(self, book: Path) -> None:
        result = run("bench", "specimen", "SP-1", "3400", "2100", book=book)
        assert result.exit_code == EXIT_RULE
        assert "thousandths tall" in result.output

    def test_the_wrong_ram_count_is_refused(self, book: Path) -> None:
        result = run(
            "bench", "specimen", "SP-1", "3400", str(NOMINAL_HEIGHT), "--rams", "4", book=book
        )
        assert result.exit_code == EXIT_RULE
        assert "took 4 rams, not 3" in result.output

    def test_an_under_filled_tube_is_refused(self, book: Path) -> None:
        result = run("bench", "specimen", "SP-1", "2100", str(NOMINAL_HEIGHT), book=book)
        assert result.exit_code == EXIT_RULE
        assert "under-filled tube" in result.output

    def test_the_height_error_carries_its_sign(self, book: Path) -> None:
        result = run("bench", "specimen", "SP-1", "3400", "2020", book=book)
        assert "+20 thousandths" in result.output
