"""Sand cost against budget, and why the variance has to be split.

A month over budget is one number and two completely different problems, and
they are fixed by different departments.

**Rate variance** is paying more per ton than the budget assumed. That is
purchasing: the bentonite went up, or a delivery came in on a spot price.

**Usage variance** is using more tons than the budget assumed for the iron
shipped. That is the sand department: the system is taking more bond, or the
dilution is running high, or the mass figure is wrong.

Reported as one number they cancel, and a month where purchasing saved five
percent while the muller overdosed by five percent reads as on budget. So they
are split, always, and the split is the report rather than a note under it.

**The budget is per ton of good iron, not per month.** A month that shipped
half its plan is not under budget for having spent less; it spent more per ton.
Budgeting in absolute money makes a bad month look thrifty, which is the one
thing a cost report must not do.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from mullerbox.addition.material import Material
from mullerbox.charge.cost import ShiftCost
from mullerbox.errors import BadInputError, RuleError
from mullerbox.units.bulk import POUNDS_PER_TON, Pounds
from mullerbox.units.money import Money, PricePerTon

_PLACES = Decimal("0.01")


@dataclass(frozen=True)
class Budget:
    """What a ton of good iron was supposed to cost in sand, and on what basis."""

    material: Material
    pounds_per_ton: Decimal
    price: PricePerTon

    def __post_init__(self) -> None:
        if not isinstance(self.material, Material):
            raise BadInputError("a budget is for a material")
        if not isinstance(self.pounds_per_ton, Decimal):
            raise BadInputError("the budgeted usage is a decimal")
        if self.pounds_per_ton < 0:
            raise BadInputError("a budgeted usage cannot be negative")
        if not isinstance(self.price, PricePerTon):
            raise BadInputError("the budgeted price is a price per ton")

    def cost_per_ton(self) -> Money:
        """What this material was budgeted to cost per ton of good iron."""
        return self.price.cost_of(Pounds(self.pounds_per_ton))

    def expected_usage(self, good_iron: Pounds) -> Pounds:
        """How much of it the budget allowed for a given tonnage shipped."""
        if not isinstance(good_iron, Pounds):
            raise BadInputError("good iron is a bulk mass")
        tons = good_iron.value / POUNDS_PER_TON
        return Pounds((self.pounds_per_ton * tons).quantize(_PLACES))


@dataclass(frozen=True)
class Variance:
    """One material's overspend, split into its two causes."""

    material: Material
    budgeted: Money
    actual: Money
    rate: Decimal
    usage: Decimal

    @property
    def total(self) -> Decimal:
        """The whole variance, in dollars. Positive means over budget."""
        return (self.rate + self.usage).quantize(_PLACES, rounding=ROUND_HALF_UP)

    @property
    def cancels_out(self) -> bool:
        """True when the two halves point opposite ways and hide each other."""
        return (self.rate > 0) != (self.usage > 0) and self.rate != 0 and self.usage != 0

    def finding(self) -> str:
        if self.cancels_out:
            return (
                f"{self.material.label}: rate {self.rate:+}, usage {self.usage:+}, "
                f"netting {self.total:+}. The two point opposite ways and would "
                "read as on budget if they were not split"
            )
        return (
            f"{self.material.label}: rate {self.rate:+}, usage {self.usage:+}, total {self.total:+}"
        )

    def __str__(self) -> str:
        return self.finding()


def variance_of(budget: Budget, actual: ShiftCost, good_iron: Pounds) -> Variance:
    """Split one material's overspend into rate and usage.

    Rate variance is the price difference over the actual quantity; usage
    variance is the quantity difference at the budgeted price. That assignment
    puts the joint term with the rate, which is the standard convention and is
    stated here because the other convention gives different numbers and both
    look right.
    """
    if not isinstance(budget, Budget):
        raise BadInputError("a budget is expected")
    if not isinstance(actual, ShiftCost):
        raise BadInputError("a costed shift is expected")
    if not isinstance(good_iron, Pounds):
        raise BadInputError("good iron is a bulk mass")
    if good_iron.is_zero:
        raise RuleError("no good iron was made, so there is nothing to budget against")
    line = actual.line_for(budget.material)
    used = line.mass if line is not None else Pounds.zero()
    spent = line.cost if line is not None else Money.zero()
    allowed = budget.expected_usage(good_iron)
    at_budget_price = budget.price.cost_of(used)
    rate = (spent.dollars - at_budget_price.dollars).quantize(_PLACES, rounding=ROUND_HALF_UP)
    usage = (budget.price.cost_of(used).dollars - budget.price.cost_of(allowed).dollars).quantize(
        _PLACES, rounding=ROUND_HALF_UP
    )
    return Variance(
        material=budget.material,
        budgeted=budget.price.cost_of(allowed),
        actual=spent,
        rate=rate,
        usage=usage,
    )


__all__ = ["Budget", "Variance", "variance_of"]
