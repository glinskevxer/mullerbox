"""A core sand batch, and the decisions its age makes for it.

The batch is the unit that ages. Sand is mixed once, sits in the hopper, and
gets blown into boxes over the next few minutes; every core out of it inherits
the batch's mix time and is therefore a different age at the moment it is blown.

So "can this be blown" is a question about a moment, never about the batch, and
the batch will not answer it without being told when. That is the whole reason
this module does not carry a clock: a batch that reads ``datetime.now()`` inside
itself cannot be tested against the boundary, cannot be replayed off a shift
record, and answers differently depending on how long the caller took to get
round to asking.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from mullerbox.core.binder import BinderSystem
from mullerbox.errors import BadInputError, RuleError, StateError
from mullerbox.units.bulk import Pounds
from mullerbox.units.duration import Seconds


@dataclass(frozen=True)
class CoreBatch:
    """One mix of core sand, with what has been drawn off it."""

    batch_id: str
    system: BinderSystem
    mixed_at: datetime
    charged: Pounds
    blown: Pounds = Pounds.zero()

    def __post_init__(self) -> None:
        if not self.batch_id.strip():
            raise BadInputError("a core batch needs an identifier")
        if not isinstance(self.system, BinderSystem):
            raise BadInputError("a core batch is mixed on a binder system")
        if not isinstance(self.mixed_at, datetime):
            raise BadInputError("a core batch is timestamped")
        if not isinstance(self.charged, Pounds):
            raise BadInputError("the charged mass is a bulk mass")
        if not isinstance(self.blown, Pounds):
            raise BadInputError("the blown mass is a bulk mass")
        if self.charged.is_zero:
            raise BadInputError("a core batch with no sand in it is not a batch")
        if self.blown > self.charged:
            raise RuleError(f"batch {self.batch_id} has blown {self.blown} out of {self.charged}")

    def age_at(self, when: datetime) -> Seconds:
        """How old the batch is at a moment, refusing to run backwards."""
        if not isinstance(when, datetime):
            raise BadInputError("an age is taken at a moment")
        if when < self.mixed_at:
            raise BadInputError(
                f"batch {self.batch_id} was mixed at {self.mixed_at}, which is after {when}"
            )
        return Seconds(int((when - self.mixed_at).total_seconds()))

    @property
    def remaining(self) -> Pounds:
        return self.charged - self.blown

    @property
    def is_spent(self) -> bool:
        return self.remaining.is_zero

    def is_workable_at(self, when: datetime) -> bool:
        return self.system.is_workable_at(self.age_at(when))

    def blow(self, mass: Pounds, when: datetime) -> CoreBatch:
        """Draw sand off the batch to fill a box.

        Refused past bench life, and refused for more than is left. Both are
        state errors rather than input errors: the arguments are fine, the batch
        is not in a position to satisfy them.
        """
        if not isinstance(mass, Pounds):
            raise BadInputError("a blow is a bulk mass")
        if mass.is_zero:
            raise BadInputError("blowing nothing is not a blow")
        age = self.age_at(when)
        if not self.system.is_workable_at(age):
            raise StateError(
                f"batch {self.batch_id} is {age} old, past the "
                f"{self.system.bench_life} bench life of "
                f"{self.system.binder.label}"
            )
        if mass > self.remaining:
            raise StateError(
                f"batch {self.batch_id} has {self.remaining} left and {mass} was asked for"
            )
        return replace(self, blown=self.blown + mass)

    @property
    def utilisation(self) -> Pounds:
        """What was actually used, which is what the yield is measured against."""
        return self.blown

    def __str__(self) -> str:
        return (
            f"core batch {self.batch_id} on {self.system.binder.label}, "
            f"{self.remaining} of {self.charged} left"
        )


@dataclass(frozen=True)
class Core:
    """One core, blown off a batch and drawn from its box."""

    core_id: str
    batch_id: str
    blown_at: datetime
    mass: Pounds

    def __post_init__(self) -> None:
        if not self.core_id.strip():
            raise BadInputError("a core needs an identifier")
        if not self.batch_id.strip():
            raise BadInputError("a core names the batch it came off")
        if not isinstance(self.blown_at, datetime):
            raise BadInputError("a core is timestamped")
        if not isinstance(self.mass, Pounds):
            raise BadInputError("a core mass is a bulk mass")
        if self.mass.is_zero:
            raise BadInputError("a core with no sand in it is not a core")

    def may_strip_at(self, when: datetime, system: BinderSystem) -> bool:
        return system.may_strip_at(self._age(when))

    def is_cured_at(self, when: datetime, system: BinderSystem) -> bool:
        return system.is_cured_at(self._age(when))

    def require_strippable(self, when: datetime, system: BinderSystem) -> None:
        """Refuse to draw a core that has not set."""
        age = self._age(when)
        if not system.may_strip_at(age):
            raise StateError(
                f"core {self.core_id} is {age} old and {system.binder.label} "
                f"strips at {system.strip_time}"
            )

    def _age(self, when: datetime) -> Seconds:
        if not isinstance(when, datetime):
            raise BadInputError("an age is taken at a moment")
        if when < self.blown_at:
            raise BadInputError(f"core {self.core_id} was blown after {when}")
        return Seconds(int((when - self.blown_at).total_seconds()))


__all__ = ["Core", "CoreBatch"]
