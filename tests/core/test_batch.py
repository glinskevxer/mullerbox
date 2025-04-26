from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from mullerbox.core.batch import Core, CoreBatch
from mullerbox.core.binder import Binder, BinderSystem
from mullerbox.errors import BadInputError, RuleError, StateError
from mullerbox.units.bulk import Pounds
from mullerbox.units.duration import Seconds
from mullerbox.units.percent import Percent
from mullerbox.units.pressure import Psi

MIXED = datetime(2025, 4, 22, 7, 30, 0)

SYSTEM = BinderSystem(
    binder=Binder.PHENOLIC_URETHANE,
    resin=Percent("1.2"),
    catalyst=Percent("0.06"),
    bench_life=Seconds(300),
    strip_time=Seconds(120),
    full_cure=Seconds(900),
    tensile_floor=Psi(180),
)


def batch(charged: str = "400", blown: str = "0") -> CoreBatch:
    return CoreBatch(
        batch_id="CB-1",
        system=SYSTEM,
        mixed_at=MIXED,
        charged=Pounds(charged),
        blown=Pounds(blown),
    )


def at(seconds: int) -> datetime:
    return MIXED + timedelta(seconds=seconds)


class TestAgeIsAlwaysAskedAboutAMoment:
    def test_the_age_comes_from_the_caller(self) -> None:
        assert batch().age_at(at(90)) == Seconds(90)

    def test_time_cannot_run_backwards(self) -> None:
        with pytest.raises(BadInputError, match="which is after"):
            batch().age_at(at(-1))

    def test_it_wants_a_moment(self) -> None:
        with pytest.raises(BadInputError, match="taken at a moment"):
            batch().age_at(90)  # type: ignore[arg-type]

    def test_workability_follows_the_binder(self) -> None:
        assert batch().is_workable_at(at(299))
        assert not batch().is_workable_at(at(300))


class TestBlowing:
    def test_it_draws_the_batch_down(self) -> None:
        after = batch().blow(Pounds(100), at(60))
        assert after.blown == Pounds(100)
        assert after.remaining == Pounds(300)

    def test_the_earlier_batch_is_untouched(self) -> None:
        first = batch()
        first.blow(Pounds(100), at(60))
        assert first.blown.is_zero

    def test_blowing_past_bench_life_is_refused(self) -> None:
        with pytest.raises(StateError, match="past the 5:00 bench life"):
            batch().blow(Pounds(100), at(301))

    def test_blowing_more_than_is_left_is_refused(self) -> None:
        with pytest.raises(StateError, match="has 400.00 lb left"):
            batch().blow(Pounds(500), at(60))

    def test_blowing_nothing_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="not a blow"):
            batch().blow(Pounds.zero(), at(60))

    def test_it_wants_a_mass(self) -> None:
        with pytest.raises(BadInputError, match="a blow is a bulk mass"):
            batch().blow(100, at(60))  # type: ignore[arg-type]

    def test_a_batch_can_be_emptied(self) -> None:
        assert batch().blow(Pounds(400), at(60)).is_spent

    def test_utilisation_is_what_was_blown(self) -> None:
        assert batch().blow(Pounds(100), at(60)).utilisation == Pounds(100)


class TestBatchConstruction:
    def test_the_pieces_are_checked(self) -> None:
        with pytest.raises(BadInputError, match="needs an identifier"):
            CoreBatch(
                batch_id=" ",
                system=SYSTEM,
                mixed_at=MIXED,
                charged=Pounds(400),
            )
        with pytest.raises(BadInputError, match="mixed on a binder system"):
            CoreBatch(
                batch_id="CB-1",
                system="furan",  # type: ignore[arg-type]
                mixed_at=MIXED,
                charged=Pounds(400),
            )
        with pytest.raises(BadInputError, match="is timestamped"):
            CoreBatch(
                batch_id="CB-1",
                system=SYSTEM,
                mixed_at="2025",  # type: ignore[arg-type]
                charged=Pounds(400),
            )
        with pytest.raises(BadInputError, match="no sand in it"):
            CoreBatch(
                batch_id="CB-1",
                system=SYSTEM,
                mixed_at=MIXED,
                charged=Pounds.zero(),
            )

    def test_more_blown_than_charged_is_refused(self) -> None:
        with pytest.raises(RuleError, match="has blown"):
            batch(charged="400", blown="500")

    def test_str_names_what_is_left(self) -> None:
        assert "200.00 lb of 400.00 lb left" in str(batch(blown="200"))


class TestCore:
    def test_it_is_checked(self) -> None:
        with pytest.raises(BadInputError, match="needs an identifier"):
            Core(core_id=" ", batch_id="CB-1", blown_at=MIXED, mass=Pounds(4))
        with pytest.raises(BadInputError, match="names the batch"):
            Core(core_id="K-1", batch_id="  ", blown_at=MIXED, mass=Pounds(4))
        with pytest.raises(BadInputError, match="no sand in it is not a core"):
            Core(core_id="K-1", batch_id="CB-1", blown_at=MIXED, mass=Pounds.zero())

    def test_stripping_follows_the_binder(self) -> None:
        core = Core(core_id="K-1", batch_id="CB-1", blown_at=MIXED, mass=Pounds(4))
        assert not core.may_strip_at(at(119), SYSTEM)
        assert core.may_strip_at(at(120), SYSTEM)

    def test_curing_follows_the_binder(self) -> None:
        core = Core(core_id="K-1", batch_id="CB-1", blown_at=MIXED, mass=Pounds(4))
        assert not core.is_cured_at(at(899), SYSTEM)
        assert core.is_cured_at(at(900), SYSTEM)

    def test_drawing_early_is_refused_by_name(self) -> None:
        core = Core(core_id="K-1", batch_id="CB-1", blown_at=MIXED, mass=Pounds(4))
        with pytest.raises(StateError, match="strips at 2:00"):
            core.require_strippable(at(60), SYSTEM)

    def test_drawing_on_time_passes(self) -> None:
        core = Core(core_id="K-1", batch_id="CB-1", blown_at=MIXED, mass=Pounds(4))
        core.require_strippable(at(120), SYSTEM)

    def test_a_core_cannot_be_aged_before_it_was_blown(self) -> None:
        core = Core(core_id="K-1", batch_id="CB-1", blown_at=MIXED, mass=Pounds(4))
        with pytest.raises(BadInputError, match="was blown after"):
            core.may_strip_at(at(-1), SYSTEM)
