from __future__ import annotations

from typing import Any

import pytest

from mullerbox.errors import BadInputError
from mullerbox.programme.coverage import coverage_of
from mullerbox.programme.schedule import Frequency, Schedule
from mullerbox.props.kind import PropertyKind
from mullerbox.spec.pattern import PatternClass
from tests.spec.helpers import sheet

LIGHT = PatternClass.LIGHT_JOBBING
THIN = PatternClass.THIN_WALL
CORE_FOUR = [
    PropertyKind.COMPACTABILITY,
    PropertyKind.GREEN_COMPRESSION,
    PropertyKind.MOISTURE,
    PropertyKind.MB_CLAY,
]


def schedule(*kinds: PropertyKind) -> Schedule:
    return Schedule(intervals=dict.fromkeys(kinds or CORE_FOUR, Frequency.DAILY))


class TestFullCoverage:
    def test_a_programme_covering_the_class_is_complete(self) -> None:
        covering = schedule(*LIGHT.controlled)
        found = coverage_of(covering, sheet(), [LIGHT])
        assert found.is_complete
        assert "covers every property" in found.findings()[0]

    def test_it_names_how_many_classes_it_checked(self) -> None:
        covering = schedule(*LIGHT.controlled)
        found = coverage_of(covering, sheet(), [LIGHT])
        assert "1 classes" in found.findings()[0]


class TestControlledAndNeverScheduled:
    def test_the_gap_is_named(self) -> None:
        found = coverage_of(schedule(), sheet(), [LIGHT])
        assert PropertyKind.PERMEABILITY in found.unscheduled
        assert not found.is_complete

    def test_the_finding_says_the_report_looks_tidy(self) -> None:
        found = coverage_of(schedule(), sheet(), [LIGHT])
        assert any("looks tidy" in x for x in found.findings())

    def test_adding_a_class_widens_the_gap(self) -> None:
        one = coverage_of(schedule(), sheet(), [LIGHT])
        two = coverage_of(schedule(), sheet(), [LIGHT, THIN])
        assert len(two.unscheduled) > len(one.unscheduled)


class TestScheduledAndNeverUsed:
    def test_bench_time_on_an_unjudged_property_is_named(self) -> None:
        covering = schedule(*LIGHT.controlled, PropertyKind.SHATTER_INDEX)
        found = coverage_of(covering, sheet(), [LIGHT])
        assert found.unused == (PropertyKind.SHATTER_INDEX,)

    def test_it_does_not_make_the_coverage_incomplete(self) -> None:
        covering = schedule(*LIGHT.controlled, PropertyKind.SHATTER_INDEX)
        found = coverage_of(covering, sheet(), [LIGHT])
        assert found.is_complete

    def test_the_finding_says_bench_time_is_the_constraint(self) -> None:
        covering = schedule(*LIGHT.controlled, PropertyKind.SHATTER_INDEX)
        found = coverage_of(covering, sheet(), [LIGHT])
        assert any("bench time is the constraint" in x for x in found.findings())


class TestControlledAndNotPublished:
    def test_a_property_with_no_band_is_never_judged(self) -> None:
        from mullerbox.spec.sheet import SpecSheet
        from tests.spec.helpers import PUBLISHED

        thin_sheet = SpecSheet(
            name="thin",
            bands={PropertyKind.COMPACTABILITY: PUBLISHED[PropertyKind.COMPACTABILITY]},
        )
        found = coverage_of(schedule(*LIGHT.controlled), thin_sheet, [LIGHT])
        assert PropertyKind.PERMEABILITY in found.unbanded
        assert not found.is_complete

    def test_it_is_reported_before_the_scheduling_gap(self) -> None:
        from mullerbox.spec.sheet import SpecSheet
        from tests.spec.helpers import PUBLISHED

        thin_sheet = SpecSheet(
            name="thin",
            bands={PropertyKind.COMPACTABILITY: PUBLISHED[PropertyKind.COMPACTABILITY]},
        )
        findings = coverage_of(schedule(), thin_sheet, [LIGHT]).findings()
        assert "never judged at all" in findings[0]


class TestGuards:
    def test_it_wants_a_schedule_and_a_sheet(self) -> None:
        bad: Any = "daily"
        with pytest.raises(BadInputError, match="a schedule is expected"):
            coverage_of(bad, sheet(), [LIGHT])
        with pytest.raises(BadInputError, match="spec sheet is expected"):
            coverage_of(schedule(), bad, [LIGHT])

    def test_it_wants_classes(self) -> None:
        with pytest.raises(BadInputError, match="no pattern classes"):
            coverage_of(schedule(), sheet(), [])
        bad: Any = ["light"]
        with pytest.raises(BadInputError, match="only pattern classes"):
            coverage_of(schedule(), sheet(), bad)

    def test_a_shop_that_never_runs_cored_work_is_not_told_about_friability(
        self,
    ) -> None:
        found = coverage_of(schedule(*LIGHT.controlled), sheet(), [LIGHT])
        assert PropertyKind.FRIABILITY not in found.unscheduled
