"""The commands that print the reports the shop reads.

``report shift`` is the one that gets run every morning and it takes a pattern
class, because a shift report without one is answering a question nobody asked.
The command will not default it: a wrong class silently produces a plausible
report against the wrong bands, which is worse than being made to type it.

``report exceptions`` is the other half and is deliberately separate. It lists
the readings that do **not** count, which is the list nobody looks at until the
sand goes wrong and everybody wants to know why the chart looked fine. Keeping
it off the shift report is a choice: the shift report says what the sand is, and
mixing in what the sand might have been makes the first question harder to
answer.
"""

from __future__ import annotations

from decimal import Decimal

import click

from mullerbox.analysis.control import MIN_POINTS, chart_of
from mullerbox.cli.context import Context, handle, pass_context
from mullerbox.cli.main import main
from mullerbox.cli.parsing import read_date
from mullerbox.errors import BadInputError
from mullerbox.props.kind import parse_property
from mullerbox.report.layout import Column, Table
from mullerbox.report.shift import shift_report
from mullerbox.spec.pattern import parse_pattern_class
from mullerbox.spec.sheet import resolve
from mullerbox.store import instrument_repo, reading_repo, result_repo, spec_repo


@main.group("report")
def reports() -> None:
    """Shift reports, exceptions and control charts."""


@reports.command("shift")
@click.argument("pattern")
@click.option("--on", "as_of", required=True, help="yyyy-mm-dd")
@click.option("--system", "system_name", default="the sand system", help="Its name.")
@pass_context
@handle
def shift(context: Context, pattern: str, as_of: str, system_name: str) -> None:
    """Print the shift report for a date, judged as a pattern class."""
    cls = parse_pattern_class(pattern)
    when = read_date(as_of)
    with context.book() as book:
        sheet = spec_repo.current_sheet(book, when)
        gathered = reading_repo.gather(book, when)
    report = shift_report(when, system_name, resolve(sheet, cls), gathered.readings)
    for line in report.render():
        context.say(line)
    if gathered.stale:
        names = ", ".join(k.label for k in gathered.stale)
        context.say("")
        context.say(f"readings over a week old: {names}")


@reports.command("exceptions")
@click.option("--on", "as_of", required=True, help="yyyy-mm-dd")
@pass_context
@handle
def exceptions(context: Context, as_of: str) -> None:
    """List the readings that do not count, and why."""
    when = read_date(as_of)
    with context.book() as book:
        found = reading_repo.uncounted(book, when)
        instruments = instrument_repo.load_all(book)
    if not found:
        context.say(f"every reading on or before {when} counts")
        return
    table = Table(
        columns=(
            Column("sample"),
            Column("property"),
            Column.number("reading"),
            Column("instrument"),
            Column("tested"),
            Column("why"),
        )
    )
    for result in found:
        instrument = instruments.get(result.instrument_tag)
        if instrument is None:
            why = "instrument not on the book"
        elif instrument.kind is not result.kind.measured_by:
            why = f"recorded against a {instrument.kind.label}"
        else:
            why = "no calibration covering the test date"
        table.add(
            result.sample_id,
            result.kind.label,
            str(result.reading),
            result.instrument_tag,
            str(result.tested_on),
            why,
        )
    for line in table.render():
        context.say(line)
    context.say("")
    context.say(f"{len(found)} readings do not count")


@reports.command("chart")
@click.argument("property_name")
@pass_context
@handle
def chart(context: Context, property_name: str) -> None:
    """Print control limits for one property from its whole history."""
    kind = parse_property(property_name)
    with context.book() as book:
        results = result_repo.results_of(book, kind)
    values = [_scalar(r.reading) for r in results]
    if len(values) < MIN_POINTS:
        context.say(
            f"{len(values)} {kind.label} readings on the book, "
            f"{MIN_POINTS} are needed for control limits"
        )
        return
    built = chart_of(values)
    context.say(f"{kind.label}: {built}")
    context.say(
        f"average moving range {built.average_moving_range}, range limit {built.range_upper}"
    )
    if built.in_control:
        return
    context.say("")
    for flag in built.flags:
        sample = results[flag.index].sample_id
        context.say(f"{sample}: {flag}")


def _scalar(reading: object) -> Decimal:
    """The bare number behind any reading, for the chart to work on."""
    value = getattr(reading, "value", None)
    if value is None:
        raise BadInputError("that reading has no number behind it")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    raise BadInputError(f"a {type(reading).__name__} does not chart")


__all__ = ["chart", "exceptions", "reports", "shift"]
