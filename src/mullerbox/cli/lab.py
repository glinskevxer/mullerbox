"""Commands the sand lab runs: samples, readings and sieve work.

``result add`` takes a bare number and the property, and builds the reading on
the property's own scale. That is the same rule the bench sheet reader follows
and for the same reason: the operator types 88 and the package decides whether
that is a permeability or a hardness, because the operator should not have to
and because letting them choose is letting them choose wrong.

``result add`` does **not** check that the instrument was in calibration. It
records what was measured. Whether the number counts is asked later, by whatever
uses it, against the calibration history as it stands then. A command that
refused the entry would lose the reading entirely when a certificate turns up
late, which happens most months.
"""

from __future__ import annotations

from datetime import date

import click

from mullerbox.cli.context import Context, handle, pass_context
from mullerbox.cli.main import main
from mullerbox.errors import BadInputError
from mullerbox.gfn.distribution import grade
from mullerbox.gfn.fineness import fineness_of
from mullerbox.props.kind import parse_property
from mullerbox.props.result import Result
from mullerbox.report.layout import Column, Table
from mullerbox.store import instrument_repo, result_repo, series_repo, sieve_repo


@main.group("lab")
def lab() -> None:
    """Samples, property readings and sieve analyses."""


@lab.command("sample-add")
@click.argument("sample_id")
@click.option("--on", "taken_on", required=True, help="yyyy-mm-dd")
@click.option("--point", required=True, help="Where the sample was pulled.")
@click.option("--system", "system_name", required=True, help="Which sand system.")
@pass_context
@handle
def add_sample(
    context: Context, sample_id: str, taken_on: str, point: str, system_name: str
) -> None:
    """Record a sand sample."""
    with context.book() as book:
        result_repo.save_sample(
            book,
            result_repo.Sample(
                sample_id=sample_id,
                taken_on=_date_from(taken_on),
                point=point,
                system_name=system_name,
            ),
        )
    context.say(f"added sample {sample_id}")


@lab.command("result-add")
@click.argument("sample_id")
@click.argument("property_name")
@click.argument("reading")
@click.option("--instrument", required=True, help="The instrument tag.")
@click.option("--on", "tested_on", required=True, help="yyyy-mm-dd")
@pass_context
@handle
def add_result(
    context: Context,
    sample_id: str,
    property_name: str,
    reading: str,
    instrument: str,
    tested_on: str,
) -> None:
    """Record one property reading against a sample."""
    kind = parse_property(property_name)
    built = Result(
        kind=kind,
        reading=kind.reading_type(reading),
        instrument_tag=instrument,
        tested_on=_date_from(tested_on),
        sample_id=sample_id,
    )
    with context.book() as book:
        result_repo.save_result(book, built)
    context.say(f"{sample_id} {kind.label} {built.reading}")


@lab.command("sample")
@click.argument("sample_id")
@pass_context
@handle
def show_sample(context: Context, sample_id: str) -> None:
    """Show a sample's readings and whether each one counts."""
    with context.book() as book:
        sample = result_repo.load_sample(book, sample_id)
        results = result_repo.load_results(book, sample_id)
        instruments = instrument_repo.load_all(book)
    context.say(f"{sample.sample_id} pulled {sample.taken_on} at {sample.point}")
    if not results:
        context.say("no readings")
        return
    table = Table(
        columns=(
            Column("property"),
            Column.number("reading"),
            Column("instrument"),
            Column("counts"),
            Column("certificate"),
        )
    )
    for entry in results:
        instrument = instruments.get(entry.instrument_tag)
        if instrument is None:
            table.add(
                entry.kind.label,
                str(entry.reading),
                entry.instrument_tag,
                "UNKNOWN INSTRUMENT",
                "",
            )
            continue
        certificate = entry.certificate_for(instrument)
        table.add(
            entry.kind.label,
            str(entry.reading),
            entry.instrument_tag,
            "yes" if certificate else "NO",
            certificate or "",
        )
    for line in table.render():
        context.say(line)


@lab.command("fineness")
@click.argument("sample_id")
@pass_context
@handle
def fineness(context: Context, sample_id: str) -> None:
    """Work out the grain fineness and the grading for a sample's sieve analysis."""
    with context.book() as book:
        analysis = sieve_repo.load_analysis(book, sample_id)
    graded = grade(fineness_of(analysis))
    context.say(f"{sample_id}: {graded}")
    context.say(f"closure {analysis.closure_error}, fines {graded.fines}")
    context.say(
        f"best three screens {', '.join(graded.best_three.labels)} "
        f"holding {graded.best_three.share}"
    )
    table = Table(columns=(Column("screen"), Column.number("retained")))
    for mesh, share in graded.fineness.retaining_screens:
        table.add(mesh.label, str(share))
    for line in table.render():
        context.say(line)


@lab.command("series-check")
@click.argument("name")
@pass_context
@handle
def series_check(context: Context, name: str) -> None:
    """Reload a screen series through its own checks and report what it holds."""
    with context.book() as book:
        series = series_repo.load_series(book, name)
    context.say(f"{series.name}: {len(series)} steps, {len(series.working_steps)} screens")
    table = Table(columns=(Column("screen"), Column.number("microns"), Column.number("multiplier")))
    for step in series.steps:
        table.add(step.label, str(step.mesh.micrometres), str(step.multiplier))
    for line in table.render():
        context.say(line)


def _date_from(text: str) -> date:
    try:
        return date.fromisoformat(text.strip())
    except ValueError:
        raise BadInputError(f"{text!r} is not a date in yyyy-mm-dd form") from None


__all__ = [
    "add_result",
    "add_sample",
    "fineness",
    "lab",
    "series_check",
    "show_sample",
]
