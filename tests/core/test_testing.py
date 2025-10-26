from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from mullerbox.core.binder import Binder, BinderSystem
from mullerbox.core.testing import (
    HANDLING_HARDNESS,
    ScratchReading,
    TensileResult,
    batch_verdict,
)
from mullerbox.errors import BadInputError, RuleError
from mullerbox.units.duration import Seconds
from mullerbox.units.percent import Percent
from mullerbox.units.pressure import Psi

MIXED = datetime(2025, 10, 20, 8, 0, 0)


def system(binder: Binder = Binder.PHENOLIC_URETHANE, cure: int = 900) -> BinderSystem:
    return BinderSystem(
        binder=binder,
        resin=Percent("1.2"),
        catalyst=Percent("0.06"),
        bench_life=Seconds(300),
        strip_time=Seconds(120),
        full_cure=Seconds(cure),
        tensile_floor=Psi(180),
    )


def result(
    specimen_id: str = "T-1",
    age: int = 900,
    tensile: str = "210",
    built: BinderSystem | None = None,
) -> TensileResult:
    return TensileResult(
        specimen_id=specimen_id,
        system=built or system(),
        mixed_at=MIXED,
        broken_at=MIXED + timedelta(seconds=age),
        tensile=Psi(tensile),
    )


class TestTheAgeIsPartOfTheResult:
    def test_it_comes_from_the_two_moments(self) -> None:
        assert result(age=900).age == Seconds(900)

    def test_breaking_before_mixing_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="broken before it was mixed"):
            TensileResult(
                specimen_id="T-1",
                system=system(),
                mixed_at=MIXED,
                broken_at=MIXED - timedelta(seconds=1),
                tensile=Psi(210),
            )

    def test_a_specimen_broken_at_cure_is_a_fair_reading(self) -> None:
        assert result(age=900).at_full_cure
        assert result(age=900).was_cured

    def test_one_broken_far_early_is_not(self) -> None:
        early = result(age=200)
        assert not early.at_full_cure
        assert not early.was_cured

    def test_the_window_is_either_side_of_cure(self) -> None:
        assert result(age=700).at_full_cure
        assert result(age=1100).at_full_cure
        assert not result(age=500).at_full_cure

    def test_str_names_the_age_and_the_binder(self) -> None:
        assert str(result()) == "T-1: 210.0 psi at 15:00 on phenolic urethane no bake"


class TestComparisonAcrossBindersIsRefused:
    def test_two_of_one_binder_compare(self) -> None:
        strong = result("T-1", tensile="240")
        weak = result("T-2", tensile="200")
        assert strong.stronger_than(weak)

    def test_two_binders_do_not(self) -> None:
        urethane = result("T-1")
        furan = result("T-2", built=system(Binder.FURAN))
        with pytest.raises(RuleError, match="not comparable"):
            urethane.stronger_than(furan)

    def test_a_specimen_off_cure_does_not_compare(self) -> None:
        cured = result("T-1", age=900)
        early = result("T-2", age=200)
        with pytest.raises(RuleError, match="not\\s+both broken at full cure"):
            cured.stronger_than(early)

    def test_it_wants_a_core_result(self) -> None:
        bad: Any = "T-2"
        with pytest.raises(BadInputError, match="compares against a core result"):
            result().require_comparable(bad)


class TestTheFloor:
    def test_above_the_floor_passes(self) -> None:
        assert result(tensile="210").meets_floor

    def test_exactly_on_it_passes(self) -> None:
        assert result(tensile="180").meets_floor

    def test_under_it_does_not(self) -> None:
        assert not result(tensile="179").meets_floor


class TestScratchIsScreeningOnly:
    def test_a_hard_core_is_fit_to_handle(self) -> None:
        assert ScratchReading("K-1", HANDLING_HARDNESS).fit_to_handle

    def test_a_soft_one_is_not(self) -> None:
        soft = ScratchReading("K-1", Decimal("60"))
        assert not soft.fit_to_handle
        assert "not fit to handle" in soft.verdict()

    def test_the_verdict_is_about_handling(self) -> None:
        assert "fit to handle" in ScratchReading("K-1", Decimal("80")).verdict()

    def test_the_dial_is_bounded(self) -> None:
        with pytest.raises(BadInputError, match="zero to a hundred"):
            ScratchReading("K-1", Decimal("101"))
        with pytest.raises(BadInputError, match="zero to a hundred"):
            ScratchReading("K-1", Decimal("-1"))

    def test_it_is_type_checked(self) -> None:
        bad: Any = 80
        with pytest.raises(BadInputError, match="is a decimal"):
            ScratchReading("K-1", bad)
        with pytest.raises(BadInputError, match="names a core"):
            ScratchReading("  ", Decimal("80"))

    def test_a_batch_is_not_judged_on_scratch(self) -> None:
        """There is no path from a scratch reading to a batch verdict."""
        bad: Any = [ScratchReading("K-1", Decimal("80"))]
        with pytest.raises(BadInputError, match="judged on core results"):
            batch_verdict(bad)


class TestBatchVerdict:
    def test_a_good_batch_passes_with_its_average(self) -> None:
        verdict = batch_verdict([result("T-1", tensile="200"), result("T-2", tensile="220")])
        assert verdict.startswith("passes")
        assert "210.0 psi" in verdict

    def test_one_under_the_floor_fails_the_batch(self) -> None:
        verdict = batch_verdict([result("T-1", tensile="200"), result("T-2", tensile="150")])
        assert verdict.startswith("fails")
        assert "T-2" in verdict

    def test_specimens_off_cure_are_left_out(self) -> None:
        verdict = batch_verdict(
            [result("T-1", tensile="200"), result("T-2", age=200, tensile="10")]
        )
        assert verdict.startswith("passes")
        assert "1 specimens" in verdict

    def test_a_batch_with_nothing_at_cure_cannot_be_judged(self) -> None:
        with pytest.raises(RuleError, match="cannot be judged"):
            batch_verdict([result("T-1", age=200)])

    def test_an_empty_batch_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="no core results to judge"):
            batch_verdict([])


class TestConstruction:
    def test_the_pieces_are_checked(self) -> None:
        bad: Any = "x"
        with pytest.raises(BadInputError, match="needs an identifier"):
            result(specimen_id="  ")
        with pytest.raises(BadInputError, match="names its binder system"):
            TensileResult(
                specimen_id="T-1",
                system=bad,
                mixed_at=MIXED,
                broken_at=MIXED,
                tensile=Psi(210),
            )
        with pytest.raises(BadInputError, match="mixed at is a moment"):
            TensileResult(
                specimen_id="T-1",
                system=system(),
                mixed_at=bad,
                broken_at=MIXED,
                tensile=Psi(210),
            )
        with pytest.raises(BadInputError, match="tensile is a pressure"):
            TensileResult(
                specimen_id="T-1",
                system=system(),
                mixed_at=MIXED,
                broken_at=MIXED,
                tensile=bad,
            )
