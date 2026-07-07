"""Taking a real inventory of a sand system.

`mullerbox.system.state` says the mass carries its provenance and that a
nameplate figure is a guess. This is the procedure that turns the guess into a
measurement, and it is worth writing down because the shop floor version of it
loses sand in three places at once.

The count is a sum of vessels. Each vessel is a level, a cross section and a
bulk density, and the bulk density is the part that goes wrong: the handbook
number for silica is for dry sand poured loose, and a moist bonded return sand
in a hopper packs differently. So the density comes from a measured sample or
the vessel is not counted, and an uncounted vessel makes the whole inventory
partial rather than quietly small.

**Sand in moulds is still system sand.** At any moment a jobbing shop has some
share of its system standing on the pouring floor in flasks, and a count taken
off the vessels alone misses it. That share is not weighed either; it is
estimated from the moulds standing and the sand each pattern takes, which the
pattern record already carries. It is the one term here that is allowed to be an
estimate, and the result says so.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from mullerbox.errors import BadInputError, RuleError
from mullerbox.system.state import SandSystem
from mullerbox.units.bulk import Pounds, total_pounds

# Below this the vessel is not worth the ladder.
SMALLEST_VESSEL_CUBIC_FEET = Decimal("5")

# A count that finds this much less than the standing figure is not a correction,
# it is a sign the count itself went wrong.
SUSPECT_SHORTFALL = Decimal("0.40")


@dataclass(frozen=True)
class Vessel:
    """One hopper, silo or belt run, and what is standing in it."""

    name: str
    capacity_cubic_feet: Decimal
    filled_fraction: Decimal
    density_pounds_per_cubic_foot: Decimal | None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise BadInputError("a vessel needs a name")
        for label, number in (
            ("capacity", self.capacity_cubic_feet),
            ("fill", self.filled_fraction),
        ):
            if not isinstance(number, Decimal):
                raise BadInputError(f"the {label} is a decimal")
        if self.capacity_cubic_feet < SMALLEST_VESSEL_CUBIC_FEET:
            raise BadInputError(
                f"{self.name} holds {self.capacity_cubic_feet} cubic feet, which is "
                "too small to be worth counting"
            )
        if not Decimal(0) <= self.filled_fraction <= Decimal(1):
            raise BadInputError(f"{self.name} cannot be {self.filled_fraction:.0%} full")
        density = self.density_pounds_per_cubic_foot
        if density is not None:
            if not isinstance(density, Decimal):
                raise BadInputError("a bulk density is a decimal")
            if density <= 0:
                raise BadInputError("a bulk density is above zero")

    @property
    def is_counted(self) -> bool:
        """Whether this vessel contributes a number rather than a hole."""
        return self.density_pounds_per_cubic_foot is not None

    @property
    def standing_cubic_feet(self) -> Decimal:
        return (self.capacity_cubic_feet * self.filled_fraction).quantize(Decimal("0.01"))

    @property
    def mass(self) -> Pounds:
        """What is in the vessel, or a refusal if nobody measured its density."""
        density = self.density_pounds_per_cubic_foot
        if density is None:
            raise RuleError(
                f"{self.name} has no measured bulk density, so what is standing in "
                "it is a volume and not a mass"
            )
        return Pounds(self.standing_cubic_feet * density)

    def __str__(self) -> str:
        return f"{self.name} {self.filled_fraction:.0%} of {self.capacity_cubic_feet} cu ft"


@dataclass(frozen=True)
class Count:
    """One inventory, taken on one day, with what it could not reach."""

    system_name: str
    counted_on: date
    vessels: tuple[Vessel, ...]
    moulds_standing: int
    sand_per_mould: Pounds

    def __post_init__(self) -> None:
        if not self.system_name.strip():
            raise BadInputError("an inventory is of a named system")
        if not isinstance(self.counted_on, date):
            raise BadInputError("an inventory is dated")
        if not self.vessels:
            raise BadInputError("an inventory with no vessels counted nothing")
        names = [vessel.name for vessel in self.vessels]
        if len(set(names)) != len(names):
            raise BadInputError("the same vessel was counted twice")
        if isinstance(self.moulds_standing, bool) or not isinstance(self.moulds_standing, int):
            raise BadInputError("the moulds standing is a whole number")
        if self.moulds_standing < 0:
            raise BadInputError("the moulds standing cannot be negative")
        if not isinstance(self.sand_per_mould, Pounds):
            raise BadInputError("the sand a mould takes is a bulk mass")

    @property
    def counted_vessels(self) -> tuple[Vessel, ...]:
        return tuple(vessel for vessel in self.vessels if vessel.is_counted)

    @property
    def uncounted_vessels(self) -> tuple[Vessel, ...]:
        return tuple(vessel for vessel in self.vessels if not vessel.is_counted)

    @property
    def is_complete(self) -> bool:
        """Whether every vessel gave a mass."""
        return not self.uncounted_vessels

    @property
    def in_vessels(self) -> Pounds:
        return total_pounds([vessel.mass for vessel in self.counted_vessels])

    @property
    def on_the_floor(self) -> Pounds:
        """The estimated share standing in moulds."""
        return self.sand_per_mould.scaled(self.moulds_standing)

    @property
    def total(self) -> Pounds:
        return self.in_vessels + self.on_the_floor

    @property
    def floor_share(self) -> Decimal:
        """How much of the count is the estimated term rather than a measured one."""
        if self.total.is_zero:
            return Decimal("0.000000")
        return self.on_the_floor.fraction_of(self.total)

    def __str__(self) -> str:
        state = "complete" if self.is_complete else "partial"
        return f"{self.system_name} on {self.counted_on}: {self.total} ({state})"


@dataclass(frozen=True)
class Reconciliation:
    """The count set against the figure the system was carrying."""

    count: Count
    standing: Pounds
    was_measured: bool

    @property
    def found(self) -> Pounds:
        return self.count.total

    @property
    def drift(self) -> Decimal:
        """Signed, as a fraction of the standing figure."""
        if self.standing.is_zero:
            raise RuleError("a system carrying no sand cannot be reconciled")
        return ((self.found.value - self.standing.value) / self.standing.value).quantize(
            Decimal("0.0001")
        )

    @property
    def is_suspect(self) -> bool:
        """A shortfall too large to be drift, on a count that did not reach everything."""
        return self.drift <= -SUSPECT_SHORTFALL and not self.count.is_complete

    def verdict(self) -> str:
        """One line for the operator taking the count."""
        if not self.count.is_complete:
            missed = ", ".join(v.name for v in self.count.uncounted_vessels)
            tail = f"; {missed} had no measured density"
        else:
            tail = ""
        basis = "measured" if self.was_measured else "nameplate"
        if self.is_suspect:
            return (
                f"found {self.found} against a {basis} {self.standing}, which is "
                f"{self.drift:.1%} and too far to be drift on a partial count{tail}"
            )
        return f"found {self.found} against a {basis} {self.standing}, {self.drift:+.1%}{tail}"

    def __str__(self) -> str:
        return self.verdict()


def reconcile(system: SandSystem, count: Count) -> Reconciliation:
    """Set an inventory against what the system was carrying."""
    if not isinstance(system, SandSystem):
        raise BadInputError("a sand system is expected")
    if not isinstance(count, Count):
        raise BadInputError("an inventory count is expected")
    if count.system_name != system.name:
        raise RuleError(f"this count is of {count.system_name} and the system is {system.name}")
    return Reconciliation(count=count, standing=system.mass, was_measured=system.is_measured)


def apply_count(system: SandSystem, count: Count) -> SandSystem:
    """Adopt an inventory, or refuse to adopt one that cannot stand up.

    A partial count is not adopted. Half a number written into the mass is worse
    than the nameplate figure it replaced, because it comes back wearing the
    measured basis and everything downstream stops asking.
    """
    reconcile(system, count)
    if not count.is_complete:
        missed = ", ".join(v.name for v in count.uncounted_vessels)
        raise RuleError(
            f"this count did not reach {missed}, so adopting it would record a "
            "partial figure as a measurement"
        )
    return system.inventoried(count.total, count.counted_on)


__all__ = [
    "Count",
    "Reconciliation",
    "SMALLEST_VESSEL_CUBIC_FEET",
    "SUSPECT_SHORTFALL",
    "Vessel",
    "apply_count",
    "reconcile",
]
