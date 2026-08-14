"""Commands that write the book back out as csv.

Each export names the columns the matching reader wants, so an exported file
goes straight back in. That is not a convenience: it is how a shop moves a
book between machines, and how anything exported can be checked by reading it
back rather than by eye.

``export results`` writes the bench sheet shape, so an export from one book
imports into another. ``export scrap`` does not, and says so in its help: it is
a report shape for a spreadsheet, and nothing reads it back.
"""

from __future__ import annotations

import click

from mullerbox.cli.context import Context, handle, pass_context
from mullerbox.cli.judging import distribution_for, sample_option
from mullerbox.cli.main import main
from mullerbox.cli.parsing import read_date
from mullerbox.defect.kind import Culprit
from mullerbox.defect.scrap import report_on
from mullerbox.errors import NotFoundError
from mullerbox.export.writer import write_sheet
from mullerbox.ingest.bench import COLUMNS as BENCH_COLUMNS
from mullerbox.props.kind import PropertyKind
from mullerbox.report.inventory import inventory_report
from mullerbox.spec.sheet import resolve
from mullerbox.store import (
    heat_repo,
    inventory_repo,
    reading_repo,
    result_repo,
    spec_repo,
)


@main.group("export")
def exporting() -> None:
    """Write the book back out as csv."""


@exporting.command("results")
@click.argument("path", type=click.Path())
@click.option(
    "--property",
    "property_name",
    default=None,
    help="Narrow to one property. Everything when left out.",
)
@pass_context
@handle
def export_results(context: Context, path: str, property_name: str | None) -> None:
    """Write every property result in the bench sheet shape, ready to re-import."""
    from mullerbox.props.kind import parse_property

    kinds = [parse_property(property_name)] if property_name is not None else list(PropertyKind)
    rows: list[list[str]] = []
    with context.book() as book:
        for kind in kinds:
            for result in result_repo.results_of(book, kind):
                rows.append(
                    [
                        result.sample_id,
                        result.kind.label,
                        str(result.reading.value),
                        result.instrument_tag,
                        result.tested_on.isoformat(),
                    ]
                )
    written = write_sheet(path, list(BENCH_COLUMNS), rows)
    context.say(f"wrote {written} results to {path}")


@exporting.command("heats")
@click.argument("path", type=click.Path())
@pass_context
@handle
def export_heats(context: Context, path: str) -> None:
    """Write every casting with its heat, mold, class, weight and disposition."""
    rows: list[list[str]] = []
    with context.book() as book:
        for number in heat_repo.list_heats(book):
            heat = heat_repo.load_heat(book, number)
            for mold in heat.molds:
                for casting in mold.castings:
                    rows.append(
                        [
                            number,
                            heat.poured_on.isoformat(),
                            mold.mold_id,
                            mold.pattern.label,
                            casting.casting_id,
                            str(casting.weight.value),
                            casting.disposition.label,
                        ]
                    )
    written = write_sheet(
        path,
        ["heat", "poured", "mold", "class", "casting", "weight", "disposition"],
        rows,
    )
    context.say(f"wrote {written} castings to {path}")


