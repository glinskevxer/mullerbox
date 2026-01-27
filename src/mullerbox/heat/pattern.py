"""The pattern register: what the shop actually makes, and what each one demands.

A pattern class is a family. A pattern is a specific thing with a specific
flask, a specific weight and a specific number of cavities, and the sand to
metal ratio it runs at is a property of the pattern rather than of the class.
So the class decides how the sand is judged and the pattern decides what the
pour record should have said.

That second use is the interesting one. A pour record is typed by a person and
it is the one number in this package nothing can check, except like this: a
pattern with a known flask and a known casting weight has an expected ratio, and
a shift whose recorded ratio is a long way off it has a bad pour record rather
than an unusual day. Catching that matters because the ratio drives every
addition, so a typo in the pour log dopes the system for a week.

**Expected ratio comes from the geometry, not from history.** Averaging what a
pattern has done before would launder a persistent typo into the expectation.
Flask volume times sand density, over cavities times casting weight, is
arithmetic on numbers somebody measured once.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from mullerbox.errors import BadInputError, RuleError
from mullerbox.spec.pattern import PatternClass
from mullerbox.units.bulk import Pounds

# Rammed green sand runs about ninety five pounds a cubic foot.
SAND_DENSITY = Decimal("95")

# How far a recorded ratio may sit from the expected one before the pour record
# is more likely wrong than the shift unusual.
RATIO_TOLERANCE = Decimal("0.35")


@dataclass(frozen=True)
class Pattern:
    """One pattern on the register."""

    pattern_id: str
    name: str
    pattern_class: PatternClass
    flask_cubic_feet: Decimal
    cavities: int
    casting_weight: Pounds

    def __post_init__(self) -> None:
        if not self.pattern_id.strip():
            raise BadInputError("a pattern needs an identifier")
        if not self.name.strip():
            raise BadInputError("a pattern needs a name")
        if not isinstance(self.pattern_class, PatternClass):
            raise BadInputError("a pattern belongs to a pattern class")
        if not isinstance(self.flask_cubic_feet, Decimal):
            raise BadInputError("the flask volume is a decimal")
        if self.flask_cubic_feet <= 0:
            raise BadInputError("a flask with no volume is not a flask")
        if isinstance(self.cavities, bool) or not isinstance(self.cavities, int):
            raise BadInputError("the cavity count is a whole number")
        if self.cavities <= 0:
            raise BadInputError("a pattern with no cavities makes nothing")
        if not isinstance(self.casting_weight, Pounds):
            raise BadInputError("a casting weight is a bulk mass")
        if self.casting_weight.is_zero:
            raise BadInputError("a casting with no weight is not a casting")

    @property
    def sand_per_mold(self) -> Pounds:
        """What the flask holds, less what the castings displace."""
        gross = self.flask_cubic_feet * SAND_DENSITY
        displaced = self.metal_per_mold.value / Decimal("450")  # iron, lb per cu ft
        net = gross - displaced * SAND_DENSITY
        if net <= 0:
            raise RuleError(f"pattern {self.pattern_id} displaces more than its flask holds")
        return Pounds(net.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    @property
    def metal_per_mold(self) -> Pounds:
        return self.casting_weight.scaled(self.cavities)

    @property
    def expected_ratio(self) -> Decimal:
        """Sand to metal from the geometry, never from what it has done before."""
        return self.sand_per_mold.ratio_to(self.metal_per_mold)

    def ratio_looks_wrong(self, recorded: Decimal) -> bool:
        """Whether a recorded ratio is far enough off to suspect the pour record."""
        if not isinstance(recorded, Decimal):
            raise BadInputError("a recorded ratio is a decimal")
        if recorded <= 0:
            raise BadInputError("a recorded ratio is above zero")
        expected = self.expected_ratio
        return abs(recorded - expected) / expected > RATIO_TOLERANCE

    def check_ratio(self, recorded: Decimal) -> str:
        """One line about a recorded ratio against what the geometry says."""
        expected = self.expected_ratio
        if not self.ratio_looks_wrong(recorded):
            return (
                f"{self.pattern_id} recorded {recorded}:1 against an expected "
                f"{expected}:1, which is normal"
            )
        return (
            f"{self.pattern_id} recorded {recorded}:1 against an expected "
            f"{expected}:1; check the pour record before dosing against it"
        )

    def __str__(self) -> str:
        return (
            f"{self.pattern_id} {self.name}: {self.cavities} up, {self.expected_ratio}:1 expected"
        )


@dataclass(frozen=True)
class Register:
    """Every pattern the shop runs."""

    patterns: tuple[Pattern, ...]

    def __post_init__(self) -> None:
        ids = [p.pattern_id for p in self.patterns]
        if len(set(ids)) != len(ids):
            raise RuleError("two patterns share an identifier")

    def find(self, pattern_id: str) -> Pattern:
        for pattern in self.patterns:
            if pattern.pattern_id == pattern_id:
                return pattern
        raise BadInputError(f"no pattern {pattern_id!r} on the register")

    def of_class(self, pattern_class: PatternClass) -> tuple[Pattern, ...]:
        if not isinstance(pattern_class, PatternClass):
            raise BadInputError("a pattern class is expected")
        return tuple(p for p in self.patterns if p.pattern_class is pattern_class)

    @property
    def classes(self) -> frozenset[PatternClass]:
        return frozenset(p.pattern_class for p in self.patterns)

    def __len__(self) -> int:
        return len(self.patterns)


__all__ = ["Pattern", "RATIO_TOLERANCE", "Register", "SAND_DENSITY"]
