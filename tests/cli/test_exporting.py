from __future__ import annotations

from pathlib import Path

import pytest

from mullerbox.cli.context import EXIT_RULE
from tests.cli.helpers import initialised, run

WHEN = "2025-12-08"


@pytest.fixture
def book(tmp_path: Path) -> Path:
    target = initialised(tmp_path)
    run("spec", "load-default", "--on", "2025-01-06", book=target)
    run("catalogue", "instrument-add", "RAM-1", "compactability", book=target)
    run(
        "catalogue", "calibrate", "RAM-1", "C-1", "--on", "2025-01-06", "--days", "400", book=target
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
        "lab", "result-add", "S-1", "comp", "42", "--instrument", "RAM-1", "--on", WHEN, book=target
    )
    run(
        "production",
        "record-heat",
        "H-1",
        "--on",
        WHEN,
        "--mold",
        "M-1:heavy jobbing:700",
        "--casting",
        "C-1:M-1:200:scrapped",
        "--casting",
        "C-2:M-1:800:shipped",
        book=target,
    )
    run("cost", "set-price", "bentonite", "142.00", "--from", "2025-01-06", book=target)
    run(
        "programme",
        "set",
        "comp",
        "every_shift",
        "--on",
        "2025-01-06",
        "--because",
        "line critical",
        book=target,
    )
    return target


class TestResultsRoundTrip:
    def test_it_writes(self, book: Path, tmp_path: Path) -> None:
        out = tmp_path / "results.csv"
        result = run("export", "results", str(out), book=book)
        assert result.exit_code == 0
        assert "wrote 1 results" in result.output
        assert out.exists()

    def test_what_it_writes_imports_into_another_book(self, book: Path, tmp_path: Path) -> None:
        out = tmp_path / "results.csv"
        run("export", "results", str(out), book=book)

        other = tmp_path / "other"
        other.mkdir()
        second = initialised(other)
        run("catalogue", "instrument-add", "RAM-1", "compactability", book=second)
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
            book=second,
        )
        loaded = run("import", "bench", str(out), book=second)
        assert loaded.exit_code == 0
        assert "loaded 1 readings, 0 problems" in loaded.output

    def test_narrowing_to_one_property(self, book: Path, tmp_path: Path) -> None:
        out = tmp_path / "results.csv"
        result = run("export", "results", str(out), "--property", "perm", book=book)
        assert "wrote 0 results" in result.output

    def test_an_unknown_property_is_refused(self, book: Path, tmp_path: Path) -> None:
        out = tmp_path / "results.csv"
        result = run("export", "results", str(out), "--property", "stickiness", book=book)
        assert result.exit_code == EXIT_RULE


class TestOtherExports:
    def test_heats(self, book: Path, tmp_path: Path) -> None:
        out = tmp_path / "heats.csv"
        result = run("export", "heats", str(out), book=book)
        assert result.exit_code == 0
        assert "wrote 2 castings" in result.output
        assert "heavy jobbing" in out.read_text(encoding="utf-8")

    def test_scrap(self, book: Path, tmp_path: Path) -> None:
        out = tmp_path / "scrap.csv"
        result = run("export", "scrap", str(out), "--heat", "H-1", book=book)
        assert result.exit_code == 0
        assert "of them to sand" in result.output

    def test_scrap_for_a_heat_that_is_not_there(self, book: Path, tmp_path: Path) -> None:
        out = tmp_path / "scrap.csv"
        result = run("export", "scrap", str(out), "--heat", "H-9", book=book)
        assert result.exit_code == EXIT_RULE

    def test_prices(self, book: Path, tmp_path: Path) -> None:
        out = tmp_path / "prices.csv"
        result = run("export", "prices", str(out), book=book)
        assert result.exit_code == 0
        assert "wrote 1 prices" in result.output

    def test_due(self, book: Path, tmp_path: Path) -> None:
        out = tmp_path / "due.csv"
        result = run("export", "due", str(out), "--on", "2026-01-01", book=book)
        assert result.exit_code == 0
        assert "compactability" in out.read_text(encoding="utf-8")

    def test_an_empty_book_writes_a_header_only(self, tmp_path: Path) -> None:
        target = initialised(tmp_path)
        out = tmp_path / "heats.csv"
        result = run("export", "heats", str(out), book=target)
        assert result.exit_code == 0
        assert "wrote 0 castings" in result.output
        assert out.read_text(encoding="utf-8").strip() == (
            "heat,poured,mold,class,casting,weight,disposition"
        )

    def test_a_missing_directory_is_refused_cleanly(self, book: Path, tmp_path: Path) -> None:
        result = run("export", "heats", str(tmp_path / "nowhere" / "x.csv"), book=book)
        assert result.exit_code == EXIT_RULE
        assert "there is no directory at" in result.output
