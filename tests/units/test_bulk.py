from __future__ import annotations

from decimal import Decimal

import pytest

from mullerbox.errors import BadInputError
from mullerbox.units.bulk import Pounds, total_pounds
from mullerbox.units.mass import Grams


class TestConstruction:
    def test_reads_the_usual_shapes(self) -> None:
        assert Pounds(150) == Pounds("150") == Pounds(150.0) == Pounds(Decimal(150))

    def test_reads_the_scale_ticket_spellings(self) -> None:
        assert Pounds("150 lb") == Pounds(150)
        assert Pounds("150lbs") == Pounds(150)
        assert Pounds("150#") == Pounds(150)
        assert Pounds("1,500") == Pounds(1500)

    def test_of_tons(self) -> None:
        assert Pounds.of_tons(5) == Pounds(10000)
        assert Pounds.of_tons("2.5") == Pounds(5000)

    def test_tons_reads_back(self) -> None:
        assert Pounds(10000).tons == Decimal("5.000")

    def test_negative_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="cannot be negative"):
            Pounds(-1)

    def test_a_steel_mill_quantity_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="not a foundry sand quantity"):
            Pounds(1000001)

    def test_unreadable_values_are_refused(self) -> None:
        with pytest.raises(BadInputError, match="is not a bulk mass"):
            Pounds("heavy")
        with pytest.raises(BadInputError, match="cannot read a bulk mass"):
            Pounds(None)
        with pytest.raises(BadInputError, match="from a boolean"):
            Pounds(True)

    def test_zero(self) -> None:
        assert Pounds.zero().is_zero
        assert Pounds().is_zero


class TestTheLabAndTheShopDoNotMix:
    def test_a_gram_is_not_a_pound(self) -> None:
        assert Pounds(50) != Grams(50)
        assert Grams(50) != Pounds(50)

    def test_they_cannot_be_added(self) -> None:
        with pytest.raises(TypeError):
            Pounds(50) + Grams(50)

    def test_they_cannot_be_ordered_against_each_other(self) -> None:
        with pytest.raises(TypeError):
            _ = Pounds(50) < Grams(60)

    def test_there_is_no_conversion_between_them(self) -> None:
        assert not hasattr(Pounds(1), "grams")
        assert not hasattr(Grams(1), "pounds")


class TestArithmetic:
    def test_addition_and_subtraction(self) -> None:
        assert Pounds(100) + Pounds(50) == Pounds(150)
        assert Pounds(150) - Pounds(50) == Pounds(100)

    def test_subtraction_refuses_to_go_negative(self) -> None:
        with pytest.raises(BadInputError, match="negative bulk mass"):
            Pounds(50) - Pounds(100)

    def test_arithmetic_against_another_type_is_not_implemented(self) -> None:
        with pytest.raises(TypeError):
            Pounds(1) + 1
        with pytest.raises(TypeError):
            Pounds(1) - 1

    def test_totalling(self) -> None:
        assert total_pounds([Pounds(10), Pounds(20), Pounds("0.5")]) == Pounds("30.5")

    def test_totalling_nothing_is_zero(self) -> None:
        assert total_pounds([]) == Pounds.zero()

    def test_totalling_refuses_a_non_mass(self) -> None:
        with pytest.raises(BadInputError, match="only bulk masses"):
            total_pounds([Pounds(1), Grams(1)])  # type: ignore[list-item]

    def test_scaling(self) -> None:
        assert Pounds(100).scaled("1.5") == Pounds(150)

    def test_scaling_is_guarded(self) -> None:
        with pytest.raises(BadInputError, match="is not a mass"):
            Pounds(1).scaled(Pounds(2))
        with pytest.raises(BadInputError, match="negative ratio"):
            Pounds(1).scaled(-1)
        with pytest.raises(BadInputError, match="cannot scale a bulk mass"):
            Pounds(1).scaled(None)
        with pytest.raises(BadInputError, match="cannot scale a bulk mass"):
            Pounds(1).scaled(True)


class TestRatios:
    def test_a_fraction_of_the_system(self) -> None:
        assert Pounds(500).fraction_of(Pounds(10000)) == Decimal("0.050000")

    def test_the_sand_to_metal_ratio(self) -> None:
        assert Pounds(9000).ratio_to(Pounds(1200)) == Decimal("7.50")

    def test_ratios_against_nothing_are_refused(self) -> None:
        with pytest.raises(BadInputError, match="fraction of nothing"):
            Pounds(1).fraction_of(Pounds.zero())
        with pytest.raises(BadInputError, match="ratio against nothing"):
            Pounds(1).ratio_to(Pounds.zero())

    def test_ratios_want_a_bulk_mass(self) -> None:
        with pytest.raises(BadInputError, match="fraction of a bulk mass"):
            Pounds(1).fraction_of(1)  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="ratio against a bulk mass"):
            Pounds(1).ratio_to(1)  # type: ignore[arg-type]


class TestPresentation:
    def test_under_a_ton_reads_in_pounds(self) -> None:
        assert str(Pounds(150)) == "150.00 lb"

    def test_a_ton_and_over_reads_in_tons(self) -> None:
        assert str(Pounds(10000)) == "5.000 t"
        assert str(Pounds(2000)) == "1.000 t"

    def test_orders_and_hashes(self) -> None:
        assert Pounds(100) < Pounds(150)
        assert len({Pounds("150.00"), Pounds(150)}) == 1
