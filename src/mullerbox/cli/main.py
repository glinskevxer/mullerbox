"""The root command group.

Commands are grouped by the part of the shop that runs them rather than by the
module that implements them, because the person typing knows which end of the
plant they are standing in and does not know the package layout. ``mullerbox
lab`` is everything the sand lab does, ``mullerbox muller`` is everything the
operator does, and so on.

``--book`` is on the root rather than on each command, so it can be set once in
an alias or a wrapper script. The book is not opened here; a subcommand that
does not touch storage never creates a file, which is why ``--help`` works on a
machine that has never run ``init``.
"""

from __future__ import annotations

import click

from mullerbox import __version__
from mullerbox.cli.context import Context, handle, pass_context, resolve_book
from mullerbox.report.layout import Column, Table
from mullerbox.store.connection import Book
from mullerbox.store.migrations import MIGRATIONS, applied, current_version, migrate


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--book",
    "book_path",
    default=None,
    metavar="PATH",
    help="Where the shop's book lives. Defaults to mullerbox.sqlite3 here.",
)
@click.option("--quiet", "-q", is_flag=True, help="Print only what was asked for.")
@click.version_option(version=__version__, prog_name="mullerbox")
@click.pass_context
def main(ctx: click.Context, book_path: str | None, quiet: bool) -> None:
    """Green sand control for a grey iron foundry."""
    ctx.obj = Context(book_path=resolve_book(book_path), quiet=quiet)


@main.command("init")
@pass_context
@handle
def init(context: Context) -> None:
    """Create the book, or bring an existing one up to date."""
    with context.fresh_book() as book:
        version = current_version(book)
    context.say(f"the book at {context.book_path} is at migration {version}")


@main.command("status")
@click.option("--verbose", is_flag=True, help="List the migrations that have been applied.")
@pass_context
@handle
def status(context: Context, verbose: bool) -> None:
    """Say what the book is, how far behind the code it is, and what it holds.

    The migration list on its own answers a question nobody has. What somebody
    typing this actually wants to know is whether they are looking at a book
    with a shop in it or an empty one, and the schema version cannot tell them:
    a freshly initialised book and a book with four years of readings are at the
    same version and print the same line.

    So the counts come first when the schema is current. When it is not, the
    counts are not printed at all, because the tables they would come from may
    not be there and a partial answer here reads as a whole one.
    """
    with context.book(migrated=False) as book:
        at = current_version(book)
        outstanding = [m for m in MIGRATIONS if m.version > at]
        history = applied(book)
        holdings = [] if outstanding else _holdings(book)
    context.say(f"book: {context.book_path}")
    context.say(f"schema: {at} of {len(MIGRATIONS)}")
    if verbose:
        for version, name in history:
            context.say(f"  applied {version}: {name}")
    if outstanding:
        context.say(f"{len(outstanding)} migrations outstanding, run init")
        return
    context.say("up to date")
    if not holdings:
        context.say("the book is empty")
        return
    table = Table(columns=(Column("holds"), Column.number("rows")))
    for label, count in holdings:
        table.add(label, str(count))
    for line in table.render():
        context.say(line)


# What is worth counting, in the order somebody reads it. Table names rather
# than repository calls, because this has to answer on a book whose contents
# nothing else in the package would load without raising.
_COUNTED: tuple[tuple[str, str], ...] = (
    ("samples", "sample"),
    ("readings", "result"),
    ("sieve analyses", "sieve_reading"),
    ("heats", "heat"),
    ("castings", "casting"),
    ("spec sheets", "spec_sheet"),
    ("instruments", "instrument"),
    ("material lots", "material_lot"),
    ("muller cycles", "recorded_cycle"),
    ("inventory counts", "inventory_count"),
)


def _holdings(book: Book) -> list[tuple[str, int]]:
    """Row counts for the tables worth reporting, skipping the empty ones."""
    found: list[tuple[str, int]] = []
    for label, table in _COUNTED:
        rows = book.scalar(f"SELECT count(*) FROM {table}")  # noqa: S608 - fixed names
        count = 0 if rows is None else int(str(rows))
        if count:
            found.append((label, count))
    return found


@main.command("migrate")
@pass_context
@handle
def migrate_command(context: Context) -> None:
    """Apply any outstanding migrations and say which ran."""
    with context.book(migrated=False) as book:
        done = migrate(book)
    if not done:
        context.say("nothing outstanding")
        return
    context.say(f"applied {', '.join(str(v) for v in done)}")


__all__ = ["init", "main", "migrate_command", "status"]
