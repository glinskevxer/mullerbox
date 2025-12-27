"""Commands for the sieves themselves, as opposed to the sand on them.

``screens stack`` is the one that matters and it refuses on an unmeasured
screen as loudly as on a worn one. That is deliberate and it is the part shops
argue with: an unmeasured screen is not a screen that passed, and a stack
report that quietly ignored the screens nobody got to would say a stack was fit
on the strength of three measurements out of eleven.
"""

from __future__ import annotations

import click

from mullerbox.cli.context import Context, handle, pass_context
from mullerbox.cli.main import main
from mullerbox.cli.parsing import read_date
from mullerbox.errors import BadInputError, SandError
from mullerbox.report.layout import Column, Table
from mullerbox.screens.wear import Check
from mullerbox.store import series_repo, wear_repo
from mullerbox.units.mesh import Mesh


@main.group("screens")
def screens() -> None:
    """Sieve wear checks and stack fitness."""


@screens.command("measure")
@click.argument("series_name")
@click.argument("mesh_number", type=int)
@click.argument("measured")
@click.option("--on", "when", required=True, help="yyyy-mm-dd")
@pass_context
@handle
def measure(context: Context, series_name: str, mesh_number: int, measured: str, when: str) -> None:
    """Record a screen's measured aperture in micrometres."""
    with context.book() as book:
        series = series_repo.load_series(book, series_name)
        mesh = _mesh_on(series, mesh_number)
        check = Check(
            mesh=mesh,
            measured_micrometres=int(measured),
            checked_on=read_date(when),
        )
        wear_repo.record_check(book, series_name, check)
    context.say(check.verdict())


@screens.command("stack")
@click.argument("series_name")
@click.option("--on", "as_of", required=True, help="yyyy-mm-dd")
@pass_context
@handle
def stack(context: Context, series_name: str, as_of: str) -> None:
    """Say whether a stack was fit to use on a date, and why not."""
    when = read_date(as_of)
    with context.book() as book:
        series = series_repo.load_series(book, series_name)
        checks = wear_repo.latest_checks(book, series, when)
        assembled = wear_repo.stack_as_of(book, series, when)
        oldest = wear_repo.oldest_check(book, series, when)
    table = Table(
        columns=(
            Column("screen"),
            Column.number("nominal"),
            Column.number("measured"),
            Column.number("drift"),
            Column("last checked"),
            Column("verdict"),
        )
    )
    for step in series.working_steps:
        found = checks.get(step.mesh)
        if found is None:
            table.add(step.label, str(step.mesh.micrometres), "", "", "never", "UNCHECKED")
            continue
        state = "wrong screen" if found.is_wrong_screen else ("worn" if found.is_worn else "ok")
        table.add(
            step.label,
            str(step.mesh.micrometres),
            str(found.measured_micrometres),
            f"{found.drift:+.2%}",
            str(found.checked_on),
            state,
        )
    for line in table.render():
        context.say(line)
    context.say("")
    try:
        assembled.require_fit()
    except SandError as exc:
        context.say(f"NOT FIT: {exc}")
        return
    if oldest is not None:
        mesh, checked = oldest
        context.say(f"fit to use; the oldest check is screen {mesh.label} on {checked}")
    else:
        context.say("fit to use")


@screens.command("wear-history")
@click.argument("series_name")
@click.argument("mesh_number", type=int)
@pass_context
@handle
def wear_history(context: Context, series_name: str, mesh_number: int) -> None:
    """Every measurement of one screen, to see how fast it is opening."""
    with context.book() as book:
        series = series_repo.load_series(book, series_name)
        mesh = _mesh_on(series, mesh_number)
        trail = wear_repo.history(book, series_name, mesh)
    if not trail:
        context.say(f"screen {mesh.label} has never been measured")
        return
    table = Table(columns=(Column("checked"), Column.number("measured"), Column.number("drift")))
    for when, measured in trail:
        check = Check(mesh=mesh, measured_micrometres=measured, checked_on=when)
        table.add(str(when), str(measured), f"{check.drift:+.2%}")
    for line in table.render():
        context.say(line)


def _mesh_on(series: object, number: int) -> Mesh:
    """The screen with that number on a series, or a refusal listing the real ones."""
    from mullerbox.screens.series import ScreenSeries

    if not isinstance(series, ScreenSeries):
        raise BadInputError("a screen series is expected")
    for step in series.steps:
        if step.mesh.number == number:
            return step.mesh
    known = ", ".join(s.label for s in series.working_steps)
    raise BadInputError(f"screen {number} is not on series {series.name}; it carries {known}")


__all__ = ["measure", "screens", "stack", "wear_history"]
