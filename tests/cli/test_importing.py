from __future__ import annotations

from pathlib import Path

import pytest

from mullerbox.cli.context import EXIT_RULE
from tests.cli.helpers import initialised, run

BENCH = (
    "sample,property,reading,instrument,tested\n"
    "S-100,comp,42.0,RAM-1,2025-07-28\n"
    "S-100,perm,110,PERM-1,2025-07-28\n"
)
LABELS = ["6", "12", "20", "30", "40", "50", "70", "100", "140", "200", "270", "PAN"]
MASSES = {"50": "8.00", "70": "22.00", "100": "16.00", "140": "4.00"}
POURS = "poured,pattern,metal,sand\n2025-07-28,heavy jobbing,10000,35000\n"
INSPECTIONS = "casting,disposition,defects\nC-1,scrapped,blow\nC-2,shipped,\n"


def sieve_csv(sample_id: str = "S-100", charged: str = "50.00") -> str:
    rows = "".join(
        f"{sample_id},{label},{MASSES.get(label, '0.00')},{charged}\n" for label in LABELS
    )
    return "sample,screen,retained,charged\n" + rows


@pytest.fixture
def book(tmp_path: Path) -> Path:
    target = initialised(tmp_path)
    run("catalogue", "load-afs", book=target)
    for tag, kind in (("RAM-1", "compactability"), ("PERM-1", "permeability")):
        run("catalogue", "instrument-add", tag, kind, book=target)
    run(
        "lab",
        "sample-add",
        "S-100",
        "--on",
        "2025-07-28",
        "--point",
        "muller",
        "--system",
        "two",
        book=target,
    )
    return target


def write(tmp_path: Path, name: str, text: str) -> Path:
    target = tmp_path / name
    target.write_text(text, encoding="utf-8")
    return target


class TestBench:
    def test_a_clean_file_loads(self, book: Path, tmp_path: Path) -> None:
        path = write(tmp_path, "bench.csv", BENCH)
        result = run("import", "bench", str(path), book=book)
        assert result.exit_code == 0
        assert "loaded 2 readings, 0 problems" in result.output

    def test_the_readings_are_on_the_book(self, book: Path, tmp_path: Path) -> None:
        run("import", "bench", str(write(tmp_path, "b.csv", BENCH)), book=book)
        shown = run("lab", "sample", "S-100", book=book)
        assert "42.00%" in shown.output
        assert "110 AFS" in shown.output

    def test_a_bad_row_is_reported_and_the_rest_load(self, book: Path, tmp_path: Path) -> None:
        text = BENCH + "S-100,stickiness,4,RAM-1,2025-07-28\n"
        result = run("import", "bench", str(write(tmp_path, "b.csv", text)), book=book)
        assert result.exit_code == 0
        assert "loaded 2 readings, 1 problems" in result.output
        assert "not a sand property" in result.output

    def test_strict_refuses_the_whole_file(self, book: Path, tmp_path: Path) -> None:
        text = BENCH + "S-100,stickiness,4,RAM-1,2025-07-28\n"
        result = run("import", "bench", str(write(tmp_path, "b.csv", text)), "--strict", book=book)
        assert result.exit_code == EXIT_RULE
        assert "--strict was given" in result.output

    def test_a_reading_for_an_unknown_sample_is_skipped(self, book: Path, tmp_path: Path) -> None:
        text = "sample,property,reading,instrument,tested\nS-999,comp,42,RAM-1,2025-07-28\n"
        result = run("import", "bench", str(write(tmp_path, "b.csv", text)), book=book)
        assert "is not on the book" in result.output
        assert "loaded 0 readings" in result.output

    def test_a_missing_file_is_refused_cleanly(self, book: Path, tmp_path: Path) -> None:
        result = run("import", "bench", str(tmp_path / "nothing.csv"), book=book)
        assert result.exit_code == EXIT_RULE
        assert "there is no file at" in result.output


