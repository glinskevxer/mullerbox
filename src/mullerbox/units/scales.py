"""The two readings that are numbers without being quantities.

Permeability is an AFS number. It is defined by the apparatus rather than by
physics: the volume of air that passes a standard specimen at a standard
pressure in a standard time, scaled so that the answer comes out as a round
figure. It has no unit and it does not convert to anything.

Mold hardness is a B scale reading off a spring loaded indenter, zero to a
hundred, and the hundred is a hard stop rather than a percentage of anything.

Both are held here rather than as bare integers because both get compared
against bands, and a bare integer compared against the wrong band is the failure
this whole package exists to prevent. Neither will compare against the other.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from functools import total_ordering
from typing import Any

from mullerbox.errors import BadInputError
from mullerbox.units.coerce import to_decimal, to_int

# Green sand runs 50 to 150 AFS. A number past a thousand is the meter left on
# the wrong orifice, which reads high by about an order of magnitude.
MAX_PERMEABILITY = 1000
MAX_HARDNESS = Decimal("100")


@total_ordering
@dataclass(frozen=True, init=False, eq=False)
class Permeability:
    """An AFS permeability number, which is a whole number by definition."""

    value: int

    def __init__(self, value: object) -> None:
        number = to_int(value, "a permeability number")
        if number < 0:
            raise BadInputError("a permeability number cannot be negative")
        if number > MAX_PERMEABILITY:
            raise BadInputError(f"{number} is not a green sand permeability")
        object.__setattr__(self, "value", number)

    @property
    def vents_freely(self) -> bool:
        """Rough shop rule: under about forty and the mold will not breathe."""
        return self.value >= 40

    def __str__(self) -> str:
        return f"{self.value} AFS"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Permeability):
            return self.value == other.value
        return NotImplemented

    def __hash__(self) -> int:
        return hash(("Permeability", self.value))

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Permeability):
            return bool(self.value < other.value)
        return NotImplemented


@total_ordering
@dataclass(frozen=True, init=False, eq=False)
class Hardness:
    """A mold hardness reading on the B scale, zero to a hundred."""

    value: Decimal

    def __init__(self, value: object) -> None:
        reading = to_decimal(value, "a hardness").quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        if reading < 0:
            raise BadInputError("a hardness cannot be negative")
        if reading > MAX_HARDNESS:
            raise BadInputError("the B scale stops at a hundred")
        object.__setattr__(self, "value", reading)

    def __str__(self) -> str:
        return f"{self.value} B"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Hardness):
            return self.value == other.value
        return NotImplemented

    def __hash__(self) -> int:
        return hash(("Hardness", self.value))

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Hardness):
            return bool(self.value < other.value)
        return NotImplemented


__all__ = ["MAX_HARDNESS", "MAX_PERMEABILITY", "Hardness", "Permeability"]
