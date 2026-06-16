from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from mullerbox.addition.material import Addition, Material
from mullerbox.charge.budget import Budget, variance_of
from mullerbox.charge.cost import PriceList, ShiftCost, cost_of
from mullerbox.errors import BadInputError, RuleError
from mullerbox.units.bulk import Pounds
from mullerbox.units.money import PricePerTon

GOOD_IRON = Pounds.of_tons(100)


def prices(bentonite: str = "142.00") -> PriceList:
    return PriceList(
        prices={
            Material.BENTONITE: PricePerTon(bentonite),
            Material.SEACOAL: PricePerTon("196.50"),
            Material.NEW_SAND: PricePerTon("38.25"),
            Material.WATER: PricePerTon("0"),
        }
    )


def budget(pounds_per_ton: str = "20", price: str = "142.00") -> Budget:
    return Budget(
        material=Material.BENTONITE,
        pounds_per_ton=Decimal(pounds_per_ton),
        price=PricePerTon(price),
    )


def actual(mass: str = "2000", price: str = "142.00") -> ShiftCost:
    charged = [Addition(material=Material.BENTONITE, mass=Pounds(mass), reason="shift")]
    return cost_of(charged, prices(price), GOOD_IRON)


class TestOnBudget:
    def test_no_variance_either_way(self) -> None:
        found = variance_of(budget(), actual(), GOOD_IRON)
        assert found.rate == Decimal("0.00")
        assert found.usage == Decimal("0.00")
        assert found.total == Decimal("0.00")

    def test_the_expected_usage_is_per_ton_shipped(self) -> None:
        assert budget("20").expected_usage(GOOD_IRON) == Pounds(2000)

    def test_half_the_tonnage_allows_half_the_material(self) -> None:
        assert budget("20").expected_usage(Pounds.of_tons(50)) == Pounds(1000)


class TestTheTwoCauses:
    def test_paying_more_per_ton_is_rate(self) -> None:
        found = variance_of(budget(), actual(price="160.00"), GOOD_IRON)
        assert found.rate > 0
        assert found.usage == Decimal("0.00")

    def test_using_more_tons_is_usage(self) -> None:
        found = variance_of(budget(), actual(mass="3000"), GOOD_IRON)
        assert found.usage > 0
        assert found.rate == Decimal("0.00")

    def test_both_at_once_add_up(self) -> None:
        found = variance_of(budget(), actual(mass="3000", price="160.00"), GOOD_IRON)
        assert found.total == found.rate + found.usage
        assert found.rate > 0
        assert found.usage > 0


class TestTheyWouldCancelIfNotSplit:
    def test_a_saving_on_price_against_an_overrun_on_usage(self) -> None:
        # Cheaper bentonite, more of it.
        found = variance_of(budget(), actual(mass="3000", price="90.00"), GOOD_IRON)
        assert found.rate < 0
        assert found.usage > 0
        assert found.cancels_out

    def test_the_finding_says_it_would_read_as_on_budget(self) -> None:
        found = variance_of(budget(), actual(mass="3000", price="90.00"), GOOD_IRON)
        assert "would read as on budget" in found.finding()

    def test_a_plain_overspend_does_not_say_that(self) -> None:
        found = variance_of(budget(), actual(mass="3000"), GOOD_IRON)
        assert not found.cancels_out
        assert "would read as on budget" not in found.finding()

    def test_a_material_never_charged_is_all_usage(self) -> None:
        found = variance_of(budget(), actual(mass="0.01"), GOOD_IRON)
        assert found.usage < 0


class TestGuards:
    def test_no_good_iron_means_nothing_to_budget_against(self) -> None:
        with pytest.raises(RuleError, match="nothing to budget against"):
            variance_of(budget(), actual(), Pounds.zero())

    def test_the_budget_is_checked(self) -> None:
        bad: Any = "bentonite"
        with pytest.raises(BadInputError, match="is for a material"):
            Budget(material=bad, pounds_per_ton=Decimal(20), price=PricePerTon(1))
        with pytest.raises(BadInputError, match="budgeted usage is a decimal"):
            Budget(material=Material.BENTONITE, pounds_per_ton=bad, price=PricePerTon(1))
        with pytest.raises(BadInputError, match="cannot be negative"):
            Budget(
                material=Material.BENTONITE,
                pounds_per_ton=Decimal(-1),
                price=PricePerTon(1),
            )
        with pytest.raises(BadInputError, match="price per ton"):
            Budget(material=Material.BENTONITE, pounds_per_ton=Decimal(20), price=bad)

    def test_the_arguments_are_checked(self) -> None:
        bad: Any = "budget"
        with pytest.raises(BadInputError, match="a budget is expected"):
            variance_of(bad, actual(), GOOD_IRON)
        with pytest.raises(BadInputError, match="costed shift is expected"):
            variance_of(budget(), bad, GOOD_IRON)
        with pytest.raises(BadInputError, match="good iron is a bulk mass"):
            variance_of(budget(), actual(), bad)
        with pytest.raises(BadInputError, match="good iron is a bulk mass"):
            budget().expected_usage(bad)

    def test_the_budgeted_cost_per_ton(self) -> None:
        assert budget("20", "142.00").cost_per_ton().dollars == Decimal("1.42")
