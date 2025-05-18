from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from mullerbox.analysis.control import (
    D4,
    E2,
    MIN_POINTS,
    Signal,
    chart_of,
)
from mullerbox.errors import BadInputError, RuleError


def run(*values: str) -> list[Decimal]:
    return [Decimal(v) for v in values]


def steady(n: int = 20) -> list[Decimal]:
    """A run that alternates by a tenth either side of forty one."""
    return [Decimal("41.0") + (Decimal("0.1") if i % 2 else Decimal("-0.1")) for i in range(n)]


class TestTheLimitsComeFromTheMovingRange:
    def test_a_steady_run_is_in_control(self) -> None:
        chart = chart_of(steady())
        assert chart.in_control
        assert chart.flags == ()

    def test_the_centre_is_the_mean(self) -> None:
        assert chart_of(steady()).centre == Decimal("41.0000")

    def test_the_limits_are_e2_times_the_average_range(self) -> None:
        chart = chart_of(steady())
        assert chart.upper - chart.centre == (E2 * chart.average_moving_range).quantize(
            Decimal("0.0001")
        )

    def test_the_range_limit_is_d4_times_it(self) -> None:
        chart = chart_of(steady())
        assert chart.range_upper == (D4 * chart.average_moving_range).quantize(Decimal("0.0001"))

    def test_the_spread_is_symmetric_about_the_centre(self) -> None:
        chart = chart_of(steady())
        assert chart.upper - chart.centre == chart.centre - chart.lower
        assert chart.spread == chart.upper - chart.lower

    def test_the_moving_ranges_are_the_shift_to_shift_jumps(self) -> None:
        chart = chart_of(run(*["41", "42"] * 10))
        assert set(chart.moving_ranges) == {Decimal(1)}


class TestDriftTheStandardDeviationWouldSwallow:
    def test_a_slow_climb_signals(self) -> None:
        climbing = [Decimal("38") + Decimal("0.2") * i for i in range(20)]
        chart = chart_of(climbing)
        assert not chart.in_control

    def test_the_climb_is_caught_as_a_trend(self) -> None:
        climbing = [Decimal("38") + Decimal("0.2") * i for i in range(20)]
        chart = chart_of(climbing)
        assert chart.flags_of(Signal.TREND_OF_SIX)

    def test_the_moving_range_stays_small_while_the_spread_is_large(self) -> None:
        climbing = [Decimal("38") + Decimal("0.2") * i for i in range(20)]
        chart = chart_of(climbing)
        # The whole run spans nearly four points and the limits are far tighter.
        assert chart.spread < Decimal("4")


class TestTheThreeSignals:
    def test_a_point_beyond_the_limits(self) -> None:
        values = steady(19) + [Decimal("60")]
        chart = chart_of(values)
        beyond = chart.flags_of(Signal.BEYOND_LIMITS)
        assert [f.index for f in beyond] == [19]

    def test_eight_on_one_side_of_the_centre(self) -> None:
        values = steady(12) + [Decimal("41.05")] * 8
        chart = chart_of(values)
        assert chart.flags_of(Signal.RUN_OF_EIGHT)

    def test_six_rising_in_a_row(self) -> None:
        values = steady(14) + run("41.1", "41.2", "41.3", "41.4", "41.5", "41.6")
        chart = chart_of(values)
        assert chart.flags_of(Signal.TREND_OF_SIX)

    def test_six_falling_in_a_row(self) -> None:
        values = steady(14) + run("40.9", "40.8", "40.7", "40.6", "40.5", "40.4")
        chart = chart_of(values)
        assert chart.flags_of(Signal.TREND_OF_SIX)

    def test_five_in_a_row_is_not_a_trend(self) -> None:
        # steady(15) ends on a down step at 40.9, so the four that follow make
        # a rising run of five points and the sixth never arrives.
        values = steady(15) + run("41.0", "41.2", "41.3", "41.4")
        chart = chart_of(values)
        assert not chart.flags_of(Signal.TREND_OF_SIX)

    def test_a_repeated_value_breaks_a_trend(self) -> None:
        values = steady(14) + run("41.1", "41.2", "41.2", "41.3", "41.4", "41.5")
        assert not chart_of(values).flags_of(Signal.TREND_OF_SIX)

    def test_a_value_on_the_centre_breaks_a_run(self) -> None:
        values = [Decimal("41.0")] * 20
        assert not chart_of(values).flags_of(Signal.RUN_OF_EIGHT)

    def test_the_flags_come_back_in_order(self) -> None:
        values = steady(10) + [Decimal("41.05")] * 9 + [Decimal("90")]
        chart = chart_of(values)
        assert [f.index for f in chart.flags] == sorted(f.index for f in chart.flags)

    def test_every_signal_has_a_label(self) -> None:
        assert all(s.label for s in Signal)

    def test_flags_of_wants_a_signal(self) -> None:
        bad: Any = "beyond"
        with pytest.raises(BadInputError, match="a signal is expected"):
            chart_of(steady()).flags_of(bad)


class TestGuards:
    def test_too_few_readings_will_not_carry_limits(self) -> None:
        with pytest.raises(RuleError, match=f"{MIN_POINTS} is the floor"):
            chart_of(steady(MIN_POINTS - 1))

    def test_exactly_the_floor_is_allowed(self) -> None:
        chart = chart_of(steady(MIN_POINTS))
        assert len(chart.values) == MIN_POINTS
        assert chart.average_moving_range == Decimal("0.2000")

    def test_it_wants_a_list_of_decimals(self) -> None:
        bad_list: Any = "41 42 41"
        with pytest.raises(BadInputError, match="a list of readings"):
            chart_of(bad_list)
        bad_values: Any = [41.0] * 20
        with pytest.raises(BadInputError, match="built from decimals"):
            chart_of(bad_values)

    def test_str_names_the_limits_and_the_state(self) -> None:
        assert "in control" in str(chart_of(steady()))
        assert "signals" in str(chart_of(steady(19) + [Decimal("60")]))
