from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from mullerbox.analysis.control import MIN_POINTS
from mullerbox.analysis.summary import State, summarise, worst_first
from mullerbox.errors import BadInputError
from mullerbox.props.kind import PropertyKind
from mullerbox.spec.band import Band
from mullerbox.units.percent import Percent

COMP = PropertyKind.COMPACTABILITY
MOISTURE = PropertyKind.MOISTURE
BAND = Band.between(COMP, Percent(38), Percent(44))


def steady(centre: str = "41", step: str = "0.1", n: int = 25) -> list[Decimal]:
    mid, jump = Decimal(centre), Decimal(step)
    return [mid + (jump if i % 2 else -jump) for i in range(n)]


def drifting(start: str = "40", step: str = "0.05", n: int = 25) -> list[Decimal]:
    return [Decimal(start) + Decimal(step) * i for i in range(n)]


class TestTheFourStates:
    def test_stable_and_capable_is_settled(self) -> None:
        got = summarise(COMP, BAND, steady())
        assert got.state is State.SETTLED
        assert not got.state.needs_action
        assert got.state.action == "leave it alone"

    def test_stable_and_out_of_band_is_consistently_wrong(self) -> None:
        got = summarise(COMP, BAND, steady(centre="50"))
        assert got.state is State.CONSISTENTLY_WRONG
        assert "move the recipe" in got.state.action

    def test_drifting_inside_the_band_is_the_cheap_one_to_act_on(self) -> None:
        got = summarise(COMP, BAND, drifting())
        assert got.state is State.DRIFTING
        assert "still cheap" in got.state.action

    def test_out_of_control_and_out_of_band_says_stop(self) -> None:
        wild = [Decimal("30") + Decimal("1.5") * i for i in range(25)]
        got = summarise(COMP, BAND, wild)
        assert got.state is State.ADRIFT
        assert "stop and find out why" in got.state.action

    def test_every_state_has_a_label_and_an_action(self) -> None:
        for state in State:
            assert state.label
            assert state.action


class TestNeitherChartAloneWouldSayIt:
    def test_the_spec_check_alone_would_pass_a_drifting_property(self) -> None:
        got = summarise(COMP, BAND, drifting())
        assert got.capability is not None
        assert got.capability.is_capable
        assert got.state is State.DRIFTING

    def test_the_control_chart_alone_would_pass_a_wrong_one(self) -> None:
        got = summarise(COMP, BAND, steady(centre="50"))
        assert got.chart is not None
        assert got.chart.in_control
        assert got.state is State.CONSISTENTLY_WRONG


class TestTooLittleHistory:
    def test_it_gets_no_state(self) -> None:
        got = summarise(COMP, BAND, steady(n=MIN_POINTS - 1))
        assert got.state is State.TOO_LITTLE_HISTORY
        assert got.chart is None
        assert got.capability is None
        assert got.projection is None

    def test_it_says_to_run_more_tests(self) -> None:
        got = summarise(COMP, BAND, steady(n=3))
        assert "run more tests" in got.state.action
        assert "3 readings" in str(got)

    def test_exactly_the_floor_gets_a_state(self) -> None:
        got = summarise(COMP, BAND, steady(n=MIN_POINTS))
        assert got.state is not State.TOO_LITTLE_HISTORY


class TestTheProjection:
    def test_a_drifting_property_reports_how_far_it_has_to_go(self) -> None:
        got = summarise(COMP, BAND, drifting())
        assert got.readings_to_band is not None
        assert "reaching the band in about" in str(got)

    def test_a_settled_one_does_not(self) -> None:
        got = summarise(COMP, BAND, steady())
        assert got.readings_to_band is None
        assert "reaching the band" not in str(got)

    def test_the_trend_is_reachable(self) -> None:
        got = summarise(COMP, BAND, drifting())
        assert got.trend is not None
        assert got.trend.is_moving

    def test_a_summary_without_history_has_no_trend(self) -> None:
        assert summarise(COMP, BAND, steady(n=3)).trend is None


class TestRanking:
    def test_the_worst_state_comes_first(self) -> None:
        wild = [Decimal("30") + Decimal("1.5") * i for i in range(25)]
        ranked = worst_first(
            [
                summarise(COMP, BAND, steady()),
                summarise(COMP, BAND, wild),
                summarise(COMP, BAND, drifting()),
            ]
        )
        assert [s.state for s in ranked] == [
            State.ADRIFT,
            State.DRIFTING,
            State.SETTLED,
        ]

    def test_settled_properties_sort_last(self) -> None:
        ranked = worst_first([summarise(COMP, BAND, steady()), summarise(COMP, BAND, drifting())])
        assert ranked[-1].state is State.SETTLED

    def test_the_soonest_to_leave_the_band_comes_first_inside_a_state(self) -> None:
        slow = summarise(COMP, BAND, drifting(step="0.02"))
        fast = summarise(COMP, BAND, drifting(start="42", step="0.05"))
        ranked = worst_first([slow, fast])
        assert ranked[0] is fast

    def test_nothing_to_rank(self) -> None:
        assert worst_first([]) == []

    def test_it_wants_summaries(self) -> None:
        bad: Any = ["comp"]
        with pytest.raises(BadInputError, match="only summaries"):
            worst_first(bad)


class TestGuards:
    def test_the_band_has_to_be_for_the_property(self) -> None:
        with pytest.raises(BadInputError, match="cannot be summarised against"):
            summarise(MOISTURE, BAND, steady())

    def test_the_types_are_checked(self) -> None:
        bad: Any = "comp"
        with pytest.raises(BadInputError, match="property kind is expected"):
            summarise(bad, BAND, steady())
        with pytest.raises(BadInputError, match="a band is expected"):
            summarise(COMP, bad, steady())
        with pytest.raises(BadInputError, match="run of readings is expected"):
            summarise(COMP, BAND, bad)
