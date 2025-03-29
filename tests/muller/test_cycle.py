from __future__ import annotations

import pytest

from mullerbox.addition.material import Addition, Material
from mullerbox.errors import BadInputError, RuleError, StateError
from mullerbox.muller.cycle import (
    MIN_DRY_MULL,
    MIN_WET_MULL,
    Cycle,
    Stage,
)
from mullerbox.units.bulk import Pounds
from mullerbox.units.duration import Seconds

RETURN = Pounds(6000)


def add(material: Material, mass: str) -> Addition:
    return Addition(material=material, mass=Pounds(mass), reason="test")


BOND = add(Material.BENTONITE, "140")
WATER = add(Material.WATER, "180")
COAL = add(Material.SEACOAL, "60")


def charged(*additions: Addition, sand: Pounds = RETURN) -> Cycle:
    return Cycle.charge("B-1", sand, list(additions))


class TestCharging:
    def test_a_cycle_starts_charged(self) -> None:
        assert charged(BOND).stage is Stage.CHARGED

    def test_zero_additions_are_dropped_on_the_way_in(self) -> None:
        nothing = Addition.nothing(Material.SEACOAL, "already at aim")
        cycle = charged(BOND, nothing)
        assert not cycle.charges(Material.SEACOAL)
        assert cycle.charges(Material.BENTONITE)

    def test_a_material_can_only_be_charged_once(self) -> None:
        with pytest.raises(RuleError, match="only be charged once"):
            charged(BOND, add(Material.BENTONITE, "40"))

    def test_the_pieces_are_checked(self) -> None:
        with pytest.raises(BadInputError, match="needs an identifier"):
            Cycle(batch_id="  ", return_sand=RETURN)
        with pytest.raises(BadInputError, match="return sand is a bulk mass"):
            Cycle(batch_id="B-1", return_sand=6000)  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="no return sand in it"):
            Cycle(batch_id="B-1", return_sand=Pounds.zero())
        with pytest.raises(BadInputError, match="charged with additions"):
            Cycle(batch_id="B-1", return_sand=RETURN, additions=("bentonite",))  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="a cycle has a stage"):
            Cycle(batch_id="B-1", return_sand=RETURN, stage="charged")  # type: ignore[arg-type]

    def test_an_overcharged_batch_is_refused(self) -> None:
        with pytest.raises(RuleError, match="past the 10% a muller can distribute"):
            charged(add(Material.NEW_SAND, "700"))

    def test_water_does_not_count_towards_the_addition_share(self) -> None:
        # 700 lb of water on 6000 lb of sand is over a tenth and is allowed.
        cycle = charged(add(Material.WATER, "700"))
        assert cycle.charges(Material.WATER)

    def test_the_batch_mass_is_everything_charged(self) -> None:
        assert charged(BOND, WATER).batch_mass == Pounds(6320)

    def test_dry_additions_leave_the_water_out(self) -> None:
        cycle = charged(BOND, WATER, COAL)
        assert {a.material for a in cycle.dry_additions} == {
            Material.BENTONITE,
            Material.SEACOAL,
        }

    def test_lookup(self) -> None:
        cycle = charged(BOND)
        assert cycle.addition_of(Material.BENTONITE) == BOND
        assert cycle.addition_of(Material.WATER) is None
        with pytest.raises(BadInputError, match="material is expected"):
            cycle.charges("bentonite")  # type: ignore[arg-type]


class TestTheDryMullComesFirst:
    def test_bentonite_needs_a_dry_mull(self) -> None:
        with pytest.raises(RuleError, match="under the 30s that distributes it"):
            charged(BOND).mulled(Seconds(20), Seconds(90))

    def test_exactly_the_minimum_passes(self) -> None:
        assert charged(BOND).mulled(MIN_DRY_MULL, Seconds(90)).stage is Stage.MULLED

    def test_water_with_no_dry_mull_at_all_is_refused(self) -> None:
        with pytest.raises(RuleError, match="no dry mull before it"):
            charged(WATER).mulled(Seconds.zero(), Seconds(90))

    def test_water_needs_a_long_enough_wet_mull(self) -> None:
        with pytest.raises(RuleError, match="under the 1:00 that develops it"):
            charged(WATER).mulled(Seconds(45), Seconds(30))

    def test_exactly_the_wet_minimum_passes(self) -> None:
        assert charged(WATER).mulled(Seconds(45), MIN_WET_MULL).stage is Stage.MULLED

    def test_a_batch_with_no_bond_or_water_may_mull_briefly(self) -> None:
        assert charged(COAL).mulled(Seconds(10), Seconds.zero()).stage is Stage.MULLED

    def test_a_mull_wants_two_durations(self) -> None:
        with pytest.raises(BadInputError, match="two durations"):
            charged(BOND).mulled(60, Seconds(90))  # type: ignore[arg-type]


class TestTheStageMachine:
    def test_charged_then_mulled_then_discharged(self) -> None:
        cycle = charged(BOND, WATER).mulled(Seconds(60), Seconds(120))
        assert cycle.stage is Stage.MULLED
        assert cycle.discharged().is_finished

    def test_a_charged_batch_cannot_be_discharged(self) -> None:
        with pytest.raises(StateError, match="is charged and cannot be discharged"):
            charged(BOND).discharged()

    def test_a_mulled_batch_cannot_be_mulled_again(self) -> None:
        cycle = charged(BOND).mulled(Seconds(60), Seconds(90))
        with pytest.raises(StateError, match="is mulled and cannot be mulled again"):
            cycle.mulled(Seconds(60), Seconds(90))

    def test_a_discharged_batch_cannot_be_discharged_again(self) -> None:
        cycle = charged(BOND).mulled(Seconds(60), Seconds(90)).discharged()
        with pytest.raises(StateError, match="is discharged and cannot be discharged"):
            cycle.discharged()

    def test_the_earlier_cycle_is_untouched(self) -> None:
        first = charged(BOND)
        first.mulled(Seconds(60), Seconds(90))
        assert first.stage is Stage.CHARGED


class TestReporting:
    def test_the_total_mull(self) -> None:
        cycle = charged(BOND, WATER).mulled(Seconds(60), Seconds(120))
        assert cycle.total_mull == Seconds(180)

    def test_an_unmulled_cycle_has_no_mull_time(self) -> None:
        assert charged(BOND).total_mull == Seconds.zero()

    def test_str_names_the_stage_and_the_mass(self) -> None:
        assert str(charged(BOND)) == "batch B-1 charged, 3.070 t after 1 additions"
