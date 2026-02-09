from __future__ import annotations

from pathlib import Path

import pytest

from mullerbox.cli.context import EXIT_RULE
from tests.cli.helpers import initialised, run

WHEN = "2026-02-04"
REGISTER = [
    "--flask",
    "8.0",
    "--cavities",
    "2",
    "--weight",
    "60",
]


@pytest.fixture
def book(tmp_path: Path) -> Path:
    target = initialised(tmp_path)
    assert (
        run(
            "pattern",
            "register",
            "P-1",
            "bearing housing",
            "medium jobbing",
            *REGISTER,
            book=target,
        ).exit_code
        == 0
    )
    return target


def load_pours(book: Path, tmp_path: Path, sand: str) -> None:
    path = tmp_path / "pours.csv"
    path.write_text(
        f"poured,pattern,metal,sand\n{WHEN},medium jobbing,10000,{sand}\n",
        encoding="utf-8",
    )
    run("import", "pours", str(path), book=book)


class TestRegistering:
    def test_a_pattern_goes_on(self, book: Path) -> None:
        result = run("pattern", "list", book=book)
        assert "P-1" in result.output
        assert ":1" in result.output

    def test_it_reports_the_expected_ratio(self, tmp_path: Path) -> None:
        target = initialised(tmp_path)
        result = run(
            "pattern", "register", "P-2", "cover plate", "thin wall", *REGISTER, book=target
        )
        assert ":1 expected" in result.output

    def test_an_unknown_class_lists_the_real_ones(self, book: Path) -> None:
        result = run("pattern", "register", "P-9", "x", "prototype", *REGISTER, book=book)
        assert result.exit_code == EXIT_RULE
        assert "is not a pattern class" in result.output

    def test_a_bad_flask_is_refused(self, book: Path) -> None:
        result = run(
            "pattern",
            "register",
            "P-9",
            "x",
            "thin wall",
            "--flask",
            "big",
            "--cavities",
            "2",
            "--weight",
            "60",
            book=book,
        )
        assert result.exit_code == EXIT_RULE
        assert "is not a flask volume" in result.output

    def test_the_same_identifier_twice_is_refused(self, book: Path) -> None:
        result = run("pattern", "register", "P-1", "x", "thin wall", *REGISTER, book=book)
        assert result.exit_code == EXIT_RULE

    def test_an_empty_register_says_so(self, tmp_path: Path) -> None:
        target = initialised(tmp_path)
        assert "no patterns" in run("pattern", "list", book=target).output

    def test_retiring(self, book: Path) -> None:
        assert run("pattern", "retire", "P-1", book=book).exit_code == 0
        assert "no patterns" in run("pattern", "list", book=book).output


class TestCheckingPourRecords:
    def test_a_consistent_record_passes(self, book: Path, tmp_path: Path) -> None:
        # Two 60 lb castings is 120 lb of metal in an 8 cubic foot flask, which
        # is close to six to one.
        load_pours(book, tmp_path, "60000")
        result = run("pattern", "check-pours", "P-1", "--on", WHEN, book=book)
        assert result.exit_code == 0
        assert "consistent with the geometry" in result.output

    def test_a_wild_record_is_flagged(self, book: Path, tmp_path: Path) -> None:
        load_pours(book, tmp_path, "300000")
        result = run("pattern", "check-pours", "P-1", "--on", WHEN, book=book)
        assert "check the pour record" in result.output
        assert "carries the same error" in result.output

    def test_it_names_both_ratios(self, book: Path, tmp_path: Path) -> None:
        load_pours(book, tmp_path, "300000")
        result = run("pattern", "check-pours", "P-1", "--on", WHEN, book=book)
        assert "30.00:1" in result.output

    def test_a_day_with_no_pour_says_so(self, book: Path) -> None:
        result = run("pattern", "check-pours", "P-1", "--on", WHEN, book=book)
        assert result.exit_code == 0
        assert "no medium jobbing pour was recorded" in result.output

    def test_a_pattern_that_is_not_registered(self, book: Path) -> None:
        result = run("pattern", "check-pours", "P-9", "--on", WHEN, book=book)
        assert result.exit_code == EXIT_RULE
