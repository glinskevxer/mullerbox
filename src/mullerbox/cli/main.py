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
@pass_context
@handle
def status(context: Context) -> None:
    """Say what the book is and how far behind the code it is."""
    with context.book(migrated=False) as book:
        at = current_version(book)
        outstanding = [m for m in MIGRATIONS if m.version > at]
        history = applied(book)
    context.say(f"book: {context.book_path}")
    context.say(f"schema: {at} of {len(MIGRATIONS)}")
    for version, name in history:
        context.say(f"  applied {version}: {name}")
    if outstanding:
        context.say(f"{len(outstanding)} migrations outstanding, run init")
    else:
        context.say("up to date")


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
