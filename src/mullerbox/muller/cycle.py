"""One muller batch, and the ordering rules that make it work.

A muller does not mix. It smears: the wheels roll bond onto grain surfaces under
pressure, and the smearing is what develops the bond. That has consequences the
arithmetic of additions does not capture.

**Dry mulling comes first, and it is not optional.** Bentonite charged into wet
sand balls up. The clay hydrates on the outside of the ball, the inside stays
dry, and the ball survives the whole cycle and goes to the molding line as a
lump with no bond in it. So the bentonite goes in against the return sand, gets
mulled dry long enough to distribute, and only then does the water go in.

**The order is a rule, not a preference.** A cycle that charged bentonite and
water together produces a batch whose measured MB clay is correct and whose
mold strength is not, which is the worst kind of wrong: it passes the lab and
fails on the floor. So the cycle refuses to be built that way rather than being
built and flagged.

**A cycle has a state.** It is charged, then mulled, then discharged, and each
step is only legal from the one before. This is not ceremony; a discharge that
did not happen and a discharge that was never recorded look the same on a shift
report, and the batch that was left in the muller overnight is a real event with
a real cost.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from decimal import Decimal
from enum import Enum

from mullerbox.addition.material import Addition, Material, dry_total
from mullerbox.errors import BadInputError, RuleError, StateError
from mullerbox.units.bulk import Pounds
from mullerbox.units.duration import Seconds

# Below this the bentonite has not been distributed, whatever the batch sheet
# says. Sixty seconds is the shop standard and thirty is the floor below which
# nobody will defend the batch.
MIN_DRY_MULL = Seconds(30)
MIN_WET_MULL = Seconds(60)

# A batch cannot absorb an unlimited addition. Past a tenth of the batch mass
# the muller is being asked to make new sand rather than to temper returned
# sand, and the cycle should be split.
MAX_ADDITION_SHARE = Decimal("0.10")


class Stage(Enum):
    """Where a batch is in its cycle."""

    CHARGED = "charged"
    MULLED = "mulled"
    DISCHARGED = "discharged"


@dataclass(frozen=True)
class Cycle:
    """One batch through the muller."""

    batch_id: str
    return_sand: Pounds
    additions: tuple[Addition, ...] = ()
    dry_mull: Seconds = field(default_factory=Seconds.zero)
    wet_mull: Seconds = field(default_factory=Seconds.zero)
    stage: Stage = Stage.CHARGED

    def __post_init__(self) -> None:
        if not self.batch_id.strip():
            raise BadInputError("a batch needs an identifier")
        if not isinstance(self.return_sand, Pounds):
            raise BadInputError("the return sand is a bulk mass")
        if self.return_sand.is_zero:
            raise BadInputError("a batch with no return sand in it is not a batch")
        for addition in self.additions:
            if not isinstance(addition, Addition):
                raise BadInputError("a cycle is charged with additions")
        materials = [a.material for a in self.additions]
        if len(set(materials)) != len(materials):
            raise RuleError("a material can only be charged once in a cycle")
        if not isinstance(self.dry_mull, Seconds):
            raise BadInputError("the dry mull is a duration")
        if not isinstance(self.wet_mull, Seconds):
            raise BadInputError("the wet mull is a duration")
        if not isinstance(self.stage, Stage):
            raise BadInputError("a cycle has a stage")
        share = dry_total(list(self.additions)).fraction_of(self.return_sand)
        if share > MAX_ADDITION_SHARE:
            raise RuleError(
                f"batch {self.batch_id} charges {share * 100:.1f}% of its own mass "
                f"in additions, past the {MAX_ADDITION_SHARE * 100:.0f}% a muller "
                "can distribute"
            )

    @classmethod
    def charge(cls, batch_id: str, return_sand: Pounds, additions: list[Addition]) -> Cycle:
        """Start a cycle by charging the return sand and the additions."""
        real = [a for a in additions if not a.is_nothing]
        return cls(batch_id=batch_id, return_sand=return_sand, additions=tuple(real))

    def addition_of(self, material: Material) -> Addition | None:
        for addition in self.additions:
            if addition.material is material:
                return addition
        return None

    def charges(self, material: Material) -> bool:
        if not isinstance(material, Material):
            raise BadInputError("a material is expected")
        return self.addition_of(material) is not None

    @property
    def dry_additions(self) -> tuple[Addition, ...]:
        return tuple(a for a in self.additions if a.material.is_dry)

    @property
    def batch_mass(self) -> Pounds:
        """What comes out, which is the return sand plus everything charged."""
        running = self.return_sand
        for addition in self.additions:
            running = running + addition.mass
        return running

    def mulled(self, dry: Seconds, wet: Seconds) -> Cycle:
        """Run the mull, refusing a schedule that will not develop the bond."""
        if self.stage is not Stage.CHARGED:
            raise StateError(
                f"batch {self.batch_id} is {self.stage.value} and cannot be mulled again"
            )
        if not isinstance(dry, Seconds) or not isinstance(wet, Seconds):
            raise BadInputError("a mull is two durations")
        if self.charges(Material.BENTONITE) and dry < MIN_DRY_MULL:
            raise RuleError(
                f"batch {self.batch_id} charges bentonite and dry mulls for {dry}, "
                f"under the {MIN_DRY_MULL} that distributes it"
            )
        if self.charges(Material.WATER):
            if dry.is_zero:
                raise RuleError(f"batch {self.batch_id} takes water with no dry mull before it")
            if wet < MIN_WET_MULL:
                raise RuleError(
                    f"batch {self.batch_id} takes water and wet mulls for {wet}, "
                    f"under the {MIN_WET_MULL} that develops it"
                )
        return replace(self, dry_mull=dry, wet_mull=wet, stage=Stage.MULLED)

    def discharged(self) -> Cycle:
        """Send the batch to the line."""
        if self.stage is not Stage.MULLED:
            raise StateError(
                f"batch {self.batch_id} is {self.stage.value} and cannot be discharged"
            )
        return replace(self, stage=Stage.DISCHARGED)

    @property
    def total_mull(self) -> Seconds:
        return self.dry_mull + self.wet_mull

    @property
    def is_finished(self) -> bool:
        return self.stage is Stage.DISCHARGED

    def __str__(self) -> str:
        return (
            f"batch {self.batch_id} {self.stage.value}, "
            f"{self.batch_mass} after {len(self.additions)} additions"
        )


__all__ = ["MAX_ADDITION_SHARE", "MIN_DRY_MULL", "MIN_WET_MULL", "Cycle", "Stage"]
