"""Commands for the things the shop sets up once and then leaves alone.

Screen series and instruments are catalogue: they change a few times a year and
everything else refers to them. So these commands are deliberately dull, and the
one interesting thing about them is that they refuse rather than overwrite. A
second ``series add`` for a name already on the book is an error, not an update,
because a series that quietly changed shape would silently invalidate every
fineness number ever computed against it and nothing downstream could tell.
"""

from __future__ import annotations

import click

from mullerbox.cal.instrument import Instrument, InstrumentKind
from mullerbox.cal.window import CalibrationWindow
from mullerbox.cli.context import Context, handle, pass_context
from mullerbox.cli.main import main
from mullerbox.cli.parsing import read_date, read_member
from mullerbox.report.layout import Column, Table
from mullerbox.screens.series import AFS_US_SERIES
from mullerbox.store import instrument_repo, series_repo


@main.group("catalogue")
def catalogue() -> None:
    """Screen series and lab instruments."""


@catalogue.command("load-afs")
@pass_context
@handle
def load_afs(context: Context) -> None:
    """Put the standard eleven screen AFS series on the book."""
    with context.book() as book:
        series_repo.save_series(book, AFS_US_SERIES)
    context.say(f"added {AFS_US_SERIES.name} with {len(AFS_US_SERIES)} screens")


@catalogue.command("series")
@pass_context
@handle
def list_series(context: Context) -> None:
    """List the screen series on the book."""
    with context.book() as book:
        names = series_repo.list_series(book)
        table = Table(columns=(Column("series"), Column.number("screens")))
        for name in names:
            table.add(name, str(len(series_repo.load_series(book, name))))
    if not names:
        context.say("no screen series on the book")
        return
    for line in table.render():
        context.say(line)


@catalogue.command("instrument-add")
@click.argument("tag")
@click.argument("kind")
@pass_context
@handle
def add_instrument(context: Context, tag: str, kind: str) -> None:
    """Put a lab instrument on the book. KIND is one of the instrument kinds."""
    with context.book() as book:
        instrument_repo.save_instrument(
            book, Instrument(tag=tag, kind=read_member(kind, InstrumentKind, "an instrument kind"))
        )
    context.say(f"added instrument {tag}")


@catalogue.command("calibrate")
@click.argument("tag")
@click.argument("certificate")
@click.option("--on", "calibrated_on", required=True, help="yyyy-mm-dd")
@click.option("--days", type=int, required=True, help="How long it is good for.")
@pass_context
@handle
def calibrate(context: Context, tag: str, certificate: str, calibrated_on: str, days: int) -> None:
    """Record a calibration certificate against an instrument."""
    window = CalibrationWindow.opened(read_date(calibrated_on), days, certificate)
    with context.book() as book:
        instrument_repo.add_calibration(book, tag, window)
    context.say(f"{tag} is good to {window.last_good_day} on {certificate}")


@catalogue.command("instruments")
@click.option("--on", "as_of", default=None, help="Check calibration on yyyy-mm-dd.")
@pass_context
@handle
def list_instruments(context: Context, as_of: str | None) -> None:
    """List the instruments and, optionally, whether they were in calibration."""
    when = read_date(as_of) if as_of else None
    with context.book() as book:
        everything = instrument_repo.load_all(book)
    if not everything:
        context.say("no instruments on the book")
        return
    columns = [Column("tag"), Column("kind"), Column.number("certificates")]
    if when is not None:
        columns.extend([Column("on " + when.isoformat()), Column("certificate")])
    table = Table(columns=tuple(columns))
    for tag in sorted(everything):
        instrument = everything[tag]
        row: list[str] = [tag, instrument.kind.label, str(len(instrument.windows))]
        if when is not None:
            covering = instrument.window_covering(when)
            row.append("in calibration" if covering else "LAPSED")
            row.append(covering.certificate if covering else "")
        table.add(*row)
    for line in table.render():
        context.say(line)


__all__ = [
    "add_instrument",
    "calibrate",
    "catalogue",
    "list_instruments",
    "list_series",
    "load_afs",
]
