"""The sqlite connection, opened the same way every time.

Four pragmas, and each one is here because leaving it out breaks something
specific rather than because it is generally advisable.

``foreign_keys`` is off by default in sqlite. Every reference in this schema is
declared and none of them would be enforced without this, which turns a schema
full of constraints into documentation.

``journal_mode=WAL`` lets the shift report read while the muller is writing.
The alternative is the report blocking the line, which the line wins.

``busy_timeout`` gives a writer five seconds to finish before a second writer
gives up. Without it a concurrent write fails instantly with "database is
locked", which on a foundry floor means a lost bench sheet.

``synchronous=NORMAL`` rather than FULL, because under WAL that is durable
against a process crash and only loses the last transactions on an operating
system crash, and the cost of FULL on the spinning disk this runs on is a tenth
of a second per commit.

The connection is handed out through a context manager and nothing else, which
is not fussiness. Python 3.13 raises a ResourceWarning for a connection that is
garbage collected without being closed, and this package runs its tests with
warnings as errors, so a leaked connection fails the suite on 3.13 and passes on
3.12. Making the closing structural is cheaper than finding that later.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path

from mullerbox.errors import ConfigError

BUSY_TIMEOUT_MS = 5000
IN_MEMORY = ":memory:"


def _configure(connection: sqlite3.Connection) -> None:
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    connection.execute("PRAGMA synchronous = NORMAL")


@dataclass
class Book:
    """An open book. Not thread shared; one per worker."""

    connection: sqlite3.Connection
    path: str

    @property
    def is_memory(self) -> bool:
        return self.path == IN_MEMORY

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> sqlite3.Cursor:
        return self.connection.execute(sql, parameters)

    def executemany(self, sql: str, parameters: list[tuple[object, ...]]) -> sqlite3.Cursor:
        return self.connection.executemany(sql, parameters)

    def one(self, sql: str, parameters: tuple[object, ...] = ()) -> sqlite3.Row | None:
        with closing(self.connection.execute(sql, parameters)) as cursor:
            row: sqlite3.Row | None = cursor.fetchone()
        return row

    def all(self, sql: str, parameters: tuple[object, ...] = ()) -> list[sqlite3.Row]:
        with closing(self.connection.execute(sql, parameters)) as cursor:
            rows: list[sqlite3.Row] = cursor.fetchall()
        return rows

    def scalar(self, sql: str, parameters: tuple[object, ...] = ()) -> object:
        row = self.one(sql, parameters)
        return None if row is None else row[0]

    @contextmanager
    def write(self) -> Iterator[Book]:
        """One transaction, committed on the way out and rolled back on a raise.

        sqlite3's own context manager commits but does not close and does not
        begin, which surprises callers in both directions. This one is explicit
        about the boundary so that a repository method can be composed into a
        larger unit of work without either nesting a commit or losing one.
        """
        try:
            yield self
        except Exception:
            self.connection.rollback()
            raise
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    @property
    def tables(self) -> list[str]:
        rows = self.all("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")
        return [str(r["name"]) for r in rows]


@contextmanager
def open_book(path: str | Path = IN_MEMORY) -> Iterator[Book]:
    """Open the book, configure it, and close it however the caller leaves."""
    target = str(path)
    if target != IN_MEMORY:
        parent = Path(target).expanduser().parent
        if not parent.exists():
            raise ConfigError(f"there is no directory at {parent}")
        target = str(Path(target).expanduser())
    try:
        connection = sqlite3.connect(target)
    except sqlite3.Error as exc:
        raise ConfigError(f"cannot open the book at {target}: {exc}") from exc
    try:
        _configure(connection)
        yield Book(connection=connection, path=target)
    finally:
        connection.close()


__all__ = ["BUSY_TIMEOUT_MS", "IN_MEMORY", "Book", "open_book"]
