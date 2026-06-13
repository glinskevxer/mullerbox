from __future__ import annotations

from pathlib import Path

import pytest

from mullerbox.cli.context import EXIT_RULE
from tests.cli.helpers import initialised, run

WHEN = "2025-11-03"

MOLDS = [
    "--mold",
    "M-1:heavy jobbing:700",
    "--mold",
    "M-2:thin wall:300",
]
CASTINGS = [
    "--casting",
    "C-1:M-1:200:scrapped",
    "--casting",
    "C-2:M-1:300:shipped",
    "--casting",
    "C-3:M-2:100:scrapped",
]

INSPECTIONS = "casting,disposition,defects\nC-1,scrapped,blow\nC-3,scrapped,blow\n"


@pytest.fixture
def book(tmp_path: Path) -> Path:
    target = initialised(tmp_path)
    run("spec", "load-default", "--on", "2025-01-06", book=target)
    run("catalogue", "instrument-add", "PERM-1", "permeability", book=target)
    run(
        "catalogue",
        "calibrate",
        "PERM-1",
        "C-1",
        "--on",
        "2025-01-06",
        "--days",
        "400",
        book=target,
    )
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
        book=target,
    )
    run(
        "lab",
        "result-add",
        "S-1",
        "perm",
        "40",
        "--instrument",
        "PERM-1",
        "--on",
        WHEN,
        book=target,
    )
    result = run("production", "record-heat", "H-1", "--on", WHEN, *MOLDS, *CASTINGS, book=target)
    assert result.exit_code == 0, result.output
    return target


class TestRecordingAHeat:
    def test_it_goes_on_the_book(self, book: Path) -> None:
        result = run("production", "heats", book=book)
        assert "H-1" in result.output
        assert "2 " in result.output

    def test_it_reports_the_metal_and_the_sand(self, tmp_path: Path) -> None:
        target = initialised(tmp_path)
        result = run(
            "production",
            "record-heat",
            "H-9",
            "--on",
            WHEN,
            "--mold",
            "M-1:heavy jobbing:700",
            "--casting",
            "C-9:M-1:200:shipped",
            book=target,
        )
        assert "200.00 lb of metal" in result.output
        assert "700.00 lb of sand" in result.output

    def test_a_malformed_mold_is_named(self, tmp_path: Path) -> None:
        target = initialised(tmp_path)
        result = run(
            "production",
            "record-heat",
            "H-9",
            "--on",
            WHEN,
            "--mold",
            "M-1:heavy jobbing",
            book=target,
        )
        assert result.exit_code == EXIT_RULE
        assert "is not ID:CLASS:SAND" in result.output

    def test_a_malformed_casting_is_named(self, tmp_path: Path) -> None:
        target = initialised(tmp_path)
        result = run(
            "production",
            "record-heat",
            "H-9",
            "--on",
            WHEN,
            "--mold",
            "M-1:heavy jobbing:700",
            "--casting",
            "C-9:M-1:200",
            book=target,
        )
        assert result.exit_code == EXIT_RULE
        assert "ID:MOLD:WEIGHT:DISPOSITION" in result.output

    def test_a_casting_for_a_mold_not_on_the_heat_is_refused(self, tmp_path: Path) -> None:
        target = initialised(tmp_path)
        result = run(
            "production",
            "record-heat",
            "H-9",
            "--on",
            WHEN,
            "--mold",
            "M-1:heavy jobbing:700",
            "--casting",
            "C-9:M-7:200:shipped",
            book=target,
        )
        assert result.exit_code == EXIT_RULE
        assert "which is not on the heat" in result.output

    def test_an_unknown_class_lists_the_real_ones(self, tmp_path: Path) -> None:
        target = initialised(tmp_path)
        result = run(
            "production",
            "record-heat",
            "H-9",
            "--on",
            WHEN,
            "--mold",
            "M-1:prototype:700",
            book=target,
        )
        assert result.exit_code == EXIT_RULE
        assert "is not a pattern class" in result.output

    def test_the_same_heat_twice_is_refused(self, book: Path) -> None:
        result = run("production", "record-heat", "H-1", "--on", WHEN, *MOLDS, *CASTINGS, book=book)
        assert result.exit_code == EXIT_RULE


