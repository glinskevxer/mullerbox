from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from mullerbox.errors import BadInputError
from mullerbox.units.mass import Grams, total


class TestConstruction:
    def test_reads_int_float_decimal_and_string(self) -> None:
        assert Grams(50) == Grams("50") == Grams(50.0) == Grams(Decimal(50))

    def test_a_trailing_g_is_allowed(self) -> None:
        assert Grams("12.34 g") == Grams("12.34")
        assert Grams("12.34g") == Grams("12.34")

    def test_rounds_half_up_at_the_centigram(self) -> None:
        assert Grams("12.005").centigrams == 1201
        assert Grams("12.004").centigrams == 1200

    def test_a_float_does_not_drift_at_the_boundary(self) -> None:
        assert Grams(12.005).centigrams == 1201

    def test_negative_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="cannot be negative"):
            Grams("-1")

    def test_a_kilogram_typed_as_grams_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="not a sand lab quantity"):
            Grams(100001)

    def test_unreadable_text_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="is not a mass"):
            Grams("heavy")

    def test_unreadable_type_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="cannot read a mass"):
            Grams(None)

    def test_from_centigrams_wants_a_whole_number(self) -> None:
        with pytest.raises(BadInputError, match="whole number"):
            Grams.from_centigrams(12.5)  # type: ignore[arg-type]

    def test_from_centigrams_refuses_negative(self) -> None:
        with pytest.raises(BadInputError, match="cannot be negative"):
            Grams.from_centigrams(-1)

    def test_zero(self) -> None:
        assert Grams.zero().is_zero
        assert Grams().is_zero


class TestArithmetic:
    def test_addition_is_exact_across_many_small_masses(self) -> None:
        screens = [Grams("0.07"), Grams("1.34"), Grams("8.91"), Grams("14.02"), Grams("25.66")]
        assert total(screens) == Grams("50.00")

    def test_total_of_nothing_is_zero(self) -> None:
        assert total([]) == Grams.zero()

    def test_total_refuses_a_non_mass(self) -> None:
        with pytest.raises(BadInputError, match="only masses"):
            total([Grams(1), 2])  # type: ignore[list-item]

    def test_subtraction_refuses_to_go_negative(self) -> None:
        with pytest.raises(BadInputError, match="negative mass"):
            Grams(1) - Grams(2)

    def test_difference_works_either_way_round(self) -> None:
        assert Grams(1).difference(Grams(2)) == Grams(1)
        assert Grams(2).difference(Grams(1)) == Grams(1)

    def test_difference_wants_a_mass(self) -> None:
        with pytest.raises(BadInputError, match="compared against a mass"):
            Grams(1).difference(2)  # type: ignore[arg-type]

    def test_adding_a_non_mass_is_not_implemented(self) -> None:
        with pytest.raises(TypeError):
            Grams(1) + 1

    def test_scaled_rounds_half_up(self) -> None:
        assert Grams("10.00").scaled("0.335") == Grams("3.35")

    def test_scaling_by_a_mass_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="not a mass"):
            Grams(1).scaled(Grams(2))

    def test_scaling_by_a_negative_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="negative ratio"):
            Grams(1).scaled(-1)

    def test_scaling_by_a_bad_type_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="cannot scale"):
            Grams(1).scaled(None)


class TestRatio:
    def test_a_fraction_keeps_six_places(self) -> None:
        assert Grams("0.07").ratio_to(Grams("50.00")) == Decimal("0.001400")

    def test_the_fractions_of_a_stack_sum_close_to_one(self) -> None:
        stack = [Grams("0.07"), Grams("1.34"), Grams("8.91"), Grams("14.02"), Grams("25.66")]
        whole = total(stack)
        assert sum((m.ratio_to(whole) for m in stack), Decimal(0)) == Decimal(1)

    def test_a_fraction_of_nothing_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="fraction of nothing"):
            Grams(1).ratio_to(Grams.zero())

    def test_a_fraction_wants_a_mass(self) -> None:
        with pytest.raises(BadInputError, match="fraction of a mass"):
            Grams(1).ratio_to(50)  # type: ignore[arg-type]


class TestProtocol:
    def test_orders(self) -> None:
        assert Grams(1) < Grams(2)
        assert sorted([Grams(3), Grams(1), Grams(2)]) == [Grams(1), Grams(2), Grams(3)]

    def test_hashes_by_value(self) -> None:
        assert len({Grams("50.00"), Grams(50), Grams("50")}) == 1

    def test_compares_unequal_against_another_type(self) -> None:
        assert Grams(1) != "1 g"

    def test_str_carries_the_unit(self) -> None:
        assert str(Grams("50")) == "50.00 g"

    def test_grams_property_is_a_quantised_decimal(self) -> None:
        assert Grams("1.5").grams == Decimal("1.50")


class TestBooleansAreNotMasses:
    def test_true_is_not_one_gram(self) -> None:
        with pytest.raises(BadInputError, match="from a boolean"):
            Grams(True)

    def test_false_is_not_zero_grams(self) -> None:
        with pytest.raises(BadInputError, match="from a boolean"):
            Grams(False)


class TestBuildingOneFromAnother:
    def test_a_mass_from_a_mass_keeps_its_value(self) -> None:
        assert Grams(Grams("42.50")) == Grams("42.50")

    def test_and_from_one_carrying_a_suffix(self) -> None:
        assert Grams(Grams("42.50 g")) == Grams("42.50")

    def test_adding_something_that_is_not_a_mass(self) -> None:
        bad: Any = "1 g"
        with pytest.raises(TypeError):
            Grams("1") + bad

    def test_subtracting_something_that_is_not_a_mass(self) -> None:
        bad: Any = "1 g"
        with pytest.raises(TypeError):
            Grams("1") - bad

    def test_subtracting_below_zero_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="negative mass"):
            Grams("1") - Grams("2")

    def test_adding_two_masses(self) -> None:
        assert Grams("1.25") + Grams("2.75") == Grams("4.00")
