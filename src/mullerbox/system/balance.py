"""Where the sand went, and whether the books close.

A shift's sand balance is the only check on whether the system mass figure is
still true. Sand in, sand out, and the difference against what the system is
believed to hold. If the balance closes month after month the mass figure is
sound; if it drifts one way consistently, the figure is wrong and every addition
computed against it has been wrong by the same proportion.

The residual is reported rather than distributed. There is a strong temptation
to close the books by assigning the gap to dust loss, because dust loss is the
one term nobody measures directly and it will absorb anything. Doing that
guarantees the balance closes and destroys the only signal it carried. Dust loss
here is estimated from the throughput and the collector's known rate, the
residual is whatever is left, and a residual that will not sit near zero is the
finding.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from mullerbox.errors import BadInputError
from mullerbox.system.state import SandSystem
from mullerbox.units.bulk import Pounds
from mullerbox.units.percent import Percent

# A shift that cannot account for more than this of its throughput has a
# measurement problem rather than a rounding problem.
RESIDUAL_TOLERANCE = Decimal("0.02")


@dataclass(frozen=True)
class Balance:
    """One shift's sand in and sand out."""

    system: SandSystem
    shift_on: date
    new_sand: Pounds
    core_sand_returned: Pounds
    shipped_on_castings: Pounds
    dust_collected: Pounds
    swept_up: Pounds
    throughput: Pounds

    def __post_init__(self) -> None:
        if not isinstance(self.system, SandSystem):
            raise BadInputError("a balance is struck against a sand system")
        if not isinstance(self.shift_on, date):
            raise BadInputError("a balance is dated")
        for name in (
            "new_sand",
            "core_sand_returned",
            "shipped_on_castings",
            "dust_collected",
            "swept_up",
            "throughput",
        ):
            if not isinstance(getattr(self, name), Pounds):
                raise BadInputError(f"{name.replace('_', ' ')} is a bulk mass")
        if self.throughput.is_zero:
            raise BadInputError("a shift that handled no sand has no balance")

    @property
    def additions_in(self) -> Pounds:
        """Everything that entered the system."""
        return self.new_sand + self.core_sand_returned

    @property
    def measured_out(self) -> Pounds:
        """Everything that left and was weighed on the way."""
        return self.shipped_on_castings + self.dust_collected + self.swept_up

    @property
    def expected_dust(self) -> Pounds:
        """What the collector should have taken, from the system's known rate."""
        return self.system.dust_loss_over(self.throughput)

    @property
    def net_change(self) -> Decimal:
        """In minus out, signed, in pounds.

        Signed, so it is a Decimal rather than a ``Pounds``. A bulk mass is
        unsigned by construction, and the whole value of this number is which
        way it points.
        """
        return self.additions_in.value - self.measured_out.value

    @property
    def residual(self) -> Decimal:
        """What the balance cannot account for, as a share of throughput.

        Positive means more went in than can be explained by what came out, so
        the system should be growing. A system that is not growing while this
        stays positive is a system whose mass figure is too high.
        """
        return (self.net_change / self.throughput.value).quantize(Decimal("0.0001"))

    @property
    def closes(self) -> bool:
        return abs(self.residual) <= RESIDUAL_TOLERANCE

    @property
    def dust_variance(self) -> Decimal:
        """Measured dust against expected dust, as a share of expected.

        A collector taking far less than its rate says is usually a full hopper
        nobody emptied, and it shows up here before it shows up as fines
        climbing in the system.
        """
        expected = self.expected_dust
        if expected.is_zero:
            raise BadInputError("no dust was expected, so there is no variance")
        return ((self.dust_collected.value - expected.value) / expected.value).quantize(
            Decimal("0.0001")
        )

    @property
    def implied_system_change(self) -> Percent:
        """The net change as a share of the believed system mass."""
        share = abs(self.net_change) / self.system.mass.value * 100
        return Percent(share.quantize(Decimal("0.01")))

    def finding(self) -> str:
        """One line saying what this balance means, if anything."""
        if self.closes:
            return f"balance closes at {self.residual:+} of throughput"
        direction = "more sand in than out" if self.net_change > 0 else "more out than in"
        return (
            f"balance does not close: {direction} by {self.residual:+} of "
            f"throughput, past the {RESIDUAL_TOLERANCE} tolerance"
        )

    def __str__(self) -> str:
        return f"{self.shift_on} {self.system.name}: {self.finding()}"


__all__ = ["Balance", "RESIDUAL_TOLERANCE"]
