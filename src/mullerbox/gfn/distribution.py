"""How tightly the sand piles up, which the fineness number cannot tell you.

The lab classifies a distribution by how much of it lands on adjacent screens.
A sand with seventy percent of its mass on three screens next to each other is a
"three screen" sand: uniform grains, predictable packing, high permeability for
its fineness, and it takes less bond because there is less surface area to coat.
A sand that needs five or six screens to reach the same share is spread: the
fines sit in the voids between the coarse grains, permeability collapses, and
the bond demand goes up even though the fineness number has not moved.

The screens have to be *adjacent on the series*, which is the part worth being
careful about. Three screens holding seventy percent between them means nothing
if they are the 20, the 70 and the 200 — that is a gap graded sand and it is the
worst of both. So the window slides over the series in stack order and the pan
is left out of it, because the pan is not a screen the sand sat on, it is what
fell through everything.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from mullerbox.errors import BadInputError
from mullerbox.gfn.fineness import Fineness
from mullerbox.units.mesh import Mesh
from mullerbox.units.percent import Percent

THREE_SCREEN_SHARE = Decimal("70")
FOUR_SCREEN_SHARE = Decimal("80")

# Anything through the 200 is flour as far as venting is concerned.
FINES_SCREENS = (200, 270)


class Grading(Enum):
    """How concentrated a distribution is.

    Ordered coarse-grained to fine-grained in the sense of *classification*
    quality, not of sand size: THREE is the tightest and SPREAD is the loosest.
    """

    THREE_SCREEN = "three screen"
    FOUR_SCREEN = "four screen"
    SPREAD = "spread"

    @property
    def is_uniform(self) -> bool:
        return self in {Grading.THREE_SCREEN, Grading.FOUR_SCREEN}


@dataclass(frozen=True)
class Window:
    """The best run of adjacent screens, and what it holds."""

    screens: tuple[Mesh, ...]
    share: Percent

    @property
    def labels(self) -> tuple[str, ...]:
        return tuple(s.label for s in self.screens)


@dataclass(frozen=True)
class Distribution:
    """A graded reading of one fineness result."""

    fineness: Fineness
    grading: Grading
    best_three: Window
    best_four: Window
    fines: Percent

    @property
    def is_uniform(self) -> bool:
        return self.grading.is_uniform

    def __str__(self) -> str:
        return f"{self.fineness} {self.grading.value}"


def _sliding_best(holdings: list[tuple[Mesh, Percent]], width: int) -> Window:
    """The adjacent run of ``width`` screens holding the most, ties to the coarse end."""
    if width <= 0:
        raise BadInputError("a window covers at least one screen")
    if len(holdings) < width:
        raise BadInputError(
            f"a window of {width} needs {width} working screens, the series has {len(holdings)}"
        )
    best_share = Decimal(-1)
    best_at = 0
    for start in range(len(holdings) - width + 1):
        share = sum((pct.value for _, pct in holdings[start : start + width]), Decimal(0))
        if share > best_share:
            best_share = share
            best_at = start
    run = holdings[best_at : best_at + width]
    return Window(
        screens=tuple(mesh for mesh, _ in run),
        share=Percent(best_share),
    )


def grade(fineness: Fineness) -> Distribution:
    """Classify a fineness result by how tightly its mass is grouped."""
    if not isinstance(fineness, Fineness):
        raise BadInputError("a grading is read off a fineness result")
    working = [(mesh, pct) for mesh, pct in fineness.spread if not mesh.is_pan]
    best_three = _sliding_best(working, 3)
    best_four = _sliding_best(working, 4)
    if best_three.share.value >= THREE_SCREEN_SHARE:
        grading = Grading.THREE_SCREEN
    elif best_four.share.value >= FOUR_SCREEN_SHARE:
        grading = Grading.FOUR_SCREEN
    else:
        grading = Grading.SPREAD
    fines = Percent(
        sum(
            (pct.value for mesh, pct in fineness.spread if mesh.number in FINES_SCREENS),
            Decimal(0),
        )
    )
    return Distribution(
        fineness=fineness,
        grading=grading,
        best_three=best_three,
        best_four=best_four,
        fines=fines,
    )


__all__ = [
    "FINES_SCREENS",
    "FOUR_SCREEN_SHARE",
    "THREE_SCREEN_SHARE",
    "Distribution",
    "Grading",
    "Window",
    "grade",
]
