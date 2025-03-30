"""How much bentonite the next batch needs.

Two numbers go in and neither is sufficient alone.

The **measurement** is methylene blue clay: how much live bond is in the system
right now. The lab runs it and it is a fact about the sand.

The **target** is not a fact about the sand. It is a fact about the work, and it
moves. A system pouring heavy at three to one is destroying bond faster than one
pouring light at nine to one, and it needs to carry more reserve to stay in band
between mulls. Holding both systems to the same published MB target means the
heavy one spends every shift climbing out of a hole. So the target is the
published figure lifted by the severity of what was actually poured.

That is the part worth being explicit about, because it inverts the intuition.
The addition is not "the target minus the reading". The target itself is
downstream of production, so the same reading against the same published spec
calls for a different addition depending on a number that came off the pour
record rather than off the bench.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from mullerbox.addition.material import Addition, Material
from mullerbox.burnout.loss import Burnout
from mullerbox.errors import BadInputError
from mullerbox.units.bulk import Pounds
from mullerbox.units.percent import Percent, Points

# How much of the published target a fully severe shift adds on top. A two to
# one shift runs severity 3, which lifts an 8.0 target to 8.96.
SEVERITY_LIFT = Decimal("0.06")

# The lift is bounded. Past this the answer is not more bentonite, it is a
# second muller or lighter work, and a system asked to carry this much reserve
# will not compact.
MAX_LIFT = Decimal("0.25")

_PLACES = Decimal("0.01")


@dataclass(frozen=True)
class BondCall:
    """The bentonite decision, with everything that went into it."""

    measured: Percent
    published_target: Percent
    working_target: Percent
    deficit: Points
    addition: Addition

    @property
    def target_was_lifted(self) -> bool:
        return self.working_target > self.published_target

    def __str__(self) -> str:
        return (
            f"MB {self.measured} against {self.working_target} "
            f"(published {self.published_target}): {self.addition}"
        )


def working_target(published: Percent, severity: object) -> Percent:
    """Lift a published bond target by how hard the sand is being worked."""
    if not isinstance(published, Percent):
        raise BadInputError("a bond target is a percentage")
    if not isinstance(severity, Decimal):
        raise BadInputError("severity is a decimal off the pour record")
    if severity <= 0:
        raise BadInputError("severity has to be above zero")
    over_reference = severity - Decimal(1)
    if over_reference <= 0:
        return published
    lift = over_reference * SEVERITY_LIFT
    if lift > MAX_LIFT:
        lift = MAX_LIFT
    return Percent(
        (published.value * (Decimal(1) + lift)).quantize(_PLACES, rounding=ROUND_HALF_UP)
    )


def bentonite_for(
    measured: Percent,
    published: Percent,
    burnout: Burnout,
    system_mass: Pounds,
) -> BondCall:
    """Work out the bentonite addition for the next batch.

    The deficit is taken against the working target rather than the published
    one, and the mass is grossed up by the material's yield because a pound of
    bentonite does not read as a pound of methylene blue clay.

    A system already at or above target gets a zero addition rather than a
    negative one. Bentonite cannot be removed from a sand system; the only way
    down is dilution with new sand, which is a different decision made by a
    different part of the shop.
    """
    if not isinstance(measured, Percent):
        raise BadInputError("the methylene blue reading is a percentage")
    if not isinstance(published, Percent):
        raise BadInputError("a bond target is a percentage")
    if not isinstance(burnout, Burnout):
        raise BadInputError("a bond call needs the shift's burnout")
    if not isinstance(system_mass, Pounds):
        raise BadInputError("the system mass is a bulk mass")
    if system_mass.is_zero:
        raise BadInputError("a system with no sand in it needs no bentonite")

    target = working_target(published, burnout.pour.severity)
    deficit = target - measured
    if not deficit.is_high:
        return BondCall(
            measured=measured,
            published_target=published,
            working_target=target,
            deficit=deficit,
            addition=Addition.nothing(
                Material.BENTONITE,
                f"MB {measured} is at or above the working target of {target}",
            ),
        )
    # One scaling rather than two. Going via an intermediate "pounds of clay
    # needed" rounds to the hundredth of a pound twice, and the second rounding
    # is applied to an already rounded number, so the answer drifts by a cent
    # against the same calculation done in one step.
    charged = system_mass.scaled(deficit.value / Decimal(100) / Material.BENTONITE.yield_factor)
    return BondCall(
        measured=measured,
        published_target=published,
        working_target=target,
        deficit=deficit,
        addition=Addition(
            material=Material.BENTONITE,
            mass=charged,
            reason=f"MB {measured} is {deficit} under the working target of {target}",
        ),
    )


__all__ = ["BondCall", "MAX_LIFT", "SEVERITY_LIFT", "bentonite_for", "working_target"]
