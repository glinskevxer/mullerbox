"""A sieve analysis: what was charged onto the stack and what came back off it.

The specimen is weighed, dropped on the top screen, shaken for a fixed time, and
then each screen is weighed back. Two masses matter and they are not the same
one. The **charged** mass is what went on. The **recovered** mass is the sum of
what came off. They differ because sand sticks to screens and blows away, and
the gap between them is the closure error.

Which of the two the retained percentages are taken against is a real decision
with a real consequence. This module takes them against the recovered mass, so
they sum to exactly one hundred and the fineness number is unaffected by a lost
gram. The closure check against the charged mass is then a separate judgement
about whether the analysis is fit to use at all, and it is reported rather than
folded into the percentages, because an analysis that lost four percent of the
specimen is not slightly wrong, it is void.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from mullerbox.errors import BadInputError, RuleError
from mullerbox.screens.series import ScreenSeries
from mullerbox.units.mass import Grams, total
from mullerbox.units.mesh import Mesh
from mullerbox.units.percent import Percent

# AFS practice allows half a percent. Past that the analysis gets re-run rather
# than reported, because the loss is not spread evenly across the stack: it
# comes off the fine screens, which is exactly where the fineness number is
# most sensitive.
CLOSURE_TOLERANCE = Decimal("0.5")


@dataclass(frozen=True)
class Retained:
    """The mass left on one screen."""

    mesh: Mesh
    mass: Grams

    def __post_init__(self) -> None:
        if not isinstance(self.mesh, Mesh):
            raise BadInputError("a retained reading is against a screen")
        if not isinstance(self.mass, Grams):
            raise BadInputError("a retained reading is a mass")


@dataclass(frozen=True)
class SieveAnalysis:
    """One shake of one specimen through one series.

    Every screen on the series has to have a reading, including the ones that
    came back empty. A missing screen and a screen that retained nothing look
    identical in a report and mean opposite things about whether the analysis
    was run properly, so a gap is refused rather than defaulted to zero.
    """

    series: ScreenSeries
    charged: Grams
    readings: tuple[Retained, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.series, ScreenSeries):
            raise BadInputError("an analysis is run against a series")
        if not isinstance(self.charged, Grams):
            raise BadInputError("the charged mass is a mass")
        if self.charged.is_zero:
            raise BadInputError("nothing was charged onto the stack")
        seen: list[Mesh] = []
        for reading in self.readings:
            if not isinstance(reading, Retained):
                raise BadInputError("an analysis is built from retained readings")
            if not self.series.contains(reading.mesh):
                raise RuleError(f"screen {reading.mesh.label} is not on series {self.series.name}")
            if reading.mesh in seen:
                raise RuleError(f"screen {reading.mesh.label} was weighed twice")
            seen.append(reading.mesh)
        missing = [m.label for m in self.series.meshes if m not in seen]
        if missing:
            raise RuleError(f"no reading for screen {missing[0]}")

    @classmethod
    def of(
        cls,
        series: ScreenSeries,
        charged: object,
        masses: Mapping[str, object],
    ) -> SieveAnalysis:
        """Build from a bench sheet, where screens are named by their labels."""
        by_label = {step.label: step.mesh for step in series.steps}
        readings: list[Retained] = []
        for label, value in masses.items():
            key = str(label).strip().upper()
            if key not in by_label:
                raise RuleError(f"screen {key} is not on series {series.name}")
            readings.append(Retained(by_label[key], Grams(value)))
        return cls(series=series, charged=Grams(charged), readings=tuple(readings))

    @property
    def ordered(self) -> tuple[Retained, ...]:
        """The readings in stack order, coarse first, whatever order they came in."""
        position = self.series.position_of
        return tuple(sorted(self.readings, key=lambda r: position(r.mesh)))

    @property
    def recovered(self) -> Grams:
        """What actually came back off the stack."""
        return total([r.mass for r in self.readings])

    @property
    def loss(self) -> Grams:
        """The gap between what went on and what came off."""
        return self.charged.difference(self.recovered)

    @property
    def closure_error(self) -> Percent:
        """The loss as a percentage of what was charged."""
        return Percent.of(self.loss.grams, self.charged.grams)

    @property
    def closes(self) -> bool:
        return self.closure_error.value <= CLOSURE_TOLERANCE

    def require_closure(self) -> None:
        """Raise unless the analysis is fit to derive anything from."""
        if self.recovered.is_zero:
            raise RuleError("nothing came back off the stack")
        if not self.closes:
            raise RuleError(
                f"the analysis is out by {self.closure_error}, past the "
                f"{CLOSURE_TOLERANCE}% closure tolerance"
            )

    def fraction_on(self, mesh: Mesh) -> Percent:
        """The share of the recovered mass left on one screen."""
        self.require_closure()
        for reading in self.readings:
            if reading.mesh == mesh:
                return Percent.of(reading.mass.grams, self.recovered.grams)
        raise BadInputError(f"screen {mesh.label} was not weighed on this analysis")

    @property
    def distribution(self) -> tuple[tuple[Mesh, Percent], ...]:
        """Every screen and its share, coarse first."""
        self.require_closure()
        recovered = self.recovered.grams
        return tuple((r.mesh, Percent.of(r.mass.grams, recovered)) for r in self.ordered)

    @property
    def pan_fraction(self) -> Percent:
        """What fell all the way through, which is the fines the lab worries about."""
        return self.fraction_on(self.series.pan.mesh)


__all__ = ["CLOSURE_TOLERANCE", "Retained", "SieveAnalysis"]
