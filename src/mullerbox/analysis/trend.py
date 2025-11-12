"""Whether a property is going somewhere, and how long before it gets there.

A control chart says a run is not random. It does not say which way it is
heading or when it will leave the band, and those are the two things the lab
actually wants: "moisture is drifting up" is interesting, and "moisture reaches
the top of the band in nine shifts" is actionable.

So this fits a straight line by least squares and projects it forward to the
band. Three things about that are deliberate.

**The slope is per reading, not per day.** Sand readings are taken on a schedule
and the schedule changes; a slope per day computed over a run whose interval
changed halfway is measuring the schedule. Per reading is what the run actually
contains.

**A projection is refused when the slope is flat.** Dividing the distance to the
band by a slope near zero produces an enormous and meaningless number of shifts,
and reporting "reaches the band in 4,000 shifts" invites the reader to treat it
as a real estimate. Below the threshold the answer is that it is not going
anywhere.

**A projection is not a prediction and is named as one.** It says where the line
would reach the band if nothing changed, and something always changes. It is
useful for ordering the properties by urgency, which is what the lab uses it
for, and not for booking a date.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

from mullerbox.analysis.control import MIN_POINTS
from mullerbox.errors import BadInputError, RuleError
from mullerbox.props.kind import PropertyKind
from mullerbox.spec.band import Band

# A slope under this many units per reading is not going anywhere.
FLAT_SLOPE = Decimal("0.001")

PLACES = Decimal("0.000001")


class Direction(Enum):
    """Which way a run is heading."""

    RISING = "rising"
    FALLING = "falling"
    FLAT = "flat"

    @property
    def label(self) -> str:
        return self.value


@dataclass(frozen=True)
class Trend:
    """A least squares line through a run, and where it is going."""

    kind: PropertyKind
    slope: Decimal
    intercept: Decimal
    readings: int
    direction: Direction

    @property
    def is_moving(self) -> bool:
        return self.direction is not Direction.FLAT

    def at(self, reading_number: int) -> Decimal:
        """Where the line sits at a given point in the run."""
        if not isinstance(reading_number, int) or isinstance(reading_number, bool):
            raise BadInputError("a reading number is a whole number")
        return (self.intercept + self.slope * reading_number).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )

    @property
    def latest(self) -> Decimal:
        return self.at(self.readings - 1)

    def readings_to(self, limit: Decimal) -> int | None:
        """How many more readings before the line reaches a value.

        None when it is not heading there: either the slope is flat, or the
        limit is behind the direction of travel.
        """
        if not isinstance(limit, Decimal):
            raise BadInputError("a limit is a decimal")
        if not self.is_moving:
            return None
        gap = limit - self.latest
        if gap == 0:
            return 0
        if (gap > 0) != (self.slope > 0):
            return None
        return int((gap / self.slope).to_integral_value(rounding=ROUND_HALF_UP))

    def __str__(self) -> str:
        if not self.is_moving:
            return f"{self.kind.label} is flat"
        return f"{self.kind.label} is {self.direction.label} {abs(self.slope)} per reading"


def trend_of(kind: PropertyKind, readings: list[Decimal]) -> Trend:
    """Fit a least squares line through a run of readings."""
    if not isinstance(kind, PropertyKind):
        raise BadInputError("a property kind is expected")
    if not isinstance(readings, list):
        raise BadInputError("a run of readings is expected")
    for reading in readings:
        if not isinstance(reading, Decimal):
            raise BadInputError("a trend is fitted to decimals")
    if len(readings) < MIN_POINTS:
        raise RuleError(
            f"{len(readings)} readings will not carry a trend, {MIN_POINTS} is the floor"
        )
    count = Decimal(len(readings))
    xs = [Decimal(i) for i in range(len(readings))]
    mean_x = sum(xs, Decimal(0)) / count
    mean_y = sum(readings, Decimal(0)) / count
    top = sum(((x - mean_x) * (y - mean_y) for x, y in zip(xs, readings, strict=True)), Decimal(0))
    bottom = sum(((x - mean_x) ** 2 for x in xs), Decimal(0))
    if bottom == 0:
        raise RuleError("a run of one point has no trend")
    slope = (top / bottom).quantize(PLACES, rounding=ROUND_HALF_UP)
    intercept = (mean_y - slope * mean_x).quantize(PLACES, rounding=ROUND_HALF_UP)
    if abs(slope) < FLAT_SLOPE:
        direction = Direction.FLAT
    elif slope > 0:
        direction = Direction.RISING
    else:
        direction = Direction.FALLING
    return Trend(
        kind=kind,
        slope=slope,
        intercept=intercept,
        readings=len(readings),
        direction=direction,
    )


@dataclass(frozen=True)
class Projection:
    """Where a trend meets its band, if nothing changes."""

    trend: Trend
    band: Band
    readings_to_limit: int | None
    limit_reached: str

    @property
    def is_heading_out(self) -> bool:
        return self.readings_to_limit is not None

    def __str__(self) -> str:
        if not self.is_heading_out:
            return f"{self.trend} and is not heading out of band"
        return (
            f"{self.trend}, reaching the {self.limit_reached} limit in about "
            f"{self.readings_to_limit} readings if nothing changes"
        )


def project(trend: Trend, band: Band) -> Projection:
    """Work out which limit a trend is heading for and how far away it is."""
    if not isinstance(trend, Trend):
        raise BadInputError("a trend is expected")
    if not isinstance(band, Band):
        raise BadInputError("a band is expected")
    if band.kind is not trend.kind:
        raise BadInputError(
            f"a {trend.kind.label} trend cannot be projected onto a {band.kind.label} band"
        )
    from mullerbox.spec.band import _scalar

    if trend.direction is Direction.RISING and band.high is not None:
        return Projection(
            trend=trend,
            band=band,
            readings_to_limit=trend.readings_to(_scalar(band.high)),
            limit_reached="upper",
        )
    if trend.direction is Direction.FALLING and band.low is not None:
        return Projection(
            trend=trend,
            band=band,
            readings_to_limit=trend.readings_to(_scalar(band.low)),
            limit_reached="lower",
        )
    return Projection(trend=trend, band=band, readings_to_limit=None, limit_reached="none")


__all__ = [
    "Direction",
    "FLAT_SLOPE",
    "PLACES",
    "Projection",
    "Trend",
    "project",
    "trend_of",
]
