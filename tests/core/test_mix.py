from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from mullerbox.core.binder import Binder, BinderSystem
from mullerbox.core.mix import SPILLAGE, cores_from, mix_for
from mullerbox.errors import BadInputError, RuleError
from mullerbox.units.bulk import Pounds
from mullerbox.units.duration import Seconds
from mullerbox.units.percent import Percent
from mullerbox.units.pressure import Psi

SYSTEM = BinderSystem(
    binder=Binder.PHENOLIC_URETHANE,
    resin=Percent("1.2"),
    catalyst=Percent("0.06"),
    bench_life=Seconds(300),
    strip_time=Seconds(120),
    full_cure=Seconds(900),
    tensile_floor=Psi(180),
)


class TestTheAllowanceIsForSpillageOnly:
    def test_the_sand_is_the_cores_plus_spillage(self) -> None:
        mix = mix_for(SYSTEM, Pounds(1000))
        assert mix.spillage == Pounds(1000).scaled(SPILLAGE)
        assert mix.sand == Pounds(1040)

    def test_there_is_no_extra_beyond_it(self) -> None:
        mix = mix_for(SYSTEM, Pounds(1000))
        assert mix.sand.value == Decimal(1000) * (Decimal(1) + SPILLAGE)

    def test_a_bigger_order_scales(self) -> None:
        small = mix_for(SYSTEM, Pounds(500))
        big = mix_for(SYSTEM, Pounds(1000))
        assert big.sand.value == small.sand.value * 2


class TestUnusedMixIsScrap:
    def test_the_whole_charge_is_lost_if_none_is_blown(self) -> None:
        mix = mix_for(SYSTEM, Pounds(1000))
        assert mix.waste_if_unused == mix.total_charge

    def test_partial_use_scraps_the_rest(self) -> None:
        mix = mix_for(SYSTEM, Pounds(1000))
        assert mix.scrap_from_blowing(Pounds(600)) == mix.total_charge - Pounds(600)

    def test_blowing_everything_scraps_nothing(self) -> None:
        mix = mix_for(SYSTEM, Pounds(1000))
        assert mix.scrap_from_blowing(mix.total_charge).is_zero

    def test_blowing_more_than_was_charged_is_refused(self) -> None:
        mix = mix_for(SYSTEM, Pounds(1000))
        with pytest.raises(RuleError, match="cannot be blown from"):
            mix.scrap_from_blowing(Pounds(9999))

    def test_it_wants_a_mass(self) -> None:
        bad: Any = 600
        with pytest.raises(BadInputError, match="blown mass is a bulk mass"):
            mix_for(SYSTEM, Pounds(1000)).scrap_from_blowing(bad)


class TestTheTwoConventions:
    def test_resin_is_a_share_of_the_sand(self) -> None:
        mix = mix_for(SYSTEM, Pounds(1000))
        assert mix.resin == mix.sand.scaled(SYSTEM.resin.fraction)

    def test_catalyst_is_a_share_of_the_resin(self) -> None:
        mix = mix_for(SYSTEM, Pounds(1000))
        assert mix.catalyst == mix.resin.scaled(SYSTEM.catalyst_ratio)

    def test_both_conventions_are_already_on_the_binder_system(self) -> None:
        """The share of sand and the share of resin are both there already.

        A conversion helper written for this module turned out to return
        ``system.catalyst`` unchanged, because the field already is the share
        of sand. The two numbers below are the two conventions and neither
        needed deriving.
        """
        assert SYSTEM.catalyst == Percent("0.06")
        assert SYSTEM.catalyst_ratio == Decimal("0.050")
        assert SYSTEM.catalyst.value == SYSTEM.resin.value * SYSTEM.catalyst_ratio

    def test_the_two_are_two_orders_apart_in_the_same_units(self) -> None:
        """Which is why reading one as the other is the mistake it is.

        Compared as fractions, because ``catalyst_ratio`` is already one and
        ``catalyst`` is a percentage. Comparing them raw is the same confusion
        the two conventions cause on the shop floor.
        """
        as_share_of_resin = SYSTEM.catalyst_ratio
        as_share_of_sand = SYSTEM.catalyst.fraction
        assert as_share_of_resin > as_share_of_sand * 50


class TestTheInverse:
    def test_it_undoes_the_spillage_allowance(self) -> None:
        mix = mix_for(SYSTEM, Pounds(1000))
        assert cores_from(SYSTEM, mix.sand) == Pounds(1000)

    def test_no_sand_makes_no_cores(self) -> None:
        assert cores_from(SYSTEM, Pounds.zero()).is_zero

    def test_it_is_guarded(self) -> None:
        bad: Any = "pep"
        with pytest.raises(BadInputError, match="binder system is expected"):
            cores_from(bad, Pounds(1000))
        with pytest.raises(BadInputError, match="sand available is a bulk mass"):
            cores_from(SYSTEM, bad)


class TestGuards:
    def test_a_mix_for_nothing_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="not a mix"):
            mix_for(SYSTEM, Pounds.zero())

    def test_a_mix_too_big_to_blow_is_refused_with_the_bench_life(self) -> None:
        with pytest.raises(RuleError, match="inside a 5:00 bench life"):
            mix_for(SYSTEM, Pounds(3000))

    def test_the_refusal_says_to_split_it(self) -> None:
        with pytest.raises(RuleError, match="split the mix"):
            mix_for(SYSTEM, Pounds(3000))

    def test_the_types_are_checked(self) -> None:
        bad: Any = "pep"
        with pytest.raises(BadInputError, match="binder system is expected"):
            mix_for(bad, Pounds(1000))
        with pytest.raises(BadInputError, match="cores wanted is a bulk mass"):
            mix_for(SYSTEM, bad)

    def test_str_names_the_charge_and_the_binder(self) -> None:
        text = str(mix_for(SYSTEM, Pounds(1000)))
        assert "charge for" in text
        assert "phenolic urethane" in text
