"""Sieve designations and the aperture behind them.

A screen is named by its mesh number, which is wires per inch and therefore goes
*up* as the opening goes *down*. Everything about sieve work reads backwards
because of this: the coarse end of a stack is the low numbers, a sand that has
"gone finer" has moved onto higher numbers, and a stack is built in descending
aperture order which is ascending mesh order.

Getting that backwards is the classic sand lab software bug, so ordering is
defined once, here, on aperture rather than on the number. A ``Mesh`` sorts
coarse to fine, which is the order a stack is assembled in and the order an
analysis is reported in.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from functools import total_ordering
from typing import Any

from mullerbox.errors import BadInputError
from mullerbox.units.coerce import to_int

# The pan sits under the stack and has no opening at all. It is a screen for
# every purpose except sieving, so it needs a place in the ordering, and zero
# aperture puts it at the fine end where it belongs.
PAN_MESH = 0
PAN_LABEL = "PAN"

MIN_MESH = 3
MAX_MESH = 400


@total_ordering
@dataclass(frozen=True, init=False, eq=False)
class Mesh:
    """One sieve designation, with the aperture it stands for in micrometres.

    Aperture is carried rather than looked up because the series in use is not
    always the US one, and two series can put different openings behind the same
    number. A screen that does not know its own opening cannot be ordered
    against a screen from another series, and mixing series in one stack is a
    real thing that happens when a screen is replaced from the wrong drawer.
    """

    number: int
    micrometres: int

    def __init__(self, number: object, micrometres: object) -> None:
        num = to_int(number, "a mesh number")
        aperture = to_int(micrometres, "an aperture")
        if num == PAN_MESH:
            if aperture != 0:
                raise BadInputError("the pan has no aperture")
        else:
            if num < MIN_MESH or num > MAX_MESH:
                raise BadInputError(f"mesh {num} is not a sand lab screen")
            if aperture <= 0:
                raise BadInputError(f"mesh {num} needs an aperture above zero")
        object.__setattr__(self, "number", num)
        object.__setattr__(self, "micrometres", aperture)

    @classmethod
    def pan(cls) -> Mesh:
        """The pan at the bottom of every stack."""
        return cls(PAN_MESH, 0)

    @property
    def is_pan(self) -> bool:
        return self.number == PAN_MESH

    @property
    def label(self) -> str:
        return PAN_LABEL if self.is_pan else str(self.number)

    @property
    def millimetres(self) -> Decimal:
        return (Decimal(self.micrometres) / 1000).quantize(Decimal("0.001"))

    def is_coarser_than(self, other: Mesh) -> bool:
        """A bigger opening, which is a smaller mesh number."""
        if not isinstance(other, Mesh):
            raise BadInputError("a screen only compares against a screen")
        return self.micrometres > other.micrometres

    def is_finer_than(self, other: Mesh) -> bool:
        if not isinstance(other, Mesh):
            raise BadInputError("a screen only compares against a screen")
        return self.micrometres < other.micrometres

    def __str__(self) -> str:
        if self.is_pan:
            return PAN_LABEL
        return f"{self.number} ({self.micrometres} um)"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Mesh):
            return (self.number, self.micrometres) == (other.number, other.micrometres)
        return NotImplemented

    def __hash__(self) -> int:
        return hash(("Mesh", self.number, self.micrometres))

    def __lt__(self, other: Any) -> bool:
        """Coarse before fine, so a sorted stack reads top to bottom."""
        if isinstance(other, Mesh):
            return bool(self.micrometres > other.micrometres)
        return NotImplemented


def parse_mesh_label(text: str, micrometres: object) -> Mesh:
    """Read a screen off a bench sheet, where the pan is spelled out."""
    label = text.strip().upper()
    if label in {PAN_LABEL, "PAN.", "P"}:
        return Mesh.pan()
    try:
        number = int(label)
    except ValueError:
        raise BadInputError(f"{text!r} is not a screen designation") from None
    return Mesh(number, micrometres)


__all__ = [
    "MAX_MESH",
    "MIN_MESH",
    "PAN_LABEL",
    "PAN_MESH",
    "Mesh",
    "parse_mesh_label",
]
