from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from mullerbox.errors import BadInputError, RuleError
from mullerbox.heat.pattern import RATIO_TOLERANCE, Pattern, Register
from mullerbox.spec.pattern import PatternClass
from mullerbox.units.bulk import Pounds


def pattern(
    pattern_id: str = "P-1",
    cubic_feet: str = "8.0",
    cavities: int = 2,
    weight: str = "60",
    cls: PatternClass = PatternClass.MEDIUM_JOBBING,
) -> Pattern:
    return Pattern(
        pattern_id=pattern_id,
        name="bearing housing",
        pattern_class=cls,
        flask_cubic_feet=Decimal(cubic_feet),
        cavities=cavities,
        casting_weight=Pounds(weight),
    )


class TestTheGeometryGivesTheRatio:
    def test_the_metal_is_the_cavities_times_the_weight(self) -> None:
        assert pattern(cavities=2, weight="60").metal_per_mold == Pounds(120)

    def test_the_sand_is_the_flask_less_what_the_metal_displaces(self) -> None:
        assert pattern().sand_per_mold < Pounds(Decimal("8.0") * Decimal("95"))

    def test_the_ratio_falls_out_of_the_two(self) -> None:
        built = pattern()
        assert built.expected_ratio == built.sand_per_mold.ratio_to(built.metal_per_mold)

    def test_a_heavier_casting_lowers_the_ratio(self) -> None:
        light = pattern(weight="30")
        heavy = pattern(weight="120")
        assert heavy.expected_ratio < light.expected_ratio

    def test_a_bigger_flask_raises_it(self) -> None:
        small = pattern(cubic_feet="6.0")
        large = pattern(cubic_feet="12.0")
        assert large.expected_ratio > small.expected_ratio

    def test_a_pattern_that_displaces_its_own_flask_is_refused(self) -> None:
        crowded = pattern(cubic_feet="0.5", cavities=20, weight="200")
        with pytest.raises(RuleError, match="displaces more than its flask holds"):
            assert crowded.sand_per_mold


class TestCatchingABadPourRecord:
    def test_a_recorded_ratio_near_the_expected_one_is_normal(self) -> None:
        built = pattern()
        assert not built.ratio_looks_wrong(built.expected_ratio)
        assert "which is normal" in built.check_ratio(built.expected_ratio)

    def test_a_ratio_well_off_is_flagged(self) -> None:
        built = pattern()
        way_off = built.expected_ratio * Decimal(3)
        assert built.ratio_looks_wrong(way_off)
        assert "check the pour record" in built.check_ratio(way_off)

    def test_exactly_on_the_tolerance_is_normal(self) -> None:
        built = pattern()
        edge = built.expected_ratio * (Decimal(1) + RATIO_TOLERANCE)
        assert not built.ratio_looks_wrong(edge)

    def test_a_hair_past_it_is_not(self) -> None:
        built = pattern()
        over = built.expected_ratio * (Decimal(1) + RATIO_TOLERANCE + Decimal("0.01"))
        assert built.ratio_looks_wrong(over)

    def test_it_catches_a_ratio_that_is_too_low_as_well(self) -> None:
        built = pattern()
        assert built.ratio_looks_wrong(built.expected_ratio / Decimal(3))

    def test_the_message_names_both_numbers(self) -> None:
        built = pattern()
        text = built.check_ratio(built.expected_ratio * Decimal(3))
        assert str(built.expected_ratio) in text

    def test_it_is_guarded(self) -> None:
        bad: Any = "6.0"
        with pytest.raises(BadInputError, match="recorded ratio is a decimal"):
            pattern().ratio_looks_wrong(bad)
        with pytest.raises(BadInputError, match="above zero"):
            pattern().ratio_looks_wrong(Decimal(0))


class TestTheRegister:
    def test_it_finds_by_identifier(self) -> None:
        register = Register(patterns=(pattern("P-1"), pattern("P-2")))
        assert register.find("P-2").pattern_id == "P-2"
        assert len(register) == 2

    def test_something_absent_is_refused(self) -> None:
        register = Register(patterns=(pattern("P-1"),))
        with pytest.raises(BadInputError, match="no pattern 'P-9'"):
            register.find("P-9")

    def test_two_patterns_cannot_share_an_identifier(self) -> None:
        with pytest.raises(RuleError, match="share an identifier"):
            Register(patterns=(pattern("P-1"), pattern("P-1")))

    def test_it_groups_by_class(self) -> None:
        register = Register(
            patterns=(
                pattern("P-1", cls=PatternClass.MEDIUM_JOBBING),
                pattern("P-2", cls=PatternClass.THIN_WALL),
            )
        )
        assert [p.pattern_id for p in register.of_class(PatternClass.THIN_WALL)] == ["P-2"]
        assert register.classes == {
            PatternClass.MEDIUM_JOBBING,
            PatternClass.THIN_WALL,
        }

    def test_grouping_wants_a_class(self) -> None:
        bad: Any = "thin wall"
        with pytest.raises(BadInputError, match="pattern class is expected"):
            Register(patterns=()).of_class(bad)


class TestConstruction:
    def test_the_pieces_are_checked(self) -> None:
        bad: Any = "x"
        with pytest.raises(BadInputError, match="needs an identifier"):
            pattern(pattern_id="  ")
        with pytest.raises(BadInputError, match="flask with no volume"):
            pattern(cubic_feet="0")
        with pytest.raises(BadInputError, match="no cavities makes nothing"):
            pattern(cavities=0)
        with pytest.raises(BadInputError, match="cavity count is a whole number"):
            pattern(cavities=bad)
        with pytest.raises(BadInputError, match="no weight is not a casting"):
            pattern(weight="0")

    def test_str_names_the_expected_ratio(self) -> None:
        assert ":1 expected" in str(pattern())
        assert "2 up" in str(pattern(cavities=2))
