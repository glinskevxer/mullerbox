from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from mullerbox.errors import BadInputError
from mullerbox.units.bulk import Pounds
from mullerbox.units.money import Money, PricePerTon, total_money


class TestMoney:
    def test_reads_the_usual_shapes(self) -> None:
        assert Money("12.34") == Money(Decimal("12.34")) == Money(12.34)

    def test_reads_a_dollar_sign_and_commas(self) -> None:
        assert Money("$1,234.56") == Money("1234.56")

    def test_whole_dollars(self) -> None:
        assert Money(12).cents == 1200

    def test_rounds_half_up_at_the_cent(self) -> None:
        assert Money("12.345").cents == 1235
        assert Money("12.344").cents == 1234

    def test_negative_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="cannot be negative"):
            Money("-1")

    def test_a_boolean_is_not_money(self) -> None:
        with pytest.raises(BadInputError, match="from a boolean"):
            Money(True)

    def test_money_reads_back_from_money(self) -> None:
        assert Money(Money("12.34")) == Money("12.34")

    def test_from_cents_is_guarded(self) -> None:
        with pytest.raises(BadInputError, match="whole number"):
            Money.from_cents(12.5)  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="cannot be negative"):
            Money.from_cents(-1)
        with pytest.raises(BadInputError, match="whole number"):
            Money.from_cents(True)

    def test_arithmetic(self) -> None:
        assert Money("1.00") + Money("2.50") == Money("3.50")
        assert Money("3.50") - Money("1.00") == Money("2.50")

    def test_subtraction_refuses_to_go_negative(self) -> None:
        with pytest.raises(BadInputError, match="negative cost"):
            Money("1.00") - Money("2.00")

    def test_arithmetic_against_another_type_is_not_implemented(self) -> None:
        with pytest.raises(TypeError):
            Money(1) + 1
        with pytest.raises(TypeError):
            Money(1) - 1

    def test_totalling(self) -> None:
        assert total_money([Money("1.01"), Money("2.02")]) == Money("3.03")
        assert total_money([]) == Money.zero()

    def test_totalling_refuses_a_non_amount(self) -> None:
        bad: Any = [Money(1), Pounds(1)]
        with pytest.raises(BadInputError, match="only amounts"):
            total_money(bad)

    def test_presentation(self) -> None:
        assert str(Money("1234.5")) == "$1,234.50"
        assert Money("1234.50").dollars == Decimal("1234.50")
        assert Money.zero().is_zero

    def test_orders_and_hashes(self) -> None:
        assert Money(1) < Money(2)
        assert len({Money("1.00"), Money(1)}) == 1
        assert Money(1) != 1


class TestPricePerTon:
    def test_it_keeps_four_places(self) -> None:
        assert PricePerTon("142.12345").dollars == Decimal("142.1235")

    def test_it_reads_a_dollar_sign(self) -> None:
        assert PricePerTon("$142.00") == PricePerTon(142)

    def test_negative_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="price cannot be negative"):
            PricePerTon(-1)

    def test_a_ton_costs_the_rate(self) -> None:
        assert PricePerTon("142.00").cost_of(Pounds(2000)) == Money("142.00")

    def test_a_pound_costs_a_two_thousandth(self) -> None:
        assert PricePerTon("2000.00").cost_of(Pounds(1)) == Money("1.00")

    def test_it_rounds_once_at_the_end(self) -> None:
        # 142.00 * 137 / 2000 = 9.727, which is 9.73 rounded once.
        assert PricePerTon("142.00").cost_of(Pounds(137)) == Money("9.73")

    def test_nothing_costs_nothing(self) -> None:
        assert PricePerTon("142.00").cost_of(Pounds.zero()).is_zero

    def test_it_wants_a_bulk_mass(self) -> None:
        bad: Any = 2000
        with pytest.raises(BadInputError, match="taken of a bulk mass"):
            PricePerTon("142.00").cost_of(bad)

    def test_presentation_and_equality(self) -> None:
        assert str(PricePerTon("142.0000")) == "$142/t"
        assert len({PricePerTon("142.00"), PricePerTon(142)}) == 1
        assert PricePerTon(142) != 142
