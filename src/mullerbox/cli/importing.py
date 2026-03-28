"""Commands that pull the shop's csv exports onto the book.

Every import prints what it could not read and then asks what to do about it.
The default is to load the good rows and report the rest, because that is what
the operator wants at seven in the morning with a file the shaker wrote
overnight. ``--strict`` refuses the whole file instead, which is what a nightly
job wants, because a nightly job cannot read a warning.

The exit code carries the same distinction. A partial load with problems exits
zero and prints them; a strict run with problems exits 2 like any other refusal.
A script can therefore choose its own policy by choosing the flag, rather than
by parsing the output.
"""

from __future__ import annotations

import click

from mullerbox.cli.context import Context, handle, pass_context
from mullerbox.cli.main import main
from mullerbox.errors import ConfigError
from mullerbox.ingest.bench import load_bench
from mullerbox.ingest.cycles import load_cycles
from mullerbox.ingest.production import load_inspections, load_pours
from mullerbox.ingest.reader import Problem, read_sheet
from mullerbox.ingest.sieve import load_sieve
from mullerbox.store import (
    cycle_repo,
    heat_repo,
    result_repo,
    series_repo,
    sieve_repo,
)


@main.group("import")
def importing() -> None:
    """Load the shop's csv exports."""


def _report(context: Context, problems: tuple[Problem, ...], strict: bool) -> None:
    """Print the problems, and refuse the file if strictness was asked for."""
    if not problems:
        return
    for problem in problems:
        context.warn(str(problem))
    if strict:
        raise ConfigError(f"{len(problems)} rows would not read and --strict was given")


@importing.command("bench")
@click.argument("path", type=click.Path())
@click.option("--strict", is_flag=True, help="Refuse the file if any row is bad.")
@pass_context
@handle
def import_bench(context: Context, path: str, strict: bool) -> None:
    """Load a bench sheet of property readings."""
    load = load_bench(read_sheet(path))
    _report(context, load.problems, strict)
    written = 0
    with context.book() as book:
        for entry in load.results:
            if not result_repo.sample_exists(book, entry.sample_id):
                context.warn(f"sample {entry.sample_id} is not on the book, skipping its readings")
                continue
            result_repo.save_result(book, entry)
            written += 1
    context.say(f"loaded {written} readings, {len(load.problems)} problems")


@importing.command("sieve")
@click.argument("path", type=click.Path())
@click.option("--series", "series_name", required=True, help="Which screen series.")
@click.option("--strict", is_flag=True, help="Refuse the file if any row is bad.")
@pass_context
@handle
def import_sieve(context: Context, path: str, series_name: str, strict: bool) -> None:
    """Load a sieve shaker export against a screen series."""
    with context.book() as book:
        series = series_repo.load_series(book, series_name)
        load = load_sieve(read_sheet(path), series)
        _report(context, load.problems, strict)
        written = 0
        for sample_id, analysis in load.analyses.items():
            if not result_repo.sample_exists(book, sample_id):
                context.warn(f"sample {sample_id} is not on the book, skipping")
                continue
            sieve_repo.save_analysis(book, sample_id, analysis)
            written += 1
    context.say(f"loaded {written} analyses, {len(load.problems)} problems")


@importing.command("pours")
@click.argument("path", type=click.Path())
@click.option("--strict", is_flag=True, help="Refuse the file if any row is bad.")
@pass_context
@handle
def import_pours(context: Context, path: str, strict: bool) -> None:
    """Load the pour log."""
    load = load_pours(read_sheet(path))
    _report(context, load.problems, strict)
    with context.book() as book:
        for pour in load.pours:
            heat_repo.save_pour(book, pour)
    context.say(f"loaded {len(load.pours)} pours, {len(load.problems)} problems")


@importing.command("inspections")
@click.argument("path", type=click.Path())
@click.option("--strict", is_flag=True, help="Refuse the file if any row is bad.")
@pass_context
@handle
def import_inspections(context: Context, path: str, strict: bool) -> None:
    """Read an inspection sheet and say what it holds.

    Nothing is written. Inspections attach to castings, and castings arrive with
    a heat, so this reads the file, checks it and reports; the attaching happens
    when the heat is recorded.
    """
    load = load_inspections(read_sheet(path))
    _report(context, load.problems, strict)
    scrapped = len(load.scrapped)
    with_defects = len(load.defects_by_casting)
    context.say(
        f"read {len(load.inspections)} inspections, {scrapped} scrapped, "
        f"{with_defects} carrying defects, {len(load.problems)} problems"
    )


@importing.command("cycles")
@click.argument("path", type=click.Path())
@click.option("--strict", is_flag=True, help="Refuse the file if any row is bad.")
@pass_context
@handle
def import_cycles(context: Context, path: str, strict: bool) -> None:
    """Load the muller controller's log of what it actually did.

    Rows the planner would have refused are loaded, not rejected. A short mull
    is the observation the log exists to carry, and a loader that dropped them
    would leave the machine's own record looking cleaner than the machine.
    """
    load = load_cycles(read_sheet(path))
    _report(context, load.problems, strict)
    written = 0
    skipped = 0
    with context.book() as book:
        for logged in load.cycles:
            if cycle_repo.cycle_exists(book, logged.cycle.batch_id):
                context.warn(f"batch {logged.cycle.batch_id} is already on the book, skipping")
                skipped += 1
                continue
            cycle_repo.record_cycle(book, logged.cycle, logged.run_on)
            written += 1
    short = sum(1 for c in load.cycles if c.cycle.mulled_short)
    context.say(
        f"loaded {written} cycles over {len(load.days)} days, {skipped} already "
        f"on the book, {len(load.problems)} problems"
    )
    if short:
        context.say(f"{short} of them mulled short of the schedule")


__all__ = [
    "import_bench",
    "import_cycles",
    "import_inspections",
    "import_pours",
    "import_sieve",
    "importing",
]
