from __future__ import annotations

from decimal import Decimal

import pytest

from mullerbox.addition.bond import (
    MAX_LIFT,
    SEVERITY_LIFT,
    bentonite_for,
    working_target,
)
from mullerbox.addition.material import Material
from mullerbox.burnout.loss import burnout_of
from mullerbox.errors import BadInputError
from mullerbox.units.bulk import Pounds
from mullerbox.units.percent import Percent, Points
from tests.burnout.helpers import pour

PUBLISHED = Percent("8.0")
SYSTEM = Pounds.of_tons(150)
CARBON = Percent("3.0")


def burnout(sand: str = "60000", metal: str = "10000", clay: str = "8.0"):  # type: ignore[no-untyped-def]
    return burnout_of(pour(sand=sand, metal=metal), Percent(clay), CARBON)


class TestTheTargetMovesWithProduction:
    def test_the_reference_shift_does_not_lift_it(self) -> None:
        assert working_target(PUBLISHED, Decimal("1.000")) == PUBLISHED

    def test_a_light_shift_does_not_lift_it_either(self) -> None:
        assert working_target(PUBLISHED, Decimal("0.500")) == PUBLISHED

    def test_a_heavy_shift_lifts_it(self) -> None:
        lifted = working_target(PUBLISHED, Decimal("2.000"))
        assert lifted > PUBLISHED
        assert lifted == Percent("8.48")

    def test_the_lift_is_proportional_to_the_excess_severity(self) -> None:
        lifted = working_target(PUBLISHED, Decimal("3.000"))
        expected = PUBLISHED.value * (Decimal(1) + Decimal(2) * SEVERITY_LIFT)
        assert lifted == Percent(expected)

    def test_the_lift_is_bounded(self) -> None:
        enormous = working_target(PUBLISHED, Decimal("50"))
        assert enormous == Percent(PUBLISHED.value * (Decimal(1) + MAX_LIFT))

    def test_it_is_guarded(self) -> None:
        with pytest.raises(BadInputError, match="bond target is a percentage"):
            working_target("8.0", Decimal(1))  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="severity is a decimal"):
            working_target(PUBLISHED, 1)
        with pytest.raises(BadInputError, match="above zero"):
            working_target(PUBLISHED, Decimal(0))


class TestTheSameReadingCallsForDifferentBentonite:
    def test_a_heavy_shift_asks_for_more_than_a_light_one(self) -> None:
        reading = Percent("7.6")
        light = bentonite_for(reading, PUBLISHED, burnout(sand="120000"), SYSTEM)
        heavy = bentonite_for(reading, PUBLISHED, burnout(sand="30000"), SYSTEM)
        assert heavy.addition.mass > light.addition.mass
        assert heavy.working_target > light.working_target

    def test_the_published_target_did_not_move(self) -> None:
        reading = Percent("7.6")
        light = bentonite_for(reading, PUBLISHED, burnout(sand="120000"), SYSTEM)
        heavy = bentonite_for(reading, PUBLISHED, burnout(sand="30000"), SYSTEM)
        assert light.published_target == heavy.published_target == PUBLISHED

    def test_a_reading_in_band_on_the_published_target_can_still_call_for_bond(
        self,
    ) -> None:
        # 8.1 is above the published 8.0 and below the working target a three
        # to one shift produces.
        call = bentonite_for(Percent("8.1"), PUBLISHED, burnout(sand="30000"), SYSTEM)
        assert call.target_was_lifted
        assert not call.addition.is_nothing

    def test_the_same_reading_needs_nothing_on_a_light_shift(self) -> None:
        call = bentonite_for(Percent("8.1"), PUBLISHED, burnout(sand="120000"), SYSTEM)
        assert not call.target_was_lifted
        assert call.addition.is_nothing


class TestTheMass:
    def test_it_is_grossed_up_by_the_yield(self) -> None:
        call = bentonite_for(Percent("7.5"), PUBLISHED, burnout(), SYSTEM)
        assert call.deficit == Points("0.50")
        assert call.addition.mass == SYSTEM.scaled(
            Decimal("0.005") / Material.BENTONITE.yield_factor
        )

    def test_the_yield_is_what_makes_it_more_than_the_bare_clay(self) -> None:
        call = bentonite_for(Percent("7.5"), PUBLISHED, burnout(), SYSTEM)
        assert call.addition.mass > SYSTEM.scaled(Decimal("0.005"))

    def test_a_bigger_system_needs_more_for_the_same_deficit(self) -> None:
        small = bentonite_for(Percent("7.5"), PUBLISHED, burnout(), Pounds.of_tons(50))
        big = bentonite_for(Percent("7.5"), PUBLISHED, burnout(), Pounds.of_tons(150))
        # Proportional to the cent. Masses are rounded to a hundredth of a
        # pound, so tripling a rounded number and rounding a tripled one differ
        # in the last place and always will.
        assert abs(big.addition.mass.value - small.addition.mass.value * 3) <= Decimal("0.01")
        assert big.addition.mass > small.addition.mass

    def test_the_addition_is_bentonite_and_says_why(self) -> None:
        call = bentonite_for(Percent("7.5"), PUBLISHED, burnout(), SYSTEM)
        assert call.addition.material is Material.BENTONITE
        assert "under the working target" in call.addition.reason


class TestAtOrAboveTarget:
    def test_exactly_on_target_adds_nothing(self) -> None:
        call = bentonite_for(PUBLISHED, PUBLISHED, burnout(sand="120000"), SYSTEM)
        assert call.addition.is_nothing
        assert "at or above" in call.addition.reason

    def test_above_target_adds_nothing_rather_than_a_negative(self) -> None:
        call = bentonite_for(Percent("9.5"), PUBLISHED, burnout(), SYSTEM)
        assert call.addition.is_nothing
        assert call.deficit.is_low

    def test_the_zero_is_still_an_addition_with_a_reason(self) -> None:
        call = bentonite_for(Percent("9.5"), PUBLISHED, burnout(), SYSTEM)
        assert call.addition.material is Material.BENTONITE
        assert call.addition.reason.strip()


class TestGuards:
    def test_the_arguments_are_checked(self) -> None:
        with pytest.raises(BadInputError, match="methylene blue reading"):
            bentonite_for("7.5", PUBLISHED, burnout(), SYSTEM)  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="bond target is a percentage"):
            bentonite_for(Percent("7.5"), "8.0", burnout(), SYSTEM)  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="needs the shift's burnout"):
            bentonite_for(Percent("7.5"), PUBLISHED, "hard", SYSTEM)  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="system mass is a bulk mass"):
            bentonite_for(Percent("7.5"), PUBLISHED, burnout(), 300000)  # type: ignore[arg-type]

    def test_an_empty_system_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="no sand in it"):
            bentonite_for(Percent("7.5"), PUBLISHED, burnout(), Pounds.zero())

    def test_str_names_the_two_targets(self) -> None:
        call = bentonite_for(Percent("7.5"), PUBLISHED, burnout(sand="30000"), SYSTEM)
        assert "published" in str(call)
        assert "MB 7.50%" in str(call)