class TestSieve:
    def test_a_clean_file_loads(self, book: Path, tmp_path: Path) -> None:
        path = write(tmp_path, "sieve.csv", sieve_csv())
        result = run("import", "sieve", str(path), "--series", "AFS US 11 screen", book=book)
        assert result.exit_code == 0
        assert "loaded 1 analyses" in result.output

    def test_the_fineness_can_then_be_read(self, book: Path, tmp_path: Path) -> None:
        path = write(tmp_path, "sieve.csv", sieve_csv())
        run("import", "sieve", str(path), "--series", "AFS US 11 screen", book=book)
        result = run("lab", "fineness", "S-100", book=book)
        assert result.exit_code == 0
        assert "GFN" in result.output
        assert "three screen" in result.output or "four screen" in result.output

    def test_a_stack_that_will_not_close_is_one_problem(self, book: Path, tmp_path: Path) -> None:
        path = write(tmp_path, "sieve.csv", sieve_csv(charged="60.00"))
        result = run("import", "sieve", str(path), "--series", "AFS US 11 screen", book=book)
        assert "closure tolerance" in result.output
        assert "loaded 0 analyses" in result.output

    def test_an_unknown_series_is_refused(self, book: Path, tmp_path: Path) -> None:
        path = write(tmp_path, "sieve.csv", sieve_csv())
        result = run("import", "sieve", str(path), "--series", "nothing", book=book)
        assert result.exit_code == EXIT_RULE


class TestPours:
    def test_a_clean_file_loads(self, book: Path, tmp_path: Path) -> None:
        path = write(tmp_path, "pours.csv", POURS)
        result = run("import", "pours", str(path), book=book)
        assert result.exit_code == 0
        assert "loaded 1 pours" in result.output

    def test_a_bad_class_is_reported(self, book: Path, tmp_path: Path) -> None:
        text = POURS + "2025-07-28,prototype,1000,3000\n"
        result = run("import", "pours", str(write(tmp_path, "p.csv", text)), book=book)
        assert "not a pattern class" in result.output


class TestInspections:
    def test_it_reads_and_reports_without_writing(self, book: Path, tmp_path: Path) -> None:
        path = write(tmp_path, "insp.csv", INSPECTIONS)
        result = run("import", "inspections", str(path), book=book)
        assert result.exit_code == 0
        assert "2 inspections, 1 scrapped" in result.output
        assert "1 carrying defects" in result.output

    def test_a_shipped_casting_with_defects_is_a_problem(self, book: Path, tmp_path: Path) -> None:
        text = INSPECTIONS + "C-3,shipped,blow\n"
        result = run("import", "inspections", str(write(tmp_path, "i.csv", text)), book=book)
        assert "shipped with 1 defects" in result.output


CYCLES = (
    "batch,run,dry,wet,bentonite,water,discharged\n"
    "B-1,2026-03-23,60,120,140,180,yes\n"
    "B-2,2026-03-23,60,20,140,180,yes\n"
    "B-3,2026-03-24,60,120,,,no\n"
)


class TestCycles:
    def test_a_clean_log_loads(self, book: Path, tmp_path: Path) -> None:
        path = write(tmp_path, "cycles.csv", CYCLES)
        result = run("import", "cycles", str(path), book=book)
        assert result.exit_code == 0
        assert "loaded 3 cycles over 2 days" in result.output

    def test_short_mulls_are_loaded_not_dropped(self, book: Path, tmp_path: Path) -> None:
        path = write(tmp_path, "cycles.csv", CYCLES)
        result = run("import", "cycles", str(path), book=book)
        assert "1 of them mulled short" in result.output

    def test_the_history_can_then_be_read(self, book: Path, tmp_path: Path) -> None:
        path = write(tmp_path, "cycles.csv", CYCLES)
        run("import", "cycles", str(path), book=book)
        result = run("muller", "history", "--from", "2026-03-23", "--to", "2026-03-24", book=book)
        assert result.exit_code == 0
        assert "SHORT" in result.output
        assert "never discharged" in result.output

    def test_loading_the_same_file_twice_skips_rather_than_failing(
        self, book: Path, tmp_path: Path
    ) -> None:
        path = write(tmp_path, "cycles.csv", CYCLES)
        run("import", "cycles", str(path), book=book)
        again = run("import", "cycles", str(path), book=book)
        assert again.exit_code == 0
        assert "loaded 0 cycles" in again.output
        assert "3 already on the book" in again.output

    def test_a_blank_discharge_flag_is_one_problem(self, book: Path, tmp_path: Path) -> None:
        text = CYCLES + "B-4,2026-03-24,60,120,,,\n"
        result = run("import", "cycles", str(write(tmp_path, "c.csv", text)), book=book)
        assert "does not report it" in result.output
        assert "loaded 3 cycles" in result.output

    def test_strict_refuses_the_whole_file(self, book: Path, tmp_path: Path) -> None:
        text = CYCLES + "B-4,2026-03-24,60,120,,,\n"
        result = run("import", "cycles", str(write(tmp_path, "c.csv", text)), "--strict", book=book)
        assert result.exit_code == EXIT_RULE


