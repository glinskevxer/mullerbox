"""Casting yield, and the three different things a foundry calls by that name.

Ask three people in a foundry what the yield was and get three numbers, because
"yield" names three ratios and nobody says which.

**Casting yield** is casting weight over poured weight: how much of the metal
ended up as casting rather than as gating and risers. It is a pattern property
and the melting department is judged on it.

**Good casting yield** is shipped weight over poured weight. It is the first
number times the scrap rate, and it is the one the plant is actually paid on.

**Sand ratio** is sand handled over good iron shipped, which is what the sand
department is judged on and has nothing to do with either of the others.

Confusing the first two is how a foundry congratulates itself on a good month
that scrapped a fifth of its castings. So this module names all three, computes
none of them without saying which it computed, and refuses to hand back a bare
"yield".
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from mullerbox.errors import BadInputError, RuleError
from mullerbox.heat.heat import Disposition, Heat
from mullerbox.units.bulk import Pounds

_PLACES = Decimal("0.0001")


@dataclass(frozen=True)
class Yields:
    """The three ratios, each named."""

    poured: Pounds
    casting_weight: Pounds
    shipped: Pounds
    sand_handled: Pounds

    def __post_init__(self) -> None:
        for name in ("poured", "casting_weight", "shipped", "sand_handled"):
            if not isinstance(getattr(self, name), Pounds):
                raise BadInputError(f"{name.replace('_', ' ')} is a bulk mass")
        if self.casting_weight > self.poured:
            raise RuleError(
                f"{self.casting_weight} of castings cannot come out of {self.poured} of metal"
            )
        if self.shipped > self.casting_weight:
            raise RuleError(
                f"{self.shipped} shipped is more than the {self.casting_weight} of castings made"
            )

    @property
    def casting_yield(self) -> Decimal:
        """Casting weight over poured weight. What melting is judged on."""
        if self.poured.is_zero:
            raise RuleError("nothing was poured, so there is no casting yield")
        return self.casting_weight.fraction_of(self.poured).quantize(_PLACES)

    @property
    def good_casting_yield(self) -> Decimal:
        """Shipped weight over poured weight. What the plant is paid on."""
        if self.poured.is_zero:
            raise RuleError("nothing was poured, so there is no good casting yield")
        return self.shipped.fraction_of(self.poured).quantize(_PLACES)

    @property
    def sand_ratio(self) -> Decimal:
        """Sand handled over good iron shipped. What the sand department is judged on."""
        if self.shipped.is_zero:
            raise RuleError("nothing shipped, so there is no sand ratio")
        return self.sand_handled.ratio_to(self.shipped)

    @property
    def scrap_share(self) -> Decimal:
        """The gap between the first two ratios, which is what scrap costs."""
        if self.casting_weight.is_zero:
            raise RuleError("no castings were made, so there is no scrap share")
        return (Decimal(1) - self.shipped.fraction_of(self.casting_weight)).quantize(
            _PLACES, rounding=ROUND_HALF_UP
        )

    def summary(self) -> list[str]:
        """All three, each said out loud, so nobody quotes the wrong one."""
        return [
            f"casting yield {self.casting_yield:.1%} "
            "(castings out of metal poured, what melting is judged on)",
            f"good casting yield {self.good_casting_yield:.1%} "
            "(shipped out of metal poured, what the plant is paid on)",
            f"sand ratio {self.sand_ratio}:1 "
            "(sand handled per pound shipped, what the sand is judged on)",
            f"the gap between the first two is {self.scrap_share:.1%} scrap",
        ]

    def __str__(self) -> str:
        return (
            f"casting {self.casting_yield:.1%}, good {self.good_casting_yield:.1%}, "
            f"sand {self.sand_ratio}:1"
        )


def yields_of(heat: Heat, sand_handled: Pounds) -> Yields:
    """Work the three ratios out of one heat.

    Sand handled comes in from outside because a heat knows the sand in its own
    molds and not the sand the system moved to make them, and those differ by
    everything that went round without being poured into.
    """
    if not isinstance(heat, Heat):
        raise BadInputError("a heat is expected")
    if not isinstance(sand_handled, Pounds):
        raise BadInputError("the sand handled is a bulk mass")
    made = Pounds.zero()
    shipped = Pounds.zero()
    for casting in heat.castings:
        made = made + casting.weight
        if casting.disposition is Disposition.SHIPPED:
            shipped = shipped + casting.weight
    return Yields(
        poured=heat.metal,
        casting_weight=made,
        shipped=shipped,
        sand_handled=sand_handled,
    )


__all__ = ["Yields", "yields_of"]
