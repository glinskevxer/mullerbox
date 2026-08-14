"""Commands for the published spec and the bands it resolves to.

``spec show`` takes a pattern class and prints the bands **in force for that
class**, which is not the same as the published sheet and is labelled so on
every run. This is the command that settles the argument on the floor about
whether the sand was in band, because the answer depends on what was being
molded and the command will not let you ask it without saying.

``spec load-default`` puts a working sheet on a fresh book so the rest of the
commands have something to judge against. It is a starting point and it says so;
a real shop replaces it with whatever metallurgy publishes.
"""

from __future__ import annotations

import click

from mullerbox.cli.context import Context, handle, pass_context
from mullerbox.cli.main import main
from mullerbox.cli.parsing import date_or_today, read_date
from mullerbox.props.kind import PropertyKind
from mullerbox.report.layout import Column, Table
from mullerbox.spec.band import Band
from mullerbox.spec.pattern import PatternClass, parse_pattern_class
from mullerbox.spec.revision import compare
from mullerbox.spec.sheet import SpecSheet, resolve
from mullerbox.store import spec_repo
from mullerbox.units.percent import Percent
from mullerbox.units.pressure import Psi, WetTensile
from mullerbox.units.scales import Hardness, Permeability

DEFAULT_NAME = "starting point"

DEFAULT_BANDS = {
    PropertyKind.COMPACTABILITY: Band.between(
        PropertyKind.COMPACTABILITY, Percent(38), Percent(44)
    ),
    PropertyKind.GREEN_COMPRESSION: Band.between(PropertyKind.GREEN_COMPRESSION, Psi(20), Psi(26)),
    PropertyKind.MOISTURE: Band.between(PropertyKind.MOISTURE, Percent("2.8"), Percent("3.6")),
    PropertyKind.MB_CLAY: Band.between(PropertyKind.MB_CLAY, Percent("7.0"), Percent("9.0")),
    PropertyKind.PERMEABILITY: Band.between(
        PropertyKind.PERMEABILITY, Permeability(90), Permeability(130)
    ),
    PropertyKind.LOI: Band.at_most(PropertyKind.LOI, Percent("3.5")),
    PropertyKind.VOLATILES: Band.at_most(PropertyKind.VOLATILES, Percent("2.2")),
    PropertyKind.FRIABILITY: Band.at_most(PropertyKind.FRIABILITY, Percent("12.0")),
    PropertyKind.WET_TENSILE: Band.at_least(PropertyKind.WET_TENSILE, WetTensile("0.20")),
    PropertyKind.MOLD_HARDNESS: Band.between(
        PropertyKind.MOLD_HARDNESS, Hardness(82), Hardness(90)
    ),
}


@main.group("spec")
def specs() -> None:
    """Published spec sheets and the bands they resolve to."""


@specs.command("load-default")
@click.option("--on", "published", required=True, help="yyyy-mm-dd")
@click.option("--name", default=DEFAULT_NAME, help="What to call the sheet.")
@pass_context
@handle
def load_default(context: Context, published: str, name: str) -> None:
    """Put a working spec sheet on the book as a starting point."""
    built = SpecSheet(name=name, bands=dict(DEFAULT_BANDS))
    with context.book() as book:
        spec_repo.save_sheet(book, built, read_date(published))
    context.say(f"published {name} with {len(built.covers)} bands")


@specs.command("sheets")
@pass_context
@handle
def list_sheets(context: Context) -> None:
    """List the published sheets, newest first."""
    with context.book() as book:
        names = spec_repo.list_sheets(book)
        table = Table(columns=(Column("sheet"), Column("published"), Column.number("bands")))
        for name in names:
            sheet = spec_repo.load_sheet(book, name)
            table.add(name, str(spec_repo.published_on(book, name)), str(len(sheet.covers)))
    if not names:
        context.say("no spec sheets on the book")
        return
    for line in table.render():
        context.say(line)


