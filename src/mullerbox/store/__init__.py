"""The book: sqlite storage, its migrations, and the repositories over it."""

from __future__ import annotations

from mullerbox.store.connection import Book, open_book

__all__ = ["Book", "open_book"]
