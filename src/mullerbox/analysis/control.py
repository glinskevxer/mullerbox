"""Control limits for a sand property, on an individuals and moving range chart.

A sand lab takes one specimen per shift per property. There is no rational
subgroup, so the X bar and R chart everybody learns does not apply and the
individuals chart is what is left.

**Limits come from the moving range, never from the standard deviation.** This
is the part that gets done wrong. The standard deviation of a run of shift
readings includes the drift between shifts, so limits built from it are wide
enough to contain the drift and will therefore never signal it. The moving range
sees only the shift to shift jump, which is the process's own noise, and limits
built from it flag the drift the standard deviation swallowed. On a sand system,
where slow drift is the failure mode and sudden jumps are rare, using the wrong
one produces a chart that has never signalled anything and is trusted because of
it.

**The constants are for a moving range of two.** 2.66 turns an average moving
range into three sigma on the individuals chart, and 3.267 is the upper limit on
the range chart itself. They are not adjustable here; a chart built on a
different subgroup size is a different chart and should say so.

**Limits are not the specification.** A process can be perfectly in control and
entirely outside the spec band, which means it is consistently making the wrong
sand. Both readings are needed and neither substitutes for the other, so nothing
in this module knows about bands.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

from mullerbox.errors import BadInputError, RuleError

# Moving range of two. E2 for the individuals chart, D4 for the range chart.
E2 = Decimal("2.66")
D4 = Decimal("3.267")

# Fewer than this and the limits are noise. Twenty is the usual advice and
# fifteen is the floor below which the chart should not be drawn at all.
MIN_POINTS = 15

PLACES = Decimal("0.0001")


class Signal(Enum):
    """Why a point was flagged."""

    BEYOND_LIMITS = "beyond the control limits"
    RUN_OF_EIGHT = "eighth of a run on one side of the centre"
    TREND_OF_SIX = "sixth of a rising or falling run"

    @property
    def label(self) -> str:
        return self.value


@dataclass(frozen=True)
class Flag:
    """One point the chart has something to say about."""

    index: int
    value: Decimal
    signal: Signal

    def __str__(self) -> str:
        return f"point {self.index} at {self.value}: {self.signal.label}"


@dataclass(frozen=True)
class ControlChart:
    """Limits for one property, and what the run of readings did against them."""

    values: tuple[Decimal, ...]
    centre: Decimal
    average_moving_range: Decimal
    upper: Decimal
    lower: Decimal
    range_upper: Decimal
    flags: tuple[Flag, ...]

    @property
    def in_control(self) -> bool:
        return not self.flags

    @property
    def moving_ranges(self) -> tuple[Decimal, ...]:
        return tuple(abs(self.values[i] - self.values[i - 1]) for i in range(1, len(self.values)))

    @property
    def spread(self) -> Decimal:
        """The distance between the limits, which is six sigma by construction."""
        return self.upper - self.lower

    def flags_of(self, signal: Signal) -> tuple[Flag, ...]:
        if not isinstance(signal, Signal):
            raise BadInputError("a signal is expected")
        return tuple(f for f in self.flags if f.signal is signal)

    def __str__(self) -> str:
        state = "in control" if self.in_control else f"{len(self.flags)} signals"
        return f"centre {self.centre}, limits {self.lower} to {self.upper}, {state}"


def _mean(values: list[Decimal]) -> Decimal:
    return (sum(values, Decimal(0)) / len(values)).quantize(PLACES, rounding=ROUND_HALF_UP)


def _runs_on_one_side(values: tuple[Decimal, ...], centre: Decimal) -> list[Flag]:
    """Eight in a row on one side of the centre line."""
    found: list[Flag] = []
    run = 0
    above = True
    for index, value in enumerate(values):
        if value == centre:
            run = 0
            continue
        side = value > centre
        run = run + 1 if (run and side == above) else 1
        above = side
        if run >= 8:
            found.append(Flag(index=index, value=value, signal=Signal.RUN_OF_EIGHT))
    return found


def _trends(values: tuple[Decimal, ...]) -> list[Flag]:
    """Six in a row rising or six in a row falling."""
    found: list[Flag] = []
    rising = 1
    falling = 1
    for index in range(1, len(values)):
        if values[index] > values[index - 1]:
            rising += 1
            falling = 1
        elif values[index] < values[index - 1]:
            falling += 1
            rising = 1
        else:
            rising = falling = 1
        if rising >= 6 or falling >= 6:
            found.append(Flag(index=index, value=values[index], signal=Signal.TREND_OF_SIX))
    return found


def chart_of(readings: list[Decimal]) -> ControlChart:
    """Build an individuals and moving range chart from a run of readings.

    The readings are bare Decimals rather than typed quantities. A chart is
    arithmetic on a sequence and works the same on a compactability, a
    permeability and a cost per ton, and giving it a quantity type would mean
    one chart per scale for no gain.
    """
    if not isinstance(readings, list):
        raise BadInputError("a chart is built from a list of readings")
    for reading in readings:
        if not isinstance(reading, Decimal):
            raise BadInputError("a chart is built from decimals")
    if len(readings) < MIN_POINTS:
        raise RuleError(
            f"{len(readings)} readings will not carry control limits, {MIN_POINTS} is the floor"
        )
    values = tuple(readings)
    centre = _mean(list(values))
    ranges = [abs(values[i] - values[i - 1]) for i in range(1, len(values))]
    average_range = _mean(ranges)
    half = (E2 * average_range).quantize(PLACES, rounding=ROUND_HALF_UP)
    upper = centre + half
    lower = centre - half
    flags: list[Flag] = [
        Flag(index=index, value=value, signal=Signal.BEYOND_LIMITS)
        for index, value in enumerate(values)
        if value > upper or value < lower
    ]
    flags.extend(_runs_on_one_side(values, centre))
    flags.extend(_trends(values))
    flags.sort(key=lambda f: (f.index, f.signal.name))
    return ControlChart(
        values=values,
        centre=centre,
        average_moving_range=average_range,
        upper=upper,
        lower=lower,
        range_upper=(D4 * average_range).quantize(PLACES, rounding=ROUND_HALF_UP),
        flags=tuple(flags),
    )


__all__ = [
    "ControlChart",
    "D4",
    "E2",
    "Flag",
    "MIN_POINTS",
    "PLACES",
    "Signal",
    "chart_of",
]
