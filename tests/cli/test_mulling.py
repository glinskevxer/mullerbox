from __future__ import annotations

from pathlib import Path

import pytest

from mullerbox.cli.context import EXIT_RULE
from tests.cli.helpers import initialised, run

WHEN = "2025-09-22"
POURS = (
    "poured,pattern,metal,sand\n"
    f"{WHEN},medium jobbing,10000,60000\n"
    f"{WHEN},heavy jobbing,10000,30000\n"
)

PLAN_ARGS = [
    "--on",
    WHEN,
    "--pattern",
    "medium jobbing",
    "--system",
    "300000",
    "--batch",
    "6000",
    "--mb",
    "7.5",
    "--mb-target",
    "8.0",
    "--loi",
    "2.4",
    "--loi-ceiling",
    "3.5",
    "--total-clay",
    "10.5",
    "--dead-target",
    "2.0",
    "--losses",
    "2000",
    "--comp",
    "38",
    "--comp-target",
    "42",
    "--return-f",
    "118",
]


@pytest.fixture
def book(tmp_path: Path) -> Path:
    target = initialised(tmp_path)
    pours = tmp_path / "pours.csv"
    pours.write_text(POURS, encoding="utf-8")
    assert run("import", "pours", str(pours), book=target).exit_code == 0
    return target


class TestPlan:
    def test_it_prints_the_four_additions(self, book: Path) -> None:
        result = run("muller", "plan", *PLAN_ARGS, book=book)
        assert result.exit_code == 0
        for material in ("bentonite", "seacoal", "new sand", "water"):
            assert material in result.output

    def test_it_names_the_ratio_and_the_severity(self, book: Path) -> None:
        result = run("muller", "plan", *PLAN_ARGS, book=book)
        assert "6.00:1" in result.output
        assert "severity 1.000" in result.output

    def test_the_projected_bond_is_on_its_own_line(self, book: Path) -> None:
        result = run("muller", "plan", *PLAN_ARGS, book=book)
        assert "bond projected from" in result.output

    def test_a_harder_shift_asks_for_more_bentonite(self, book: Path) -> None:
        medium = run("muller", "plan", *PLAN_ARGS, book=book)
        heavy_args = list(PLAN_ARGS)
        heavy_args[heavy_args.index("--pattern") + 1] = "heavy jobbing"
        heavy = run("muller", "plan", *heavy_args, book=book)
        assert "3.00:1" in heavy.output
        assert medium.output != heavy.output

    def test_a_day_with_no_pour_record_is_refused(self, book: Path) -> None:
        args = list(PLAN_ARGS)
        args[args.index("--on") + 1] = "2025-01-01"
        result = run("muller", "plan", *args, book=book)
        assert result.exit_code == EXIT_RULE
        assert "pour record on" in result.output

    def test_a_class_that_was_not_poured_is_refused(self, book: Path) -> None:
        args = list(PLAN_ARGS)
        args[args.index("--pattern") + 1] = "thin wall"
        result = run("muller", "plan", *args, book=book)
        assert result.exit_code == EXIT_RULE

    def test_every_number_is_required(self, book: Path) -> None:
        args = [a for a in PLAN_ARGS if a not in {"--system", "300000"}]
        result = run("muller", "plan", *args, book=book)
        assert result.exit_code != 0

    def test_a_bad_date_names_the_format(self, book: Path) -> None:
        args = list(PLAN_ARGS)
        args[args.index("--on") + 1] = "22/09/2025"
        result = run("muller", "plan", *args, book=book)
        assert result.exit_code == EXIT_RULE
        assert "yyyy-mm-dd" in result.output


class TestCheckCycle:
    def test_a_good_schedule_passes(self, book: Path) -> None:
        result = run(
            "muller",
            "check-cycle",
            "--batch",
            "B-1",
            "--return-sand",
            "6000",
            "--bentonite",
            "140",
            "--water",
            "180",
            "--dry",
            "60",
            "--wet",
            "120",
            book=book,
        )
        assert result.exit_code == 0
        assert "passes" in result.output
        assert "3:00 total mull" in result.output

    def test_bentonite_with_too_little_dry_mull_is_refused(self, book: Path) -> None:
        result = run(
            "muller",
            "check-cycle",
            "--batch",
            "B-1",
            "--return-sand",
            "6000",
            "--bentonite",
            "140",
            "--dry",
            "20",
            "--wet",
            "120",
            book=book,
        )
        assert result.exit_code == EXIT_RULE
        assert "distributes it" in result.output

    def test_water_with_no_dry_mull_is_refused(self, book: Path) -> None:
        result = run(
            "muller",
            "check-cycle",
            "--batch",
            "B-1",
            "--return-sand",
            "6000",
            "--water",
            "180",
            "--dry",
            "0",
            "--wet",
            "120",
            book=book,
        )
        assert result.exit_code == EXIT_RULE
        assert "no dry mull before it" in result.output

    def test_water_with_too_short_a_wet_mull_is_refused(self, book: Path) -> None:
        result = run(
            "muller",
            "check-cycle",
            "--batch",
            "B-1",
            "--return-sand",
            "6000",
            "--water",
            "180",
            "--dry",
            "60",
            "--wet",
            "30",
            book=book,
        )
        assert result.exit_code == EXIT_RULE
        assert "develops it" in result.output

    def test_an_overcharged_batch_is_refused(self, book: Path) -> None:
        result = run(
            "muller",
            "check-cycle",
            "--batch",
            "B-1",
            "--return-sand",
            "6000",
            "--bentonite",
            "900",
            "--dry",
            "60",
            "--wet",
            "120",
            book=book,
        )
        assert result.exit_code == EXIT_RULE
        assert "a muller can distribute" in result.output

    def test_a_batch_with_nothing_charged_still_checks(self, book: Path) -> None:
        result = run(
            "muller",
            "check-cycle",
            "--batch",
            "B-1",
            "--return-sand",
            "6000",
            "--dry",
            "10",
            "--wet",
            "0",
            book=book,
        )
        assert result.exit_code == 0


