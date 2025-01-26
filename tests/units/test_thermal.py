from __future__ import annotations

from decimal import Decimal

import pytest

from mullerbox.errors import BadInputError
from mullerbox.units.thermal import Temperature


class TestConstruction:
    def test_celsius_is_the_canonical_scale(self) -> None:
        assert Temperature.celsius_of(49).celsius == Decimal("49.0")

    def test_fahrenheit_converts_on_the_way_in(self) -> None:
        assert Temperature.fahrenheit(120).celsius == Decimal("48.9")

    def test_the_two_constructors_agree_at_the_freezing_point(self) -> None:
        assert Temperature.fahrenheit(32) == Temperature.celsius_of(0)

    def test_a_round_trip_holds_to_a_tenth(self) -> None:
        assert Temperature.fahrenheit(120).fahrenheit_value == Decimal("120.0")

    def test_a_trailing_scale_letter_is_allowed(self) -> None:
        assert Temperature.celsius_of("49 C") == Temperature.celsius_of(49)
        assert Temperature.celsius_of("49 deg") == Temperature.celsius_of(49)

    def test_below_absolute_zero_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="absolute zero"):
            Temperature.celsius_of("-274")

    def test_a_metal_reading_in_a_sand_column_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="not a sand or a metal reading"):
            Temperature.celsius_of(1501)

    def test_unreadable_values_are_refused(self) -> None:
        with pytest.raises(BadInputError, match="is not a temperature"):
            Temperature.celsius_of("hot")
        with pytest.raises(BadInputError, match="cannot read a temperature"):
            Temperature.celsius_of(None)
        with pytest.raises(BadInputError, match="from a boolean"):
            Temperature.celsius_of(True)


class TestComparison:
    def test_warmer_than(self) -> None:
        assert Temperature.fahrenheit(130).warmer_than(Temperature.fahrenheit(110))

    def test_difference_is_always_positive(self) -> None:
        hot = Temperature.celsius_of(50)
        cool = Temperature.celsius_of(30)
        assert hot.difference(cool) == Decimal("20.0")
        assert cool.difference(hot) == Decimal("20.0")

    def test_comparison_wants_a_temperature(self) -> None:
        with pytest.raises(BadInputError, match="only compares against a temperature"):
            Temperature.celsius_of(1).warmer_than(1)  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="only compares against a temperature"):
            Temperature.celsius_of(1).difference(1)  # type: ignore[arg-type]

    def test_orders_and_hashes(self) -> None:
        assert Temperature.celsius_of(20) < Temperature.celsius_of(30)
        assert len({Temperature.celsius_of("49.0"), Temperature.celsius_of(49)}) == 1

    def test_unequal_against_another_type(self) -> None:
        assert Temperature.celsius_of(49) != 49

    def test_str_names_the_scale(self) -> None:
        assert str(Temperature.celsius_of(49)) == "49.0 C"
