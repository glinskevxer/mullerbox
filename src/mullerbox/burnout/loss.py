"""How much of the bond and the carbon the pour killed.

Bentonite does not burn. It dehydroxylates: above about six hundred Celsius the
clay loses the structural water that lets it swell, and what comes back on the
next cycle is a fine inert powder that still shows up in a total clay wash and
does not show up in a methylene blue titration. That difference is the whole
reason the lab runs both tests. Total clay counts everything; MB clay counts
only what is still alive.

Seacoal is different again. It does burn, it is consumed rather than deadened,
and it goes faster than the clay because it starts at a lower temperature.

Both losses are driven by the same thing: what share of the sand in the system
got hot enough. That share is inversely proportional to the sand to metal ratio,
because the heat comes from the metal and the sand is what it is spread through.
The proportionality is capped, because past a point the sand nearest the casting
is already fully dead and pouring more metal into the same molds does not kill
it twice.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from mullerbox.burnout.pour import Pour
from mullerbox.errors import BadInputError
from mullerbox.units.percent import Percent, Points

# The share of system sand taken past the dehydroxylation temperature at a one
# to one pour, and the ceiling that share cannot pass however hot the shift.
#
# The ceilings are set where they actually bite. The first pass at this put them
# at 0.50 and 0.85, which are defensible physical saturation points and were
# both unreachable: the lowest ratio a pour record is allowed to carry is two to
# one, which puts the clay share at 0.30 and the carbon share at 0.60 before any
# ceiling is consulted. A ceiling that cannot fire is not a safety net, it is a
# branch no test can reach and a claim about behaviour that never happens. These
# ones bind over the bottom of the plausible range, which is where the linear
# model stops being believable anyway.
CLAY_HOT_SHARE_AT_UNITY = Decimal("0.60")
CLAY_MAX_DEAD_SHARE = Decimal("0.28")

# Carbon goes at a lower temperature, so a larger share of the system loses it.
CARBON_HOT_SHARE_AT_UNITY = Decimal("1.20")
CARBON_MAX_BURNT_SHARE = Decimal("0.55")

PLACES = Decimal("0.01")


@dataclass(frozen=True)
class Burnout:
    """What one pour took out of the system, in points of each property."""

    pour: Pour
    dead_clay_share: Decimal
    burnt_carbon_share: Decimal
    clay_lost: Points
    carbon_lost: Points

    @property
    def is_severe(self) -> bool:
        """True when this pour killed a fifth of the live bond or more."""
        return self.dead_clay_share >= Decimal("0.20")

    def __str__(self) -> str:
        return (
            f"{self.pour.poured_on} lost {self.clay_lost} of live clay "
            f"and {self.carbon_lost} of carbon"
        )


def _share(at_unity: Decimal, ceiling: Decimal, ratio: Decimal) -> Decimal:
    share = at_unity / ratio
    if share > ceiling:
        share = ceiling
    return share.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def burnout_of(pour: Pour, live_clay: Percent, carbon: Percent) -> Burnout:
    """Work out what a pour took, given what was in the sand going in.

    The losses are proportional to what was there. A system running four percent
    live clay loses half as many points as one running eight, from the same
    pour, because the loss is a share of the bond present rather than a fixed
    number of points. Publishing addition rates as fixed points is the standard
    shop shortcut and it is why a system that has drifted low takes so long to
    recover: the fixed rate was written for the bond level it used to have.
    """
    if not isinstance(pour, Pour):
        raise BadInputError("a burnout is worked out from a pour")
    if not isinstance(live_clay, Percent):
        raise BadInputError("live clay is a percentage")
    if not isinstance(carbon, Percent):
        raise BadInputError("carbon is a percentage")
    ratio = pour.require_plausible()
    clay_share = _share(CLAY_HOT_SHARE_AT_UNITY, CLAY_MAX_DEAD_SHARE, ratio)
    carbon_share = _share(CARBON_HOT_SHARE_AT_UNITY, CARBON_MAX_BURNT_SHARE, ratio)
    return Burnout(
        pour=pour,
        dead_clay_share=clay_share,
        burnt_carbon_share=carbon_share,
        clay_lost=Points((live_clay.value * clay_share).quantize(PLACES, rounding=ROUND_HALF_UP)),
        carbon_lost=Points((carbon.value * carbon_share).quantize(PLACES, rounding=ROUND_HALF_UP)),
    )


__all__ = [
    "CARBON_HOT_SHARE_AT_UNITY",
    "CARBON_MAX_BURNT_SHARE",
    "CLAY_HOT_SHARE_AT_UNITY",
    "CLAY_MAX_DEAD_SHARE",
    "Burnout",
    "burnout_of",
]
