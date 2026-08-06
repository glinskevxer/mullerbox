from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from mullerbox.errors import BadInputError
from mullerbox.report.inventory import (
    LEVEL_LIMIT,
    InventoryReport,
    Movement,
    expected_new_sand,
    inventory_report,
)
from mullerbox.system.inventory import Count, Vessel
from mullerbox.units.bulk import Pounds

D = Decimal


def vessel(name: str = "silo", fill: str = "0.80", density: str | None = "95") -> Vessel:
    return Vessel(
        name=name,
        capacity_cubic_feet=D(1000),
        filled_fraction=D(fill),
        density_pounds_per_cubic_foot=None if density is None else D(density),
    )


def count(when: date, fill: str = "0.80", complete: bool = True, name: str = "two") -> Count:
    vessels: tuple[Vessel, ...] = (vessel(fill=fill),)
    if not complete:
        vessels = (*vessels, vessel(name="hopper", density=None))
    return Count(
        system_name=name,
        counted_on=when,
        vessels=vessels,
        moulds_standing=0,
        sand_per_mould=Pounds(300),
    )


JAN = date(2025, 1, 6)
JUL = date(2025, 7, 6)
JAN_NEXT = date(2026, 1, 5)


class TestAMovement:
    def test_it_measures_the_change(self) -> None:
        got = Movement(before=count(JAN, "0.80"), after=count(JUL, "0.70"))
        assert got.change == D("-9500.00")
        assert got.days == 181

    def test_a_growing_system_reads_positive(self) -> None:
        got = Movement(before=count(JAN, "0.70"), after=count(JUL, "0.80"))
        assert got.change > 0

    def test_it_annualises(self) -> None:
        got = Movement(before=count(JAN, "0.80"), after=count(JAN_NEXT, "0.70"))
        assert got.per_year == D("-9526")

    def test_a_partial_end_makes_it_untrustworthy(self) -> None:
        got = Movement(before=count(JAN), after=count(JUL, complete=False))
        assert not got.is_trustworthy

    def test_two_complete_ends_are_trustworthy(self) -> None:
        assert Movement(before=count(JAN), after=count(JUL)).is_trustworthy

    def test_it_runs_forward(self) -> None:
        with pytest.raises(BadInputError, match="runs forward in time"):
            Movement(before=count(JUL), after=count(JAN))

    def test_the_same_day_is_not_a_movement(self) -> None:
        with pytest.raises(BadInputError, match="runs forward in time"):
            Movement(before=count(JAN), after=count(JAN))

    def test_it_wants_counts(self) -> None:
        bad: Any = "a count"
        with pytest.raises(BadInputError, match="between two counts"):
            Movement(before=bad, after=count(JUL))

    def test_str_names_the_direction(self) -> None:
        got = Movement(before=count(JAN, "0.80"), after=count(JUL, "0.70"))
        assert "lost" in str(got)
        assert "over 181 days" in str(got)


class TestTheRun:
    def test_two_counts_is_not_a_trend(self) -> None:
        got = inventory_report("two", [count(JAN), count(JUL)])
        assert not got.has_a_trend
        assert got.drift_per_year is None
        assert "is not a trend" in got.findings()[0]

    def test_three_is(self) -> None:
        got = inventory_report(
            "two", [count(JAN, "0.80"), count(JUL, "0.75"), count(JAN_NEXT, "0.70")]
        )
        assert got.has_a_trend
        assert got.drift_per_year == D("-9526")

    def test_a_losing_system_is_named_as_losing(self) -> None:
        got = inventory_report(
            "two", [count(JAN, "0.80"), count(JUL, "0.75"), count(JAN_NEXT, "0.70")]
        )
        assert "losing" in got.findings()[0]

    def test_a_gaining_one_is_named_as_gaining(self) -> None:
        got = inventory_report(
            "two", [count(JAN, "0.70"), count(JUL, "0.75"), count(JAN_NEXT, "0.80")]
        )
        assert "gaining" in got.findings()[0]

    def test_a_level_one_says_level(self) -> None:
        got = inventory_report(
            "two", [count(JAN, "0.80"), count(JUL, "0.80"), count(JAN_NEXT, "0.80")]
        )
        assert "level" in got.findings()[0]
        assert abs(got.drift_per_year or D(1)) <= LEVEL_LIMIT

    def test_a_partial_count_is_plotted_and_marked(self) -> None:
        got = inventory_report("two", [count(JAN), count(JUL, complete=False), count(JAN_NEXT)])
        assert not got.every_count_is_complete
        assert any("did not reach every vessel" in line for line in got.findings())
        assert len(got.counts) == 3

    def test_a_system_never_counted(self) -> None:
        got = inventory_report("two", [])
        assert got.latest is None
        assert got.findings() == ["two has never been inventoried"]
        assert got.movements == ()

    def test_the_latest_is_the_last(self) -> None:
        got = inventory_report("two", [count(JAN), count(JUL)])
        assert got.latest is not None
        assert got.latest.counted_on == JUL


class TestReportShape:
    def test_counts_out_of_order_are_refused(self) -> None:
        with pytest.raises(BadInputError, match="not in date order"):
            inventory_report("two", [count(JUL), count(JAN)])

    def test_two_counts_on_one_day(self) -> None:
        with pytest.raises(BadInputError, match="share a date"):
            inventory_report("two", [count(JAN), count(JAN)])

    def test_a_count_of_another_system(self) -> None:
        with pytest.raises(BadInputError, match="is in the two report"):
            inventory_report("two", [count(JAN), count(JUL, name="one")])

    def test_it_needs_a_system_name(self) -> None:
        with pytest.raises(BadInputError, match="named system"):
            inventory_report("  ", [])

    def test_it_holds_counts(self) -> None:
        bad: Any = "a count"
        with pytest.raises(BadInputError, match="holds counts"):
            InventoryReport(system_name="two", counts=(bad,))


class TestTheSheet:
    def test_it_has_a_row_per_count(self) -> None:
        lines = inventory_report("two", [count(JAN), count(JUL)]).render()
        assert any(str(JAN) in line for line in lines)
        assert any(str(JUL) in line for line in lines)

    def test_the_first_row_has_no_change(self) -> None:
        table = inventory_report("two", [count(JAN), count(JUL, "0.70")]).table()
        rendered = table.render()
        assert "+" not in rendered[2]
        assert "-" in rendered[3]

    def test_an_empty_run_renders_the_finding_alone(self) -> None:
        lines = inventory_report("two", []).render()
        assert any("never been inventoried" in line for line in lines)
        assert not any("counted" in line for line in lines)

    def test_str_is_the_sheet(self) -> None:
        got = inventory_report("two", [count(JAN)])
        assert str(got) == "\n".join(got.render())


class TestTheNewSandAnswer:
    def test_a_losing_system_gets_a_figure(self) -> None:
        got = inventory_report(
            "two", [count(JAN, "0.80"), count(JUL, "0.75"), count(JAN_NEXT, "0.70")]
        )
        assert expected_new_sand(got) == Pounds(9526)

    def test_a_gaining_one_gets_nothing_rather_than_zero(self) -> None:
        got = inventory_report(
            "two", [count(JAN, "0.70"), count(JUL, "0.75"), count(JAN_NEXT, "0.80")]
        )
        assert expected_new_sand(got) is None

    def test_and_neither_does_a_run_too_short_to_read(self) -> None:
        assert expected_new_sand(inventory_report("two", [count(JAN)])) is None