@specs.command("show")
@click.argument("pattern")
@click.option("--on", "as_of", default=None, help="Which sheet was in force, yyyy-mm-dd.")
@pass_context
@handle
def show(context: Context, pattern: str, as_of: str | None) -> None:
    """Show the bands in force for a pattern class."""
    cls = parse_pattern_class(pattern)
    when = date_or_today(as_of)
    with context.book() as book:
        sheet = spec_repo.current_sheet(book, when)
    resolved = resolve(sheet, cls)
    context.say(f"{sheet.name} resolved for {cls.label}")
    context.say(
        f"tolerance factor {cls.tolerance_factor}, "
        f"{len(resolved.covers)} of {len(cls.controlled)} controlled properties banded"
    )
    table = Table(
        columns=(
            Column("property"),
            Column("published"),
            Column("in force"),
        )
    )
    for kind in sorted(cls.controlled, key=lambda k: k.name):
        published_band = sheet.bands.get(kind)
        if published_band is None:
            table.add(kind.label, "not published", "not judged")
            continue
        in_force = resolved.band_for(kind)
        table.add(
            kind.label,
            str(published_band).removeprefix(f"{kind.label} "),
            str(in_force).removeprefix(f"{kind.label} "),
        )
    for line in table.render():
        context.say(line)
    missing = sheet.missing_for(cls)
    if missing:
        names = ", ".join(sorted(k.label for k in missing))
        context.say(f"controlled but not published: {names}")


@specs.command("classes")
@pass_context
@handle
def classes(context: Context) -> None:
    """List the pattern classes and what each one controls."""
    table = Table(
        columns=(
            Column("class"),
            Column("section"),
            Column("cored"),
            Column.number("tolerance"),
            Column.number("controls"),
        )
    )
    for cls in PatternClass:
        table.add(
            cls.label,
            cls.section.label,
            "yes" if cls.is_cored else "no",
            str(cls.tolerance_factor),
            str(len(cls.controlled)),
        )
    for line in table.render():
        context.say(line)


@specs.command("diff")
@click.argument("was")
@click.argument("now")
@pass_context
@handle
def diff(context: Context, was: str, now: str) -> None:
    """Say what a revision changed, material changes first.

    Material means a change that can put in band sand out of band on the day it
    is published: a moved aim, a narrowed band, or a property that was not
    controlled and now is. A widened band and a dropped property are real and
    put nothing out, so they are listed below the line.
    """
    with context.book() as book:
        before = spec_repo.load_sheet(book, was)
        after = spec_repo.load_sheet(book, now)
    revision = compare(before, after)
    for line in revision.render():
        context.say(line)
    if revision.is_empty:
        return
    context.say("")
    context.say(
        f"{len(revision.material)} of {len(revision.changes)} changes are "
        "material, meaning sand that was in band may not be"
    )


@specs.command("check-revision")
@click.argument("was")
@click.argument("now")
@click.argument("pattern")
@pass_context
@handle
def check_revision(context: Context, was: str, now: str, pattern: str) -> None:
    """Show what a revision does to the bands in force for one class of work."""
    cls = parse_pattern_class(pattern)
    with context.book() as book:
        before = spec_repo.load_sheet(book, was)
        after = spec_repo.load_sheet(book, now)
    old_bands = resolve(before, cls)
    new_bands = resolve(after, cls)
    table = Table(columns=(Column("property"), Column("was in force"), Column("now in force")))
    touched = sorted(old_bands.covers | new_bands.covers, key=lambda k: k.name)
    moved = 0
    for kind in touched:
        old = (
            str(old_bands.band_for(kind)).removeprefix(f"{kind.label} ")
            if old_bands.judges(kind)
            else "not judged"
        )
        new = (
            str(new_bands.band_for(kind)).removeprefix(f"{kind.label} ")
            if new_bands.judges(kind)
            else "not judged"
        )
        if old != new:
            moved += 1
        table.add(kind.label, old, new)
    for line in table.render():
        context.say(line)
    context.say("")
    context.say(f"{moved} of {len(touched)} bands in force for {cls.label} work move")


__all__ = [
    "DEFAULT_BANDS",
    "DEFAULT_NAME",
    "check_revision",
    "classes",
    "diff",
    "list_sheets",
    "load_default",
    "show",
    "specs",
]
