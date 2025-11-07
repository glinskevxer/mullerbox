from __future__ import annotations

from pathlib import Path

import pytest

from mullerbox.cli.context import EXIT_RULE
from tests.cli.helpers import initialised, run

WHEN = "2025-11-04"


@pytest.fixture
def book(tmp_path: Path) -> Path:
    target = initialised(tmp_path)
    for material, rate in (
        ("bentonite", "142.00"),
        ("seacoal", "196.50"),
        ("new sand", "38.25"),
        ("water", "0"),
    ):
        assert (
            run("cost", "set-price", material, rate, "--from", "2025-01-06", book=target).exit_code
            == 0
        )
    return target


def with_heat(book: Path) -> Path:
    run(
        "production",
        "record-heat",
        "H-1",
        "--on",
        WHEN,
        "--mold",
        "M-1:heavy jobbing:700",
        "--casting",
        "C-1:M-1:20000:shipped",
        "--casting",
        "C-2:M-1:2000:scrapped",
        book=book,
    )
    return book


class TestPrices:
    def test_setting_and_showing(self, book: Path) -> None:
        result = run("cost", "prices", "--on", WHEN, book=book)
        assert result.exit_code == 0
        assert "142" in result.output
        assert "NOT PRICED" not in result.output

    def test_a_hole_is_named(self, tmp_path: Path) -> None:
        target = initialised(tmp_path)
        run("cost", "set-price", "bentonite", "142.00", "--from", "2025-01-06", book=target)
        result = run("cost", "prices", "--on", WHEN, book=target)
        assert "NOT PRICED" in result.output
        assert "no price on or before" in result.output

    def test_the_same_material_and_day_twice_is_refused(self, book: Path) -> None:
        result = run("cost", "set-price", "bentonite", "158.00", "--from", "2025-01-06", book=book)
        assert result.exit_code == EXIT_RULE

    def test_a_rise_takes_effect_from_its_date(self, book: Path) -> None:
        run("cost", "set-price", "bentonite", "158.00", "--from", "2025-06-02", book=book)
        march = run("cost", "prices", "--on", "2025-03-01", book=book)
        july = run("cost", "prices", "--on", "2025-07-01", book=book)
        assert "142" in march.output
        assert "158" in july.output

    def test_an_unknown_material_lists_the_real_ones(self, book: Path) -> None:
        result = run("cost", "set-price", "gravel", "10", "--from", "2025-01-06", book=book)
        assert result.exit_code == EXIT_RULE
        assert "is not a material" in result.output


class TestTheShiftSheet:
    def test_it_prices_what_was_actually_charged(self, book: Path) -> None:
        with_heat(book)
        result = run(
            "cost", "shift", "--on", WHEN, "--bentonite", "2000", "--new-sand", "4000", book=book
        )
        assert result.exit_code == 0
        assert "$142.00" in result.output
        assert "$76.50" in result.output
        assert "total $218.50" in result.output

    def test_the_good_iron_comes_off_the_book(self, book: Path) -> None:
        with_heat(book)
        result = run("cost", "shift", "--on", WHEN, "--bentonite", "2000", book=book)
        assert "from the heats on the book" in result.output
        assert "10.000 t" in result.output

    def test_scrapped_castings_are_not_good_iron(self, book: Path) -> None:
        with_heat(book)
        result = run("cost", "shift", "--on", WHEN, "--bentonite", "2000", book=book)
        assert "11.000 t" not in result.output

    def test_a_typed_figure_says_it_was_typed(self, book: Path) -> None:
        result = run(
            "cost", "shift", "--on", WHEN, "--bentonite", "2000", "--good-iron", "40000", book=book
        )
        assert "as typed, not from the book" in result.output

    def test_the_cost_per_ton_is_reported(self, book: Path) -> None:
        with_heat(book)
        result = run("cost", "shift", "--on", WHEN, "--bentonite", "2000", book=book)
        assert "per ton of good iron $14.20" in result.output

    def test_the_largest_line_is_named(self, book: Path) -> None:
        with_heat(book)
        result = run(
            "cost", "shift", "--on", WHEN, "--bentonite", "2000", "--water", "9000", book=book
        )
        assert "largest line is bentonite" in result.output

    def test_water_appears_at_zero_rather_than_vanishing(self, book: Path) -> None:
        with_heat(book)
        result = run(
            "cost", "shift", "--on", WHEN, "--bentonite", "2000", "--water", "9000", book=book
        )
        assert "water" in result.output
        assert "$0.00" in result.output

    def test_a_day_with_no_heats_is_refused_by_name(self, book: Path) -> None:
        # After the prices took effect, so the price lookup is not what fires.
        result = run("cost", "shift", "--on", "2025-02-03", "--bentonite", "2000", book=book)
        assert result.exit_code == EXIT_RULE
        assert "no heats were recorded" in result.output

    def test_a_date_before_the_prices_is_refused_by_the_price_lookup(self, book: Path) -> None:
        result = run("cost", "shift", "--on", "2025-01-02", "--bentonite", "2000", book=book)
        assert result.exit_code == EXIT_RULE
        assert "price on or before" in result.output

    def test_no_good_iron_says_there_is_no_rate(self, book: Path) -> None:
        result = run(
            "cost", "shift", "--on", WHEN, "--bentonite", "2000", "--good-iron", "0", book=book
        )
        assert result.exit_code == 0
        assert "no good iron" in result.output
        assert "per ton of good iron" not in result.output

    def test_a_missing_price_stops_the_costing(self, tmp_path: Path) -> None:
        target = initialised(tmp_path)
        run("cost", "set-price", "bentonite", "142.00", "--from", "2025-01-06", book=target)
        result = run(
            "cost",
            "shift",
            "--on",
            WHEN,
            "--bentonite",
            "2000",
            "--good-iron",
            "40000",
            book=target,
        )
        assert result.exit_code == EXIT_RULE
        assert "price on or before" in result.output

    def test_charging_nothing_costs_nothing(self, book: Path) -> None:
        with_heat(book)
        result = run("cost", "shift", "--on", WHEN, book=book)
        assert "total $0.00" in result.output
