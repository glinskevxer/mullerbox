from __future__ import annotations

from decimal import Decimal

import pytest

from mullerbox.errors import BadInputError
from mullerbox.units.bulk import Pounds
from mullerbox.units.coerce import to_decimal, to_int
from mullerbox.units.mass import Grams
from mullerbox.units.percent import Percent
from mullerbox.units.scales import Hardness


class TestToDecimal:
    def test_a_decimal_comes_straight_back(self) -> None:
        value = Decimal("1.23")
        assert to_decimal(value, "a mass") is value

    def test_an_int_converts_exactly(self) -> None:
        assert to_decimal(7, "a mass") == Decimal(7)

    def test_a_float_goes_through_repr(self) -> None:
        assert to_decimal(12.005, "a mass") == Decimal("12.005")

    def test_a_string_is_stripped_and_lowered(self) -> None:
        assert to_decimal("  1.5  ", "a mass") == Decimal("1.5")

    def test_the_longest_suffix_wins(self) -> None:
        # "lb" would match first alphabetically and leave a stray "s".
        assert to_decimal("150lbs", "a bulk mass", suffixes=("lb", "lbs")) == Decimal(150)

    def test_only_one_suffix_is_taken(self) -> None:
        assert to_decimal("150 lb", "a bulk mass", suffixes=("lb", "#")) == Decimal(150)

    def test_commas_are_optional(self) -> None:
        assert to_decimal("1,500", "a bulk mass", strip_commas=True) == Decimal(1500)
        with pytest.raises(BadInputError, match="is not a bulk mass"):
            to_decimal("1,500", "a bulk mass")

    def test_unreadable_text_names_the_quantity(self) -> None:
        with pytest.raises(BadInputError, match="'heavy' is not a mass"):
            to_decimal("heavy", "a mass")

    def test_an_unreadable_type_names_the_type(self) -> None:
        with pytest.raises(BadInputError, match="cannot read a mass from NoneType"):
            to_decimal(None, "a mass")

    def test_the_article_comes_from_the_caller(self) -> None:
        with pytest.raises(BadInputError, match="cannot read an aperture from NoneType"):
            to_decimal(None, "an aperture")


class TestToInt:
    def test_an_int_comes_back(self) -> None:
        assert to_int(50, "a mesh number") == 50

    def test_a_string_converts(self) -> None:
        assert to_int(" 50 ", "a mesh number") == 50

    def test_a_float_is_refused_rather_than_rounded(self) -> None:
        with pytest.raises(BadInputError, match="cannot read a mesh number from float"):
            to_int(50.4, "a mesh number")

    def test_unreadable_text_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="'fifty' is not a mesh number"):
            to_int("fifty", "a mesh number")


class TestBooleansAreRefusedEverywhere:
    """bool subclasses int, so every quantity had to be checked separately."""

    def test_the_helper_refuses_both_ways(self) -> None:
        with pytest.raises(BadInputError, match="from a boolean"):
            to_decimal(True, "a mass")
        with pytest.raises(BadInputError, match="from a boolean"):
            to_int(False, "a mesh number")

    def test_a_flag_no_longer_reads_as_one_gram(self) -> None:
        with pytest.raises(BadInputError, match="cannot read a mass from a boolean"):
            Grams(True)

    def test_a_flag_no_longer_reads_as_one_percent(self) -> None:
        with pytest.raises(BadInputError, match="cannot read a percentage from a boolean"):
            Percent(True)

    @pytest.mark.parametrize("scale", [Grams, Percent, Pounds, Hardness])
    def test_no_quantity_accepts_a_boolean(self, scale: type) -> None:
        with pytest.raises(BadInputError, match="from a boolean"):
            scale(True)


class TestPrefixes:
    def test_a_currency_symbol_is_stripped_from_the_front(self) -> None:
        assert to_decimal("$12.34", "an amount", prefixes=("$",)) == Decimal("12.34")

    def test_the_longest_prefix_wins(self) -> None:
        assert to_decimal("us$12.34", "an amount", prefixes=("$", "us$")) == Decimal("12.34")

    def test_only_one_prefix_is_taken(self) -> None:
        with pytest.raises(BadInputError, match="is not an amount"):
            to_decimal("$$12.34", "an amount", prefixes=("$",))

    def test_a_prefix_and_a_suffix_together(self) -> None:
        assert to_decimal("$12.34 usd", "an amount", prefixes=("$",), suffixes=("usd",)) == Decimal(
            "12.34"
        )

    def test_no_prefix_present_is_fine(self) -> None:
        assert to_decimal("12.34", "an amount", prefixes=("$",)) == Decimal("12.34")
