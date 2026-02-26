"""What each test needs before it is a test.

Every property in this package has a published method, and every method has
preconditions. Some need a rammed specimen, some need a weighed split of loose
sand, and one of them needs the sand to be at bench temperature because the
titration is temperature sensitive. A result taken without its preconditions is
not a low quality result, it is a number.

Collecting the preconditions here rather than in each test's own module does one
thing that matters: it makes the list askable. "What do I need before I can run
a methylene blue" is a question a new technician asks constantly and the answer
is currently spread across a method book. It is also what lets the entry path
refuse a result whose preconditions were not met, rather than accepting it and
discovering the problem when the control chart goes strange a fortnight later.

**The specimen requirement is the important one.** Three of these tests are
destructive tests on a rammed cylinder and share the same specimen; the rest are
on loose sand. Recording which is which is what lets one specimen carry three
results and stops a fourth being hung off it.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from mullerbox.errors import BadInputError, RuleError
from mullerbox.props.kind import PropertyKind
from mullerbox.units.mass import Grams


class Preparation(Enum):
    """What the sand has to be in before the test can run."""

    RAMMED_SPECIMEN = "a rammed specimen"
    LOOSE_SPLIT = "a weighed split of loose sand"
    WASHED = "a washed and dried split"
    IGNITED = "a split for the muffle"

    @property
    def label(self) -> str:
        return self.value

    @property
    def needs_specimen(self) -> bool:
        return self is Preparation.RAMMED_SPECIMEN


@dataclass(frozen=True)
class Procedure:
    """One test method and what it needs."""

    kind: PropertyKind
    preparation: Preparation
    sample_mass: Grams
    destructive: bool
    bench_temperature: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.kind, PropertyKind):
            raise BadInputError("a procedure is for a property")
        if not isinstance(self.preparation, Preparation):
            raise BadInputError("a procedure names a preparation")
        if not isinstance(self.sample_mass, Grams):
            raise BadInputError("a sample mass is a mass")
        if self.sample_mass.is_zero:
            raise BadInputError("a test on no sand is not a test")

    @property
    def needs_specimen(self) -> bool:
        return self.preparation.needs_specimen

    def requirements(self) -> list[str]:
        """Everything that has to be true before this test may be run."""
        lines = [
            f"{self.preparation.label}",
            f"{self.sample_mass} of sand",
            f"the {self.kind.measured_by.label}, in calibration",
        ]
        if self.bench_temperature:
            lines.append("the sand at bench temperature")
        if self.destructive:
            lines.append("the specimen is destroyed and cannot carry another test")
        return lines

    def __str__(self) -> str:
        return f"{self.kind.label}: {self.preparation.label}, {self.sample_mass}"


PROCEDURES: dict[PropertyKind, Procedure] = {
    PropertyKind.COMPACTABILITY: Procedure(
        kind=PropertyKind.COMPACTABILITY,
        preparation=Preparation.LOOSE_SPLIT,
        sample_mass=Grams(170),
        destructive=False,
    ),
    PropertyKind.GREEN_COMPRESSION: Procedure(
        kind=PropertyKind.GREEN_COMPRESSION,
        preparation=Preparation.RAMMED_SPECIMEN,
        sample_mass=Grams(170),
        destructive=True,
    ),
    PropertyKind.PERMEABILITY: Procedure(
        kind=PropertyKind.PERMEABILITY,
        preparation=Preparation.RAMMED_SPECIMEN,
        sample_mass=Grams(170),
        destructive=False,
    ),
    PropertyKind.MOISTURE: Procedure(
        kind=PropertyKind.MOISTURE,
        preparation=Preparation.LOOSE_SPLIT,
        sample_mass=Grams(50),
        destructive=True,
    ),
    PropertyKind.MB_CLAY: Procedure(
        kind=PropertyKind.MB_CLAY,
        preparation=Preparation.LOOSE_SPLIT,
        sample_mass=Grams(5),
        destructive=True,
        bench_temperature=True,
    ),
    PropertyKind.TOTAL_CLAY: Procedure(
        kind=PropertyKind.TOTAL_CLAY,
        preparation=Preparation.WASHED,
        sample_mass=Grams(50),
        destructive=True,
    ),
    PropertyKind.LOI: Procedure(
        kind=PropertyKind.LOI,
        preparation=Preparation.IGNITED,
        sample_mass=Grams(10),
        destructive=True,
    ),
    PropertyKind.VOLATILES: Procedure(
        kind=PropertyKind.VOLATILES,
        preparation=Preparation.IGNITED,
        sample_mass=Grams(10),
        destructive=True,
    ),
    PropertyKind.FRIABILITY: Procedure(
        kind=PropertyKind.FRIABILITY,
        preparation=Preparation.RAMMED_SPECIMEN,
        sample_mass=Grams(170),
        destructive=True,
    ),
    PropertyKind.WET_TENSILE: Procedure(
        kind=PropertyKind.WET_TENSILE,
        preparation=Preparation.RAMMED_SPECIMEN,
        sample_mass=Grams(170),
        destructive=True,
    ),
    PropertyKind.MOLD_HARDNESS: Procedure(
        kind=PropertyKind.MOLD_HARDNESS,
        preparation=Preparation.RAMMED_SPECIMEN,
        sample_mass=Grams(170),
        destructive=False,
    ),
    PropertyKind.SHATTER_INDEX: Procedure(
        kind=PropertyKind.SHATTER_INDEX,
        preparation=Preparation.RAMMED_SPECIMEN,
        sample_mass=Grams(170),
        destructive=True,
    ),
}


def procedure_for(kind: PropertyKind) -> Procedure:
    """The published method for one property."""
    if not isinstance(kind, PropertyKind):
        raise BadInputError("a property kind is expected")
    return PROCEDURES[kind]


def sand_needed(kinds: list[PropertyKind]) -> Grams:
    """How much sand a set of tests takes between them.

    Non destructive tests on the same rammed specimen share it, so they are
    counted once rather than per test. Everything else adds up.
    """
    total = Decimal(0)
    specimen_counted = False
    for kind in kinds:
        procedure = procedure_for(kind)
        if procedure.needs_specimen and not procedure.destructive:
            if specimen_counted:
                continue
            specimen_counted = True
        total += procedure.sample_mass.grams
    return Grams(total)


def one_specimen_only(kinds: list[PropertyKind]) -> None:
    """Refuse a set of tests that cannot share one rammed specimen.

    Two destructive tests on a rammed specimen need two specimens, which is
    fine and is not what this catches. What it catches is a caller planning to
    run them off one, which is the mistake a bench sheet makes when it lists
    several tests against a single specimen number.
    """
    destructive = [
        kind
        for kind in kinds
        if procedure_for(kind).needs_specimen and procedure_for(kind).destructive
    ]
    if len(destructive) > 1:
        named = ", ".join(k.label for k in destructive)
        raise RuleError(
            f"{named} each destroy the specimen, so they need {len(destructive)} "
            "specimens and not one"
        )


__all__ = [
    "PROCEDURES",
    "Preparation",
    "Procedure",
    "one_specimen_only",
    "procedure_for",
    "sand_needed",
]
