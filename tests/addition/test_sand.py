from __future__ import annotations

from decimal import Decimal

import pytest

from mullerbox.addition.material import Material
from mullerbox.addition.sand import (
    MAX_REPLACEMENT_SHARE,
    dead_clay,
    dead_clay_after,
    new_sand_for,
    share_to_reach,
)
from mullerbox.errors import BadInputError
from mullerbox.units.bulk import Pounds
from mullerbox.units.percent import Percent

SYSTEM = Pounds.of_tons(100)
TARGET = Percent("2.0")


class TestDeadClay:
    def test_it_is_what_the_wash_found_and_the_titration_did_not(self) -> None:
        assert dead_clay(Percent("11.0"), Percent("8.0")) == Percent("3.0")

    def test_no_dead_clay_at_all(self) -> None:
        assert dead_clay(Percent("8.0"), Percent("8.0")) == Percent.zero()

    def test_live_above_total_means_a_bad_test(self) -> None:
        with pytest.raises(BadInputError, match="one of the two tests is wrong"):
            dead_clay(Percent("8.0"), Percent("9.0"))

    def test_it_is_guarded(self) -> None:
        with pytest.raises(BadInputError, match="total clay is a percentage"):
            dead_clay("11.0", Percent("8.0"))  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="live clay is a percentage"):
            dead_clay(Percent("11.0"), "8.0")  # type: ignore[arg-type]


class TestTheShareIsProportionalNotDifferential:
    def test_three_to_two_takes_a_third_of_the_system(self) -> None:
        assert share_to_reach(Percent("3.0"), Percent("2.0")) == Decimal("0.333333")

    def test_halving_takes_half(self) -> None:
        assert share_to_reach(Percent("4.0"), Percent("2.0")) == Decimal("0.500000")

    def test_already_at_target_takes_nothing(self) -> None:
        assert share_to_reach(Percent("2.0"), Percent("2.0")) == Decimal(0)

    def test_below_target_takes_nothing(self) -> None:
        assert share_to_reach(Percent("1.0"), Percent("2.0")) == Decimal(0)

    def test_nothing_there_takes_nothing(self) -> None:
        assert share_to_reach(Percent.zero(), Percent("2.0")) == Decimal(0)

    def test_it_is_guarded(self) -> None:
        with pytest.raises(BadInputError, match="current level is a percentage"):
            share_to_reach("3.0", TARGET)  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="target level is a percentage"):
            share_to_reach(Percent("3.0"), "2.0")  # type: ignore[arg-type]


class TestTheTwoRequirementsStaySeparate:
    def test_the_larger_one_governs(self) -> None:
        call = new_sand_for(Pounds(2000), Percent("3.0"), TARGET, SYSTEM)
        assert call.dilution_governs
        assert call.addition.mass == call.dilution

    def test_make_up_governs_only_when_dilution_is_nearly_satisfied(self) -> None:
        # Dead clay barely above target, so the dilution requirement is under
        # two thousand pounds against nine thousand lost. This is the unusual
        # case; on any system that has drifted, dilution wins.
        call = new_sand_for(Pounds(9000), Percent("2.02"), TARGET, SYSTEM)
        assert not call.dilution_governs
        assert call.addition.mass == call.make_up

    def test_they_are_never_added_together(self) -> None:
        call = new_sand_for(Pounds(2000), Percent("3.0"), TARGET, SYSTEM)
        assert call.addition.mass < call.make_up + call.dilution

    def test_both_are_reported_whichever_wins(self) -> None:
        call = new_sand_for(Pounds(2000), Percent("3.0"), TARGET, SYSTEM)
        assert call.make_up == Pounds(2000)
        assert not call.dilution.is_zero

    def test_nothing_needed_at_all(self) -> None:
        call = new_sand_for(Pounds.zero(), Percent("2.0"), TARGET, SYSTEM)
        assert call.addition.is_nothing
        assert call.addition.material is Material.NEW_SAND
        assert call.addition.reason.strip()


class TestTheCap:
    def test_a_big_requirement_is_clipped(self) -> None:
        call = new_sand_for(Pounds.zero(), Percent("6.0"), TARGET, SYSTEM)
        assert call.capped
        assert call.replacement_share == MAX_REPLACEMENT_SHARE
        assert "capped at" in call.addition.reason

    def test_a_modest_requirement_is_not(self) -> None:
        call = new_sand_for(Pounds.zero(), Percent("2.2"), TARGET, SYSTEM)
        assert not call.capped
        assert call.replacement_share < MAX_REPLACEMENT_SHARE

    def test_the_honest_share_is_still_visible_through_share_to_reach(self) -> None:
        assert share_to_reach(Percent("6.0"), TARGET) > MAX_REPLACEMENT_SHARE


class TestTheInverseAgrees:
    def test_replacing_the_computed_share_lands_on_the_target(self) -> None:
        current = Percent("3.0")
        share = share_to_reach(current, TARGET)
        replaced = SYSTEM.scaled(share)
        assert dead_clay_after(current, replaced, SYSTEM) == TARGET

    def test_replacing_nothing_changes_nothing(self) -> None:
        assert dead_clay_after(Percent("3.0"), Pounds.zero(), SYSTEM) == Percent("3.0")

    def test_replacing_everything_clears_it(self) -> None:
        assert dead_clay_after(Percent("3.0"), SYSTEM, SYSTEM) == Percent.zero()

    def test_replacing_more_than_there_is_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="more sand cannot be replaced"):
            dead_clay_after(Percent("3.0"), Pounds.of_tons(200), SYSTEM)

    def test_it_is_guarded(self) -> None:
        with pytest.raises(BadInputError, match="current level is a percentage"):
            dead_clay_after("3.0", Pounds(1), SYSTEM)  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="replaced mass is a bulk mass"):
            dead_clay_after(Percent("3.0"), 1, SYSTEM)  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="system mass is a bulk mass"):
            dead_clay_after(Percent("3.0"), Pounds(1), 100)  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="no dead clay"):
            dead_clay_after(Percent("3.0"), Pounds.zero(), Pounds.zero())


class TestGuards:
    def test_the_arguments_are_checked(self) -> None:
        with pytest.raises(BadInputError, match="system losses are a bulk mass"):
            new_sand_for(2000, Percent("3.0"), TARGET, SYSTEM)  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="system mass is a bulk mass"):
            new_sand_for(Pounds(2000), Percent("3.0"), TARGET, 100)  # type: ignore[arg-type]

    def test_an_empty_system_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="cannot be diluted"):
            new_sand_for(Pounds(2000), Percent("3.0"), TARGET, Pounds.zero())

    def test_str_names_the_driver(self) -> None:
        call = new_sand_for(Pounds(2000), Percent("3.0"), TARGET, SYSTEM)
        assert "driven by dilution" in str(call)