class TestRecordingWhatHappened:
    def test_a_normal_cycle_records(self, book: Path) -> None:
        result = run(
            "muller",
            "record",
            "B-1",
            "--on",
            WHEN,
            "--dry",
            "60",
            "--wet",
            "120",
            "--bentonite",
            "140",
            "--water",
            "180",
            book=book,
        )
        assert result.exit_code == 0
        assert "to schedule" in result.output

    def test_a_short_cycle_records_and_warns(self, book: Path) -> None:
        result = run(
            "muller",
            "record",
            "B-2",
            "--on",
            WHEN,
            "--dry",
            "60",
            "--wet",
            "20",
            "--bentonite",
            "140",
            "--water",
            "180",
            book=book,
        )
        assert result.exit_code == 0
        assert "short" in result.output
        assert "recorded anyway" in result.output

    def test_check_cycle_would_have_refused_the_same_schedule(self, book: Path) -> None:
        refused = run(
            "muller",
            "check-cycle",
            "--batch",
            "B-3",
            "--return-sand",
            "6000",
            "--water",
            "180",
            "--dry",
            "60",
            "--wet",
            "20",
            book=book,
        )
        assert refused.exit_code == EXIT_RULE
        recorded = run(
            "muller",
            "record",
            "B-3",
            "--on",
            WHEN,
            "--dry",
            "60",
            "--wet",
            "20",
            "--water",
            "180",
            book=book,
        )
        assert recorded.exit_code == 0

    def test_a_batch_left_in_the_muller(self, book: Path) -> None:
        run(
            "muller",
            "record",
            "B-4",
            "--on",
            WHEN,
            "--dry",
            "60",
            "--wet",
            "120",
            "--not-discharged",
            book=book,
        )
        result = run("muller", "history", "--from", WHEN, "--to", WHEN, book=book)
        assert "NO" in result.output
        assert "never discharged" in result.output

    def test_the_same_batch_twice_is_refused(self, book: Path) -> None:
        run("muller", "record", "B-5", "--on", WHEN, "--dry", "60", "--wet", "120", book=book)
        result = run(
            "muller", "record", "B-5", "--on", WHEN, "--dry", "60", "--wet", "120", book=book
        )
        assert result.exit_code == EXIT_RULE


class TestHistory:
    def test_a_quiet_span_says_so(self, book: Path) -> None:
        result = run("muller", "history", "--from", WHEN, "--to", WHEN, book=book)
        assert result.exit_code == 0
        assert "no cycles were recorded" in result.output

    def test_a_clean_run_has_nothing_to_say(self, book: Path) -> None:
        for n in range(10):
            run(
                "muller",
                "record",
                f"C-{n}",
                "--on",
                WHEN,
                "--dry",
                "60",
                "--wet",
                "120",
                "--bentonite",
                "140",
                "--water",
                "180",
                book=book,
            )
        result = run("muller", "history", "--from", WHEN, "--to", WHEN, book=book)
        assert "nothing to say about the machine" in result.output

    def test_a_run_of_short_mulls_is_reported(self, book: Path) -> None:
        for n in range(5):
            run(
                "muller",
                "record",
                f"S-{n}",
                "--on",
                WHEN,
                "--dry",
                "60",
                "--wet",
                "20",
                "--bentonite",
                "140",
                "--water",
                "180",
                book=book,
            )
        result = run("muller", "history", "--from", WHEN, "--to", WHEN, book=book)
        assert "SHORT" in result.output
        assert "outrunning the muller" in result.output

    def test_water_heavy_cycles_are_reported(self, book: Path) -> None:
        for n in range(5):
            run(
                "muller",
                "record",
                f"W-{n}",
                "--on",
                WHEN,
                "--dry",
                "60",
                "--wet",
                "120",
                "--bentonite",
                "140",
                "--water",
                "300",
                book=book,
            )
        result = run(
            "muller", "history", "--from", WHEN, "--to", WHEN, "--planned-water", "180", book=book
        )
        assert "undeveloped bond" in result.output

    def test_a_backwards_span_is_refused(self, book: Path) -> None:
        result = run("muller", "history", "--from", "2026-01-01", "--to", "2025-01-01", book=book)
        assert result.exit_code == EXIT_RULE
        assert "backwards" in result.output
