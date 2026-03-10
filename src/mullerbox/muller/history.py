"""What the muller actually did, as opposed to what was planned for it.

``Cycle`` is a plan. It refuses a schedule that will not develop the bond, which
is right at the point of planning and makes it the wrong type to read history
off: a run of ``Cycle`` objects cannot contain a short mull, because the type
would not have let one be built. Counting short mulls across them would be
counting something that cannot occur.

What the machine's own log contains is different. It records the times the
muller ran for, including the ones an operator overrode, and those are exactly
the cycles worth counting. So history works on a ``RecordedCycle``, which
validates nothing about the schedule and only says what happened. It is the same
split the costing module makes between the additions that were planned and the
ones that went in, and for the same reason: the plan and the event disagree, and
the disagreement is the finding.

Three things are worth counting across a run.

**Short mulls.** An operator behind on the line shortens the mull, and it is the
first thing to go. One short mull is a bad minute; a fifth of them short is a
line being run faster than the muller can supply.

**Water-heavy cycles.** A muller that is not developing bond makes sand that
reads dry, so the operator adds water. A rising share of cycles over the planned
water is a bond development problem wearing a moisture problem's mask.

**Cycles charged and never discharged.** A batch left in the muller is a real
event with a real cost, and it only shows up in a count.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from mullerbox.errors import BadInputError, RuleError
from mullerbox.muller.cycle import MIN_DRY_MULL, MIN_WET_MULL
from mullerbox.units.bulk import Pounds
from mullerbox.units.duration import Seconds

SHORT_MULL_SHARE = Decimal("0.20")
HEAVY_WATER = Decimal("1.25")
_PLACES = Decimal("0.0001")


@dataclass(frozen=True)
class RecordedCycle:
    """What the muller's log says one batch actually did.

    Deliberately unvalidated about the schedule. A recorded cycle with a ten
    second wet mull is not an error to refuse, it is the observation the whole
    module exists to count.
    """

    batch_id: str
    dry_mull: Seconds
    wet_mull: Seconds
    bentonite: Pounds
    water: Pounds
    discharged: bool = True

    def __post_init__(self) -> None:
        if not self.batch_id.strip():
            raise BadInputError("a recorded cycle needs a batch number")
        for name in ("dry_mull", "wet_mull"):
            if not isinstance(getattr(self, name), Seconds):
                raise BadInputError(f"the {name.replace('_', ' ')} is a duration")
        for name in ("bentonite", "water"):
            if not isinstance(getattr(self, name), Pounds):
                raise BadInputError(f"the {name} charged is a bulk mass")

    @property
    def took_bentonite(self) -> bool:
        return not self.bentonite.is_zero

    @property
    def took_water(self) -> bool:
        return not self.water.is_zero

    @property
    def mulled_short(self) -> bool:
        """Whether the machine ran under the schedule for what it was charged with."""
        if self.took_bentonite and self.dry_mull < MIN_DRY_MULL:
            return True
        return self.took_water and self.wet_mull < MIN_WET_MULL

    @property
    def total_mull(self) -> Seconds:
        return self.dry_mull + self.wet_mull

    def __str__(self) -> str:
        state = "short" if self.mulled_short else "to schedule"
        return f"{self.batch_id}: {self.total_mull} {state}"


@dataclass(frozen=True)
class History:
    """A run of recorded cycles read as a set rather than one at a time."""

    cycles: tuple[RecordedCycle, ...]

    def __post_init__(self) -> None:
        for cycle in self.cycles:
            if not isinstance(cycle, RecordedCycle):
                raise BadInputError("a history is built from recorded cycles")
        ids = [c.batch_id for c in self.cycles]
        if len(set(ids)) != len(ids):
            raise RuleError("two cycles share a batch number")

    def __len__(self) -> int:
        return len(self.cycles)

    @property
    def abandoned(self) -> tuple[RecordedCycle, ...]:
        """Charged and never discharged, which is a batch left in the machine."""
        return tuple(c for c in self.cycles if not c.discharged)

    @property
    def short_mulls(self) -> tuple[RecordedCycle, ...]:
        return tuple(c for c in self.cycles if c.mulled_short)

    def water_heavy(self, planned: Pounds) -> tuple[RecordedCycle, ...]:
        """Cycles that took materially more water than the plan called for."""
        if not isinstance(planned, Pounds):
            raise BadInputError("the planned water is a bulk mass")
        if planned.is_zero:
            raise BadInputError("a plan with no water in it has no overrun")
        threshold = planned.scaled(HEAVY_WATER)
        return tuple(c for c in self.cycles if c.water > threshold)

    def _share(self, count: int) -> Decimal:
        if not self.cycles:
            raise RuleError("no cycles were recorded, so there is no share to take")
        return (Decimal(count) / Decimal(len(self.cycles))).quantize(
            _PLACES, rounding=ROUND_HALF_UP
        )

    @property
    def short_mull_share(self) -> Decimal:
        return self._share(len(self.short_mulls))

    @property
    def is_running_short(self) -> bool:
        """Whether short mulls are frequent enough to be the machine."""
        return self.short_mull_share > SHORT_MULL_SHARE

    @property
    def average_mull(self) -> Seconds:
        """The mean total mull across the recorded cycles."""
        if not self.cycles:
            raise RuleError("no cycles were recorded, so there is no average")
        return Seconds(sum(c.total_mull.value for c in self.cycles) // len(self.cycles))

    def findings(self, planned_water: Pounds) -> list[str]:
        """The case for looking at the machine, or the absence of one."""
        if not self.cycles:
            return ["no cycles were recorded"]
        lines: list[str] = []
        if self.abandoned:
            named = ", ".join(c.batch_id for c in self.abandoned)
            lines.append(f"{len(self.abandoned)} batches were never discharged: {named}")
        if self.is_running_short:
            lines.append(
                f"{self.short_mull_share:.0%} of cycles mulled short, past the "
                f"{SHORT_MULL_SHARE:.0%} that says the line is outrunning the muller"
            )
        heavy = self.water_heavy(planned_water)
        if heavy:
            lines.append(
                f"{self._share(len(heavy)):.0%} of cycles took over "
                f"{HEAVY_WATER:.0%} of the planned water, which is what "
                "undeveloped bond looks like to an operator"
            )
        if not lines:
            lines.append(
                f"{len(self.cycles)} cycles, averaging {self.average_mull}, "
                "with nothing to say about the machine"
            )
        return lines


__all__ = ["HEAVY_WATER", "History", "RecordedCycle", "SHORT_MULL_SHARE"]
