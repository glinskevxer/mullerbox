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


class TestTheScrapExportNamesItsBand:
    def test_the_column_is_there(self, book: Path, tmp_path: Path) -> None:
        target = tmp_path / "scrap.csv"
        result = run("export", "scrap", str(target), "--heat", "H-1", book=book)
        assert result.exit_code == 0, result.output
        assert "perm band" in target.read_text(encoding="utf-8")

    def test_without_a_sample_it_says_anchor(self, book: Path, tmp_path: Path) -> None:
        target = tmp_path / "scrap.csv"
        run("export", "scrap", str(target), "--heat", "H-1", book=book)
        body = target.read_text(encoding="utf-8").splitlines()
        assert all(line.endswith("anchor") for line in body[1:])

    def test_a_sample_with_no_analysis_is_refused(self, book: Path, tmp_path: Path) -> None:
        target = tmp_path / "scrap.csv"
        result = run("export", "scrap", str(target), "--heat", "H-1", "--sample", "S-9", book=book)
        assert result.exit_code != 0


class TestExportingTheInventory:
    def take(self, book: Path, when: str, fill: str, complete: bool = True) -> None:
        args = [
            "system",
            "inventory",
            "--name",
            "two",
            "--on",
            when,
            "--vessel",
            f"silo:1000:{fill}:95",
        ]
        if not complete:
            args += ["--vessel", "hopper:400:0.50"]
        assert run(*args, book=book).exit_code == 0

    def test_one_row_per_count(self, book: Path, tmp_path: Path) -> None:
        self.take(book, "2025-01-06", "0.80")
        self.take(book, "2025-07-06", "0.75")
        target = tmp_path / "inv.csv"
        result = run("export", "inventory", str(target), "--name", "two", book=book)
        assert result.exit_code == 0, result.output
        assert "wrote 2 counts" in result.output
        assert len(target.read_text(encoding="utf-8").strip().splitlines()) == 3

    def test_the_header_names_the_columns(self, book: Path, tmp_path: Path) -> None:
        self.take(book, "2025-01-06", "0.80")
        target = tmp_path / "inv.csv"
        run("export", "inventory", str(target), "--name", "two", book=book)
        header = target.read_text(encoding="utf-8").splitlines()[0]
        assert header == "system,counted,total,in vessels,on the floor,change,state"

    def test_the_first_row_has_no_change(self, book: Path, tmp_path: Path) -> None:
        self.take(book, "2025-01-06", "0.80")
        self.take(book, "2025-07-06", "0.75")
        target = tmp_path / "inv.csv"
        run("export", "inventory", str(target), "--name", "two", book=book)
        rows = target.read_text(encoding="utf-8").splitlines()
        assert rows[1].split(",")[5] == ""
        assert rows[2].split(",")[5].startswith("-")

    def test_a_partial_count_is_marked(self, book: Path, tmp_path: Path) -> None:
        self.take(book, "2025-01-06", "0.80", complete=False)
        target = tmp_path / "inv.csv"
        run("export", "inventory", str(target), "--name", "two", book=book)
        assert target.read_text(encoding="utf-8").strip().endswith("partial")

    def test_the_run_is_reported_once_there_is_one(self, book: Path, tmp_path: Path) -> None:
        self.take(book, "2025-01-06", "0.80")
        self.take(book, "2025-07-06", "0.75")
        self.take(book, "2026-01-05", "0.70")
        target = tmp_path / "inv.csv"
        result = run("export", "inventory", str(target), "--name", "two", book=book)
        assert "lb a year" in result.output

    def test_a_short_run_reports_no_rate(self, book: Path, tmp_path: Path) -> None:
        self.take(book, "2025-01-06", "0.80")
        target = tmp_path / "inv.csv"
        result = run("export", "inventory", str(target), "--name", "two", book=book)
        assert "lb a year" not in result.output

    def test_a_system_never_counted_writes_a_header_only(self, book: Path, tmp_path: Path) -> None:
        target = tmp_path / "inv.csv"
        result = run("export", "inventory", str(target), "--name", "two", book=book)
        assert result.exit_code == 0, result.output
        assert "wrote 0 counts" in result.output
