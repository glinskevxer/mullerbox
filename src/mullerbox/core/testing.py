"""Testing a core sand, which is a different test on a different clock.

Green sand is tested as it is: rammed damp and broken. Core sand cannot be,
because at the moment it is mixed it has no strength at all and an hour later it
has all of it. So a core sand test is a *tensile* test on a cured specimen, and
the specimen's age at break is part of the result rather than a detail.

That makes the comparison awkward in a way worth writing down. Two tensile
figures are only comparable if they were broken at the same age, and "the same
age" means the same age *for that binder*, because a phenolic urethane is fully
cured in fifteen minutes and a furan takes two hours. So a result carries its
binder and its age, and comparing two results across binders is refused rather
than done badly.

**Scratch hardness is a screening test and this module says so.** It is quick,
it needs no specimen, and it correlates with tensile only loosely. It is used to
decide whether a core is worth handling, never to decide whether a batch is
good, and a caller asking for a pass or fail on scratch hardness alone gets a
refusal.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from mullerbox.core.binder import Binder, BinderSystem
from mullerbox.errors import BadInputError, RuleError
from mullerbox.units.duration import Seconds
from mullerbox.units.pressure import Psi

# Scratch hardness runs 0 to 100 on the same dial as mold hardness, and this is
# the line below which a core is not worth carrying to the line.
HANDLING_HARDNESS = Decimal("70")

# A tensile broken this far either side of full cure is comparable to one broken
# at full cure. Outside it, the number is measuring the cure and not the sand.
CURE_WINDOW = Seconds(300)


@dataclass(frozen=True)
class TensileResult:
    """One core specimen broken at one age."""

    specimen_id: str
    system: BinderSystem
    mixed_at: datetime
    broken_at: datetime
    tensile: Psi

    def __post_init__(self) -> None:
        if not self.specimen_id.strip():
            raise BadInputError("a specimen needs an identifier")
        if not isinstance(self.system, BinderSystem):
            raise BadInputError("a core result names its binder system")
        for name in ("mixed_at", "broken_at"):
            if not isinstance(getattr(self, name), datetime):
                raise BadInputError(f"the {name.replace('_', ' ')} is a moment")
        if not isinstance(self.tensile, Psi):
            raise BadInputError("a tensile is a pressure")
        if self.broken_at < self.mixed_at:
            raise BadInputError(f"specimen {self.specimen_id} was broken before it was mixed")

    @property
    def age(self) -> Seconds:
        return Seconds(int((self.broken_at - self.mixed_at).total_seconds()))

    @property
    def binder(self) -> Binder:
        return self.system.binder

    @property
    def was_cured(self) -> bool:
        return self.system.is_cured_at(self.age)

    @property
    def at_full_cure(self) -> bool:
        """Whether it was broken close enough to full cure to be a fair reading."""
        gap = abs(self.age.value - self.system.full_cure.value)
        return gap <= CURE_WINDOW.value

    @property
    def meets_floor(self) -> bool:
        return self.tensile >= self.system.tensile_floor

    def require_comparable(self, other: TensileResult) -> None:
        """Refuse a comparison that would be meaningless.

        Two binders cure differently, so a tensile at ten minutes means
        something quite different on each. Refusing is better than a number
        somebody will quote.
        """
        if not isinstance(other, TensileResult):
            raise BadInputError("a core result compares against a core result")
        if self.binder is not other.binder:
            raise RuleError(
                f"specimen {self.specimen_id} is {self.binder.label} and "
                f"{other.specimen_id} is {other.binder.label}, so their tensiles "
                "are not comparable"
            )
        if not (self.at_full_cure and other.at_full_cure):
            raise RuleError(
                f"specimens {self.specimen_id} and {other.specimen_id} were not "
                "both broken at full cure"
            )

    def stronger_than(self, other: TensileResult) -> bool:
        self.require_comparable(other)
        return self.tensile > other.tensile

    def __str__(self) -> str:
        return f"{self.specimen_id}: {self.tensile} at {self.age} on {self.binder.label}"


@dataclass(frozen=True)
class ScratchReading:
    """A screening reading off the scratch dial. Not a batch verdict."""

    core_id: str
    hardness: Decimal

    def __post_init__(self) -> None:
        if not self.core_id.strip():
            raise BadInputError("a scratch reading names a core")
        if not isinstance(self.hardness, Decimal):
            raise BadInputError("a scratch hardness is a decimal")
        if self.hardness < 0 or self.hardness > 100:
            raise BadInputError("the scratch dial runs from zero to a hundred")

    @property
    def fit_to_handle(self) -> bool:
        return self.hardness >= HANDLING_HARDNESS

    def verdict(self) -> str:
        """A handling judgement, and it says what it is not."""
        if self.fit_to_handle:
            return f"{self.core_id} is fit to handle at {self.hardness} scratch"
        return f"{self.core_id} reads {self.hardness} scratch and is not fit to handle"


def batch_verdict(results: list[TensileResult]) -> str:
    """Whether a core batch passes, from its tensiles and nothing else.

    Scratch readings do not appear here. They screen individual cores for
    handling; a batch is judged on tensile at full cure or it is not judged.
    """
    if not results:
        raise BadInputError("no core results to judge")
    for result in results:
        if not isinstance(result, TensileResult):
            raise BadInputError("a batch is judged on core results")
    usable = [r for r in results if r.at_full_cure]
    if not usable:
        raise RuleError(
            "none of these specimens was broken at full cure, so the batch cannot be judged"
        )
    failed = [r for r in usable if not r.meets_floor]
    average = (sum((r.tensile.value for r in usable), Decimal(0)) / len(usable)).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )
    if failed:
        named = ", ".join(r.specimen_id for r in failed)
        return f"fails: {len(failed)} of {len(usable)} under the floor ({named})"
    return f"passes: {len(usable)} specimens averaging {average} psi"


__all__ = [
    "CURE_WINDOW",
    "HANDLING_HARDNESS",
    "ScratchReading",
    "TensileResult",
    "batch_verdict",
]
