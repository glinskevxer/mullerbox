"""The dust collector, which is a sand classifier nobody thinks of as one.

A collector is installed to keep the shop breathable and it does something else
at the same time: it takes fines out of the sand, preferentially, every hour it
runs. Over a year that shifts the whole system coarser, and nothing in the daily
readings shows it happening because the fineness number moves a point a month.

The shift is not neutral. Fines carry most of the surface area, so removing them
lowers the bond demand and raises the permeability, and a system that has been
quietly getting coarser for a year is a system whose bentonite additions have
been slightly too high for a year.

**The collector's take is modelled as a screen, not as a percentage.** A flat
percentage of the throughput is what shops assume and it is wrong in the way
that matters: the collector does not take a slice of the sand, it takes the
fines. So the model is a capture fraction per screen, high at the pan end and
near zero at the coarse end, applied to the distribution rather than to the
mass.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from mullerbox.errors import BadInputError
from mullerbox.gfn.fineness import Fineness
from mullerbox.units.bulk import Pounds
from mullerbox.units.mesh import Mesh
from mullerbox.units.percent import Percent

# What share of the sand on each screen the collector takes, by aperture. A
# cyclone and a baghouse both catch nearly everything under about fifty
# micrometres and almost nothing above two hundred.
FULLY_CAPTURED_BELOW = 53
BARELY_CAPTURED_ABOVE = 212


def capture_fraction(mesh: Mesh) -> Decimal:
    """The share of the sand on one screen that the collector takes.

    One at the pan, near zero at the coarse end, and a straight line between the
    two bounds. Linear is not the aerodynamics and it is the right shape: the
    real curve is a sigmoid and the difference between them is smaller than the
    difference between either and the flat percentage shops usually assume.
    """
    if not isinstance(mesh, Mesh):
        raise BadInputError("a screen is expected")
    if mesh.is_pan:
        return Decimal(1)
    aperture = mesh.micrometres
    if aperture <= FULLY_CAPTURED_BELOW:
        return Decimal(1)
    if aperture >= BARELY_CAPTURED_ABOVE:
        return Decimal(0)
    span = Decimal(BARELY_CAPTURED_ABOVE - FULLY_CAPTURED_BELOW)
    over = Decimal(aperture - FULLY_CAPTURED_BELOW)
    return ((span - over) / span).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Take:
    """What the collector removed from one throughput, screen by screen."""

    throughput: Pounds
    removed: Pounds
    by_screen: tuple[tuple[Mesh, Pounds], ...]

    @property
    def share_removed(self) -> Percent:
        if self.throughput.is_zero:
            raise BadInputError("nothing went through, so nothing was taken")
        return Percent.of(self.removed.value, self.throughput.value)

    @property
    def coarsest_touched(self) -> Mesh | None:
        """The coarsest screen the collector took anything off."""
        touched = [mesh for mesh, mass in self.by_screen if not mass.is_zero]
        return min(touched) if touched else None

    def __str__(self) -> str:
        return f"{self.removed} of {self.throughput} to the collector"


def collector_take(fineness: Fineness, throughput: Pounds) -> Take:
    """What the collector removes from a throughput of sand of a known spread.

    Takes the distribution rather than a bare mass, which is the whole point:
    two systems running the same tonnage through the same collector lose
    different amounts, and the one with more fines loses more.
    """
    if not isinstance(fineness, Fineness):
        raise BadInputError("a fineness result is expected")
    if not isinstance(throughput, Pounds):
        raise BadInputError("a throughput is a bulk mass")
    removed = Decimal(0)
    per_screen: list[tuple[Mesh, Pounds]] = []
    for mesh, share in fineness.spread:
        on_screen = throughput.value * share.fraction
        taken = (on_screen * capture_fraction(mesh)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        removed += taken
        per_screen.append((mesh, Pounds(taken)))
    return Take(
        throughput=throughput,
        removed=Pounds(removed),
        by_screen=tuple(per_screen),
    )


def fineness_after(fineness: Fineness, take: Take) -> Decimal:
    """Where the grain fineness number lands once the collector has had its share.

    Positive movement means finer, which the collector never causes. The number
    that comes back is always at or below the one that went in, and the gap is
    the drift nobody sees on a daily reading.
    """
    if not isinstance(take, Take):
        raise BadInputError("a collector take is expected")
    if not isinstance(fineness, Fineness):
        raise BadInputError("a fineness result is expected")
    taken = dict(take.by_screen)
    weighted = Decimal(0)
    total = Decimal(0)
    for mesh, share in fineness.spread:
        before = take.throughput.value * share.fraction
        left = before - taken.get(mesh, Pounds.zero()).value
        if left <= 0:
            continue
        multiplier = _multiplier_for(fineness, mesh)
        weighted += left * multiplier
        total += left
    if total <= 0:
        raise BadInputError("the collector took everything, so there is no sand left")
    return (weighted / total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _multiplier_for(fineness: Fineness, mesh: Mesh) -> Decimal:
    """The screen's fineness multiplier, read back off the spread's own order."""
    for index, (held, _) in enumerate(fineness.spread):
        if held == mesh:
            return _AFS_MULTIPLIERS[index]
    raise BadInputError(f"screen {mesh.label} is not in this distribution")


# The AFS multipliers in stack order, which is the order a spread carries.
_AFS_MULTIPLIERS: tuple[Decimal, ...] = tuple(
    Decimal(x) for x in (3, 5, 10, 20, 30, 40, 50, 70, 100, 140, 200, 300)
)


__all__ = [
    "BARELY_CAPTURED_ABOVE",
    "FULLY_CAPTURED_BELOW",
    "Take",
    "capture_fraction",
    "collector_take",
    "fineness_after",
]
