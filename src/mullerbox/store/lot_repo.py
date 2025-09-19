"""Reading and writing delivered material lots.

The certificate's claims go in their own table, one row per field, rather than
as columns on the lot. Two reasons and the second is the operational one.

A certificate that claims nothing and a certificate that claims zero are
different, and a nullable column cannot tell them apart without a second column
saying whether the first is meaningful. A row per claim makes absence structural
rather than a convention.

And suppliers add fields. Every year somebody starts certifying a property
nobody used to, and a claims table takes that without a migration, where a
column per property needs one every time. The claim names are checked against
what the package understands on the way back out, so an unknown one is caught
rather than silently ignored.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from mullerbox.addition.material import Material
from mullerbox.errors import BadInputError, DuplicateError, NotFoundError
from mullerbox.store.connection import Book
from mullerbox.supplier.lot import Certificate, Lot, LotState
from mullerbox.units.bulk import Pounds
from mullerbox.units.percent import Percent

# The claim fields, and whether each is a bare decimal or a percentage.
_CLAIM_IS_PERCENT: dict[str, bool] = {
    "grain_fineness": False,
    "clay": True,
    "moisture": True,
    "loss_on_ignition": True,
}


def lot_exists(book: Book, lot_id: str) -> bool:
    return book.one("SELECT lot_id FROM material_lot WHERE lot_id = ?", (lot_id,)) is not None


def save_lot(book: Book, lot: Lot) -> None:
    """Write a lot and its certificate's claims."""
    if not isinstance(lot, Lot):
        raise BadInputError("a lot is expected")
    if lot_exists(book, lot.lot_id):
        raise DuplicateError("lot", lot.lot_id)
    with book.write():
        book.execute(
            "INSERT INTO material_lot"
            " (lot_id, material, mass_lb, delivered_on, certificate, state,"
            "  released_by, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                lot.lot_id,
                lot.material.name,
                str(lot.mass.value),
                lot.delivered_on.isoformat(),
                lot.certificate.number,
                lot.state.name,
                lot.released_by,
                lot.note,
            ),
        )
        for field in lot.certificate.claims:
            value = getattr(lot.certificate, field)
            raw = value.value if isinstance(value, Percent) else value
            book.execute(
                "INSERT INTO lot_claim (lot_id, field, value) VALUES (?, ?, ?)",
                (lot.lot_id, field, str(raw)),
            )


def update_lot(book: Book, lot: Lot) -> None:
    """Write a lot's state back, for a test, a release or a quarantine."""
    if not isinstance(lot, Lot):
        raise BadInputError("a lot is expected")
    if not lot_exists(book, lot.lot_id):
        raise NotFoundError("lot", lot.lot_id)
    with book.write():
        book.execute(
            "UPDATE material_lot SET state = ?, released_by = ?, note = ? WHERE lot_id = ?",
            (lot.state.name, lot.released_by, lot.note, lot.lot_id),
        )


def load_lot(book: Book, lot_id: str) -> Lot:
    """Rebuild a lot and its certificate."""
    row = book.one(
        "SELECT lot_id, material, mass_lb, delivered_on, certificate, state,"
        " released_by, note FROM material_lot WHERE lot_id = ?",
        (lot_id,),
    )
    if row is None:
        raise NotFoundError("lot", lot_id)
    claims = book.all(
        "SELECT field, value FROM lot_claim WHERE lot_id = ? ORDER BY field",
        (lot_id,),
    )
    built: dict[str, object] = {}
    for claim in claims:
        field = str(claim["field"])
        if field not in _CLAIM_IS_PERCENT:
            raise BadInputError(
                f"the book carries a claim for {field!r}, which is not on a certificate"
            )
        text = str(claim["value"])
        try:
            number = Decimal(text)
        except InvalidOperation:
            raise BadInputError(
                f"lot {lot_id} carries {text!r} as its {field}, which is not a number"
            ) from None
        built[field] = Percent(number) if _CLAIM_IS_PERCENT[field] else number
    return Lot(
        lot_id=str(row["lot_id"]),
        material=_material_from(str(row["material"])),
        mass=Pounds(str(row["mass_lb"])),
        delivered_on=date.fromisoformat(str(row["delivered_on"])),
        certificate=Certificate(number=str(row["certificate"]), **built),  # type: ignore[arg-type]
        state=_state_from(str(row["state"])),
        released_by=str(row["released_by"]),
        note=str(row["note"]),
    )


def list_lots(book: Book, material: Material | None = None) -> list[str]:
    if material is None:
        rows = book.all("SELECT lot_id FROM material_lot ORDER BY delivered_on, lot_id")
    else:
        if not isinstance(material, Material):
            raise BadInputError("a material is expected")
        rows = book.all(
            "SELECT lot_id FROM material_lot WHERE material = ? ORDER BY delivered_on, lot_id",
            (material.name,),
        )
    return [str(r["lot_id"]) for r in rows]


def held(book: Book) -> list[Lot]:
    """Every lot that cannot go into the system, for the morning walk round."""
    rows = book.all(
        "SELECT lot_id FROM material_lot WHERE state != ? ORDER BY delivered_on, lot_id",
        (LotState.RELEASED.name,),
    )
    return [load_lot(book, str(r["lot_id"])) for r in rows]


def _material_from(name: str) -> Material:
    try:
        return Material[name]
    except KeyError:
        raise BadInputError(f"the book carries material {name!r}, which is not one") from None


def _state_from(name: str) -> LotState:
    try:
        return LotState[name]
    except KeyError:
        raise BadInputError(f"the book carries lot state {name!r}, which is not one") from None


__all__ = ["held", "list_lots", "load_lot", "lot_exists", "save_lot", "update_lot"]
