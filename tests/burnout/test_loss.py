from __future__ import annotations

from decimal import Decimal

import pytest

from mullerbox.burnout.loss import (
    CARBON_HOT_SHARE_AT_UNITY,
    CARBON_MAX_BURNT_SHARE,
    CLAY_HOT_SHARE_AT_UNITY,
    CLAY_MAX_DEAD_SHARE,
    burnout_of,
)
from mullerbox.burnout.pour import MIN_RATIO
from mullerbox.errors import BadInputError
from mullerbox.units.percent import Percent, Points
from tests.burnout.helpers import pour

CLAY = Percent("8.0")
CARBON = Percent("3.0")


class TestTheShareRisesAsTheRatioFalls:
    def test_a_heavy_shift_kills_more_than_a_light_one(self) -> None:
        heavy = burnout_of(pour(sand="30000", metal="10000"), CLAY, CARBON)
        light = burnout_of(pour(sand="90000", metal="10000"), CLAY, CARBON)
        assert heavy.dead_clay_share > light.dead_clay_share
        assert heavy.clay_lost > light.clay_lost

    def test_the_reference_shift(self) -> None:
        got = burnout_of(pour(sand="60000", metal="10000"), CLAY, CARBON)
        assert got.dead_clay_share == Decimal("0.1000")
        assert got.clay_lost == Points("0.80")

    def test_the_clay_cap_binds_at_the_bottom_of_the_plausible_range(self) -> None:
        hardest = burnout_of(pour(sand="20000", metal="10000"), CLAY, CARBON)
        assert hardest.pour.sand_to_metal == Decimal("2.00")
        assert hardest.dead_clay_share == CLAY_MAX_DEAD_SHARE

    def test_the_carbon_cap_binds_there_too(self) -> None:
        hardest = burnout_of(pour(sand="20000", metal="10000"), CLAY, CARBON)
        assert hardest.burnt_carbon_share == CARBON_MAX_BURNT_SHARE

    def test_the_caps_are_reachable_rather_than_decorative(self) -> None:
        """Both ceilings have to fire somewhere inside the allowed range."""
        assert CLAY_MAX_DEAD_SHARE < CLAY_HOT_SHARE_AT_UNITY / MIN_RATIO
        assert CARBON_MAX_BURNT_SHARE < CARBON_HOT_SHARE_AT_UNITY / MIN_RATIO

    def test_just_above_the_binding_ratio_the_cap_lets_go(self) -> None:
        loose = burnout_of(pour(sand="30000", metal="10000"), CLAY, CARBON)
        assert loose.dead_clay_share == Decimal("0.2000")
        assert loose.dead_clay_share < CLAY_MAX_DEAD_SHARE


class TestCarbonGoesFasterThanClay:
    def test_at_every_ratio_in_the_range(self) -> None:
        for sand in ("30000", "60000", "90000", "120000"):
            got = burnout_of(pour(sand=sand, metal="10000"), CLAY, CARBON)
            assert got.burnt_carbon_share > got.dead_clay_share


class TestTheLossIsAShareOfWhatWasThere:
    def test_half_the_bond_loses_half_the_points(self) -> None:
        rich = burnout_of(pour(), Percent("8.0"), CARBON)
        lean = burnout_of(pour(), Percent("4.0"), CARBON)
        assert lean.clay_lost == rich.clay_lost.scaled("0.5")

    def test_no_bond_loses_nothing(self) -> None:
        got = burnout_of(pour(), Percent.zero(), Percent.zero())
        assert got.clay_lost == Points.zero()
        assert got.carbon_lost == Points.zero()

    def test_the_share_does_not_depend_on_what_was_there(self) -> None:
        rich = burnout_of(pour(), Percent("8.0"), CARBON)
        lean = burnout_of(pour(), Percent("4.0"), CARBON)
        assert rich.dead_clay_share == lean.dead_clay_share


class TestSeverity:
    def test_a_hard_shift_reports_severe(self) -> None:
        assert burnout_of(pour(sand="24000", metal="10000"), CLAY, CARBON).is_severe

    def test_a_normal_shift_does_not(self) -> None:
        assert not burnout_of(pour(), CLAY, CARBON).is_severe


class TestGuards:
    def test_it_wants_a_pour_and_two_percentages(self) -> None:
        with pytest.raises(BadInputError, match="worked out from a pour"):
            burnout_of("6:1", CLAY, CARBON)  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="live clay is a percentage"):
            burnout_of(pour(), "8.0", CARBON)  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="carbon is a percentage"):
            burnout_of(pour(), CLAY, "3.0")  # type: ignore[arg-type]

    def test_an_implausible_pour_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="is not a pour record"):
            burnout_of(pour(sand="19000", metal="10000"), CLAY, CARBON)

    def test_str_names_both_losses(self) -> None:
        got = burnout_of(pour(), CLAY, CARBON)
        assert "live clay" in str(got)
        assert "carbon" in str(got)
