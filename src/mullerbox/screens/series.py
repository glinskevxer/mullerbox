"""A screen series: the stack of sieves, in order, and the weight each carries.

A series is more than a list of screens. Every screen in it carries a
multiplier, and the grain fineness number is the multiplier-weighted average of
the retained distribution. Those multipliers are a property of the series and
not of the sample, which is the part that gets implemented wrong: a lab that
swaps a screen for one from a different series and keeps using the old
multiplier produces a fineness number that is not wrong in any way an assertion
would catch, it is just quietly not comparable to last month's.

So the series owns both, the pair is immutable, and an analysis names the series
it was run on.
"""

from __future__ import annotations

from dataclasses import dataclass

from mullerbox.errors import BadInputError
from mullerbox.units.mesh import Mesh


@dataclass(frozen=True)
class Step:
    """One screen in a series, with the fineness multiplier it carries."""

    mesh: Mesh
    multiplier: int

    def __post_init__(self) -> None:
        if not isinstance(self.mesh, Mesh):
            raise BadInputError("a step is built on a screen")
        if isinstance(self.multiplier, bool) or not isinstance(self.multiplier, int):
            raise BadInputError("a fineness multiplier is a whole number")
        if self.multiplier <= 0:
            raise BadInputError("a fineness multiplier has to be above zero")

    @property
    def label(self) -> str:
        return self.mesh.label


@dataclass(frozen=True)
class ScreenSeries:
    """An ordered stack of screens, coarse at the top, pan at the bottom.

    The ordering is checked on construction rather than sorted into place. A
    series handed over out of order is a transcription error in whatever built
    it, and silently sorting it hides the fault while producing a stack that no
    longer matches the physical one in the lab.
    """

    name: str
    steps: tuple[Step, ...]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise BadInputError("a screen series needs a name")
        if len(self.steps) < 2:
            raise BadInputError("a series needs at least one screen and a pan")
        if not self.steps[-1].mesh.is_pan:
            raise BadInputError("a series ends at the pan")
        if any(step.mesh.is_pan for step in self.steps[:-1]):
            raise BadInputError("only the last step is the pan")
        for above, below in zip(self.steps, self.steps[1:], strict=False):
            if not above.mesh.is_coarser_than(below.mesh):
                raise BadInputError(f"screen {below.label} does not sit under screen {above.label}")
        multipliers = [step.multiplier for step in self.steps]
        if multipliers != sorted(multipliers):
            raise BadInputError("fineness multipliers rise from coarse to fine")
        if len(set(multipliers)) != len(multipliers):
            raise BadInputError("two screens cannot carry the same multiplier")

    def __len__(self) -> int:
        return len(self.steps)

    @property
    def meshes(self) -> tuple[Mesh, ...]:
        return tuple(step.mesh for step in self.steps)

    @property
    def labels(self) -> tuple[str, ...]:
        return tuple(step.label for step in self.steps)

    @property
    def pan(self) -> Step:
        return self.steps[-1]

    @property
    def working_steps(self) -> tuple[Step, ...]:
        """Everything above the pan, which is what actually sieves."""
        return self.steps[:-1]

    def step_for(self, mesh: Mesh) -> Step:
        """The step carrying a screen, refusing a screen from another series."""
        if not isinstance(mesh, Mesh):
            raise BadInputError("a series is indexed by a screen")
        for step in self.steps:
            if step.mesh == mesh:
                return step
        raise BadInputError(f"screen {mesh.label} is not on series {self.name}")

    def multiplier_for(self, mesh: Mesh) -> int:
        return self.step_for(mesh).multiplier

    def position_of(self, mesh: Mesh) -> int:
        """Where a screen sits in the stack, counting from the coarse end."""
        for index, step in enumerate(self.steps):
            if step.mesh == mesh:
                return index
        raise BadInputError(f"screen {mesh.label} is not on series {self.name}")

    def contains(self, mesh: Mesh) -> bool:
        return any(step.mesh == mesh for step in self.steps)


# The eleven screen US series with the AFS multipliers. These numbers are the
# reason a fineness number from one lab means anything to another one, so they
# are written out rather than generated.
AFS_US_SERIES = ScreenSeries(
    name="AFS US 11 screen",
    steps=(
        Step(Mesh(6, 3350), 3),
        Step(Mesh(12, 1700), 5),
        Step(Mesh(20, 850), 10),
        Step(Mesh(30, 600), 20),
        Step(Mesh(40, 425), 30),
        Step(Mesh(50, 300), 40),
        Step(Mesh(70, 212), 50),
        Step(Mesh(100, 150), 70),
        Step(Mesh(140, 106), 100),
        Step(Mesh(200, 75), 140),
        Step(Mesh(270, 53), 200),
        Step(Mesh.pan(), 300),
    ),
)


__all__ = ["AFS_US_SERIES", "ScreenSeries", "Step"]
