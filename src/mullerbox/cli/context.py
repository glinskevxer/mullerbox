"""What every command needs, and how the package's errors reach the operator.

Two decisions, both about what the person at the terminal sees.

**A ``SandError`` prints as one line and exits 2.** No traceback. Everything in
that hierarchy is raised deliberately, with a message written for the shop, and
a traceback in front of it makes an intelligible message look like a crash. The
exit code is 2 rather than 1 so that a shell script can tell "you asked for
something the rules forbid" from "the program fell over", which exits 1 by the
usual convention and keeps its traceback.

**The book is opened per command, not per process.** The CLI is short lived and
a command that does not touch storage should not create a file. Commands that
need the book ask for it and get a context manager; commands that do not never
open one, so ``mullerbox --help`` on a machine with no book works.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar, cast

import click

from mullerbox.errors import ConfigError, SandError
from mullerbox.store.connection import Book, open_book
from mullerbox.store.migrations import migrate, require_current

EXIT_RULE = 2
DEFAULT_BOOK = "mullerbox.sqlite3"


@dataclass
class Context:
    """The options every command shares."""

    book_path: str
    quiet: bool = False

    @contextmanager
    def book(self, *, migrated: bool = True) -> Iterator[Book]:
        """Open the book, refusing one that is behind the code."""
        with open_book(self.book_path) as opened:
            if migrated:
                require_current(opened)
            yield opened

    @contextmanager
    def fresh_book(self) -> Iterator[Book]:
        """Open the book and bring it up to date, for the setup commands."""
        with open_book(self.book_path) as opened:
            migrate(opened)
            yield opened

    def say(self, message: str) -> None:
        if not self.quiet:
            click.echo(message)

    def warn(self, message: str) -> None:
        click.echo(message, err=True)


pass_context = click.make_pass_decorator(Context)

_Command = TypeVar("_Command", bound=Callable[..., Any])


def handle(action: _Command) -> _Command:
    """Wrap a command body so the package's errors print as one line.

    Used as a decorator on the command function. Anything descended from
    ``SandError`` becomes a ``ClickException`` with exit code 2; anything else
    is left alone so a real bug still reaches the operator as a traceback and
    gets reported as one.
    """
    if not callable(action):
        raise ConfigError("a command body is expected")

    def wrapped(*args: Any, **kwargs: Any) -> Any:
        try:
            return action(*args, **kwargs)
        except SandError as exc:
            raise RuleFailure(str(exc)) from None

    wrapped.__name__ = getattr(action, "__name__", "command")
    wrapped.__doc__ = getattr(action, "__doc__", None)
    return cast("_Command", wrapped)


class RuleFailure(click.ClickException):
    """A refusal from the shop's rules, printed without a traceback."""

    exit_code = EXIT_RULE

    def format_message(self) -> str:
        return self.message


def resolve_book(path: str | None) -> str:
    """Where the book lives, from the option or the default."""
    if path is None:
        return DEFAULT_BOOK
    text = str(path).strip()
    if not text:
        raise ConfigError("the book path is empty")
    if text == ":memory:":
        return text
    return str(Path(text).expanduser())


__all__ = [
    "Context",
    "DEFAULT_BOOK",
    "EXIT_RULE",
    "RuleFailure",
    "handle",
    "pass_context",
    "resolve_book",
]
