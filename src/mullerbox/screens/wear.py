"""Checking the physical sieves, which nothing downstream can do for you.

A test sieve is a woven wire cloth in a frame and it wears. The wires stretch,
the apertures open up, and a screen that has opened by ten percent passes sand
it should have held. The analysis still closes, the fineness number still
computes, and it is wrong: the sand reads coarser than it is, every run, until
somebody measures the cloth.

Nothing in the arithmetic can detect this. A closed analysis on a worn stack
looks exactly like a closed analysis on a good one, which is why the check has
to be a separate physical act with its own record. This module is that record.

Two checks and they catch different things.

**Aperture drift** is the wear itself: the measured average opening against the
nominal one. It is slow and it is one directional, so a screen that has drifted
never comes back.

**Wire count** catches the other failure, which is a screen that has been
*replaced* with the wrong one. That happens when a frame is pulled from the
wrong drawer, and it is not gradual: the aperture is simply wrong from that day
on. A drift check alone would flag it as extreme wear and somebody would order
a new screen for a screen that is fine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from mullerbox.errors import BadInputError, RuleError
from mullerbox.screens.series import ScreenSeries
from mullerbox.units.mesh import Mesh

# How far an aperture may open before the screen is retired, as a fraction.
WEAR_LIMIT = Decimal("0.05")

# How far past the limit is not wear at all but the wrong screen in the frame.
WRONG_SCREEN_LIMIT = Decimal("0.20")


@dataclass(frozen=True)
class Check:
    """One screen measured against what it should be."""

    mesh: Mesh
    measured_micrometres: int
    checked_on: date

    def __post_init__(self) -> None:
        if not isinstance(self.mesh, Mesh):
            raise BadInputError("a wear check is against a screen")
        if self.mesh.is_pan:
            raise BadInputError("the pan has no aperture to wear")
        if isinstance(self.measured_micrometres, bool) or not isinstance(
            self.measured_micrometres, int
        ):
            raise BadInputError("a measured aperture is a whole number")
        if self.measured_micrometres <= 0:
            raise BadInputError("a measured aperture is above zero")
        if not isinstance(self.checked_on, date):
            raise BadInputError("a wear check is dated")

    @property
    def drift(self) -> Decimal:
        """How far the aperture has opened, as a fraction of nominal.

        Signed. A negative drift is a screen reading tighter than nominal, which
        wear does not cause and which therefore means the wrong screen or a bad
        measurement.
        """
        nominal = Decimal(self.mesh.micrometres)
        return ((Decimal(self.measured_micrometres) - nominal) / nominal).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )

    @property
    def is_worn(self) -> bool:
        return abs(self.drift) > WEAR_LIMIT

    @property
    def is_wrong_screen(self) -> bool:
        """Too far out to be wear, or tighter than nominal, which wear is not."""
        return abs(self.drift) > WRONG_SCREEN_LIMIT or self.drift < -WEAR_LIMIT

    def verdict(self) -> str:
        """One line saying what to do about this screen."""
        if self.is_wrong_screen:
            return (
                f"screen {self.mesh.label} measures {self.measured_micrometres} "
                f"against a nominal {self.mesh.micrometres}, which is not wear; "
                "check the frame carries the right cloth"
            )
        if self.is_worn:
            return (
                f"screen {self.mesh.label} has opened {self.drift:.2%} and is "
                "past the wear limit; retire it"
            )
        return f"screen {self.mesh.label} is within {self.drift:.2%} of nominal"

    def __str__(self) -> str:
        return self.verdict()


@dataclass(frozen=True)
class StackCheck:
    """A whole stack measured on one day."""

    series: ScreenSeries
    checks: tuple[Check, ...]
    checked_on: date

    def __post_init__(self) -> None:
        if not isinstance(self.series, ScreenSeries):
            raise BadInputError("a stack check is against a series")
        seen: list[Mesh] = []
        for check in self.checks:
            if not isinstance(check, Check):
                raise BadInputError("a stack check is built from screen checks")
            if not self.series.contains(check.mesh):
                raise RuleError(f"screen {check.mesh.label} is not on series {self.series.name}")
            if check.mesh in seen:
                raise RuleError(f"screen {check.mesh.label} was measured twice")
            seen.append(check.mesh)

    @property
    def unchecked(self) -> tuple[Mesh, ...]:
        """Working screens nobody measured, which is not a pass."""
        measured = {c.mesh for c in self.checks}
        return tuple(step.mesh for step in self.series.working_steps if step.mesh not in measured)

    @property
    def worn(self) -> tuple[Check, ...]:
        return tuple(c for c in self.checks if c.is_worn and not c.is_wrong_screen)

    @property
    def wrong(self) -> tuple[Check, ...]:
        return tuple(c for c in self.checks if c.is_wrong_screen)

    @property
    def is_fit_to_use(self) -> bool:
        """A stack is fit only when every working screen was measured and passed."""
        return not self.unchecked and not self.worn and not self.wrong

    def require_fit(self) -> None:
        """Refuse a stack that should not be producing numbers."""
        if self.unchecked:
            names = ", ".join(m.label for m in self.unchecked)
            raise RuleError(f"screens {names} were not measured, so this stack is unverified")
        if self.wrong:
            raise RuleError(self.wrong[0].verdict())
        if self.worn:
            raise RuleError(self.worn[0].verdict())


__all__ = ["Check", "StackCheck", "WEAR_LIMIT", "WRONG_SCREEN_LIMIT"]
