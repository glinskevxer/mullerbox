"""Whether the sand is making the right stuff, as opposed to making it consistently.

The control chart answers one question: is this process stable. Capability
answers the other: is the stable thing it produces inside the band. They are
independent and all four combinations happen.

- In control and capable. Leave it alone.
- In control and not capable. The process is doing exactly what it always does
  and what it always does is wrong. Adjusting the muller will not help; the
  recipe or the band has to change.
- Out of control and capable. It is wandering but the band is wide enough to
  absorb it. This is where most systems live and it is a trap: the wander is
  real and the day the band tightens it becomes scrap.
- Neither. Stop and find out why before doing anything else.

Reading one without the other gets the diagnosis wrong in both directions, which
is why nothing in this module computes control limits and nothing in the control
module knows about bands.

**Cp and Cpk both, always.** Cp asks whether the spread would fit inside the
band. Cpk asks whether it fits where the process actually sits. A process
centred badly has a good Cp and a poor Cpk, and quoting Cp alone is the standard
way to make an off-centre process look fine.

**Sigma comes from the moving range**, the same as the control limits, and for
the same reason: the sample standard deviation of a drifting run measures the
drift as well as the noise, and capability computed from it flatters a process
that is wandering.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from mullerbox.analysis.control import MIN_POINTS
from mullerbox.errors import BadInputError, RuleError
from mullerbox.props.kind import PropertyKind
from mullerbox.spec.band import Band

# The bias correction that turns an average moving range of two into a sigma.
D2 = Decimal("1.128")

# The usual industrial line: 1.33 is capable, 1.00 is marginal, below is not.
CAPABLE = Decimal("1.33")
MARGINAL = Decimal("1.00")

PLACES = Decimal("0.001")


@dataclass(frozen=True)
class Capability:
    """How a run of readings sits against the band it is judged by."""

    kind: PropertyKind
    band: Band
    mean: Decimal
    sigma: Decimal
    cp: Decimal | None
    cpk: Decimal

    @property
    def is_capable(self) -> bool:
        return self.cpk >= CAPABLE

    @property
    def is_marginal(self) -> bool:
        return MARGINAL <= self.cpk < CAPABLE

    @property
    def is_off_centre(self) -> bool:
        """True when the spread would fit but the process is not sitting in it."""
        return self.cp is not None and self.cp - self.cpk >= Decimal("0.2")

    def verdict(self) -> str:
        """One line saying what the Cpk means, and whether centring would fix it."""
        if self.is_capable:
            centred = "" if not self.is_off_centre else ", though it sits off centre"
            return f"capable at Cpk {self.cpk}{centred}"
        if self.is_marginal:
            return f"marginal at Cpk {self.cpk}"
        if self.is_off_centre:
            return (
                f"not capable at Cpk {self.cpk}, but Cp {self.cp} says the spread "
                "would fit if it were centred"
            )
        return f"not capable at Cpk {self.cpk}, and the spread alone will not fit"

    def __str__(self) -> str:
        return f"{self.kind.label}: {self.verdict()}"


def sigma_from(readings: list[Decimal]) -> Decimal:
    """Process sigma, estimated from the average moving range."""
    if len(readings) < 2:
        raise RuleError("two readings are the fewest that have a moving range")
    ranges = [abs(readings[i] - readings[i - 1]) for i in range(1, len(readings))]
    average = sum(ranges, Decimal(0)) / len(ranges)
    return (average / D2).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def capability_of(kind: PropertyKind, band: Band, readings: list[Decimal]) -> Capability:
    """Work out Cp and Cpk for a run of readings against a band.

    A one ended band has no Cp, because there is no width for the spread to fit
    inside. It still has a Cpk, taken against the single limit, and that is the
    number that matters for a property like loss on ignition where only one
    direction hurts.
    """
    if not isinstance(kind, PropertyKind):
        raise BadInputError("a property kind is expected")
    if not isinstance(band, Band):
        raise BadInputError("a band is expected")
    if band.kind is not kind:
        raise BadInputError(f"a {kind.label} run cannot be judged against a {band.kind.label} band")
    if not isinstance(readings, list):
        raise BadInputError("a run of readings is expected")
    for reading in readings:
        if not isinstance(reading, Decimal):
            raise BadInputError("capability is worked out from decimals")
    if len(readings) < MIN_POINTS:
        raise RuleError(
            f"{len(readings)} readings will not carry a capability, {MIN_POINTS} is the floor"
        )
    sigma = sigma_from(readings)
    if sigma == 0:
        raise RuleError("every reading is identical, so the process has no measurable spread")
    mean = (sum(readings, Decimal(0)) / len(readings)).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )
    from mullerbox.spec.band import _scalar

    low = None if band.low is None else _scalar(band.low)
    high = None if band.high is None else _scalar(band.high)
    cp = None
    if low is not None and high is not None:
        cp = ((high - low) / (6 * sigma)).quantize(PLACES, rounding=ROUND_HALF_UP)
    sides: list[Decimal] = []
    if high is not None:
        sides.append((high - mean) / (3 * sigma))
    if low is not None:
        sides.append((mean - low) / (3 * sigma))
    cpk = min(sides).quantize(PLACES, rounding=ROUND_HALF_UP)
    return Capability(kind=kind, band=band, mean=mean, sigma=sigma, cp=cp, cpk=cpk)


__all__ = [
    "CAPABLE",
    "Capability",
    "D2",
    "MARGINAL",
    "PLACES",
    "capability_of",
    "sigma_from",
]
