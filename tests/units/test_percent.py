from __future__ import annotations

from decimal import Decimal

import pytest

from mullerbox.errors import BadInputError
from mullerbox.units.percent import Percent, Points


class TestPercentConstruction:
    def test_reads_the_usual_shapes(self) -> None:
        assert Percent(38) == Percent("38") == Percent(38.0) == Percent(Decimal(38))

    def test_a_trailing_sign_is_allowed(self) -> None:
        assert Percent("3.25%") == Percent("3.25")

    def test_rounds_half_up_to_two_places(self) -> None:
        assert Percent("3.255").value == Decimal("3.26")
        assert Percent("3.254").value == Decimal("3.25")

    def test_negative_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="cannot be negative"):
            Percent("-0.01")

    def test_over_the_whole_specimen_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="more than the whole specimen"):
            Percent("100.01")

    def test_a_hundred_is_allowed(self) -> None:
        assert Percent(100).value == Decimal("100.00")

    def test_unreadable_text_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="is not a percentage"):
            Percent("damp")

    def test_unreadable_type_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="cannot read a percentage"):
            Percent(None)

    def test_of_a_part_and_a_whole(self) -> None:
        assert Percent.of(Decimal("1.62"), Decimal("50")) == Percent("3.24")

    def test_of_nothing_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="above zero"):
            Percent.of(1, 0)

    def test_of_a_negative_part_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="part cannot be negative"):
            Percent.of(-1, 50)

    def test_fraction_of_one(self) -> None:
        assert Percent("3.25").fraction == Decimal("0.032500")

    def test_zero(self) -> None:
        assert Percent.zero() == Percent(0)


class TestPercentDifferenceIsPoints:
    def test_subtracting_two_percentages_gives_points(self) -> None:
        gap = Percent(42) - Percent(38)
        assert isinstance(gap, Points)
        assert gap == Points(4)

    def test_the_difference_carries_its_sign(self) -> None:
        assert (Percent(36) - Percent(38)) == Points(-2)

    def test_subtracting_a_non_percent_is_not_implemented(self) -> None:
        with pytest.raises(TypeError):
            Percent(1) - 1

    def test_moving_by_points(self) -> None:
        assert Percent(38).moved(Points(4)) == Percent(42)
        assert Percent(38).moved(Points(-4)) == Percent(34)

    def test_moving_clamps_at_both_ends(self) -> None:
        assert Percent(2).moved(Points(-5)) == Percent(0)
        assert Percent(98).moved(Points(5)) == Percent(100)

    def test_moving_wants_points(self) -> None:
        with pytest.raises(BadInputError, match="moves by points"):
            Percent(38).moved(4)  # type: ignore[arg-type]


class TestPoints:
    def test_points_may_be_negative(self) -> None:
        assert Points(-4).is_low
        assert Points(4).is_high
        assert Points.zero().is_zero

    def test_absolute_and_negation(self) -> None:
        assert abs(Points(-4)) == Points(4)
        assert -Points(4) == Points(-4)

    def test_addition_and_subtraction(self) -> None:
        assert Points(4) + Points(-1) == Points(3)
        assert Points(4) - Points(1) == Points(3)

    def test_arithmetic_against_a_non_point_is_not_implemented(self) -> None:
        with pytest.raises(TypeError):
            Points(1) + 1
        with pytest.raises(TypeError):
            Points(1) - 1

    def test_scaling(self) -> None:
        assert Points(4).scaled("0.5") == Points(2)

    def test_scaling_by_points_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="not points"):
            Points(1).scaled(Points(2))

    def test_scaling_by_a_bad_type_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="cannot scale points"):
            Points(1).scaled(None)

    def test_str_shows_the_sign(self) -> None:
        assert str(Points(4)) == "+4.00 pt"
        assert str(Points(-4)) == "-4.00 pt"

    def test_orders_and_hashes(self) -> None:
        assert Points(-1) < Points(1)
        assert len({Points("4.00"), Points(4)}) == 1

    def test_unequal_against_another_type(self) -> None:
        assert Points(1) != 1
        assert Percent(1) != 1


class TestPercentProtocol:
    def test_orders(self) -> None:
        assert Percent(1) < Percent(2)

    def test_hashes_by_value(self) -> None:
        assert len({Percent("38.00"), Percent(38)}) == 1

    def test_str_carries_the_sign(self) -> None:
        assert str(Percent("3.25")) == "3.25%"
