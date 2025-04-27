from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from mullerbox.addition.material import Addition, Material
from mullerbox.charge.cost import PriceList, cost_of
from mullerbox.errors import BadInputError, RuleError
from mullerbox.units.bulk import Pounds
from mullerbox.units.money import Money, PricePerTon

PRICES = PriceList(
    prices={
        Material.BENTONITE: PricePerTon("142.00"),
        Material.SEACOAL: PricePerTon("196.50"),
        Material.NEW_SAND: PricePerTon("38.25"),
        Material.WATER: PricePerTon("0"),
    }
)
GOOD_IRON = Pounds.of_tons(20)


def add(material: Material, mass: str) -> Addition:
    return Addition(material=material, mass=Pounds(mass), reason="test")


class TestPriceList:
    def test_it_needs_a_price_for_everything(self) -> None:
        with pytest.raises(RuleError, match="no price for"):
            PriceList(prices={Material.BENTONITE: PricePerTon("142.00")})

    def test_it_is_keyed_by_material(self) -> None:
        bad: Any = {"bentonite": PricePerTon("142.00")}
        with pytest.raises(BadInputError, match="keyed by material"):
            PriceList(prices=bad)

    def test_it_holds_prices(self) -> None:
        bad: Any = dict.fromkeys(Material, "142.00")
        with pytest.raises(BadInputError, match="holds prices per ton"):
            PriceList(prices=bad)

    def test_lookup(self) -> None:
        assert PRICES.price_of(Material.BENTONITE) == PricePerTon("142.00")
        bad: Any = "bentonite"
        with pytest.raises(BadInputError, match="material is expected"):
            PRICES.price_of(bad)


class TestCosting:
    def test_one_line_per_material(self) -> None:
        got = cost_of(
            [add(Material.BENTONITE, "500"), add(Material.NEW_SAND, "4000")],
            PRICES,
            GOOD_IRON,
        )
        assert len(got.lines) == 2

    def test_repeat_additions_of_one_material_merge(self) -> None:
        got = cost_of(
            [add(Material.BENTONITE, "300"), add(Material.BENTONITE, "200")],
            PRICES,
            GOOD_IRON,
        )
        assert len(got.lines) == 1
        assert got.lines[0].mass == Pounds(500)

    def test_the_total_is_the_sum_of_the_lines(self) -> None:
        got = cost_of(
            [add(Material.BENTONITE, "500"), add(Material.NEW_SAND, "4000")],
            PRICES,
            GOOD_IRON,
        )
        assert got.total == Money("35.50") + Money("76.50")

    def test_a_line_is_priced_at_the_list_rate(self) -> None:
        got = cost_of([add(Material.BENTONITE, "2000")], PRICES, GOOD_IRON)
        assert got.lines[0].cost == Money("142.00")

    def test_water_gets_a_zero_line_rather_than_no_line(self) -> None:
        got = cost_of([add(Material.WATER, "900")], PRICES, GOOD_IRON)
        line = got.line_for(Material.WATER)
        assert line is not None
        assert line.cost.is_zero

    def test_a_material_never_charged_gets_no_line(self) -> None:
        got = cost_of([add(Material.BENTONITE, "500")], PRICES, GOOD_IRON)
        assert got.line_for(Material.SEACOAL) is None

    def test_nothing_charged_costs_nothing(self) -> None:
        got = cost_of([], PRICES, GOOD_IRON)
        assert got.total.is_zero
        assert got.heaviest_line is None

    def test_the_heaviest_line_ignores_the_free_one(self) -> None:
        got = cost_of(
            [add(Material.WATER, "9000"), add(Material.BENTONITE, "500")],
            PRICES,
            GOOD_IRON,
        )
        heaviest = got.heaviest_line
        assert heaviest is not None
        assert heaviest.material is Material.BENTONITE


class TestPerTonOfGoodIron:
    def test_it_divides_by_what_shipped(self) -> None:
        got = cost_of([add(Material.BENTONITE, "2000")], PRICES, Pounds.of_tons(20))
        assert got.per_ton_of_good_iron == Decimal("7.10")

    def test_scrapping_makes_the_shift_more_expensive(self) -> None:
        additions = [add(Material.BENTONITE, "2000")]
        clean = cost_of(additions, PRICES, Pounds.of_tons(20))
        scrappy = cost_of(additions, PRICES, Pounds.of_tons(10))
        assert scrappy.per_ton_of_good_iron > clean.per_ton_of_good_iron

    def test_no_good_iron_has_no_cost_per_ton(self) -> None:
        got = cost_of([add(Material.BENTONITE, "500")], PRICES, Pounds.zero())
        with pytest.raises(RuleError, match="no cost per ton"):
            assert got.per_ton_of_good_iron


class TestGuards:
    def test_the_arguments_are_checked(self) -> None:
        bad_prices: Any = {}
        with pytest.raises(BadInputError, match="needs a price list"):
            cost_of([], bad_prices, GOOD_IRON)
        bad_iron: Any = 40000
        with pytest.raises(BadInputError, match="good iron is a bulk mass"):
            cost_of([], PRICES, bad_iron)
        bad_add: Any = [Pounds(1)]
        with pytest.raises(BadInputError, match="only additions can be costed"):
            cost_of(bad_add, PRICES, GOOD_IRON)

    def test_str_reads_as_a_sheet_line(self) -> None:
        got = cost_of([add(Material.BENTONITE, "2000")], PRICES, GOOD_IRON)
        assert str(got) == "$142.00 of sand against 20.000 t of good iron"
        assert "bentonite" in str(got.lines[0])