class TestListing:
    def test_an_empty_book_says_so(self, tmp_path: Path) -> None:
        target = initialised(tmp_path)
        assert "no heats" in run("production", "heats", book=target).output

    def test_it_shows_the_scrap_rate_by_weight(self, book: Path) -> None:
        result = run("production", "heats", book=book)
        assert "50.00%" in result.output

    def test_narrowing_to_a_day(self, book: Path) -> None:
        assert "H-1" in run("production", "heats", "--on", WHEN, book=book).output
        assert "H-1" not in run("production", "heats", "--on", "2025-01-01", book=book).output


class TestTheScrapSheet:
    def test_it_runs_end_to_end(self, book: Path, tmp_path: Path) -> None:
        path = tmp_path / "insp.csv"
        path.write_text(INSPECTIONS, encoding="utf-8")
        result = run("production", "scrap", "H-1", "--inspections", str(path), book=book)
        assert result.exit_code == 0
        assert "scrap on heat H-1" in result.output

    def test_the_low_permeability_lands_on_the_sand(self, book: Path, tmp_path: Path) -> None:
        path = tmp_path / "insp.csv"
        path.write_text(INSPECTIONS, encoding="utf-8")
        result = run("production", "scrap", "H-1", "--inspections", str(path), book=book)
        assert "permeability" in result.output
        assert "sand" in result.output

    def test_without_inspections_nothing_reaches_the_sand(self, book: Path) -> None:
        result = run("production", "scrap", "H-1", book=book)
        assert result.exit_code == 0
        assert "pattern" in result.output

    def test_the_summary_is_one_line(self, book: Path) -> None:
        result = run("production", "scrap", "H-1", "--summary", book=book)
        assert result.exit_code == 0
        assert len([x for x in result.output.strip().split("\n") if x]) == 1

    def test_a_heat_that_is_not_there(self, book: Path) -> None:
        result = run("production", "scrap", "H-9", book=book)
        assert result.exit_code == EXIT_RULE

    def test_a_heat_that_poured_nothing_is_refused_by_name(self, tmp_path: Path) -> None:
        """Shares of nothing are undefined, not zero."""
        target = initialised(tmp_path)
        run("spec", "load-default", "--on", "2025-01-06", book=target)
        run(
            "production",
            "record-heat",
            "H-2",
            "--on",
            WHEN,
            "--mold",
            "M-1:heavy jobbing:700",
            book=target,
        )
        result = run("production", "scrap", "H-2", book=target)
        assert result.exit_code == EXIT_RULE
        assert "poured no metal" in result.output

    def test_a_heat_with_no_molds_at_all_is_refused(self, tmp_path: Path) -> None:
        target = initialised(tmp_path)
        run("spec", "load-default", "--on", "2025-01-06", book=target)
        result = run("production", "record-heat", "H-3", "--on", WHEN, book=target)
        assert result.exit_code != 0


