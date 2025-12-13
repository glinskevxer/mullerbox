"""Two tests on one sample, and what their disagreement means.

Running a property twice on one sample is the only check a lab has on itself.
Everything else compares the sand against a spec, which cannot distinguish sand
that moved from a bench that is drifting.

The repeatability limit is the number two results from one operator on one
sample should agree within, most of the time. It is a property of the test, not
of the sand: a green compression is repeatable to about a psi and a methylene
blue titration to about a fifth of a point, and those numbers come from the
method rather than from how the shop is running.

**A pair outside the limit does not tell you which one is wrong.** That is the
part shops get wrong: the instinct is to keep the one nearer the target and
discard the other, which is how a bench that reads high stays undetected for
months. The honest answer is that neither result stands and the test is run
again, so this module refuses to pick a survivor and says so.

**The mean of a good pair is better than either of its halves**, and that is
worth taking. A pair inside the limit averages to a number with less noise in it
than a single reading, which is why the lab runs duplicates on the properties it
trusts least.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from mullerbox.errors import BadInputError, RuleError
from mullerbox.props.kind import PropertyKind

# What two results on one sample should agree within, per property, in the
# property's own units. From the AFS method statements.
REPEATABILITY: dict[PropertyKind, Decimal] = {
    PropertyKind.COMPACTABILITY: Decimal("2.0"),
    PropertyKind.GREEN_COMPRESSION: Decimal("1.0"),
    PropertyKind.PERMEABILITY: Decimal("6"),
    PropertyKind.MOISTURE: Decimal("0.15"),
    PropertyKind.MB_CLAY: Decimal("0.20"),
    PropertyKind.TOTAL_CLAY: Decimal("0.30"),
    PropertyKind.LOI: Decimal("0.15"),
    PropertyKind.VOLATILES: Decimal("0.15"),
    PropertyKind.FRIABILITY: Decimal("1.5"),
    PropertyKind.WET_TENSILE: Decimal("0.03"),
    PropertyKind.MOLD_HARDNESS: Decimal("2.0"),
    PropertyKind.SHATTER_INDEX: Decimal("3.0"),
}


@dataclass(frozen=True)
class Pair:
    """Two results on one sample for one property."""

    kind: PropertyKind
    first: Decimal
    second: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.kind, PropertyKind):
            raise BadInputError("a property kind is expected")
        for name in ("first", "second"):
            if not isinstance(getattr(self, name), Decimal):
                raise BadInputError(f"the {name} reading is a decimal")

    @property
    def spread(self) -> Decimal:
        return abs(self.first - self.second)

    @property
    def limit(self) -> Decimal:
        return REPEATABILITY[self.kind]

    @property
    def agrees(self) -> bool:
        return self.spread <= self.limit

    @property
    def mean(self) -> Decimal:
        """The better estimate, which only exists when the pair agrees.

        A disagreeing pair has a mean arithmetically and it is not an estimate
        of anything, so asking for it is refused rather than answered.
        """
        self.require_agreement()
        return ((self.first + self.second) / 2).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    def require_agreement(self) -> None:
        """Refuse to hand out a number from a pair that did not repeat."""
        if not self.agrees:
            raise RuleError(
                f"the two {self.kind.label} results differ by {self.spread}, past "
                f"the {self.limit} repeatability limit, so neither one stands "
                "and the test is run again"
            )

    def __str__(self) -> str:
        state = "agrees" if self.agrees else "DOES NOT REPEAT"
        return (
            f"{self.kind.label} {self.first} and {self.second}, "
            f"spread {self.spread} against {self.limit}, {state}"
        )


def limit_for(kind: PropertyKind) -> Decimal:
    """What two results on one sample should agree within."""
    if not isinstance(kind, PropertyKind):
        raise BadInputError("a property kind is expected")
    return REPEATABILITY[kind]


def check(kind: PropertyKind, first: Decimal, second: Decimal) -> Pair:
    """Build a pair and report whether it repeated."""
    return Pair(kind=kind, first=first, second=second)


def worst(pairs: list[Pair]) -> Pair | None:
    """The pair furthest past its own limit, for the bench's own control chart.

    Ranked by how far past the limit rather than by raw spread, because the
    limits differ by an order of magnitude between properties and a raw spread
    ranking would put permeability at the top of every list.
    """
    for pair in pairs:
        if not isinstance(pair, Pair):
            raise BadInputError("only pairs can be ranked")
    failing = [p for p in pairs if not p.agrees]
    if not failing:
        return None
    return max(failing, key=lambda p: p.spread / p.limit)


__all__ = ["Pair", "REPEATABILITY", "check", "limit_for", "worst"]
