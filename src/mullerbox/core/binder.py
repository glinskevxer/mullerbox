"""Core sand binder systems, and the clock each one runs on.

Green sand has no clock. A batch mulled this morning is the same batch this
afternoon, and the sand in the system has been going round for years. Core sand
is the opposite: the binder starts reacting the moment the catalyst meets it,
and everything after that is a race.

That gives core sand three times that green sand has no equivalent of, and
mixing them up is the standard way to scrap a shift's cores.

**Bench life** is how long the mixed sand stays workable in the hopper. Past it
the sand will still blow into the box and will not develop full strength,
because the binder has already reacted with itself instead of at the grain
contacts.

**Strip time** is how long the core must stay in the box before it can be drawn
without slumping. Too early and the core distorts; the shop's pressure is
always to draw early, because the box is the bottleneck.

**Full cure** is when the core reaches the strength it will be handled and
poured at. Between strip and full cure the core is real but fragile.

They run in that order and the ordering is checked, because a system quoted with
a strip time past its bench life is a typo in the supplier's data sheet and it
happens.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from mullerbox.errors import BadInputError
from mullerbox.units.duration import Seconds
from mullerbox.units.percent import Percent
from mullerbox.units.pressure import Psi


class Binder(Enum):
    """The binder chemistries this shop runs."""

    SHELL = "shell"
    PHENOLIC_URETHANE = "phenolic urethane no bake"
    FURAN = "furan no bake"
    SODIUM_SILICATE = "sodium silicate"

    @property
    def label(self) -> str:
        return self.value

    @property
    def is_heat_cured(self) -> bool:
        """Shell cures in a hot box; the rest cure chemically at room temperature."""
        return self is Binder.SHELL

    @property
    def gasses_on_pour(self) -> bool:
        """Whether this binder contributes gas the mold has to vent.

        Silicate does not, which is why it survives on thin sections where the
        organics cannot, and why nobody uses it anywhere else: it does not break
        down after the pour either, so the cores will not shake out.
        """
        return self is not Binder.SODIUM_SILICATE


@dataclass(frozen=True)
class BinderSystem:
    """One binder as this shop actually runs it, with its own numbers."""

    binder: Binder
    resin: Percent
    catalyst: Percent
    bench_life: Seconds
    strip_time: Seconds
    full_cure: Seconds
    tensile_floor: Psi

    def __post_init__(self) -> None:
        if not isinstance(self.binder, Binder):
            raise BadInputError("a binder system names a binder")
        for name in ("resin", "catalyst"):
            value = getattr(self, name)
            if not isinstance(value, Percent):
                raise BadInputError(f"the {name} addition is a percentage")
        if self.resin.value <= 0:
            raise BadInputError("a binder system with no resin is not a binder system")
        for name in ("bench_life", "strip_time", "full_cure"):
            if not isinstance(getattr(self, name), Seconds):
                raise BadInputError(f"the {name.replace('_', ' ')} is a duration")
        if not isinstance(self.tensile_floor, Psi):
            raise BadInputError("the tensile floor is a pressure")
        if self.strip_time >= self.bench_life:
            raise BadInputError(
                f"{self.binder.label} strips at {self.strip_time} and its bench life "
                f"is {self.bench_life}, so the sand dies before the core can be drawn"
            )
        if self.full_cure <= self.strip_time:
            raise BadInputError(
                f"{self.binder.label} cures at {self.full_cure}, which is not after "
                f"its strip time of {self.strip_time}"
            )

    @property
    def total_binder(self) -> Percent:
        return Percent(self.resin.value + self.catalyst.value)

    @property
    def catalyst_ratio(self) -> Decimal:
        """Catalyst as a share of resin, which is what the supplier quotes."""
        if self.resin.value <= 0:
            raise BadInputError("no resin to take a ratio against")
        return (self.catalyst.value / self.resin.value).quantize(Decimal("0.001"))

    @property
    def fragile_window(self) -> Seconds:
        """Between drawing the core and its being safe to handle."""
        return self.full_cure - self.strip_time

    def is_workable_at(self, age: Seconds) -> bool:
        """Whether sand this old may still be blown."""
        if not isinstance(age, Seconds):
            raise BadInputError("an age is a duration")
        return age < self.bench_life

    def may_strip_at(self, age: Seconds) -> bool:
        if not isinstance(age, Seconds):
            raise BadInputError("an age is a duration")
        return age >= self.strip_time

    def is_cured_at(self, age: Seconds) -> bool:
        if not isinstance(age, Seconds):
            raise BadInputError("an age is a duration")
        return age >= self.full_cure

    def __str__(self) -> str:
        return f"{self.binder.label} at {self.resin} resin, bench life {self.bench_life}"


__all__ = ["Binder", "BinderSystem"]
