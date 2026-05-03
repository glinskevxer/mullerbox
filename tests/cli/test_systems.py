from __future__ import annotations

from pathlib import Path

import pytest

from mullerbox.cli.context import EXIT_RULE
from tests.cli.helpers import initialised, run

BALANCE = [
    "--on",
    "2025-11-10",
    "--mass",
    "300000",
    "--inventoried",
    "2025-09-01",
    "--batch",
    "6000",
    "--return-f",
    "118",
    "--dust-rate",
    "0.4",
    "--new-sand",
    "4000",
    "--core-return",
    "1200",
    "--shipped",
    "3800",
    "--dust",
    "1400",
    "--swept",
    "100",
    "--throughput",
    "350000",
]


@pytest.fixture
def book(tmp_path: Path) -> Path:
    return initialised(tmp_path)


class TestBalance:
    def test_a_tight_balance_closes(self, book: Path) -> None:
        result = run("system", "balance", *BALANCE, book=book)
        assert result.exit_code == 0
        assert "balance closes" in result.output

    def test_it_lists_both_sides(self, book: Path) -> None:
        result = run("system", "balance", *BALANCE, book=book)
        for term in ("new sand in", "shipped on castings", "dust expected"):
            assert term in result.output

    def test_a_wide_balance_does_not_close(self, book: Path) -> None:
        args = list(BALANCE)
        args[args.index("--new-sand") + 1] = "40000"
        result = run("system", "balance", *args, book=book)
        assert "does not close" in result.output
        assert "more sand in than out" in result.output

    def test_it_says_the_residual_is_not_distributed(self, book: Path) -> None:
        result = run("system", "balance", *BALANCE, book=book)
        assert "not distributed" in result.output

    def test_the_dust_variance_is_reported(self, book: Path) -> None:
        args = list(BALANCE)
        args[args.index("--dust") + 1] = "700"
        result = run("system", "balance", *args, book=book)
        assert "dust variance" in result.output
        assert "-50.00%" in result.output

    def test_a_nameplate_mass_is_called_out(self, book: Path) -> None:
        args = [*BALANCE, "--basis", "nameplate"]
        result = run("system", "balance", *args, book=book)
        assert "nameplate figure" in result.output
        assert "carries the same error" in result.output

    def test_a_stale_inventory_is_called_out(self, book: Path) -> None:
        args = list(BALANCE)
        args[args.index("--inventoried") + 1] = "2024-01-01"
        result = run("system", "balance", *args, book=book)
        assert "not been inventoried recently enough" in result.output

    def test_a_fresh_measured_mass_says_neither(self, book: Path) -> None:
        result = run("system", "balance", *BALANCE, book=book)
        assert "nameplate figure" not in result.output
        assert "inventoried recently enough" not in result.output

    def test_a_muller_bigger_than_the_system_is_refused(self, book: Path) -> None:
        args = list(BALANCE)
        args[args.index("--mass") + 1] = "5000"
        result = run("system", "balance", *args, book=book)
        assert result.exit_code == EXIT_RULE
        assert "more than the system" in result.output

    def test_an_unknown_basis_lists_the_real_ones(self, book: Path) -> None:
        args = [*BALANCE, "--basis", "guessed"]
        result = run("system", "balance", *args, book=book)
        assert result.exit_code == EXIT_RULE
        assert "is not a mass basis" in result.output


class TestCooler:
    def test_sizing_for_a_target(self, book: Path) -> None:
        result = run(
            "system",
            "cooler",
            "--sand",
            "100000",
            "--entering-f",
            "200",
            "--wet-bulb-f",
            "60",
            "--wanted-f",
            "115",
            book=book,
        )
        assert result.exit_code == 0
        assert "of water to take" in result.output

    def test_an_unreachable_target_says_why(self, book: Path) -> None:
        result = run(
            "system",
            "cooler",
            "--sand",
            "100000",
            "--entering-f",
            "200",
            "--wet-bulb-f",
            "90",
            "--wanted-f",
            "85",
            book=book,
        )
        assert "wet bulb" in result.output
        assert "the floor is" in result.output

    def test_a_spray_rate_says_where_it_lands(self, book: Path) -> None:
        result = run(
            "system",
            "cooler",
            "--sand",
            "100000",
            "--entering-f",
            "200",
            "--wet-bulb-f",
            "60",
            "--water",
            "1660",
            book=book,
        )
        assert result.exit_code == 0
        assert "takes" in result.output
        assert "F" in result.output

    def test_neither_option_asks_for_one(self, book: Path) -> None:
        result = run(
            "system",
            "cooler",
            "--sand",
            "100000",
            "--entering-f",
            "200",
            "--wet-bulb-f",
            "60",
            book=book,
        )
        assert result.exit_code == 0
        assert "give either a target" in result.output

    def test_a_cooler_does_not_heat(self, book: Path) -> None:
        result = run(
            "system",
            "cooler",
            "--sand",
            "100000",
            "--entering-f",
            "100",
            "--wet-bulb-f",
            "60",
            "--wanted-f",
            "150",
            book=book,
        )
        assert result.exit_code == EXIT_RULE
        assert "does not heat" in result.output


