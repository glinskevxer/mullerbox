"""Commands for what the sand cost, and what it cost per ton of good iron.

``cost shift`` takes the additions as options rather than reading them off the
book, because the book records what the *plan* said and the cost has to be
against what actually went in. Those differ, routinely, and a cost report built
on the plan flatters a shift where the operator overdosed.

The good iron figure comes off the heats on the book, because that one is
recorded and a typed figure would be somebody's memory of it. Where the two
sources are available the recorded one wins; where only a typed one exists the
command says so on the sheet.
"""

from __future__ import annotations

import click

from mullerbox.addition.material import Addition, Material
from mullerbox.charge.budget import Budget, variance_of
from mullerbox.charge.cost import cost_of
from mullerbox.cli.context import Context, handle, pass_context
from mullerbox.cli.main import main
from mullerbox.cli.parsing import read_date, read_decimal, read_member
from mullerbox.errors import BadInputError, RuleError
from mullerbox.heat.heat import Disposition
from mullerbox.report.layout import Column, Table, heading
from mullerbox.store import heat_repo, price_repo
from mullerbox.units.bulk import Pounds
from mullerbox.units.money import PricePerTon


@main.group("cost")
def costing() -> None:
    """Material prices and what a shift's sand cost."""


@costing.command("set-price")
@click.argument("material_name")
@click.argument("per_ton")
@click.option("--from", "effective", required=True, help="Effective from, yyyy-mm-dd.")
@pass_context
@handle
def set_price(context: Context, material_name: str, per_ton: str, effective: str) -> None:
    """Record what a material costs from a date."""
    material = read_member(material_name, Material, "a material")
    with context.book() as book:
        price_repo.set_price(book, material, PricePerTon(per_ton), read_date(effective))
    context.say(f"{material.label} is {PricePerTon(per_ton)} from {effective}")


@costing.command("prices")
@click.option("--on", "as_of", required=True, help="yyyy-mm-dd")
@pass_context
@handle
def prices(context: Context, as_of: str) -> None:
    """Show the price list as it stood on a date, and any holes in it."""
    when = read_date(as_of)
    with context.book() as book:
        priced = price_repo.priced_materials(book, when)
        table = Table(columns=(Column("material"), Column.number("per ton")))
        for material in Material:
            if material in priced:
                table.add(material.label, str(price_repo.price_on(book, material, when)))
            else:
                table.add(material.label, "NOT PRICED")
    for line in table.render():
        context.say(line)
    missing = [m for m in Material if m not in priced]
    if missing:
        names = ", ".join(m.label for m in missing)
        context.say("")
        context.say(f"no price on or before {when} for: {names}")


@costing.command("shift")
@click.option("--on", "as_of", required=True, help="yyyy-mm-dd")
@click.option("--bentonite", default="0", help="Bentonite actually charged, pounds.")
@click.option("--seacoal", default="0", help="Seacoal actually charged, pounds.")
@click.option("--new-sand", default="0", help="New sand actually charged, pounds.")
@click.option("--water", default="0", help="Water actually charged, pounds.")
@click.option(
    "--good-iron",
    default=None,
    help="Good iron in pounds. Taken off the heats on the book when left out.",
)
@pass_context
@handle
def shift(
    context: Context,
    as_of: str,
    bentonite: str,
    seacoal: str,
    new_sand: str,
    water: str,
    good_iron: str | None,
) -> None:
    """Price a shift's actual additions against the good iron it made."""
    when = read_date(as_of)
    charged = [
        Addition(material=material, mass=Pounds(mass), reason="charged on the shift")
        for material, mass in (
            (Material.BENTONITE, bentonite),
            (Material.SEACOAL, seacoal),
            (Material.NEW_SAND, new_sand),
            (Material.WATER, water),
        )
        if Pounds(mass).value > 0
    ]
    with context.book() as book:
        listed = price_repo.price_list_on(book, when)
        if good_iron is None:
            shipped, source = _shipped_on(book, when), "from the heats on the book"
        else:
            shipped, source = Pounds(good_iron), "as typed, not from the book"
    sheet = cost_of(charged, listed, shipped)
    for line in heading(f"sand cost for {when}"):
        context.say(line)
    context.say(f"good iron {shipped} {source}")
    context.say("")
    table = Table(
        columns=(
            Column("material"),
            Column.number("charged"),
            Column.number("per ton"),
            Column.number("cost"),
        )
    )
    for entry in sheet.lines:
        table.add(entry.material.label, str(entry.mass), str(entry.price), str(entry.cost))
    for line in table.render():
        context.say(line)
    context.say("")
    context.say(f"total {sheet.total}")
    if shipped.is_zero:
        context.say("no good iron, so there is no cost per ton")
        return
    context.say(f"per ton of good iron ${sheet.per_ton_of_good_iron}")
    heaviest = sheet.heaviest_line
    if heaviest is not None:
        context.say(f"largest line is {heaviest.material.label} at {heaviest.cost}")


def _shipped_on(book: object, when: object) -> Pounds:
    """Good iron off the heats poured that day, by weight of shipped castings."""
    from datetime import date

    from mullerbox.store.connection import Book

    if not isinstance(book, Book):
        raise BadInputError("an open book is expected")
    if not isinstance(when, date):
        raise BadInputError("a date is expected")
    running = Pounds.zero()
    for number in heat_repo.list_heats(book, when):
        heat = heat_repo.load_heat(book, number)
        for casting in heat.castings:
            if casting.disposition is Disposition.SHIPPED:
                running = running + casting.weight
    if running.is_zero and not heat_repo.list_heats(book, when):
        raise RuleError(f"no heats were recorded on {when}, so there is no good iron figure")
    return running


@costing.command("variance")
@click.argument("material_name")
@click.option("--on", "as_of", required=True, help="yyyy-mm-dd")
@click.option("--budget-lb-per-ton", required=True, help="Budgeted usage.")
@click.option("--budget-price", required=True, help="Budgeted price per ton.")
@click.option("--used", required=True, help="What was actually charged, pounds.")
@click.option("--good-iron", required=True, help="Good iron shipped, pounds.")
@pass_context
@handle
def variance(
    context: Context,
    material_name: str,
    as_of: str,
    budget_lb_per_ton: str,
    budget_price: str,
    used: str,
    good_iron: str,
) -> None:
    """Split a material's overspend into rate and usage.

    Reported as one number the two halves cancel, and a month where purchasing
    saved five percent while the muller overdosed by five percent reads as on
    budget. The split is the report, not a footnote under it.
    """
    material = read_member(material_name, Material, "a material")
    when = read_date(as_of)
    shipped = Pounds(good_iron)
    charged = [Addition(material=material, mass=Pounds(used), reason="charged on the shift")]
    with context.book() as book:
        listed = price_repo.price_list_on(book, when)
    costed = cost_of(charged, listed, shipped)
    budget = Budget(
        material=material,
        pounds_per_ton=read_decimal(budget_lb_per_ton, "budgeted usage"),
        price=PricePerTon(budget_price),
    )
    found = variance_of(budget, costed, shipped)
    table = Table(columns=(Column("term"), Column.number("value")))
    table.add("budgeted usage", str(budget.expected_usage(shipped)))
    table.add("actually used", str(Pounds(used)))
    table.add("budgeted cost", str(found.budgeted))
    table.add("actual cost", str(found.actual))
    table.add("rate variance", f"{found.rate:+}")
    table.add("usage variance", f"{found.usage:+}")
    table.add("total variance", f"{found.total:+}")
    for line in table.render():
        context.say(line)
    context.say("")
    context.say(found.finding())


__all__ = ["costing", "prices", "set_price", "shift", "variance"]
