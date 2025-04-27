"""Costing a shift's sand, and the one number the plant manager reads.

The sand department is measured on cost per ton of *good* iron shipped, and the
"good" is what makes it a sand number rather than a purchasing number. A shift
that saved two hundred dollars of bentonite and scrapped a ton of castings had
an expensive shift, and the only way to see that is to divide by what was
shipped rather than by what was poured.

Water is priced at zero and still appears on the breakdown. It costs nothing
per pound and it is the largest single lever on whether the sand works, so
leaving it off the sheet makes the sheet look like the whole story when it is
not. A zero line that is present says "considered and free"; a missing line says
nothing.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from mullerbox.addition.material import Addition, Material
from mullerbox.errors import BadInputError, RuleError
from mullerbox.units.bulk import POUNDS_PER_TON, Pounds
from mullerbox.units.money import Money, PricePerTon, total_money


@dataclass(frozen=True)
class PriceList:
    """What each material costs, delivered."""

    prices: Mapping[Material, PricePerTon]

    def __post_init__(self) -> None:
        for material, price in self.prices.items():
            if not isinstance(material, Material):
                raise BadInputError("a price list is keyed by material")
            if not isinstance(price, PricePerTon):
                raise BadInputError("a price list holds prices per ton")
        missing = [m.label for m in Material if m not in self.prices]
        if missing:
            raise RuleError(f"the price list has no price for {missing[0]}")

    def price_of(self, material: Material) -> PricePerTon:
        if not isinstance(material, Material):
            raise BadInputError("a material is expected")
        return self.prices[material]


@dataclass(frozen=True)
class Line:
    """One material's contribution to a shift's sand cost."""

    material: Material
    mass: Pounds
    price: PricePerTon
    cost: Money

    def __str__(self) -> str:
        return f"{self.material.label}: {self.mass} at {self.price} = {self.cost}"


@dataclass(frozen=True)
class ShiftCost:
    """A shift's sand additions, priced."""

    lines: tuple[Line, ...]
    good_iron: Pounds

    @property
    def total(self) -> Money:
        return total_money([line.cost for line in self.lines])

    def line_for(self, material: Material) -> Line | None:
        for line in self.lines:
            if line.material is material:
                return line
        return None

    @property
    def per_ton_of_good_iron(self) -> Decimal:
        """Dollars of sand per ton shipped, to the cent.

        Raises rather than returning zero when nothing was shipped. A shift that
        made no good castings has an undefined cost per ton, not a free one, and
        a zero here would average into a month and quietly improve it.
        """
        if self.good_iron.is_zero:
            raise RuleError("no good iron was made, so there is no cost per ton")
        tons = self.good_iron.value / POUNDS_PER_TON
        return (self.total.dollars / tons).quantize(Decimal("0.01"))

    @property
    def heaviest_line(self) -> Line | None:
        """The material that cost the most, which is nearly always new sand."""
        priced = [line for line in self.lines if not line.cost.is_zero]
        if not priced:
            return None
        return max(priced, key=lambda line: line.cost.cents)

    def __str__(self) -> str:
        return f"{self.total} of sand against {self.good_iron} of good iron"


def cost_of(additions: list[Addition], prices: PriceList, good_iron: Pounds) -> ShiftCost:
    """Price a shift's additions, one line per material charged.

    Materials are merged by kind before pricing, so a shift that made three
    bentonite additions gets one bentonite line. The breakdown is what the
    manager reads, and three lines for one material invites the reader to
    compare them against each other rather than against the sand.
    """
    if not isinstance(prices, PriceList):
        raise BadInputError("costing needs a price list")
    if not isinstance(good_iron, Pounds):
        raise BadInputError("good iron is a bulk mass")
    merged: dict[Material, Decimal] = {}
    for addition in additions:
        if not isinstance(addition, Addition):
            raise BadInputError("only additions can be costed")
        merged[addition.material] = merged.get(addition.material, Decimal(0)) + addition.mass.value
    lines: list[Line] = []
    for material in Material:
        if material not in merged:
            continue
        mass = Pounds(merged[material])
        price = prices.price_of(material)
        lines.append(Line(material=material, mass=mass, price=price, cost=price.cost_of(mass)))
    return ShiftCost(lines=tuple(lines), good_iron=good_iron)


__all__ = ["Line", "PriceList", "ShiftCost", "cost_of"]
