"""Two benches measuring one sample, and which of them is drifting.

Duplicates on one bench catch a bench that has become noisy. They cannot catch a
bench that has become *wrong*, because a wrong bench repeats beautifully. The
only thing that catches that is a second bench, and the only way to use a second
bench is to split one sample and run both.

**The limit is wider than the repeatability limit, by root two.** Two results
from one bench carry one bench's noise. Two results from two benches carry both,
and independent noise adds in quadrature, so the expected spread is larger by a
factor of the square root of two. Using the repeatability limit here would flag
half of all honest comparisons, and a check that cries wolf gets turned off.

**A bias is directional and a spread is not.** The whole value of a cross check
is knowing which bench reads high, so the difference keeps its sign and the
report names the instrument rather than the pair.

**One comparison proves nothing about which bench is right.** Two benches
disagreeing tells you one of them is off; it takes a third, or a reference
sample of known value, to say which. So this module reports the disagreement and
the direction, and refuses to nominate a culprit.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from mullerbox.errors import BadInputError
from mullerbox.props.duplicate import limit_for
from mullerbox.props.kind import PropertyKind

# Two independent benches spread wider than one. Root two, to four places.
INDEPENDENCE_FACTOR = Decimal("1.4142")


@dataclass(frozen=True)
class Comparison:
    """One property measured on two benches from one split sample."""

    kind: PropertyKind
    sample_id: str
    first_tag: str
    first_reading: Decimal
    second_tag: str
    second_reading: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.kind, PropertyKind):
            raise BadInputError("a property kind is expected")
        if not self.sample_id.strip():
            raise BadInputError("a comparison names the sample it split")
        for name in ("first_tag", "second_tag"):
            if not str(getattr(self, name)).strip():
                raise BadInputError("a comparison names both instruments")
        if self.first_tag == self.second_tag:
            raise BadInputError(
                f"both readings came off {self.first_tag}, which is a duplicate "
                "rather than a cross check"
            )
        for name in ("first_reading", "second_reading"):
            if not isinstance(getattr(self, name), Decimal):
                raise BadInputError(f"the {name.replace('_', ' ')} is a decimal")

    @property
    def bias(self) -> Decimal:
        """How much the second bench reads above the first. Signed."""
        return self.second_reading - self.first_reading

    @property
    def limit(self) -> Decimal:
        """What two independent benches should agree within."""
        return (limit_for(self.kind) * INDEPENDENCE_FACTOR).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )

    @property
    def agrees(self) -> bool:
        return abs(self.bias) <= self.limit

    @property
    def high_bench(self) -> str | None:
        """The instrument reading higher, when they disagree at all."""
        if self.bias == 0:
            return None
        return self.second_tag if self.bias > 0 else self.first_tag

    def finding(self) -> str:
        """What the comparison says, without nominating a culprit."""
        if self.agrees:
            return (
                f"{self.first_tag} and {self.second_tag} agree on "
                f"{self.kind.label} within {self.limit}"
            )
        return (
            f"{self.first_tag} and {self.second_tag} differ by {abs(self.bias)} on "
            f"{self.kind.label}, past the {self.limit} cross check limit; "
            f"{self.high_bench} reads higher. One of them is off and this "
            "comparison cannot say which"
        )

    def __str__(self) -> str:
        return self.finding()


def cross_check_limit(kind: PropertyKind) -> Decimal:
    """What two benches should agree within, which is wider than one bench."""
    if not isinstance(kind, PropertyKind):
        raise BadInputError("a property kind is expected")
    return (limit_for(kind) * INDEPENDENCE_FACTOR).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )


def average_bias(comparisons: list[Comparison]) -> Decimal:
    """The mean bias over several comparisons of the same pair, signed.

    One comparison cannot separate a real bias from a bad pair of readings.
    Several in the same direction can, which is why the average is worth having
    and a single comparison's bias is not worth acting on.
    """
    if not comparisons:
        raise BadInputError("no comparisons to average")
    pairs = set()
    for comparison in comparisons:
        if not isinstance(comparison, Comparison):
            raise BadInputError("only comparisons can be averaged")
        pairs.add((comparison.kind, comparison.first_tag, comparison.second_tag))
    if len(pairs) > 1:
        raise BadInputError(
            "these comparisons are not all the same property on the same two "
            "benches, so their biases do not average"
        )
    total = sum((c.bias for c in comparisons), Decimal(0))
    return (total / len(comparisons)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


__all__ = [
    "Comparison",
    "INDEPENDENCE_FACTOR",
    "average_bias",
    "cross_check_limit",
]
