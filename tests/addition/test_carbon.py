from __future__ import annotations

from decimal import Decimal

import pytest

from mullerbox.addition.carbon import HEADROOM, aim_under, seacoal_for
from mullerbox.addition.material import Material
from mullerbox.burnout.loss import burnout_of
from mullerbox.errors import BadInputError
from mullerbox.units.bulk import Pounds
from mullerbox.units.percent import Percent
from tests.burnout.helpers import pour

CEILING = Percent("3.5")
SYSTEM = Pounds.of_tons(100)


def burnout(sand: str = "60000"):  # type: ignore[no-untyped-def]
    return burnout_of(pour(sand=sand), Percent("8.0"), Percent("3.0"))


def call(measured: str, ceiling: Percent = CEILING):  # type: ignore[no-untyped-def]
    return seacoal_for(Percent(measured), ceiling, burnout(), SYSTEM)


class TestTheAimSitsUnderTheCeiling:
    def test_it_is_the_ceiling_times_the_headroom(self) -> None:
        assert aim_under(CEILING) == Percent((CEILING.value * HEADROOM).quantize(Decimal("0.01")))

    def test_it_is_always_below_the_ceiling(self) -> None:
        for ceiling in ("2.0", "3.5", "5.0"):
            assert aim_under(Percent(ceiling)) < Percent(ceiling)

    def test_it_is_guarded(self) -> None:
        with pytest.raises(BadInputError, match="LOI ceiling is a percentage"):
            aim_under("3.5")  # type: ignore[arg-type]


class TestBelowTheAim:
    def test_it_calls_for_seacoal(self) -> None:
        got = call("2.4")
        assert not got.addition.is_nothing
        assert got.addition.material is Material.SEACOAL

    def test_the_mass_is_grossed_up_by_the_yield(self) -> None:
        got = call("2.4")
        assert got.addition.mass == SYSTEM.scaled(
            got.shortfall.value / Decimal(100) / Material.SEACOAL.yield_factor
        )

    def test_a_bigger_shortfall_calls_for_more(self) -> None:
        assert call("2.0").addition.mass > call("2.6").addition.mass

    def test_the_reason_names_what_the_pour_took(self) -> None:
        assert "to the pour" in call("2.4").addition.reason


class TestBetweenTheAimAndTheCeiling:
    def test_it_calls_for_nothing(self) -> None:
        got = call("3.2")
        assert got.addition.is_nothing
        assert "at or above the aim" in got.addition.reason

    def test_it_is_not_reported_as_over_the_ceiling(self) -> None:
        assert not call("3.2").is_over_ceiling

    def test_exactly_on_the_aim_calls_for_nothing(self) -> None:
        got = seacoal_for(aim_under(CEILING), CEILING, burnout(), SYSTEM)
        assert got.addition.is_nothing


class TestOverTheCeiling:
    def test_it_calls_for_nothing_and_says_why(self) -> None:
        got = call("3.8")
        assert got.is_over_ceiling
        assert got.addition.is_nothing
        assert "already over the ceiling" in got.addition.reason

    def test_the_ceiling_reason_is_distinct_from_the_aim_reason(self) -> None:
        assert "over the ceiling" in call("3.8").addition.reason
        assert "over the ceiling" not in call("3.2").addition.reason

    def test_exactly_on_the_ceiling_is_not_over_it(self) -> None:
        assert not call("3.5").is_over_ceiling


class TestTheBurnoutIsCarried:
    def test_it_is_reported_whatever_the_call(self) -> None:
        for measured in ("2.4", "3.2", "3.8"):
            assert not call(measured).burnt.is_zero

    def test_a_harder_shift_burnt_more(self) -> None:
        light = seacoal_for(Percent("2.4"), CEILING, burnout(sand="120000"), SYSTEM)
        heavy = seacoal_for(Percent("2.4"), CEILING, burnout(sand="30000"), SYSTEM)
        assert heavy.burnt > light.burnt

    def test_the_burnout_does_not_change_the_mass(self) -> None:
        """The addition closes the measured gap; the burnout is context."""
        light = seacoal_for(Percent("2.4"), CEILING, burnout(sand="120000"), SYSTEM)
        heavy = seacoal_for(Percent("2.4"), CEILING, burnout(sand="30000"), SYSTEM)
        assert light.addition.mass == heavy.addition.mass


class TestGuards:
    def test_the_arguments_are_checked(self) -> None:
        with pytest.raises(BadInputError, match="loss on ignition reading"):
            seacoal_for("2.4", CEILING, burnout(), SYSTEM)  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="LOI ceiling is a percentage"):
            seacoal_for(Percent("2.4"), "3.5", burnout(), SYSTEM)  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="needs the shift's burnout"):
            seacoal_for(Percent("2.4"), CEILING, "hard", SYSTEM)  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="system mass is a bulk mass"):
            seacoal_for(Percent("2.4"), CEILING, burnout(), 200000)  # type: ignore[arg-type]

    def test_an_empty_system_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="no sand in it"):
            seacoal_for(Percent("2.4"), CEILING, burnout(), Pounds.zero())

    def test_str_names_the_ceiling(self) -> None:
        assert "under a ceiling of 3.50%" in str(call("2.4"))
