"""Commands for incoming material: booking a lot in, checking it, releasing it.

``material verify`` prints the comparison and stops. It does not release or
quarantine the lot, and that is deliberate: the arithmetic says whether the
claims held and a person decides what to do about it, because releasing sand
into a system is a decision somebody's name goes on. ``material release`` takes
that name as an argument for the same reason.

``material held`` is the morning walk round. Everything not released, oldest
first, with why. A shop with sand it cannot use needs that list to be one
command and not a query.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

import click

from mullerbox.addition.material import Material
from mullerbox.cli.context import Context, handle, pass_context
from mullerbox.cli.main import main
from mullerbox.errors import BadInputError
from mullerbox.report.layout import Column, Table
from mullerbox.store import lot_repo
from mullerbox.supplier.incoming import verify
from mullerbox.supplier.lot import Certificate, Lot
from mullerbox.units.bulk import Pounds
from mullerbox.units.percent import Percent


@main.group("material")
def materials() -> None:
    """Incoming lots, their certificates and their release."""


@materials.command("book-in")
@click.argument("lot_id")
@click.argument("material_name")
@click.argument("mass")
@click.option("--on", "delivered", required=True, help="yyyy-mm-dd")
@click.option("--certificate", required=True, help="The supplier's COA number.")
@click.option("--gfn", default=None, help="Claimed grain fineness.")
@click.option("--clay", default=None, help="Claimed clay, percent.")
@click.option("--moisture", default=None, help="Claimed moisture, percent.")
@click.option("--loi", default=None, help="Claimed loss on ignition, percent.")
@pass_context
@handle
def book_in(
    context: Context,
    lot_id: str,
    material_name: str,
    mass: str,
    delivered: str,
    certificate: str,
    gfn: str | None,
    clay: str | None,
    moisture: str | None,
    loi: str | None,
) -> None:
    """Book a delivered lot onto the book with what its certificate claims."""
    claims: dict[str, object] = {}
    if gfn is not None:
        claims["grain_fineness"] = _decimal_from(gfn, "grain fineness")
    for name, value in (("clay", clay), ("moisture", moisture), ("loss_on_ignition", loi)):
        if value is not None:
            claims[name] = Percent(value)
    built = Lot(
        lot_id=lot_id,
        material=_material_from(material_name),
        mass=Pounds(mass),
        delivered_on=_date_from(delivered),
        certificate=Certificate(number=certificate, **claims),  # type: ignore[arg-type]
    )
    with context.book() as book:
        lot_repo.save_lot(book, built)
    claimed = len(built.certificate.claims)
    context.say(f"booked in {built}, certificate claims {claimed} properties")


@materials.command("verify")
@click.argument("lot_id")
@click.option("--gfn", default=None, help="The lab's grain fineness.")
@click.option("--clay", default=None, help="The lab's clay, percent.")
@click.option("--moisture", default=None, help="The lab's moisture, percent.")
@click.option("--loi", default=None, help="The lab's loss on ignition, percent.")
@pass_context
@handle
def verify_lot(
    context: Context,
    lot_id: str,
    gfn: str | None,
    clay: str | None,
    moisture: str | None,
    loi: str | None,
) -> None:
    """Compare the lab's own readings against the certificate. Changes nothing."""
    measured: dict[str, object] = {}
    if gfn is not None:
        measured["grain_fineness"] = _decimal_from(gfn, "grain fineness")
    for name, value in (("clay", clay), ("moisture", moisture), ("loss_on_ignition", loi)):
        if value is not None:
            measured[name] = Percent(value)
    with context.book() as book:
        lot = lot_repo.load_lot(book, lot_id)
    checked = verify(lot, **measured)
    context.say(str(checked))
    for discrepancy in checked.discrepancies:
        context.say(f"  {discrepancy}")
    if checked.unchecked:
        names = ", ".join(checked.unchecked)
        context.say(f"  claims the lab did not check: {names}")


@materials.command("test")
@click.argument("lot_id")
@click.option("--note", default="", help="What the lab did.")
@pass_context
@handle
def mark_tested(context: Context, lot_id: str, note: str) -> None:
    """Mark that the lab has run its own tests on a lot."""
    with context.book() as book:
        lot_repo.update_lot(book, lot_repo.load_lot(book, lot_id).tested(note))
    context.say(f"lot {lot_id} is tested")


@materials.command("release")
@click.argument("lot_id")
@click.option("--by", required=True, help="Who is releasing it.")
@pass_context
@handle
def release(context: Context, lot_id: str, by: str) -> None:
    """Release a tested lot into the system, naming who released it."""
    with context.book() as book:
        lot_repo.update_lot(book, lot_repo.load_lot(book, lot_id).released(by=by))
    context.say(f"lot {lot_id} released by {by}")


@materials.command("quarantine")
@click.argument("lot_id")
@click.option("--why", required=True, help="Why it is being held.")
@pass_context
@handle
def quarantine(context: Context, lot_id: str, why: str) -> None:
    """Hold a lot out of the system."""
    with context.book() as book:
        lot_repo.update_lot(book, lot_repo.load_lot(book, lot_id).quarantined(why))
    context.say(f"lot {lot_id} quarantined: {why}")


@materials.command("held")
@pass_context
@handle
def list_held(context: Context) -> None:
    """Every lot that cannot go into the system, oldest first."""
    with context.book() as book:
        lots = lot_repo.held(book)
    if not lots:
        context.say("nothing held")
        return
    table = Table(
        columns=(
            Column("lot"),
            Column("material"),
            Column.number("mass"),
            Column("delivered"),
            Column("state"),
            Column("note"),
        )
    )
    for lot in lots:
        table.add(
            lot.lot_id,
            lot.material.label,
            str(lot.mass),
            str(lot.delivered_on),
            lot.state.label,
            lot.note,
        )
    for line in table.render():
        context.say(line)


def _material_from(text: str) -> Material:
    key = text.strip().upper().replace("-", "_").replace(" ", "_")
    try:
        return Material[key]
    except KeyError:
        known = ", ".join(m.name.lower() for m in Material)
        raise BadInputError(f"{text!r} is not a material; try {known}") from None


def _decimal_from(text: str, what: str) -> Decimal:
    try:
        return Decimal(text.strip())
    except InvalidOperation:
        raise BadInputError(f"{text!r} is not a {what}") from None


def _date_from(text: str) -> date:
    try:
        return date.fromisoformat(text.strip())
    except ValueError:
        raise BadInputError(f"{text!r} is not a date in yyyy-mm-dd form") from None


__all__ = [
    "book_in",
    "list_held",
    "mark_tested",
    "materials",
    "quarantine",
    "release",
    "verify_lot",
]
