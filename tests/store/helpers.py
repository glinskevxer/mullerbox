from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from mullerbox.store.connection import Book, open_book
from mullerbox.store.migrations import migrate


@contextmanager
def migrated_book() -> Iterator[Book]:
    with open_book() as book:
        migrate(book)
        yield book