WEAR = "screen,measured,checked\n30,600,2026-07-01\n40,425,2026-07-01\n"
FULL_WEAR = "screen,measured,checked\n" + "".join(
    f"{label},{micro},2026-07-01\n"
    for label, micro in (
        ("6", 3350),
        ("12", 1700),
        ("20", 850),
        ("30", 600),
        ("40", 425),
        ("50", 300),
        ("70", 212),
        ("100", 150),
        ("140", 106),
        ("200", 75),
        ("270", 53),
    )
)


class TestWear:
    def test_a_clean_sheet_loads(self, book: Path, tmp_path: Path) -> None:
        result = run(
            "import",
            "wear",
            str(write(tmp_path, "w.csv", WEAR)),
            "--series",
            "AFS US 11 screen",
            book=book,
        )
        assert result.exit_code == 0, result.output
        assert "loaded 2 checks, 0 problems" in result.output

    def test_the_checks_are_on_the_book(self, book: Path, tmp_path: Path) -> None:
        run(
            "import",
            "wear",
            str(write(tmp_path, "w.csv", WEAR)),
            "--series",
            "AFS US 11 screen",
            book=book,
        )
        shown = run("screens", "wear-history", "AFS US 11 screen", "30", book=book)
        assert "600" in shown.output

    def test_a_frame_from_the_wrong_drawer_is_named(self, book: Path, tmp_path: Path) -> None:
        text = "screen,measured,checked\n33,600,2026-07-01\n"
        result = run(
            "import",
            "wear",
            str(write(tmp_path, "w.csv", text)),
            "--series",
            "AFS US 11 screen",
            book=book,
        )
        assert "wrong drawer" in result.output
        assert "loaded 0 checks, 1 problems" in result.output

    def test_strict_refuses_the_whole_file(self, book: Path, tmp_path: Path) -> None:
        text = "screen,measured,checked\n33,600,2026-07-01\n"
        result = run(
            "import",
            "wear",
            str(write(tmp_path, "w.csv", text)),
            "--series",
            "AFS US 11 screen",
            "--strict",
            book=book,
        )
        assert result.exit_code == EXIT_RULE

    def test_it_says_what_the_sheet_did_not_cover(self, book: Path, tmp_path: Path) -> None:
        result = run(
            "import",
            "wear",
            str(write(tmp_path, "w.csv", WEAR)),
            "--series",
            "AFS US 11 screen",
            book=book,
        )
        assert "did not cover" in result.output

    def test_a_full_sheet_leaves_nothing_uncovered(self, book: Path, tmp_path: Path) -> None:
        result = run(
            "import",
            "wear",
            str(write(tmp_path, "w.csv", FULL_WEAR)),
            "--series",
            "AFS US 11 screen",
            book=book,
        )
        assert "did not cover" not in result.output
        assert "loaded 11 checks" in result.output

    def test_a_full_sheet_makes_the_stack_fit(self, book: Path, tmp_path: Path) -> None:
        run(
            "import",
            "wear",
            str(write(tmp_path, "w.csv", FULL_WEAR)),
            "--series",
            "AFS US 11 screen",
            book=book,
        )
        shown = run("screens", "stack", "AFS US 11 screen", "--on", "2026-07-02", book=book)
        assert "fit to use" in shown.output

    def test_a_worn_screen_is_warned_about(self, book: Path, tmp_path: Path) -> None:
        text = "screen,measured,checked\n30,680,2026-07-01\n"
        result = run(
            "import",
            "wear",
            str(write(tmp_path, "w.csv", text)),
            "--series",
            "AFS US 11 screen",
            book=book,
        )
        assert "past the wear limit" in result.output

    def test_an_unknown_series_is_refused(self, book: Path, tmp_path: Path) -> None:
        result = run(
            "import", "wear", str(write(tmp_path, "w.csv", WEAR)), "--series", "nope", book=book
        )
        assert result.exit_code != 0
