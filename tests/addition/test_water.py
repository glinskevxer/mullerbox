from __future__ import annotations

from decimal import Decimal

import pytest

from mullerbox.addition.material import Material
from mullerbox.addition.water import (
    ALLOWANCE_PER_DEGREE,
    BASE_RESPONSE,
    EVAPORATION_ONSET_C,
    MAX_ALLOWANCE,
    REFERENCE_CLAY,
    evaporation_allowance,
    response_at,
    water_for,
)
from mullerbox.errors import BadInputError
from mullerbox.units.bulk import Pounds
from mullerbox.units.percent import Percent
from mullerbox.units.thermal import Temperature

TARGET = Percent("42")
CLAY = Percent("8.0")
BATCH = Pounds(6000)
COOL = Temperature.celsius_of(35)
HOT = Temperature.celsius_of(60)


def call(  # type: ignore[no-untyped-def]
    measured: str = "38",
    clay: Percent = CLAY,
    temperature: Temperature = COOL,
    batch: Pounds = BATCH,
):
    return water_for(Percent(measured), TARGET, clay, batch, temperature)


class TestTheResponseDependsOnTheBond:
    def test_the_reference_bond_gives_the_base_response(self) -> None:
        assert response_at(Percent(REFERENCE_CLAY)) == BASE_RESPONSE

    def test_a_richer_system_responds_less(self) -> None:
        assert response_at(Percent("10.0")) < BASE_RESPONSE

    def test_a_leaner_system_responds_more(self) -> None:
        assert response_at(Percent("6.0")) > BASE_RESPONSE

    def test_twice_the_bond_halves_the_response(self) -> None:
        assert response_at(Percent("16.0")) == BASE_RESPONSE / 2

    def test_it_is_guarded(self) -> None:
        with pytest.raises(BadInputError, match="bond level is a percentage"):
            response_at("8.0")  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="no bond has no water response"):
            response_at(Percent.zero())


class TestTheSameShortfallNeedsDifferentWater:
    def test_a_richer_system_takes_more_water(self) -> None:
        lean = call(clay=Percent("6.0"))
        rich = call(clay=Percent("10.0"))
        assert rich.addition.mass > lean.addition.mass

    def test_the_shortfall_was_the_same(self) -> None:
        lean = call(clay=Percent("6.0"))
        rich = call(clay=Percent("10.0"))
        assert lean.shortfall == rich.shortfall

    def test_the_moisture_needed_is_the_shortfall_over_the_response(self) -> None:
        got = call()
        assert got.moisture_needed == (got.shortfall.value / got.response).quantize(
            Decimal("0.0001")
        )


class TestTheHeatAllowance:
    def test_cool_sand_gets_no_allowance(self) -> None:
        assert evaporation_allowance(COOL) == Decimal(0)
        assert not call(temperature=COOL).was_allowed_for_heat

    def test_exactly_at_the_onset_gets_nothing(self) -> None:
        at_onset = Temperature.celsius_of(EVAPORATION_ONSET_C)
        assert evaporation_allowance(at_onset) == Decimal(0)

    def test_hot_sand_gets_an_uplift(self) -> None:
        assert evaporation_allowance(HOT) == Decimal(10) * ALLOWANCE_PER_DEGREE
        assert call(temperature=HOT).was_allowed_for_heat

    def test_the_allowance_is_capped(self) -> None:
        very_hot = Temperature.celsius_of(120)
        assert evaporation_allowance(very_hot) == MAX_ALLOWANCE

    def test_hot_sand_gets_more_water_for_the_same_shortfall(self) -> None:
        assert call(temperature=HOT).addition.mass > call(temperature=COOL).addition.mass

    def test_the_uplift_is_exactly_the_allowance(self) -> None:
        cool = call(temperature=COOL)
        hot = call(temperature=HOT)
        assert hot.addition.mass == cool.addition.mass.scaled(Decimal(1) + hot.allowance)

    def test_it_wants_a_temperature(self) -> None:
        with pytest.raises(BadInputError, match="return sand temperature"):
            evaporation_allowance(60)  # type: ignore[arg-type]


class TestTheMass:
    def test_a_bigger_batch_takes_proportionally_more(self) -> None:
        small = call(batch=Pounds(3000))
        big = call(batch=Pounds(6000))
        assert abs(big.addition.mass.value - small.addition.mass.value * 2) <= Decimal("0.01")

    def test_the_addition_is_water_and_says_why(self) -> None:
        got = call()
        assert got.addition.material is Material.WATER
        assert "response" in got.addition.reason


class TestAtOrAboveTarget:
    def test_on_target_adds_nothing(self) -> None:
        got = call(measured="42")
        assert got.addition.is_nothing
        assert "at or above" in got.addition.reason

    def test_over_target_adds_nothing_rather_than_a_negative(self) -> None:
        got = call(measured="46")
        assert got.addition.is_nothing
        assert got.shortfall.is_low
        assert got.moisture_needed == Decimal(0)

    def test_the_response_is_still_reported(self) -> None:
        assert call(measured="46").response == BASE_RESPONSE


class TestGuards:
    def test_the_arguments_are_checked(self) -> None:
        with pytest.raises(BadInputError, match="compactability reading"):
            water_for("38", TARGET, CLAY, BATCH, COOL)  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="compactability target"):
            water_for(Percent(38), "42", CLAY, BATCH, COOL)  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="batch mass is a bulk mass"):
            water_for(Percent(38), TARGET, CLAY, 6000, COOL)  # type: ignore[arg-type]

    def test_an_empty_batch_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="no sand in it"):
            water_for(Percent(38), TARGET, CLAY, Pounds.zero(), COOL)

    def test_str_names_both_readings(self) -> None:
        assert "compactability 38.00% against 42.00%" in str(call())
