"""Control, capability and trend for one property, read together.

Each of the three answers a different question and none of them is enough alone.
Read together they place a property in one of a small number of states, and the
state is what decides what to do:

- **stable and capable**: leave it alone.
- **stable and not capable**: the process is consistent and consistently wrong.
  Adjusting the muller will not help; the recipe or the band has to move.
- **drifting but still in band**: nothing is scrap yet and something is
  changing. This is the state worth acting on, because it is the only one where
  acting is cheap.
- **out of control and out of band**: stop and find out why.

The value of naming the states is that the wrong action for each is the obvious
one for another. A drifting property looks fine on a spec check and a stable
out-of-band property looks fine on a control chart, and a shop that reads only
one of the two charts takes the wrong action about half the time.

**A property with too little history gets no state at all**, rather than a
provisional one. Fifteen readings is already a low bar and a state assigned
below it would be read as a finding.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from mullerbox.analysis.capability import Capability, capability_of
from mullerbox.analysis.control import MIN_POINTS, ControlChart, chart_of
from mullerbox.analysis.trend import Projection, Trend, project, trend_of
from mullerbox.errors import BadInputError
from mullerbox.props.kind import PropertyKind
from mullerbox.spec.band import Band


class State(Enum):
    """Where a property stands, from all three readings together."""

    SETTLED = "stable and capable"
    CONSISTENTLY_WRONG = "stable and not capable"
    DRIFTING = "drifting but still in band"
    ADRIFT = "out of control and out of band"
    TOO_LITTLE_HISTORY = "not enough history"

    @property
    def label(self) -> str:
        return self.value

    @property
    def needs_action(self) -> bool:
        return self in {
            State.CONSISTENTLY_WRONG,
            State.DRIFTING,
            State.ADRIFT,
        }

    @property
    def action(self) -> str:
        """What to do about a property in this state."""
        return _ACTION[self]


_ACTION: dict[State, str] = {
    State.SETTLED: "leave it alone",
    State.CONSISTENTLY_WRONG: ("the muller will not fix this; move the recipe or move the band"),
    State.DRIFTING: "act now, while it is still cheap",
    State.ADRIFT: "stop and find out why before adjusting anything",
    State.TOO_LITTLE_HISTORY: "run more tests before reading anything into it",
}


@dataclass(frozen=True)
class Summary:
    """One property's three readings and the state they add up to."""

    kind: PropertyKind
    readings: int
    chart: ControlChart | None
    capability: Capability | None
    projection: Projection | None
    state: State

    @property
    def trend(self) -> Trend | None:
        return None if self.projection is None else self.projection.trend

    @property
    def readings_to_band(self) -> int | None:
        if self.projection is None:
            return None
        return self.projection.readings_to_limit

    def __str__(self) -> str:
        if self.state is State.TOO_LITTLE_HISTORY:
            return f"{self.kind.label}: {self.readings} readings, {self.state.label}"
        line = f"{self.kind.label}: {self.state.label}"
        due = self.readings_to_band
        if due is not None:
            line += f", reaching the band in about {due} readings"
        return line


def summarise(kind: PropertyKind, band: Band, readings: list[Decimal]) -> Summary:
    """Read a property three ways and say which state it is in."""
    if not isinstance(kind, PropertyKind):
        raise BadInputError("a property kind is expected")
    if not isinstance(band, Band):
        raise BadInputError("a band is expected")
    if band.kind is not kind:
        raise BadInputError(
            f"a {kind.label} run cannot be summarised against a {band.kind.label} band"
        )
    if not isinstance(readings, list):
        raise BadInputError("a run of readings is expected")
    if len(readings) < MIN_POINTS:
        return Summary(
            kind=kind,
            readings=len(readings),
            chart=None,
            capability=None,
            projection=None,
            state=State.TOO_LITTLE_HISTORY,
        )
    chart = chart_of(readings)
    capability = capability_of(kind, band, readings)
    projection = project(trend_of(kind, readings), band)
    if chart.in_control:
        state = State.SETTLED if capability.is_capable else State.CONSISTENTLY_WRONG
    elif capability.is_capable:
        state = State.DRIFTING
    else:
        state = State.ADRIFT
    return Summary(
        kind=kind,
        readings=len(readings),
        chart=chart,
        capability=capability,
        projection=projection,
        state=state,
    )


def worst_first(summaries: list[Summary]) -> list[Summary]:
    """Rank by what needs doing, soonest first inside each state.

    Ordered by state rather than by any single number, because the states are
    not comparable on one axis: a property heading out of band in three
    readings and one that is already out are different problems and a numeric
    ranking would interleave them.
    """
    order = {
        State.ADRIFT: 0,
        State.CONSISTENTLY_WRONG: 1,
        State.DRIFTING: 2,
        State.TOO_LITTLE_HISTORY: 3,
        State.SETTLED: 4,
    }
    for summary in summaries:
        if not isinstance(summary, Summary):
            raise BadInputError("only summaries can be ranked")
    return sorted(
        summaries,
        key=lambda s: (
            order[s.state],
            s.readings_to_band if s.readings_to_band is not None else 10**6,
            s.kind.name,
        ),
    )


__all__ = ["State", "Summary", "summarise", "worst_first"]
