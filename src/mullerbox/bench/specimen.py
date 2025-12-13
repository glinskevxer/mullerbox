"""The rammed specimen, which every green sand number is measured on.

A green compression strength is not a property of the sand. It is a property of
a two inch cylinder of that sand rammed three times with a fourteen pound weight
falling two inches, and every part of that sentence matters. Ram it twice and it
reads low; ram it four times and it reads high; use a slightly short tube and it
reads high again. The AFS procedure exists so that two labs comparing numbers
are comparing sand rather than technique.

**The height tolerance is the check that the ram count was right.** A correctly
made specimen finishes at two inches within a thirty second of an inch, because
the sand volume and the ram energy are both fixed. A specimen outside that
window was made wrong, and the number off it is not a reading of anything. So
the height is measured, the specimen is accepted or rejected on it, and a
rejected specimen cannot carry a result.

That is the whole reason this module exists: without it, "the compactability was
42" and "the specimen was short so the compactability read 42" are the same row
on a bench sheet.

**Compactability is measured on the way in, not on the specimen.** It is the
percentage the sand column shrank under the rams, so it comes from the loose
height and the final height and is the one number that cannot be re-measured
afterwards. A specimen that was not weighed loose has no compactability, ever.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from mullerbox.errors import BadInputError, RuleError
from mullerbox.units.percent import Percent

# The standard specimen, in thousandths of an inch so the arithmetic is exact.
NOMINAL_HEIGHT = 2000
HEIGHT_TOLERANCE = 31  # a thirty second of an inch, rounded to a thousandth
STANDARD_RAMS = 3

# A loose column shorter than this cannot compact to two inches under three
# rams, so the tube was under-filled.
MIN_LOOSE_HEIGHT = 2200
MAX_LOOSE_HEIGHT = 6000


@dataclass(frozen=True)
class Specimen:
    """One rammed cylinder, and whether it was made properly."""

    specimen_id: str
    loose_height: int
    rammed_height: int
    rams: int = STANDARD_RAMS

    def __post_init__(self) -> None:
        if not self.specimen_id.strip():
            raise BadInputError("a specimen needs an identifier")
        for name in ("loose_height", "rammed_height", "rams"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise BadInputError(f"the {name.replace('_', ' ')} is a whole number")
        if self.rams <= 0:
            raise BadInputError("a specimen that was never rammed is loose sand")
        if self.rammed_height <= 0:
            raise BadInputError("a rammed height has to be above zero")
        if self.loose_height < MIN_LOOSE_HEIGHT:
            raise BadInputError(
                f"a loose column of {self.loose_height} thousandths is an under-filled tube"
            )
        if self.loose_height > MAX_LOOSE_HEIGHT:
            raise BadInputError(
                f"a loose column of {self.loose_height} thousandths is an over-filled tube"
            )
        if self.rammed_height > self.loose_height:
            raise RuleError(
                f"specimen {self.specimen_id} rammed to {self.rammed_height} "
                f"from a loose column of {self.loose_height}, which is taller"
            )

    @property
    def height_error(self) -> int:
        """Thousandths of an inch away from two inches, signed."""
        return self.rammed_height - NOMINAL_HEIGHT

    @property
    def within_tolerance(self) -> bool:
        return abs(self.height_error) <= HEIGHT_TOLERANCE

    @property
    def was_rammed_to_standard(self) -> bool:
        return self.rams == STANDARD_RAMS

    @property
    def is_acceptable(self) -> bool:
        """Whether a result off this specimen means anything."""
        return self.within_tolerance and self.was_rammed_to_standard

    def require_acceptable(self) -> None:
        """Refuse to let a result hang off a specimen that was made wrong."""
        if not self.was_rammed_to_standard:
            raise RuleError(
                f"specimen {self.specimen_id} took {self.rams} rams, not "
                f"{STANDARD_RAMS}, so nothing measured on it is comparable"
            )
        if not self.within_tolerance:
            direction = "tall" if self.height_error > 0 else "short"
            raise RuleError(
                f"specimen {self.specimen_id} finished {abs(self.height_error)} "
                f"thousandths {direction}, past the {HEIGHT_TOLERANCE} tolerance, "
                "so it was not made properly"
            )

    @property
    def compactability(self) -> Percent:
        """How far the column shrank under the rams, as a percentage.

        The one reading that cannot be taken again later: once the specimen is
        rammed the loose height is gone. It is computed here rather than by the
        caller so that it is always taken against the loose column and never
        against the nominal height, which is the shortcut that makes it wrong on
        an under-filled tube.
        """
        shrink = self.loose_height - self.rammed_height
        return Percent(
            (Decimal(shrink) / Decimal(self.loose_height) * 100).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        )

    def __str__(self) -> str:
        state = "good" if self.is_acceptable else "REJECT"
        return (
            f"{self.specimen_id}: {self.rammed_height} thousandths after {self.rams} rams, {state}"
        )


def ram(
    specimen_id: str, loose_height: int, rammed_height: int, rams: int = STANDARD_RAMS
) -> Specimen:
    """Make a specimen from what the technician measured."""
    return Specimen(
        specimen_id=specimen_id,
        loose_height=loose_height,
        rammed_height=rammed_height,
        rams=rams,
    )


def acceptable(specimens: list[Specimen]) -> list[Specimen]:
    """Only the specimens a result may hang off."""
    for specimen in specimens:
        if not isinstance(specimen, Specimen):
            raise BadInputError("only specimens can be filtered")
    return [s for s in specimens if s.is_acceptable]


__all__ = [
    "HEIGHT_TOLERANCE",
    "MAX_LOOSE_HEIGHT",
    "MIN_LOOSE_HEIGHT",
    "NOMINAL_HEIGHT",
    "STANDARD_RAMS",
    "Specimen",
    "acceptable",
    "ram",
]
