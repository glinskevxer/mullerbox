"""Commands for the testing programme: what is due and what earned its interval.

``programme review`` is the one that closes the loop. It reads each property's
history off the book, builds its control chart, and says whether the interval
should move. It does not move it: ``programme set`` does that, and it takes a
reason.

Keeping the review and the change apart is the whole design. A programme that
adjusted itself would relax an interval on a quiet fortnight and nobody would
know why the test frequency dropped. A review that recommends and a change that
records who agreed leaves a trail somebody can read in six months.
"""

from __future__ import annotations

from decimal import Decimal

import click

from mullerbox.analysis.control import MIN_POINTS, chart_of
from mullerbox.cli.context import Context, handle, pass_context
from mullerbox.cli.main import main
from mullerbox.cli.parsing import read_date, read_member
from mullerbox.programme.schedule import PINNED, Frequency, adjusted
from mullerbox.props.kind import PropertyKind, parse_property
from mullerbox.report.layout import Column, Table
from mullerbox.store import programme_repo, result_repo
from mullerbox.units.reading import scalar_of


@main.group("programme")
def programme() -> None:
    """How often each property is tested."""


@programme.command("set")
@click.argument("property_name")
@click.argument("frequency_name")
@click.option("--on", "when", required=True, help="yyyy-mm-dd")
@click.option("--because", required=True, help="Why the interval is what it is.")
@pass_context
@handle
def set_interval(
    context: Context, property_name: str, frequency_name: str, when: str, because: str
) -> None:
    """Put a property on the programme, or move its interval."""
    kind = parse_property(property_name)
    frequency = read_member(frequency_name, Frequency, "a frequency")
    with context.book() as book:
        programme_repo.set_interval(book, kind, frequency, read_date(when), because)
    context.say(f"{kind.label} is tested {frequency.label}")


@programme.command("due")
@click.option("--on", "as_of", required=True, help="yyyy-mm-dd")
@pass_context
@handle
def due(context: Context, as_of: str) -> None:
    """What wants testing, most overdue first."""
    when = read_date(as_of)
    with context.book() as book:
        schedule = programme_repo.load_schedule(book)
        tested = programme_repo.last_tested(book)
    wanted = schedule.due_on(when, tested)
    if not wanted:
        context.say(f"nothing is due on {when}")
        return
    table = Table(
        columns=(
            Column("property"),
            Column("interval"),
            Column("last tested"),
            Column.number("days over"),
        )
    )
    for entry in wanted:
        table.add(
            entry.kind.label,
            entry.frequency.label,
            "never" if entry.never_tested else str(entry.last_tested),
            "" if entry.never_tested else str(entry.days_over),
        )
    for line in table.render():
        context.say(line)


@programme.command("review")
@pass_context
@handle
def review(context: Context) -> None:
    """Say which intervals the charts justify moving. Changes nothing."""
    with context.book() as book:
        schedule = programme_repo.load_schedule(book)
        histories: dict[PropertyKind, list[Decimal]] = {}
        for kind in sorted(schedule.covers, key=lambda k: k.name):
            histories[kind] = [scalar_of(r.reading) for r in result_repo.results_of(book, kind)]
    table = Table(
        columns=(
            Column("property"),
            Column("now"),
            Column.number("readings"),
            Column("chart"),
            Column("recommendation"),
        )
    )
    for kind, values in histories.items():
        current = schedule.frequency_of(kind)
        if kind in PINNED:
            table.add(kind.label, current.label, str(len(values)), "", "pinned")
            continue
        if len(values) < MIN_POINTS:
            table.add(
                kind.label,
                current.label,
                str(len(values)),
                "too few",
                "leave it",
            )
            continue
        chart = chart_of(values)
        moved = adjusted(schedule, kind, chart).frequency_of(kind)
        state = "in control" if chart.in_control else f"{len(chart.flags)} signals"
        advice = "leave it" if moved is current else f"move to {moved.label}"
        table.add(kind.label, current.label, str(len(values)), state, advice)
    for line in table.render():
        context.say(line)


@programme.command("history")
@click.argument("property_name")
@pass_context
@handle
def history(context: Context, property_name: str) -> None:
    """Every time a property's interval moved, and why."""
    kind = parse_property(property_name)
    with context.book() as book:
        trail = programme_repo.changes(book, kind)
    if not trail:
        context.say(f"{kind.label} has never had its interval moved")
        return
    table = Table(columns=(Column("when"), Column("was"), Column("became"), Column("because")))
    for when, was, became, because in trail:
        table.add(str(when), was.lower(), became.lower(), because)
    for line in table.render():
        context.say(line)


__all__ = ["due", "history", "programme", "review", "set_interval"]
