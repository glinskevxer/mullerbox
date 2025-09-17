from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from mullerbox.errors import BadInputError, RuleError
from mullerbox.system.cooler import (
    APPROACH_F,
    LATENT_HEAT,
    SAND_SPECIFIC_HEAT,
    cooling_water_for,
    floor_temperature,
    reachable_temperature,
)
from mullerbox.units.bulk import Pounds
from mullerbox.units.thermal import Temperature

STREAM = Pounds(100000)
HOT = Temperature.fahrenheit(200)
WANTED = Temperature.fahrenheit(115)
DRY_DAY = Temperature.fahrenheit(60)
HUMID_DAY = Temperature.fahrenheit(90)
AGGRESSIVE = Temperature.fahrenheit(85)


class TestTheFloor:
    def test_it_is_the_wet_bulb_plus_the_approach(self) -> None:
        floor = floor_temperature(DRY_DAY)
        assert floor.fahrenheit_value == DRY_DAY.fahrenheit_value + APPROACH_F

    def test_a_humid_day_raises_it(self) -> None:
        assert floor_temperature(HUMID_DAY).warmer_than(floor_temperature(DRY_DAY))

    def test_it_wants_a_temperature(self) -> None:
        bad: Any = 60
        with pytest.raises(BadInputError, match="wet bulb temperature is expected"):
            floor_temperature(bad)


class TestHowMuchWater:
    def test_a_reachable_call_comes_back_with_water(self) -> None:
        call = cooling_water_for(STREAM, HOT, WANTED, DRY_DAY)
        assert call.reachable
        assert not call.water.is_zero

    def test_the_arithmetic_is_the_heat_balance(self) -> None:
        call = cooling_water_for(STREAM, HOT, WANTED, DRY_DAY)
        # sand mass * specific heat * the drop, over the latent heat. The drop
        # comes off the call rather than off the numbers typed above, because
        # the Fahrenheit round trip through stored Celsius costs a tenth.
        expected = (STREAM.value * SAND_SPECIFIC_HEAT * call.drop_wanted / LATENT_HEAT).quantize(
            Decimal("0.01")
        )
        assert call.water == Pounds(expected)

    def test_a_bigger_drop_takes_more_water(self) -> None:
        small = cooling_water_for(STREAM, HOT, Temperature.fahrenheit(180), DRY_DAY)
        big = cooling_water_for(STREAM, HOT, WANTED, DRY_DAY)
        assert big.water > small.water

    def test_more_sand_takes_more_water(self) -> None:
        light = cooling_water_for(Pounds(50000), HOT, WANTED, DRY_DAY)
        heavy = cooling_water_for(STREAM, HOT, WANTED, DRY_DAY)
        assert heavy.water > light.water

    def test_the_drop_wanted_is_reported(self) -> None:
        # 200 F to 115 F is 85 degrees, less a tenth to the Celsius round trip.
        drop = cooling_water_for(STREAM, HOT, WANTED, DRY_DAY).drop_wanted
        assert abs(drop - Decimal(85)) <= Decimal("0.2")

    def test_no_drop_needs_no_water(self) -> None:
        call = cooling_water_for(STREAM, WANTED, WANTED, DRY_DAY)
        assert call.reachable
        assert call.water.is_zero


class TestTheAugustProblem:
    def test_an_aggressive_target_on_a_humid_day_is_out_of_reach(self) -> None:
        call = cooling_water_for(STREAM, HOT, AGGRESSIVE, HUMID_DAY)
        assert not call.reachable
        assert call.water.is_zero

    def test_it_says_why_rather_than_raising(self) -> None:
        call = cooling_water_for(STREAM, HOT, AGGRESSIVE, HUMID_DAY)
        assert "wet bulb" in str(call)
        assert "floor" in str(call)

    def test_the_same_target_is_reachable_on_a_dry_day(self) -> None:
        assert cooling_water_for(STREAM, HOT, AGGRESSIVE, DRY_DAY).reachable

    def test_an_ordinary_target_clears_the_floor_on_any_day(self) -> None:
        assert cooling_water_for(STREAM, HOT, WANTED, HUMID_DAY).reachable

    def test_a_target_exactly_on_the_floor_is_reachable(self) -> None:
        floor = floor_temperature(HUMID_DAY)
        assert cooling_water_for(STREAM, HOT, floor, HUMID_DAY).reachable

    def test_a_hair_below_the_floor_is_not(self) -> None:
        floor = floor_temperature(HUMID_DAY)
        under = Temperature.celsius_of(floor.celsius - Decimal("0.5"))
        assert not cooling_water_for(STREAM, HOT, under, HUMID_DAY).reachable


class TestWhatComesOut:
    def test_the_inverse_agrees_with_the_forward_calculation(self) -> None:
        call = cooling_water_for(STREAM, HOT, WANTED, DRY_DAY)
        landed = reachable_temperature(STREAM, HOT, call.water, DRY_DAY)
        assert abs(landed.fahrenheit_value - WANTED.fahrenheit_value) <= Decimal("0.2")

    def test_no_water_leaves_the_sand_where_it_was(self) -> None:
        landed = reachable_temperature(STREAM, HOT, Pounds.zero(), DRY_DAY)
        assert landed.fahrenheit_value == HOT.fahrenheit_value

    def test_more_water_lands_colder(self) -> None:
        less = reachable_temperature(STREAM, HOT, Pounds(500), DRY_DAY)
        more = reachable_temperature(STREAM, HOT, Pounds(1500), DRY_DAY)
        assert more.celsius < less.celsius

    def test_it_cannot_go_below_the_floor_however_much_water(self) -> None:
        landed = reachable_temperature(STREAM, HOT, Pounds(100000), HUMID_DAY)
        assert landed == floor_temperature(HUMID_DAY)


class TestGuards:
    def test_a_cooler_does_not_heat(self) -> None:
        with pytest.raises(RuleError, match="a cooler does not heat"):
            cooling_water_for(STREAM, WANTED, HOT, DRY_DAY)

    def test_no_sand_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="nothing to do"):
            cooling_water_for(Pounds.zero(), HOT, WANTED, DRY_DAY)
        with pytest.raises(BadInputError, match="nothing to do"):
            reachable_temperature(Pounds.zero(), HOT, Pounds(1), DRY_DAY)

    def test_the_types_are_checked(self) -> None:
        bad_mass: Any = 100000
        with pytest.raises(BadInputError, match="sand stream is a bulk mass"):
            cooling_water_for(bad_mass, HOT, WANTED, DRY_DAY)
        bad_temp: Any = 200
        with pytest.raises(BadInputError, match="entering temperature is a temperature"):
            cooling_water_for(STREAM, bad_temp, WANTED, DRY_DAY)
        with pytest.raises(BadInputError, match="wanted temperature is a temperature"):
            cooling_water_for(STREAM, HOT, bad_temp, DRY_DAY)
        with pytest.raises(BadInputError, match="wet bulb temperature is a temperature"):
            cooling_water_for(STREAM, HOT, WANTED, bad_temp)
        with pytest.raises(BadInputError, match="cooling water is a bulk mass"):
            reachable_temperature(STREAM, HOT, bad_mass, DRY_DAY)

    def test_str_names_the_water_when_reachable(self) -> None:
        assert "of water to take" in str(cooling_water_for(STREAM, HOT, WANTED, DRY_DAY))