@exporting.command("scrap")
@click.argument("path", type=click.Path())
@click.option("--heat", "heat_number", required=True, help="Which heat.")
@sample_option
@pass_context
@handle
def export_scrap(context: Context, path: str, heat_number: str, sample_id: str | None) -> None:
    """Write a heat's scrap charges. A report shape; nothing reads it back.

    The sheet carries a column saying which permeability band judged it. An
    export that did not would be read months later with no way to tell whether
    the anchor or the shifted band produced the charges in it.
    """
    with context.book() as book:
        heat = heat_repo.load_heat(book, heat_number)
        sheet = spec_repo.current_sheet(book, heat.poured_on)
        gathered = reading_repo.gather(book, heat.poured_on)
        distribution = distribution_for(book, sample_id)
    if not heat.molds:
        raise NotFoundError("molds on heat", heat_number)
    specs = {cls: resolve(sheet, cls) for cls in heat.patterns}
    report = report_on(heat, {}, specs, gathered.readings, distribution)
    judged = "shifted" if report.judged_on_analysis else "anchor"
    rows = [
        [
            report.heat_number,
            charge.casting.casting_id,
            charge.mold_id,
            charge.pattern.label,
            str(charge.weight.value),
            charge.culprit.label,
            ";".join(k.label for k in charge.sand_properties),
            judged,
        ]
        for charge in report.charges
    ]
    written = write_sheet(
        path,
        [
            "heat",
            "casting",
            "mold",
            "class",
            "weight",
            "charged to",
            "properties",
            "perm band",
        ],
        rows,
    )
    sand = report.weight_charged_to(Culprit.SAND)
    context.say(f"wrote {written} charges to {path}, {sand} of them to sand")


@exporting.command("prices")
@click.argument("path", type=click.Path())
@pass_context
@handle
def export_prices(context: Context, path: str) -> None:
    """Write the whole price history."""
    from mullerbox.addition.material import Material
    from mullerbox.store import price_repo

    rows: list[list[str]] = []
    with context.book() as book:
        for material in Material:
            for when, price in price_repo.history(book, material):
                rows.append([material.label, when.isoformat(), str(price.dollars)])
    written = write_sheet(path, ["material", "effective", "per ton"], rows)
    context.say(f"wrote {written} prices to {path}")


@exporting.command("due")
@click.argument("path", type=click.Path())
@click.option("--on", "as_of", required=True, help="yyyy-mm-dd")
@pass_context
@handle
def export_due(context: Context, path: str, as_of: str) -> None:
    """Write what the testing programme wants, most overdue first."""
    from mullerbox.store import programme_repo

    when = read_date(as_of)
    with context.book() as book:
        schedule = programme_repo.load_schedule(book)
        tested = programme_repo.last_tested(book)
    rows: list[list[str]] = []
    for entry in schedule.due_on(when, tested):
        last = entry.last_tested
        rows.append(
            [
                entry.kind.label,
                entry.frequency.label,
                "" if last is None else last.isoformat(),
                "" if last is None else str(entry.days_over),
            ]
        )
    written = write_sheet(path, ["property", "interval", "last tested", "days over"], rows)
    context.say(f"wrote {written} due tests to {path}")


@exporting.command("inventory")
@click.argument("path", type=click.Path())
@click.option("--name", required=True, help="Which sand system.")
@pass_context
@handle
def export_inventory(context: Context, path: str, name: str) -> None:
    """Write a system's inventory counts, one row per count.

    The vessels are not written. A count's vessels are the working out, and a
    sheet that carried them would have a variable number of columns; what the
    reader wants out of a file like this is the run, which is the totals and
    whether each one was complete.
    """
    with context.book() as book:
        dates = inventory_repo.count_dates(book, name)
        counts = [inventory_repo.load_count(book, name, when) for when in dates]
    report = inventory_report(name, counts)
    changes = {m.after.counted_on: m.change for m in report.movements}
    rows = [
        [
            name,
            str(count.counted_on),
            str(count.total.value),
            str(count.in_vessels.value),
            str(count.on_the_floor.value),
            str(changes.get(count.counted_on, "")),
            "complete" if count.is_complete else "partial",
        ]
        for count in counts
    ]
    written = write_sheet(
        path,
        ["system", "counted", "total", "in vessels", "on the floor", "change", "state"],
        rows,
    )
    context.say(f"wrote {written} counts to {path}")
    drift = report.drift_per_year
    if drift is not None:
        context.say(f"the run reads {drift:+} lb a year")


__all__ = [
    "export_due",
    "export_heats",
    "export_inventory",
    "export_prices",
    "export_results",
    "export_scrap",
    "exporting",
]