SHEET = [
    "--on",
    "2025-11-10",
    "--mass",
    "300000",
    "--inventoried",
    "2025-09-01",
    "--batch",
    "6000",
    "--return-f",
    "118",
    "--dust-rate",
    "0.4",
]
LABELS = ["6", "12", "20", "30", "40", "50", "70", "100", "140", "200", "270", "PAN"]


def sieve_csv(sample_id: str, **held: str) -> str:
    masses = dict.fromkeys(LABELS, "0.00")
    masses.update(held)
    rows = "".join(f"{sample_id},{k},{v},50.00\n" for k, v in masses.items())
    return "sample,screen,retained,charged\n" + rows


class TestTheSystemSheet:
    def test_a_sound_system_says_so(self, book: Path) -> None:
        result = run("system", "report", *SHEET, book=book)
        assert result.exit_code == 0
        assert "nothing about the system needs attention" in result.output

    def test_a_nameplate_mass_leads_the_sheet(self, book: Path) -> None:
        result = run("system", "report", *SHEET, "--basis", "nameplate", book=book)
        assert "CANNOT BE DOSED AGAINST" in result.output

    def test_hot_return_sand_is_called_out(self, book: Path) -> None:
        args = list(SHEET)
        args[args.index("--return-f") + 1] = "140"
        result = run("system", "report", *args, book=book)
        assert "flash off" in result.output

    def test_the_table_carries_the_derived_numbers(self, book: Path) -> None:
        result = run("system", "report", *SHEET, book=book)
        assert "turns per pass" in result.output
        assert "dust loss rate" in result.output


class TestTheCollector:
    def _load(self, book: Path, tmp_path: Path, sample: str, **held: str) -> None:
        run("catalogue", "load-afs", book=book)
        run(
            "lab",
            "sample-add",
            sample,
            "--on",
            "2025-11-10",
            "--point",
            "muller",
            "--system",
            "two",
            book=book,
        )
        path = tmp_path / f"{sample}.csv"
        path.write_text(sieve_csv(sample, **held), encoding="utf-8")
        run("import", "sieve", str(path), "--series", "AFS US 11 screen", book=book)

    def test_a_fine_sand_loses_something(self, book: Path, tmp_path: Path) -> None:
        self._load(book, tmp_path, "S-1", **{"140": "30.00", "270": "20.00"})
        result = run("system", "collector", "S-1", "--throughput", "100000", book=book)
        assert result.exit_code == 0
        assert "to the collector" in result.output
        assert "of the throughput" in result.output

    def test_a_sand_that_is_all_fines_says_nothing_survives(
        self, book: Path, tmp_path: Path
    ) -> None:
        self._load(book, tmp_path, "S-4", **{"270": "50.00"})
        result = run("system", "collector", "S-4", "--throughput", "100000", book=book)
        assert result.exit_code == 0
        assert "nothing of it survives the pass" in result.output

    def test_a_coarse_sand_loses_nothing(self, book: Path, tmp_path: Path) -> None:
        self._load(book, tmp_path, "S-2", **{"20": "50.00"})
        result = run("system", "collector", "S-2", "--throughput", "100000", book=book)
        assert "nothing on this sand is fine enough" in result.output

    def test_it_names_the_drift_no_daily_reading_shows(self, book: Path, tmp_path: Path) -> None:
        self._load(book, tmp_path, "S-3", **{"70": "25.00", "200": "25.00"})
        result = run("system", "collector", "S-3", "--throughput", "100000", book=book)
        assert "drifts from GFN" in result.output
        assert "no daily reading shows" in result.output

    def test_a_sample_with_no_analysis(self, book: Path) -> None:
        result = run("system", "collector", "S-9", "--throughput", "100000", book=book)
        assert result.exit_code == EXIT_RULE
