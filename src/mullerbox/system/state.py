"""The circulating sand system, and why its mass is an estimate.

Nobody weighs a sand system. The number every shop quotes is the design figure
from when the equipment went in, and the real one has drifted: sand has been
lost to the collector and the floor for years, and new sand has gone in at
whatever rate the operator felt was right. A system quoted at two hundred tons
is commonly running at a hundred and forty.

That matters because every addition in this package is a share of the system
mass. A bentonite calculation against a system that is thirty percent smaller
than believed overdoses by thirty percent, every shift, and the MB clay climbs
until somebody notices the sand will not compact.

So the mass carries its provenance. A ``measured`` figure came from an actual
inventory; a ``nameplate`` figure is the design number and is a guess. Anything
that computes an addition can ask which it is, and the reports say so, because
"the bond is drifting up" and "the system mass is wrong" look identical on a
control chart and are fixed by completely different work.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from enum import Enum

from mullerbox.errors import BadInputError, RuleError
from mullerbox.units.bulk import Pounds
from mullerbox.units.percent import Percent
from mullerbox.units.thermal import Temperature

# A system inventory older than this has stopped being a measurement.
INVENTORY_STALE_DAYS = 180


class MassBasis(Enum):
    """Where the system mass figure came from."""

    MEASURED = "measured"
    NAMEPLATE = "nameplate"

    @property
    def is_trustworthy(self) -> bool:
        return self is MassBasis.MEASURED

    @property
    def label(self) -> str:
        return self.value


@dataclass(frozen=True)
class SandSystem:
    """One circulating sand system."""

    name: str
    mass: Pounds
    basis: MassBasis
    established_on: date
    batch_size: Pounds
    return_temperature: Temperature
    dust_loss_rate: Percent

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise BadInputError("a sand system needs a name")
        if not isinstance(self.mass, Pounds):
            raise BadInputError("the system mass is a bulk mass")
        if self.mass.is_zero:
            raise BadInputError("a system with no sand in it is not a system")
        if not isinstance(self.basis, MassBasis):
            raise BadInputError("the system mass has a basis")
        if not isinstance(self.established_on, date):
            raise BadInputError("the mass figure is dated")
        if not isinstance(self.batch_size, Pounds):
            raise BadInputError("the batch size is a bulk mass")
        if self.batch_size.is_zero:
            raise BadInputError("a muller that takes no batch is not a muller")
        if self.batch_size > self.mass:
            raise RuleError(
                f"{self.name} holds {self.mass} and its muller takes {self.batch_size}, "
                "which is more than the system"
            )
        if not isinstance(self.return_temperature, Temperature):
            raise BadInputError("the return sand temperature is a temperature")
        if not isinstance(self.dust_loss_rate, Percent):
            raise BadInputError("the dust loss rate is a percentage")

    @property
    def is_measured(self) -> bool:
        return self.basis.is_trustworthy

    def is_stale_at(self, when: date) -> bool:
        """Whether the mass figure is too old to rely on."""
        if not isinstance(when, date):
            raise BadInputError("staleness is checked against a date")
        if when < self.established_on:
            raise BadInputError(
                f"{self.name} was inventoried on {self.established_on}, after {when}"
            )
        return (when - self.established_on).days > INVENTORY_STALE_DAYS

    def require_trustworthy(self, when: date) -> Pounds:
        """The mass, or a refusal saying why it should not be dosed against."""
        if not self.is_measured:
            raise RuleError(
                f"{self.name} carries a nameplate mass of {self.mass}, which is a "
                "design figure and not an inventory"
            )
        if self.is_stale_at(when):
            days = (when - self.established_on).days
            raise RuleError(
                f"{self.name} was last inventoried {days} days ago, past the "
                f"{INVENTORY_STALE_DAYS} day limit"
            )
        return self.mass

    @property
    def turns_per_batch(self) -> Decimal:
        """How many batches make one pass of the whole system."""
        return (self.mass.value / self.batch_size.value).quantize(Decimal("0.01"))

    def dust_loss_over(self, sand_handled: Pounds) -> Pounds:
        """What the collector takes out of a given throughput."""
        if not isinstance(sand_handled, Pounds):
            raise BadInputError("throughput is a bulk mass")
        return sand_handled.scaled(self.dust_loss_rate.fraction)

    def inventoried(self, mass: Pounds, when: date) -> SandSystem:
        """Record a real inventory, which promotes the basis to measured."""
        if not isinstance(mass, Pounds):
            raise BadInputError("the system mass is a bulk mass")
        if mass.is_zero:
            raise BadInputError("an inventory of nothing is not an inventory")
        if not isinstance(when, date):
            raise BadInputError("an inventory is dated")
        if when < self.established_on:
            raise RuleError(f"{self.name} already carries a figure from {self.established_on}")
        return replace(self, mass=mass, basis=MassBasis.MEASURED, established_on=when)

    def __str__(self) -> str:
        return f"{self.name}: {self.mass} ({self.basis.label})"


__all__ = ["INVENTORY_STALE_DAYS", "MassBasis", "SandSystem"]
