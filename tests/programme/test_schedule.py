from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from mullerbox.analysis.control import chart_of
from mullerbox.errors import BadInputError
from mullerbox.programme.schedule import (
    CLEAN_RUN_TO_RELAX,
    PINNED,
    Frequency,
    Schedule,
    adjusted,
)
from mullerbox.props.kind import PropertyKind

COMP = PropertyKind.COMPACTABILITY
LOI = PropertyKind.LOI
MB = PropertyKind.MB_CLAY
AS_OF = date(2025, 8, 25)


def schedule() -> Schedule:
    return Schedule(
        intervals={
            COMP: Frequency.EVERY_SHIFT,
            MB: Frequency.WEEKLY,
            LOI: Frequency.MONTHLY,
        }
    )


def steady(n: int = 25) -> list[Decimal]:
    return [Decimal("41.0") + (Decimal("0.1") if i % 2 else Decimal("-0.1")) for i in range(n)]


def wandering() -> list[Decimal]:
    return [Decimal("38") + Decimal("0.2") * i for i in range(25)]


class TestTheLadder:
    def test_it_runs_tightest_to_loosest(self) -> None:
        assert Frequency.EVERY_SHIFT.rank < Frequency.QUARTERLY.rank

    def test_stepping_tighter_and_looser(self) -> None:
        assert Frequency.WEEKLY.tighter() is Frequency.DAILY
        assert Frequency.WEEKLY.looser() is Frequency.MONTHLY

    def test_the_ends_hold(self) -> None:
        assert Frequency.EVERY_SHIFT.tighter() is Frequency.EVERY_SHIFT
        assert Frequency.QUARTERLY.looser() is Frequency.QUARTERLY

    def test_every_frequency_has_a_label_and_days(self) -> None:
        for frequency in Frequency:
            assert frequency.label
            assert frequency.days > 0


class TestWhatIsDue:
    def test_nothing_overdue_is_quiet(self) -> None:
        last = {COMP: AS_OF, MB: AS_OF, LOI: AS_OF}
        assert schedule().due_on(AS_OF, last) == ()

    def test_a_property_past_its_interval_is_due(self) -> None:
        last = {COMP: AS_OF, MB: date(2025, 8, 1), LOI: AS_OF}
        due = schedule().due_on(AS_OF, last)
        assert [d.kind for d in due] == [MB]

    def test_exactly_on_the_interval_is_due(self) -> None:
        last = {COMP: AS_OF, MB: date(2025, 8, 18), LOI: AS_OF}
        due = schedule().due_on(AS_OF, last)
        assert due[0].days_over == 0

    def test_a_day_short_is_not(self) -> None:
        last = {COMP: AS_OF, MB: date(2025, 8, 19), LOI: AS_OF}
        assert schedule().due_on(AS_OF, last) == ()

    def test_never_tested_sorts_to_the_top(self) -> None:
        due = schedule().due_on(AS_OF, {COMP: AS_OF})
        assert due[0].never_tested
        assert "never tested" in str(due[0])

    def test_the_most_overdue_comes_first(self) -> None:
        last = {COMP: date(2025, 8, 24), MB: date(2025, 7, 1), LOI: date(2025, 8, 1)}
        due = schedule().due_on(AS_OF, last)
        assert due[0].kind is MB

    def test_a_future_test_date_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="which is after"):
            schedule().due_on(AS_OF, {COMP: date(2025, 9, 1)})

    def test_it_wants_a_date(self) -> None:
        bad: Any = "2025-08-25"
        with pytest.raises(BadInputError, match="a date is expected"):
            schedule().due_on(bad, {})

    def test_str_names_the_interval(self) -> None:
        last = {COMP: AS_OF, MB: date(2025, 8, 1), LOI: AS_OF}
        assert "weekly interval" in str(schedule().due_on(AS_OF, last)[0])


class TestNextDue:
    def test_it_adds_the_interval(self) -> None:
        assert schedule().next_due(MB, date(2025, 8, 1)) == date(2025, 8, 8)

    def test_it_is_guarded(self) -> None:
        bad: Any = "2025-08-01"
        with pytest.raises(BadInputError, match="a date is expected"):
            schedule().next_due(MB, bad)
        with pytest.raises(BadInputError, match="is not on the programme"):
            schedule().next_due(PropertyKind.PERMEABILITY, date(2025, 8, 1))


class TestTheIntervalIsEarned:
    def test_a_wandering_property_tightens_at_once(self) -> None:
        moved = adjusted(schedule(), LOI, chart_of(wandering()))
        assert moved.frequency_of(LOI) is Frequency.EVERY_SHIFT

    def test_a_stable_property_relaxes_one_step(self) -> None:
        moved = adjusted(schedule(), LOI, chart_of(steady()))
        assert moved.frequency_of(LOI) is Frequency.QUARTERLY

    def test_relaxing_takes_a_long_enough_run(self) -> None:
        short = chart_of(steady(CLEAN_RUN_TO_RELAX - 1))
        assert adjusted(schedule(), LOI, short).frequency_of(LOI) is Frequency.MONTHLY

    def test_tightening_does_not_wait_for_a_long_run(self) -> None:
        short = chart_of(wandering()[:16])
        moved = adjusted(schedule(), LOI, short)
        assert moved.frequency_of(LOI) is Frequency.EVERY_SHIFT

    def test_a_pinned_property_never_relaxes(self) -> None:
        moved = adjusted(schedule(), COMP, chart_of(steady()))
        assert moved.frequency_of(COMP) is Frequency.EVERY_SHIFT

    def test_a_pinned_property_is_not_tightened_either(self) -> None:
        moved = adjusted(schedule(), COMP, chart_of(wandering()))
        assert moved.frequency_of(COMP) is Frequency.EVERY_SHIFT

    def test_the_pinned_set_is_the_cheap_fast_pair(self) -> None:
        assert {COMP, PropertyKind.MOISTURE} == PINNED

    def test_the_original_schedule_is_untouched(self) -> None:
        original = schedule()
        adjusted(original, LOI, chart_of(wandering()))
        assert original.frequency_of(LOI) is Frequency.MONTHLY

    def test_it_is_guarded(self) -> None:
        bad: Any = "monthly"
        with pytest.raises(BadInputError, match="a schedule is expected"):
            adjusted(bad, LOI, chart_of(steady()))
        with pytest.raises(BadInputError, match="control chart is expected"):
            adjusted(schedule(), LOI, bad)


class TestConstruction:
    def test_an_empty_schedule_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="not a schedule"):
            Schedule(intervals={})

    def test_it_is_keyed_by_property_and_holds_frequencies(self) -> None:
        bad_key: Any = {"comp": Frequency.DAILY}
        with pytest.raises(BadInputError, match="keyed by property"):
            Schedule(intervals=bad_key)
        bad_value: Any = {COMP: "daily"}
        with pytest.raises(BadInputError, match="holds frequencies"):
            Schedule(intervals=bad_value)

    def test_lookup_is_guarded(self) -> None:
        bad: Any = "comp"
        with pytest.raises(BadInputError, match="property kind is expected"):
            schedule().frequency_of(bad)

    def test_setting_a_frequency_is_guarded(self) -> None:
        bad: Any = "daily"
        with pytest.raises(BadInputError, match="a frequency is expected"):
            schedule().with_frequency(COMP, bad)
        with pytest.raises(BadInputError, match="property kind is expected"):
            schedule().with_frequency(bad, Frequency.DAILY)

    def test_covers(self) -> None:
        assert schedule().covers == {COMP, MB, LOI}
