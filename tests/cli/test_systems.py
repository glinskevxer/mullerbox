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
