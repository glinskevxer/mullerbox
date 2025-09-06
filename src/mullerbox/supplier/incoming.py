"""Checking a delivered lot against what its certificate claimed.

The check is a comparison, never a merge. Each claim the supplier made is put
next to the lab's own reading of the same lot and the gap is reported. Nothing
here decides that one of the two is correct: the lab's number governs what the
shop does with the sand, and the supplier's number governs what the shop says to
the supplier, and both are needed for different conversations.

**A claim the supplier did not make is not a pass.** A certificate with only a
number on it agrees with everything. So the verification reports unchecked
claims separately from checked ones, and a lot whose certificate claimed nothing
comes back with zero discrepancies and a warning that says so, rather than a
clean bill.

**The tolerances are the supplier's, not the shop's.** They are what a delivery
is allowed to vary by, which is wider than what the sand system is allowed to
vary by, because a lot is one delivery and the system is an average of many. A
lot inside the delivery tolerance can still move a system that is already at the
edge of its band, and this module says nothing about that.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from mullerbox.errors import BadInputError
from mullerbox.supplier.lot import Lot
from mullerbox.units.percent import Percent

# What a delivery is allowed to differ from its certificate by.
FINENESS_TOLERANCE = Decimal("3.0")
CLAY_TOLERANCE = Decimal("0.30")
MOISTURE_TOLERANCE = Decimal("0.50")
LOI_TOLERANCE = Decimal("0.30")

_TOLERANCES: dict[str, Decimal] = {
    "grain_fineness": FINENESS_TOLERANCE,
    "clay": CLAY_TOLERANCE,
    "moisture": MOISTURE_TOLERANCE,
    "loss_on_ignition": LOI_TOLERANCE,
}

_LABELS: dict[str, str] = {
    "grain_fineness": "grain fineness",
    "clay": "clay",
    "moisture": "moisture",
    "loss_on_ignition": "loss on ignition",
}


@dataclass(frozen=True)
class Discrepancy:
    """One claim that did not survive the lab's own test."""

    field: str
    claimed: Decimal
    measured: Decimal
    tolerance: Decimal

    @property
    def gap(self) -> Decimal:
        return self.measured - self.claimed

    @property
    def label(self) -> str:
        return _LABELS.get(self.field, self.field)

    def __str__(self) -> str:
        return (
            f"{self.label}: certificate says {self.claimed}, "
            f"the lab reads {self.measured}, {self.gap:+} against a "
            f"tolerance of {self.tolerance}"
        )


@dataclass(frozen=True)
class Verification:
    """What the lab found against what the supplier claimed."""

    lot: Lot
    checked: tuple[str, ...]
    unchecked: tuple[str, ...]
    discrepancies: tuple[Discrepancy, ...]

    @property
    def agrees(self) -> bool:
        return not self.discrepancies

    @property
    def checked_nothing(self) -> bool:
        """True when there was nothing to check, which is not the same as a pass."""
        return not self.checked

    def recommendation(self) -> str:
        """What to do with the lot, in one line."""
        if self.checked_nothing:
            return (
                f"certificate {self.lot.certificate.number} claims nothing that was "
                "checked, so this is not a clearance"
            )
        if self.agrees:
            return f"{len(self.checked)} claims checked and all agree, fit to release"
        return (
            f"{len(self.discrepancies)} of {len(self.checked)} claims are outside "
            "the delivery tolerance, quarantine and raise it with the supplier"
        )

    def __str__(self) -> str:
        return f"lot {self.lot.lot_id}: {self.recommendation()}"


def _as_decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, Percent):
        return value.value
    raise BadInputError("a measured value is a percentage or a decimal")


def verify(lot: Lot, **measured: object) -> Verification:
    """Compare the lab's readings against the certificate's claims.

    Keyword arguments name the certificate's fields. A field the lab did not
    measure is skipped; a field the certificate did not claim is skipped and
    reported as unchecked. Only the intersection is a comparison.
    """
    if not isinstance(lot, Lot):
        raise BadInputError("a lot is expected")
    unknown = [name for name in measured if name not in _TOLERANCES]
    if unknown:
        known = ", ".join(sorted(_TOLERANCES))
        raise BadInputError(f"{unknown[0]!r} is not on a certificate; try {known}")
    certificate = lot.certificate
    checked: list[str] = []
    unchecked: list[str] = []
    found: list[Discrepancy] = []
    for field in sorted(_TOLERANCES):
        claimed = getattr(certificate, field)
        if claimed is None:
            continue
        if field not in measured:
            unchecked.append(field)
            continue
        claimed_value = _as_decimal(claimed)
        measured_value = _as_decimal(measured[field])
        tolerance = _TOLERANCES[field]
        checked.append(field)
        if abs(measured_value - claimed_value) > tolerance:
            found.append(
                Discrepancy(
                    field=field,
                    claimed=claimed_value,
                    measured=measured_value,
                    tolerance=tolerance,
                )
            )
    return Verification(
        lot=lot,
        checked=tuple(checked),
        unchecked=tuple(unchecked),
        discrepancies=tuple(found),
    )


__all__ = [
    "CLAY_TOLERANCE",
    "Discrepancy",
    "FINENESS_TOLERANCE",
    "LOI_TOLERANCE",
    "MOISTURE_TOLERANCE",
    "Verification",
    "verify",
]
