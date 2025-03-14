"""A pour, and the one ratio that governs everything downstream of it.

The sand to metal ratio is the mass of sand in the molds divided by the mass of
metal poured into them. It is the single number that decides how hard the shift
was on the sand, and it is the input to every addition the muller makes
afterwards.

Low ratio means little sand around a lot of metal, so a large share of the sand
in the system gets hot enough to matter. High ratio means the heat is spread
through more sand and less of it is damaged. A jobbing foundry runs anywhere
from three to one on heavy work up to ten to one on small light castings, and
the difference between those two shifts is roughly a factor of three in how much
bentonite has to go back in.

The ratio is a property of the pour rather than of the sand, which is the part
that catches people out: nothing the lab measures tells you what it was. It has
to come off the pour record, and a sand system reconciled without it will be
chasing its bond level all week.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from mullerbox.errors import BadInputError
from mullerbox.spec.pattern import PatternClass
from mullerbox.units.bulk import Pounds

# Outside this a pour record is a typo. Under two to one there is not enough
# sand to hold the metal, and over twenty to one somebody poured a test bar.
MIN_RATIO = Decimal("2")
MAX_RATIO = Decimal("20")


@dataclass(frozen=True)
class Pour:
    """One shift's worth of metal into one shift's worth of molds."""

    poured_on: date
    pattern: PatternClass
    metal: Pounds
    sand: Pounds

    def __post_init__(self) -> None:
        if not isinstance(self.poured_on, date):
            raise BadInputError("a pour is dated")
        if not isinstance(self.pattern, PatternClass):
            raise BadInputError("a pour names the pattern class it ran")
        if not isinstance(self.metal, Pounds):
            raise BadInputError("metal poured is a bulk mass")
        if not isinstance(self.sand, Pounds):
            raise BadInputError("sand in the molds is a bulk mass")
        if self.metal.is_zero:
            raise BadInputError("a pour with no metal in it is not a pour")
        if self.sand.is_zero:
            raise BadInputError("a pour with no sand in it is not a pour")

    @property
    def sand_to_metal(self) -> Decimal:
        """Pounds of sand per pound of metal."""
        return self.sand.ratio_to(self.metal)

    @property
    def is_plausible(self) -> bool:
        return MIN_RATIO <= self.sand_to_metal <= MAX_RATIO

    def require_plausible(self) -> Decimal:
        """The ratio, or a refusal naming what was recorded."""
        ratio = self.sand_to_metal
        if not self.is_plausible:
            raise BadInputError(
                f"a sand to metal ratio of {ratio} to 1 is not a pour record: "
                f"{self.sand} of sand against {self.metal} of metal"
            )
        return ratio

    @property
    def severity(self) -> Decimal:
        """How hard this pour was on the sand, as a multiple of a six to one shift.

        Six to one is the middle of the jobbing range and the ratio the shop's
        published addition rates were written against, so it reads as one and
        everything else reads as a multiple of it. A three to one shift comes
        back as two, and it takes about twice the bentonite.
        """
        return (Decimal(6) / self.require_plausible()).quantize(Decimal("0.001"))

    def __str__(self) -> str:
        return f"{self.poured_on} {self.pattern.label} {self.sand_to_metal}:1"


def combined(pours: list[Pour]) -> Decimal:
    """The mass weighted sand to metal ratio across several pours.

    Averaging the ratios themselves is the obvious move and it is wrong: a two
    ladle pour and a forty ladle pour would count equally, and the small one is
    usually the odd one. Summing the masses first weights each pour by how much
    metal actually went through it.
    """
    if not pours:
        raise BadInputError("no pours to combine")
    metal = Decimal(0)
    sand = Decimal(0)
    for pour in pours:
        if not isinstance(pour, Pour):
            raise BadInputError("only pours can be combined")
        metal += pour.metal.value
        sand += pour.sand.value
    return (sand / metal).quantize(Decimal("0.01"))


__all__ = ["MAX_RATIO", "MIN_RATIO", "Pour", "combined"]
