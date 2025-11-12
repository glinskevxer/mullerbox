from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from mullerbox.analysis.control import MIN_POINTS
from mullerbox.analysis.trend import Direction, project, trend_of
from mullerbox.errors import BadInputError, RuleError
from mullerbox.props.kind import PropertyKind
from mullerbox.spec.band import Band
from mullerbox.units.percent import Percent

MOISTURE = PropertyKind.MOISTURE
BAND = Band.between(MOISTURE, Percent("2.8"), Percent("3.6"))
CEILING = Band.at_most(PropertyKind.LOI, Percent("3.5"))


def rising(start: str = "3.0", step: str = "0.02", n: int = 25) -> list[Decimal]:
    return [Decimal(start) + Decimal(step) * i for i in range(n)]


def flat(value: str = "3.2", n: int = 25) -> list[Decimal]:
    return [Decimal(value) + (Decimal("0.0002") if i % 2 else Decimal(0)) for i in range(n)]


class TestFittingTheLine:
    def test_a_rising_run_reads_rising(self) -> None:
        got = trend_of(MOISTURE, rising())
        assert got.direction is Direction.RISING
        assert got.is_moving

    def test_a_falling_run_reads_falling(self) -> None:
        got = trend_of(MOISTURE, rising(step="-0.02"))
        assert got.direction is Direction.FALLING

    def test_a_flat_run_reads_flat(self) -> None:
        got = trend_of(MOISTURE, flat())
        assert got.direction is Direction.FLAT
        assert not got.is_moving
        assert "is flat" in str(got)

    def test_the_slope_is_per_reading(self) -> None:
        got = trend_of(MOISTURE, rising(step="0.02"))
        assert abs(got.slope - Decimal("0.02")) < Decimal("0.0001")

    def test_the_line_passes_through_the_run(self) -> None:
        got = trend_of(MOISTURE, rising(start="3.0", step="0.02"))
        assert abs(got.at(0) - Decimal("3.0")) < Decimal("0.001")
        assert abs(got.latest - Decimal("3.48")) < Decimal("0.001")

    def test_str_names_the_direction_and_the_slope(self) -> None:
        assert "rising" in str(trend_of(MOISTURE, rising()))
        assert "per reading" in str(trend_of(MOISTURE, rising()))


class TestReadingsToALimit:
    def test_it_counts_forward_to_a_limit_ahead(self) -> None:
        got = trend_of(MOISTURE, rising(start="3.0", step="0.02"))
        # latest is 3.48, rising 0.02 a reading, so 3.6 is six away.
        assert got.readings_to(Decimal("3.6")) == 6

    def test_a_limit_behind_the_direction_is_not_reached(self) -> None:
        got = trend_of(MOISTURE, rising(step="0.02"))
        assert got.readings_to(Decimal("2.0")) is None

    def test_a_limit_already_reached_is_zero_away(self) -> None:
        got = trend_of(MOISTURE, rising(start="3.0", step="0.02"))
        assert got.readings_to(got.latest) == 0

    def test_a_flat_run_reaches_nothing(self) -> None:
        assert trend_of(MOISTURE, flat()).readings_to(Decimal("3.6")) is None

    def test_it_wants_a_decimal(self) -> None:
        bad: Any = "3.6"
        with pytest.raises(BadInputError, match="a limit is a decimal"):
            trend_of(MOISTURE, rising()).readings_to(bad)

    def test_at_wants_a_whole_number(self) -> None:
        bad: Any = 1.5
        with pytest.raises(BadInputError, match="whole number"):
            trend_of(MOISTURE, rising()).at(bad)


class TestProjection:
    def test_a_rising_trend_heads_for_the_upper_limit(self) -> None:
        got = project(trend_of(MOISTURE, rising()), BAND)
        assert got.is_heading_out
        assert got.limit_reached == "upper"
        assert "reaching the upper limit" in str(got)

    def test_a_falling_trend_heads_for_the_lower_limit(self) -> None:
        got = project(trend_of(MOISTURE, rising(start="3.5", step="-0.02")), BAND)
        assert got.limit_reached == "lower"

    def test_a_flat_trend_heads_nowhere(self) -> None:
        got = project(trend_of(MOISTURE, flat()), BAND)
        assert not got.is_heading_out
        assert "not heading out of band" in str(got)

    def test_a_rising_trend_against_a_ceiling_only_band(self) -> None:
        got = project(trend_of(PropertyKind.LOI, rising(start="2.5")), CEILING)
        assert got.is_heading_out

    def test_a_falling_trend_against_a_ceiling_only_band_heads_nowhere(self) -> None:
        got = project(trend_of(PropertyKind.LOI, rising(start="3.0", step="-0.02")), CEILING)
        assert not got.is_heading_out

    def test_the_projection_says_it_assumes_nothing_changes(self) -> None:
        assert "if nothing changes" in str(project(trend_of(MOISTURE, rising()), BAND))

    def test_the_band_has_to_be_for_the_property(self) -> None:
        with pytest.raises(BadInputError, match="cannot be projected onto"):
            project(trend_of(MOISTURE, rising()), CEILING)

    def test_it_is_guarded(self) -> None:
        bad: Any = "rising"
        with pytest.raises(BadInputError, match="a trend is expected"):
            project(bad, BAND)
        with pytest.raises(BadInputError, match="a band is expected"):
            project(trend_of(MOISTURE, rising()), bad)


class TestGuards:
    def test_too_few_readings(self) -> None:
        with pytest.raises(RuleError, match=f"{MIN_POINTS} is the floor"):
            trend_of(MOISTURE, rising(n=MIN_POINTS - 1))

    def test_the_types_are_checked(self) -> None:
        bad: Any = "moisture"
        with pytest.raises(BadInputError, match="property kind is expected"):
            trend_of(bad, rising())
        with pytest.raises(BadInputError, match="run of readings is expected"):
            trend_of(MOISTURE, bad)
        bad_values: Any = [3.0] * 25
        with pytest.raises(BadInputError, match="fitted to decimals"):
            trend_of(MOISTURE, bad_values)

    def test_every_direction_has_a_label(self) -> None:
        assert all(d.label for d in Direction)
