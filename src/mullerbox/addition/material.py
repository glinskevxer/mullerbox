"""The four things that go into a muller batch, and what an addition is.

An addition carries its reason as well as its mass. That is not documentation.
The mass alone is unauditable: a hundred and forty pounds of bentonite is
correct or badly wrong depending on whether it was worked out against a bond
deficit, a burnout replacement, or somebody's memory of last Tuesday, and the
number looks identical in all three cases. When the sand goes off and the shift
gets reconstructed, the reason is the only part that says which calculation was
being run.

Materials are not interchangeable and the type says so. Every one of them has a
different yield, a different price, and a different consequence for getting it
wrong, and the one thing they share is being measured in pounds.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from mullerbox.errors import BadInputError
from mullerbox.units.bulk import Pounds


class Material(Enum):
    """What can be charged into a muller batch."""

    BENTONITE = "bentonite"
    SEACOAL = "seacoal"
    NEW_SAND = "new sand"
    WATER = "water"

    @property
    def label(self) -> str:
        return self.value

    @property
    def yield_factor(self) -> Decimal:
        """How much of what goes in survives to be measured.

        Bentonite arrives with some of its swelling capacity already used up by
        storage and does not fully develop in one mull, so a point of bentonite
        does not read as a point of methylene blue clay. Seacoal loses its
        volatiles the same way. New sand and water are what they are.
        """
        return _YIELD[self]

    @property
    def is_dry(self) -> bool:
        return self is not Material.WATER


_YIELD: dict[Material, Decimal] = {
    Material.BENTONITE: Decimal("0.85"),
    Material.SEACOAL: Decimal("0.90"),
    Material.NEW_SAND: Decimal("1.00"),
    Material.WATER: Decimal("1.00"),
}


@dataclass(frozen=True)
class Addition:
    """One material, one mass, and why."""

    material: Material
    mass: Pounds
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.material, Material):
            raise BadInputError("an addition is of a material")
        if not isinstance(self.mass, Pounds):
            raise BadInputError("an addition is a bulk mass")
        if not self.reason.strip():
            raise BadInputError("an addition records why it was made")

    @classmethod
    def nothing(cls, material: Material, reason: str) -> Addition:
        """A zero addition, which is a decision and not an absence.

        The muller operator needs to be able to tell "the calculation said add
        nothing" from "nobody ran the calculation". Both produce no bentonite in
        the batch and only one of them is fine.
        """
        return cls(material=material, mass=Pounds.zero(), reason=reason)

    @property
    def is_nothing(self) -> bool:
        return self.mass.is_zero

    def __str__(self) -> str:
        return f"{self.mass} {self.material.label} ({self.reason})"


def dry_total(additions: list[Addition]) -> Pounds:
    """Everything except the water, which is what changes the batch mass on paper."""
    running = Decimal(0)
    for addition in additions:
        if not isinstance(addition, Addition):
            raise BadInputError("only additions can be totalled")
        if addition.material.is_dry:
            running += addition.mass.value
    return Pounds(running)


__all__ = ["Addition", "Material", "dry_total"]