class TestPareto:
    HEAVY_SCRAP = "casting,disposition,defects\nC-1,scrapped,penetration\nC-3,scrapped,pinhole\n"

    def test_it_ranks_by_weight(self, book: Path, tmp_path: Path) -> None:
        path = tmp_path / "insp.csv"
        path.write_text(self.HEAVY_SCRAP, encoding="utf-8")
        result = run("production", "pareto", "--inspections", str(path), book=book)
        assert result.exit_code == 0
        assert "work on:" in result.output

    def test_the_vital_few_are_marked(self, book: Path, tmp_path: Path) -> None:
        path = tmp_path / "insp.csv"
        path.write_text(self.HEAVY_SCRAP, encoding="utf-8")
        result = run("production", "pareto", "--inspections", str(path), book=book)
        assert "vital few" in result.output
        assert "cumulative" in result.output

    def test_an_empty_book_says_so(self, tmp_path: Path) -> None:
        target = initialised(tmp_path)
        run("spec", "load-default", "--on", "2025-01-06", book=target)
        path = tmp_path / "insp.csv"
        path.write_text(self.HEAVY_SCRAP, encoding="utf-8")
        result = run("production", "pareto", "--inspections", str(path), book=target)
        assert "no heats on the book to rank" in result.output

    def test_no_defects_written_means_nothing_to_rank(self, book: Path, tmp_path: Path) -> None:
        path = tmp_path / "insp.csv"
        path.write_text("casting,disposition,defects\nC-1,scrapped,\n", encoding="utf-8")
        result = run("production", "pareto", "--inspections", str(path), book=book)
        assert "no scrap to rank" in result.output

    def test_sand_only_narrows_it(self, book: Path, tmp_path: Path) -> None:
        path = tmp_path / "insp.csv"
        path.write_text(
            "casting,disposition,defects\nC-1,scrapped,blow\nC-3,scrapped,shrinkage\n",
            encoding="utf-8",
        )
        everything = run("production", "pareto", "--inspections", str(path), book=book)
        sand = run("production", "pareto", "--inspections", str(path), "--sand-only", book=book)
        assert "shrinkage" in everything.output
        assert "shrinkage" not in sand.output

    def test_narrowing_to_a_day(self, book: Path, tmp_path: Path) -> None:
        path = tmp_path / "insp.csv"
        path.write_text(self.HEAVY_SCRAP, encoding="utf-8")
        result = run(
            "production", "pareto", "--inspections", str(path), "--on", "2020-01-01", book=book
        )
        assert "no heats on the book to rank" in result.output


class TestYields:
    def test_all_three_are_named(self, book: Path) -> None:
        result = run("production", "yields", "H-1", "--sand-handled", "100000", book=book)
        assert result.exit_code == 0
        assert "what melting is judged on" in result.output
        assert "what the plant is paid on" in result.output
        assert "what the sand is judged on" in result.output

    def test_the_scrap_gap_is_spelled_out(self, book: Path) -> None:
        result = run("production", "yields", "H-1", "--sand-handled", "100000", book=book)
        assert "the gap between the first two" in result.output

    def test_a_heat_that_is_not_there(self, book: Path) -> None:
        result = run("production", "yields", "H-9", "--sand-handled", "100000", book=book)
        assert result.exit_code == EXIT_RULE

    def test_it_names_what_was_poured(self, book: Path) -> None:
        result = run("production", "yields", "H-1", "--sand-handled", "100000", book=book)
        assert "poured" in result.output


class TestMonth:
    def test_it_rolls_the_heats_in_the_span(self, book: Path) -> None:
        result = run(
            "production",
            "month",
            "--from",
            WHEN,
            "--to",
            WHEN,
            "--sand-handled",
            "100000",
            book=book,
        )
        assert result.exit_code == 0
        assert "1 heats" in result.output

    def test_a_quiet_span_says_so(self, book: Path) -> None:
        result = run(
            "production",
            "month",
            "--from",
            "2020-01-01",
            "--to",
            "2020-12-31",
            "--sand-handled",
            "100000",
            book=book,
        )
        assert "no heats were poured between" in result.output

    def test_a_backwards_span_is_refused(self, book: Path) -> None:
        result = run(
            "production",
            "month",
            "--from",
            "2026-01-01",
            "--to",
            "2025-01-01",
            "--sand-handled",
            "100000",
            book=book,
        )
        assert result.exit_code == EXIT_RULE
        assert "backwards" in result.output

    def test_it_names_all_three_ratios_too(self, book: Path) -> None:
        result = run(
            "production",
            "month",
            "--from",
            WHEN,
            "--to",
            WHEN,
            "--sand-handled",
            "100000",
            book=book,
        )
        assert "casting yield" in result.output
        assert "sand ratio" in result.output
