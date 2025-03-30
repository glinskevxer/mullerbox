"""The grain fineness number, and why one number is not enough.

GFN is the multiplier-weighted average of the retained distribution. It is the
number every sand specification is written in and the number every supplier
quotes, and taken alone it is close to useless, because it is an average and two
completely different sands average the same.

A sand piled on three adjacent screens and a sand spread evenly across nine can
carry the same GFN. They do not mold the same. The tight one packs to a lower
permeability and takes less bond to hold together; the spread one has fines
filling the voids between the coarse grains and will not vent. So the fineness
number and the spread are computed here together and travel together, and
nothing downstream is allowed to take the number without also being handed the
spread it came from.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from mullerbox.errors import BadInputError, RuleError
from mullerbox.screens.analysis import SieveAnalysis
from mullerbox.units.mesh import Mesh
from mullerbox.units.percent import Percent

PLACES = Decimal("0.01")

# Foundry sands run 45 to 90 GFN. Outside this the number is arithmetically
# fine and physically meaningless, which is worth saying out loud rather than
# passing along to a spec comparison that will quietly fail it.
TYPICAL_LOW = Decimal("35")
TYPICAL_HIGH = Decimal("120")


@dataclass(frozen=True)
class Fineness:
    """A grain fineness number and the distribution it was averaged out of."""

    value: Decimal
    spread: tuple[tuple[Mesh, Percent], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.value, Decimal):
            raise BadInputError("a fineness number is a decimal")
        if self.value <= 0:
            raise BadInputError("a fineness number has to be above zero")
        if not self.spread:
            raise BadInputError("a fineness number carries the spread it came from")

    @property
    def is_typical(self) -> bool:
        """False for a number that is arithmetic rather than sand."""
        return TYPICAL_LOW <= self.value <= TYPICAL_HIGH

    @property
    def retaining_screens(self) -> tuple[tuple[Mesh, Percent], ...]:
        """Only the screens that actually held something, coarse first."""
        return tuple((mesh, pct) for mesh, pct in self.spread if pct.value > 0)

    def fraction_on(self, mesh: Mesh) -> Percent:
        for held, pct in self.spread:
            if held == mesh:
                return pct
        raise BadInputError(f"screen {mesh.label} is not in this distribution")

    def coarser_than(self, mesh: Mesh) -> Percent:
        """Everything held above a given screen, which is what a vent argument needs."""
        running = Decimal(0)
        for held, pct in self.spread:
            if held == mesh:
                return Percent(running)
            running += pct.value
        raise BadInputError(f"screen {mesh.label} is not in this distribution")

    def __str__(self) -> str:
        return f"GFN {self.value}"


def fineness_of(analysis: SieveAnalysis) -> Fineness:
    """Work the grain fineness number out of a closed sieve analysis.

    The weighting runs over the recovered distribution, so the percentages
    already sum to one hundred and the divisor is a hundred rather than a
    re-summed total. Re-summing would be defensible arithmetic and a worse
    check: if the percentages did not sum to a hundred, that is a fault in the
    analysis and dividing it away would hide it.
    """
    if not isinstance(analysis, SieveAnalysis):
        raise BadInputError("a fineness number is worked out of a sieve analysis")
    analysis.require_closure()
    spread = analysis.distribution
    series = analysis.series
    weighted = Decimal(0)
    total = Decimal(0)
    for mesh, pct in spread:
        weighted += pct.value * series.multiplier_for(mesh)
        total += pct.value
    if total != Decimal(100):
        raise RuleError(f"the distribution sums to {total}%, not 100%")
    value = (weighted / Decimal(100)).quantize(PLACES, rounding=ROUND_HALF_UP)
    if value <= 0:
        raise RuleError("the distribution carries no grain at all")
    return Fineness(value=value, spread=spread)


__all__ = ["Fineness", "PLACES", "TYPICAL_HIGH", "TYPICAL_LOW", "fineness_of"]
