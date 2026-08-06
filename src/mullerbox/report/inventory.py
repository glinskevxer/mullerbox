"""The inventory sheet, and the trend nobody plots.

One count answers "how much sand is in the system". A run of counts answers the
question the shop actually has, which is "where is it going". A jobbing foundry
loses sand to the collector, to the floor and to the castings it ships, and it
puts new sand back in at whatever rate the operator felt was right. The two
almost never match, and the mismatch shows up as a system that is quietly
shrinking or quietly growing over a year.

The sheet leads with the run rather than the latest figure for that reason. The
latest figure is already on the system record; what is not anywhere is the line
through the last four counts, and that line is the only thing that says whether
the new sand rate is right.

**A partial count is plotted and marked, not dropped.** Dropping it makes the
trend look tidier than the evidence, and a partial count is still a floor: the
system holds at least that much. Marking it lets the reader discount it without
the sheet having decided for them.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from mullerbox.errors import BadInputError
from mullerbox.report.layout import Column, Table, heading
from mullerbox.system.inventory import Count
from mullerbox.units.bulk import Pounds

# A run shorter than this is two points and a straight line through them.
SHORTEST_TREND = 3

# Pounds a year of drift below which the run is level rather than moving.
LEVEL_LIMIT = Decimal("2000")

_DAYS_PER_YEAR = Decimal("365")


@dataclass(frozen=True)
class Movement:
    """What changed between two counts."""

    before: Count
    after: Count

    def __post_init__(self) -> None:
        for count in (self.before, self.after):
            if not isinstance(count, Count):
                raise BadInputError("a movement is between two counts")
        if self.after.counted_on <= self.before.counted_on:
            raise BadInputError("a movement runs forward in time")

    @property
    def days(self) -> int:
        return (self.after.counted_on - self.before.counted_on).days

    @property
    def change(self) -> Decimal:
        """Signed pounds, because a system can grow as well as shrink."""
        return self.after.total.value - self.before.total.value

    @property
    def per_year(self) -> Decimal:
        """The change annualised, which is the number to compare against new sand."""
        return (self.change * _DAYS_PER_YEAR / Decimal(self.days)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )

    @property
    def is_trustworthy(self) -> bool:
        """Both ends complete, which is what a rate needs."""
        return self.before.is_complete and self.after.is_complete

    def __str__(self) -> str:
        direction = "gained" if self.change >= 0 else "lost"
        return (
            f"{self.before.counted_on} to {self.after.counted_on}: "
            f"{direction} {abs(self.change)} lb over {self.days} days"
        )


@dataclass(frozen=True)
class InventoryReport:
    """A system's counts, read as a run."""

    system_name: str
    counts: tuple[Count, ...]

    def __post_init__(self) -> None:
        if not self.system_name.strip():
            raise BadInputError("an inventory report is of a named system")
        for count in self.counts:
            if not isinstance(count, Count):
                raise BadInputError("an inventory report holds counts")
            if count.system_name != self.system_name:
                raise BadInputError(
                    f"a count of {count.system_name} is in the {self.system_name} report"
                )
        dates = [count.counted_on for count in self.counts]
        if dates != sorted(dates):
            raise BadInputError("the counts are not in date order")
        if len(set(dates)) != len(dates):
            raise BadInputError("two counts share a date")

    @property
    def latest(self) -> Count | None:
        return self.counts[-1] if self.counts else None

    @property
    def movements(self) -> tuple[Movement, ...]:
        return tuple(
            Movement(before=a, after=b) for a, b in zip(self.counts, self.counts[1:], strict=False)
        )

    @property
    def has_a_trend(self) -> bool:
        return len(self.counts) >= SHORTEST_TREND

    @property
    def drift_per_year(self) -> Decimal | None:
        """The whole run annualised, or nothing if there is not enough of it."""
        if not self.has_a_trend:
            return None
        return Movement(before=self.counts[0], after=self.counts[-1]).per_year

    @property
    def every_count_is_complete(self) -> bool:
        return all(count.is_complete for count in self.counts)

    def findings(self) -> list[str]:
        """What the run says, in the order a reader needs it."""
        if not self.counts:
            return [f"{self.system_name} has never been inventoried"]
        lines: list[str] = []
        drift = self.drift_per_year
        if drift is None:
            lines.append(f"{len(self.counts)} counts is not a trend; {SHORTEST_TREND} makes one")
        elif abs(drift) <= LEVEL_LIMIT:
            lines.append(f"the system is level at {abs(drift)} lb a year of movement")
        elif drift < 0:
            lines.append(
                f"the system is losing {abs(drift)} lb a year, which is sand going "
                "out that new sand is not replacing"
            )
        else:
            lines.append(
                f"the system is gaining {drift} lb a year, which is new sand going "
                "in faster than the system loses it"
            )
        if not self.every_count_is_complete:
            partial = sum(1 for c in self.counts if not c.is_complete)
            lines.append(
                f"{partial} of these counts did not reach every vessel, so the run "
                "is a floor and not a measurement"
            )
        return lines

    def table(self) -> Table:
        """One row per count, with the change from the one before it."""
        built = Table(
            columns=(
                Column("counted"),
                Column.number("total"),
                Column.number("change"),
                Column.number("floor share"),
                Column("state"),
            )
        )
        previous: Count | None = None
        for count in self.counts:
            change = ""
            if previous is not None:
                change = f"{Movement(before=previous, after=count).change:+}"
            built.add(
                str(count.counted_on),
                str(count.total),
                change,
                f"{count.floor_share:.1%}",
                "complete" if count.is_complete else "partial",
            )
            previous = count
        return built

    def render(self) -> list[str]:
        """The sheet, with the run read out above the table."""
        lines = heading(f"{self.system_name} inventory")
        lines.extend(self.findings())
        if not self.counts:
            return lines
        lines.append("")
        lines.extend(self.table().render())
        return lines

    def __str__(self) -> str:
        return "\n".join(self.render())


def inventory_report(system_name: str, counts: list[Count]) -> InventoryReport:
    """Build the inventory sheet from a system's counts, oldest first."""
    return InventoryReport(system_name=system_name, counts=tuple(counts))


def expected_new_sand(report: InventoryReport) -> Pounds | None:
    """New sand a year that would hold the system level, or nothing without a trend.

    Only the losing direction gets an answer. A system that is gaining does not
    need a new sand figure, it needs somebody to stop adding, and returning a
    zero here would read as "the calculation says none" rather than "this is not
    the question to ask".
    """
    drift = report.drift_per_year
    if drift is None or drift >= 0:
        return None
    return Pounds(abs(drift))


__all__ = [
    "InventoryReport",
    "LEVEL_LIMIT",
    "Movement",
    "SHORTEST_TREND",
    "expected_new_sand",
    "inventory_report",
]
