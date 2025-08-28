"""A delivered lot, and the certificate that came with it.

A certificate of analysis is what the supplier says the material is. It is not a
measurement the shop made and this package never treats it as one. Every number
on it is a claim, kept separate from the lab's own reading of the same lot, and
the two are compared rather than merged.

That separation is the whole reason this module exists. A shop that loads the
certificate values into the same table as its own results ends up with a sand
system whose recorded GFN came half from its own shaker and half from a supplier
who has never seen the shaker. When the numbers disagree, and they do, there is
nothing left to compare against.

**A lot has a state and the ordering is one way.** Delivered, then tested, then
released or quarantined. Nothing goes back to delivered, and nothing is used out
of quarantine without a release that names who released it. Sand that went into
the system before it was tested is a real event that a foundry needs to be able
to reconstruct, so the state is on the lot rather than being inferred from
whether a test exists.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from enum import Enum

from mullerbox.addition.material import Material
from mullerbox.errors import BadInputError, StateError
from mullerbox.units.bulk import Pounds
from mullerbox.units.percent import Percent


class LotState(Enum):
    """Where a lot is in its acceptance."""

    DELIVERED = "delivered"
    TESTED = "tested"
    RELEASED = "released"
    QUARANTINED = "quarantined"

    @property
    def label(self) -> str:
        return self.value

    @property
    def may_be_used(self) -> bool:
        return self is LotState.RELEASED


@dataclass(frozen=True)
class Certificate:
    """What the supplier claims about a lot. Claims, not measurements."""

    number: str
    grain_fineness: Decimal | None = None
    clay: Percent | None = None
    moisture: Percent | None = None
    loss_on_ignition: Percent | None = None

    def __post_init__(self) -> None:
        if not self.number.strip():
            raise BadInputError("a certificate needs a number")
        if self.grain_fineness is not None:
            if not isinstance(self.grain_fineness, Decimal):
                raise BadInputError("a claimed fineness is a decimal")
            if self.grain_fineness <= 0:
                raise BadInputError("a claimed fineness has to be above zero")
        for name in ("clay", "moisture", "loss_on_ignition"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, Percent):
                raise BadInputError(f"a claimed {name.replace('_', ' ')} is a percentage")

    @property
    def claims(self) -> tuple[str, ...]:
        """Which fields the supplier actually filled in."""
        return tuple(
            name
            for name in ("grain_fineness", "clay", "moisture", "loss_on_ignition")
            if getattr(self, name) is not None
        )

    @property
    def is_bare(self) -> bool:
        """A certificate with a number and nothing else is common and useless."""
        return not self.claims


@dataclass(frozen=True)
class Lot:
    """One delivery of one material."""

    lot_id: str
    material: Material
    mass: Pounds
    delivered_on: date
    certificate: Certificate
    state: LotState = LotState.DELIVERED
    released_by: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        if not self.lot_id.strip():
            raise BadInputError("a lot needs an identifier")
        if not isinstance(self.material, Material):
            raise BadInputError("a lot is of a material")
        if not isinstance(self.mass, Pounds):
            raise BadInputError("a lot mass is a bulk mass")
        if self.mass.is_zero:
            raise BadInputError("a lot with nothing in it is not a lot")
        if not isinstance(self.delivered_on, date):
            raise BadInputError("a lot is dated")
        if not isinstance(self.certificate, Certificate):
            raise BadInputError("a lot carries a certificate")
        if not isinstance(self.state, LotState):
            raise BadInputError("a lot has a state")
        if self.state is LotState.RELEASED and not self.released_by.strip():
            raise BadInputError("a released lot names who released it")

    @property
    def may_be_used(self) -> bool:
        return self.state.may_be_used

    def require_usable(self) -> None:
        if not self.may_be_used:
            raise StateError(
                f"lot {self.lot_id} is {self.state.label} and cannot go into the system"
            )

    def tested(self, note: str = "") -> Lot:
        """Mark that the lab has run its own tests on this lot."""
        if self.state is not LotState.DELIVERED:
            raise StateError(f"lot {self.lot_id} is {self.state.label} and has already been tested")
        return replace(self, state=LotState.TESTED, note=note)

    def released(self, by: str) -> Lot:
        """Let the lot into the system, naming who said so."""
        if self.state is not LotState.TESTED:
            raise StateError(f"lot {self.lot_id} is {self.state.label} and has not been tested")
        if not by.strip():
            raise BadInputError("a release names who released it")
        return replace(self, state=LotState.RELEASED, released_by=by)

    def quarantined(self, why: str) -> Lot:
        """Hold the lot, from any state before release."""
        if self.state is LotState.RELEASED:
            raise StateError(f"lot {self.lot_id} has been released and is already in the system")
        if not why.strip():
            raise BadInputError("a quarantine names a reason")
        return replace(self, state=LotState.QUARANTINED, note=why)

    def __str__(self) -> str:
        return f"lot {self.lot_id}: {self.mass} of {self.material.label}, {self.state.label}"


__all__ = ["Certificate", "Lot", "LotState"]
