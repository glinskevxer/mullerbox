"""Commands for what came off the line: heats, castings and the scrap sheet.

``production scrap`` is the command the whole defect layer exists for, and
running it end to end is what proves that layer works. It loads a heat, resolves
the spec for every class that heat ran, gathers the sand readings that counted
at the pour date, and charges each scrapped casting once.

The resolution is per mold class rather than per heat. A heat that ran two
classes gets two resolutions and its castings are judged against whichever
applied to the mold they came out of, which is why the sheet can charge one
casting to the sand and the one beside it to the pattern on identical sand.
"""

from __future__ import annotations

import click

from mullerbox.cli.context import Context, handle, pass_context
from mullerbox.cli.main import main
from mullerbox.cli.parsing import read_date, read_member
from mullerbox.defect.kind import DefectKind
from mullerbox.defect.scrap import report_on
from mullerbox.errors import BadInputError, NotFoundError
from mullerbox.heat.heat import Casting, Disposition, Heat, Mold
from mullerbox.ingest.production import load_inspections
from mullerbox.ingest.reader import read_sheet
from mullerbox.report.layout import Column, Table
from mullerbox.report.scrap import scrap_sheet, totals_line
from mullerbox.spec.pattern import PatternClass
from mullerbox.spec.sheet import resolve
from mullerbox.store import heat_repo, reading_repo, spec_repo
from mullerbox.units.bulk import Pounds


@main.group("production")
def production() -> None:
    """Heats, castings and the scrap that came off them."""


@production.command("record-heat")
@click.argument("heat_number")
@click.option("--on", "poured", required=True, help="yyyy-mm-dd")
@click.option(
    "--mold",
    "molds",
    multiple=True,
    required=True,
    metavar="ID:CLASS:SAND",
    help="A mold, its pattern class and the sand in it. Repeat for each.",
)
@click.option(
    "--casting",
    "castings",
    multiple=True,
    metavar="ID:MOLD:WEIGHT:DISPOSITION",
    help="A casting and what happened to it. Repeat for each.",
)
@pass_context
@handle
def record_heat(
    context: Context,
    heat_number: str,
    poured: str,
    molds: tuple[str, ...],
    castings: tuple[str, ...],
) -> None:
    """Record a heat, its molds and its castings in one go."""
    by_mold: dict[str, list[Casting]] = {}
    for spec in castings:
        parts = spec.split(":")
        if len(parts) != 4:
            raise BadInputError(f"{spec!r} is not ID:MOLD:WEIGHT:DISPOSITION")
        casting_id, mold_id, weight, disposition = parts
        by_mold.setdefault(mold_id, []).append(
            Casting(
                casting_id=casting_id,
                weight=Pounds(weight),
                disposition=read_member(disposition, Disposition, "a disposition"),
            )
        )
    built: list[Mold] = []
    for spec in molds:
        parts = spec.split(":")
        if len(parts) != 3:
            raise BadInputError(f"{spec!r} is not ID:CLASS:SAND")
        mold_id, pattern, sand = parts
        built.append(
            Mold(
                mold_id=mold_id,
                pattern=read_member(pattern, PatternClass, "a pattern class"),
                sand=Pounds(sand),
                castings=tuple(by_mold.pop(mold_id, [])),
            )
        )
    if by_mold:
        stray = sorted(by_mold)[0]
        raise BadInputError(f"casting given for mold {stray!r}, which is not on the heat")
    heat = Heat(heat_number=heat_number, poured_on=read_date(poured), molds=tuple(built))
    with context.book() as book:
        heat_repo.save_heat(book, heat)
    context.say(f"recorded {heat}, {heat.metal} of metal in {heat.sand} of sand")


@production.command("heats")
@click.option("--on", "as_of", default=None, help="Narrow to one day, yyyy-mm-dd.")
@pass_context
@handle
def list_heats(context: Context, as_of: str | None) -> None:
    """List the heats on the book."""
    when = read_date(as_of) if as_of else None
    with context.book() as book:
        numbers = heat_repo.list_heats(book, when)
        table = Table(
            columns=(
                Column("heat"),
                Column("poured"),
                Column.number("molds"),
                Column.number("metal"),
                Column.number("scrap"),
            )
        )
        for number in numbers:
            heat = heat_repo.load_heat(book, number)
            rate = "" if heat.metal.is_zero else f"{heat.scrap_rate:.2%}"
            table.add(number, str(heat.poured_on), str(len(heat.molds)), str(heat.metal), rate)
    if not numbers:
        context.say("no heats on the book")
        return
    for line in table.render():
        context.say(line)


@production.command("scrap")
@click.argument("heat_number")
@click.option(
    "--inspections",
    "path",
    default=None,
    type=click.Path(),
    help="An inspection sheet naming the defects on each casting.",
)
@click.option("--summary", is_flag=True, help="One line rather than the full sheet.")
@pass_context
@handle
def scrap(context: Context, heat_number: str, path: str | None, summary: bool) -> None:
    """Charge a heat's scrap, resolving the spec per mold class."""
    defects: dict[str, tuple[DefectKind, ...]] = {}
    if path is not None:
        load = load_inspections(read_sheet(path))
        for problem in load.problems:
            context.warn(str(problem))
        defects = dict(load.defects_by_casting)
    with context.book() as book:
        heat = heat_repo.load_heat(book, heat_number)
        sheet = spec_repo.current_sheet(book, heat.poured_on)
        gathered = reading_repo.gather(book, heat.poured_on)
    if not heat.molds:
        raise NotFoundError("molds on heat", heat_number)
    specs = {cls: resolve(sheet, cls) for cls in heat.patterns}
    report = report_on(heat, defects, specs, gathered.readings)
    if summary:
        context.say(totals_line(report))
        return
    for line in scrap_sheet(report).render():
        context.say(line)


__all__ = ["list_heats", "production", "record_heat", "scrap"]
