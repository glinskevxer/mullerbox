from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from mullerbox.errors import BadInputError, RuleError
from mullerbox.muller.history import HEAVY_WATER, History, RecordedCycle
from mullerbox.units.bulk import Pounds
from mullerbox.units.duration import Seconds

PLANNED_WATER = Pounds(180)


def cycle(
    batch_id: str,
    dry: int = 60,
    wet: int = 120,
    water: str = "180",
    bond: str = "140",
    mull: bool = True,
) -> RecordedCycle:
    return RecordedCycle(
        batch_id=batch_id,
        dry_mull=Seconds(dry),
        wet_mull=Seconds(wet),
        bentonite=Pounds(bond),
        water=Pounds(water),
        discharged=mull,
    )


class TestShortMulls:
    def test_a_run_of_good_cycles_says_nothing(self) -> None:
        history = History(cycles=tuple(cycle(f"B-{n}") for n in range(10)))
        assert history.short_mulls == ()
        assert not history.is_running_short

    def test_a_short_dry_mull_is_counted(self) -> None:
        short = cycle("B-9", dry=10)
        history = History(cycles=(*[cycle(f"B-{n}") for n in range(9)], short))
        assert history.short_mulls == (short,)

    def test_a_cycle_that_took_neither_cannot_mull_short(self) -> None:
        bare = cycle("B-9", dry=1, wet=0, bond="0", water="0")
        assert not bare.mulled_short

    def test_a_short_wet_mull_is_counted(self) -> None:
        history = History(
            cycles=(
                *[cycle(f"B-{n}") for n in range(4)],
                *[cycle(f"S-{n}", wet=30) for n in range(4)],
            )
        )
        assert len(history.short_mulls) == 4
        assert history.short_mull_share == Decimal("0.5000")
        assert history.is_running_short

    def test_one_short_mull_in_ten_is_a_bad_minute(self) -> None:
        history = History(cycles=(*[cycle(f"B-{n}") for n in range(9)], cycle("S-1", wet=30)))
        assert not history.is_running_short

    def test_exactly_on_the_share_is_not_the_machine(self) -> None:
        history = History(
            cycles=(
                *[cycle(f"B-{n}") for n in range(8)],
                *[cycle(f"S-{n}", wet=30) for n in range(2)],
            )
        )
        assert history.short_mull_share == Decimal("0.2000")
        assert not history.is_running_short


class TestWaterHeavyCycles:
    def test_a_cycle_over_the_threshold_is_flagged(self) -> None:
        heavy = cycle("W-1", water="260")
        history = History(cycles=(cycle("B-1"), heavy))
        assert history.water_heavy(PLANNED_WATER) == (heavy,)

    def test_exactly_on_the_threshold_is_not(self) -> None:
        edge = cycle("W-1", water=str(PLANNED_WATER.scaled(HEAVY_WATER).value))
        history = History(cycles=(edge,))
        assert history.water_heavy(PLANNED_WATER) == ()

    def test_a_plan_with_no_water_has_no_overrun(self) -> None:
        history = History(cycles=(cycle("B-1"),))
        with pytest.raises(BadInputError, match="no overrun"):
            history.water_heavy(Pounds.zero())

    def test_it_wants_a_mass(self) -> None:
        bad: Any = 180
        with pytest.raises(BadInputError, match="planned water is a bulk mass"):
            History(cycles=(cycle("B-1"),)).water_heavy(bad)


class TestAbandonedBatches:
    def test_a_charged_and_unmulled_cycle_is_counted(self) -> None:
        history = History(cycles=(cycle("B-1"), cycle("B-2", mull=False)))
        assert [c.batch_id for c in history.abandoned] == ["B-2"]
        assert len(history.cycles) == 2

    def test_they_are_named_in_the_findings(self) -> None:
        history = History(cycles=(cycle("B-1"), cycle("B-2", mull=False)))
        findings = history.findings(PLANNED_WATER)
        assert any("never discharged" in x for x in findings)
        assert any("B-2" in x for x in findings)

    def test_an_undischarged_cycle_still_counts_in_the_shares(self) -> None:
        """It ran; it just was not emptied. Its mull times are real."""
        history = History(cycles=(cycle("B-1"), cycle("B-2", mull=False)))
        assert history.short_mull_share == Decimal("0.0000")


class TestFindings:
    def test_a_clean_run_says_there_is_nothing_to_say(self) -> None:
        history = History(cycles=tuple(cycle(f"B-{n}") for n in range(10)))
        findings = history.findings(PLANNED_WATER)
        assert len(findings) == 1
        assert "nothing to say about the machine" in findings[0]

    def test_short_mulls_are_reported_with_the_threshold(self) -> None:
        history = History(cycles=tuple(cycle(f"S-{n}", wet=30) for n in range(5)))
        findings = history.findings(PLANNED_WATER)
        assert any("outrunning the muller" in x for x in findings)

    def test_water_heavy_cycles_name_the_bond_explanation(self) -> None:
        history = History(cycles=tuple(cycle(f"W-{n}", water="260") for n in range(5)))
        findings = history.findings(PLANNED_WATER)
        assert any("undeveloped bond" in x for x in findings)

    def test_an_empty_history_says_nothing_was_recorded(self) -> None:
        assert History(cycles=()).findings(PLANNED_WATER) == ["no cycles were recorded"]


class TestAverages:
    def test_the_average_mull(self) -> None:
        history = History(cycles=(cycle("B-1", dry=60, wet=120),))
        assert history.average_mull == Seconds(180)

    def test_an_empty_history_has_no_average(self) -> None:
        with pytest.raises(RuleError, match="no average"):
            assert History(cycles=()).average_mull

    def test_an_empty_history_has_no_share(self) -> None:
        with pytest.raises(RuleError, match="no share to take"):
            assert History(cycles=()).short_mull_share


class TestConstruction:
    def test_it_wants_recorded_cycles(self) -> None:
        bad: Any = ("B-1",)
        with pytest.raises(BadInputError, match="built from recorded cycles"):
            History(cycles=bad)

    def test_a_recorded_cycle_validates_only_its_own_pieces(self) -> None:
        bad: Any = 60
        with pytest.raises(BadInputError, match="needs a batch number"):
            cycle("  ")
        with pytest.raises(BadInputError, match="dry mull is a duration"):
            RecordedCycle(
                batch_id="B-1",
                dry_mull=bad,
                wet_mull=Seconds(120),
                bentonite=Pounds(140),
                water=Pounds(180),
            )
        with pytest.raises(BadInputError, match="water charged is a bulk mass"):
            RecordedCycle(
                batch_id="B-1",
                dry_mull=Seconds(60),
                wet_mull=Seconds(120),
                bentonite=Pounds(140),
                water=bad,
            )

    def test_it_records_a_schedule_the_plan_would_have_refused(self) -> None:
        """The whole point: Cycle refuses this, the log contains it."""
        short = cycle("B-1", dry=5, wet=5)
        assert short.mulled_short
        assert "short" in str(short)

    def test_two_cycles_cannot_share_a_batch_number(self) -> None:
        with pytest.raises(RuleError, match="share a batch number"):
            History(cycles=(cycle("B-1"), cycle("B-1")))

    def test_length_counts_every_cycle(self) -> None:
        assert len(History(cycles=(cycle("B-1"), cycle("B-2", mull=False)))) == 2
