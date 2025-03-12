"""The strength readings, which come off three different instruments in three
different units and get compared to each other constantly.

Green compression strength is pounds per square inch. Wet tensile strength is
grams per square centimetre and is a much smaller number for a much smaller
force. Splitting strength and hot strength are psi again. The lab talks about
all of them as "strength" and a control chart will happily plot a wet tensile
against a green compression band if nothing stops it, so the units are separate
types that do not compare against each other.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from functools import total_ordering
from typing import Any

from mullerbox.errors import BadInputError
from mullerbox.units.coerce import to_decimal

PSI_PLACES = Decimal("0.1")
WET_TENSILE_PLACES = Decimal("0.01")

# Green sand runs 15 to 35 psi. A hundred is bonded sand, not green sand, and
# a thousand is somebody reading the hot strength scale on the wrong rig.
MAX_PSI = Decimal("1000")
MAX_WET_TENSILE = Decimal("100")


SUFFIXES = ("psi", "g/cm2", "g/cm^2", "gcm2")


def _decimal_from(value: object, what: str) -> Decimal:
    return to_decimal(value, what, suffixes=SUFFIXES)


@total_ordering
@dataclass(frozen=True, init=False, eq=False)
class Psi:
    """Pounds per square inch, to a tenth, which is what the gauge reads."""

    value: Decimal

    def __init__(self, value: object) -> None:
        psi = _decimal_from(value, "a pressure").quantize(PSI_PLACES, rounding=ROUND_HALF_UP)
        if psi < 0:
            raise BadInputError("a strength cannot be negative")
        if psi > MAX_PSI:
            raise BadInputError(f"{psi} psi is not a green sand strength")
        object.__setattr__(self, "value", psi)

    @classmethod
    def zero(cls) -> Psi:
        return cls(0)

    def __add__(self, other: object) -> Psi:
        if not isinstance(other, Psi):
            return NotImplemented
        return Psi(self.value + other.value)

    def __sub__(self, other: object) -> Psi:
        if not isinstance(other, Psi):
            return NotImplemented
        gap = self.value - other.value
        return Psi(gap if gap > 0 else Decimal(0))

    def scaled(self, factor: object) -> Psi:
        if isinstance(factor, Psi):
            raise BadInputError("a pressure times a pressure is not a pressure")
        if not isinstance(factor, str | int | Decimal | float):
            raise BadInputError(f"cannot scale a pressure by {type(factor).__name__}")
        ratio = factor if isinstance(factor, Decimal) else Decimal(str(factor))
        if ratio < 0:
            raise BadInputError("cannot scale a pressure by a negative ratio")
        return Psi(self.value * ratio)

    def __str__(self) -> str:
        return f"{self.value} psi"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Psi):
            return self.value == other.value
        return NotImplemented

    def __hash__(self) -> int:
        return hash(("Psi", self.value))

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Psi):
            return bool(self.value < other.value)
        return NotImplemented


@total_ordering
@dataclass(frozen=True, init=False, eq=False)
class WetTensile:
    """Grams per square centimetre, to a hundredth.

    Deliberately not convertible to psi. The conversion exists in physics and
    the lab never does it, because the wet tensile band and the green
    compression band were set independently against different failure modes and
    a number moved from one scale to the other means nothing against the other's
    band.
    """

    value: Decimal

    def __init__(self, value: object) -> None:
        wt = _decimal_from(value, "a wet tensile").quantize(
            WET_TENSILE_PLACES, rounding=ROUND_HALF_UP
        )
        if wt < 0:
            raise BadInputError("a wet tensile cannot be negative")
        if wt > MAX_WET_TENSILE:
            raise BadInputError(f"{wt} g/cm2 is not a wet tensile reading")
        object.__setattr__(self, "value", wt)

    @classmethod
    def zero(cls) -> WetTensile:
        return cls(0)

    def __str__(self) -> str:
        return f"{self.value} g/cm2"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, WetTensile):
            return self.value == other.value
        return NotImplemented

    def __hash__(self) -> int:
        return hash(("WetTensile", self.value))

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, WetTensile):
            return bool(self.value < other.value)
        return NotImplemented


__all__ = [
    "MAX_PSI",
    "MAX_WET_TENSILE",
    "PSI_PLACES",
    "WET_TENSILE_PLACES",
    "Psi",
    "WetTensile",
]
