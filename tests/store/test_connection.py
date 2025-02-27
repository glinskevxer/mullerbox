from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from mullerbox.errors import ConfigError
from mullerbox.store.connection import open_book


class TestOpening:
    def test_an_in_memory_book_opens_and_closes(self) -> None:
        with open_book() as book:
            assert book.is_memory
            assert book.scalar("SELECT 1") == 1

    def test_a_file_book_is_created(self, tmp_path: Path) -> None:
        target = tmp_path / "shop.sqlite3"
        with open_book(target) as book:
            assert not book.is_memory
            book.execute("CREATE TABLE t (a INTEGER)")
            book.connection.commit()
        assert target.exists()

    def test_a_missing_directory_is_refused(self, tmp_path: Path) -> None:
        opening = open_book(tmp_path / "nowhere" / "shop.sqlite3")
        with pytest.raises(ConfigError, match="there is no directory at"):
            opening.__enter__()

    def test_the_connection_is_closed_on_the_way_out(self) -> None:
        with open_book() as book:
            connection = book.connection
        with pytest.raises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")

    def test_the_connection_is_closed_even_after_a_raise(self) -> None:
        held: list[sqlite3.Connection] = []

        def blow_up() -> None:
            with open_book() as book:
                held.append(book.connection)
                raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            blow_up()
        with pytest.raises(sqlite3.ProgrammingError):
            held[0].execute("SELECT 1")


class TestPragmas:
    def test_foreign_keys_are_enforced(self) -> None:
        with open_book() as book:
            assert book.scalar("PRAGMA foreign_keys") == 1

    def test_a_declared_reference_actually_bites(self) -> None:
        with open_book() as book:
            book.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
            book.execute(
                "CREATE TABLE child ("
                " id INTEGER PRIMARY KEY,"
                " parent_id INTEGER NOT NULL REFERENCES parent (id))"
            )
            with pytest.raises(sqlite3.IntegrityError):
                book.execute("INSERT INTO child (id, parent_id) VALUES (1, 99)")

    def test_the_busy_timeout_is_set(self) -> None:
        with open_book() as book:
            assert book.scalar("PRAGMA busy_timeout") == 5000

    def test_a_file_book_runs_in_wal(self, tmp_path: Path) -> None:
        with open_book(tmp_path / "shop.sqlite3") as book:
            assert str(book.scalar("PRAGMA journal_mode")).lower() == "wal"

    def test_rows_come_back_addressable_by_name(self) -> None:
        with open_book() as book:
            book.execute("CREATE TABLE t (a INTEGER, b TEXT)")
            book.execute("INSERT INTO t VALUES (1, 'x')")
            row = book.one("SELECT a, b FROM t")
            assert row is not None
            assert row["b"] == "x"


class TestQueries:
    def test_one_gives_nothing_when_there_is_nothing(self) -> None:
        with open_book() as book:
            book.execute("CREATE TABLE t (a INTEGER)")
            assert book.one("SELECT a FROM t") is None

    def test_all_gives_every_row(self) -> None:
        with open_book() as book:
            book.execute("CREATE TABLE t (a INTEGER)")
            book.executemany("INSERT INTO t VALUES (?)", [(1,), (2,), (3,)])
            assert [r["a"] for r in book.all("SELECT a FROM t ORDER BY a")] == [1, 2, 3]

    def test_scalar_gives_nothing_when_there_is_nothing(self) -> None:
        with open_book() as book:
            book.execute("CREATE TABLE t (a INTEGER)")
            assert book.scalar("SELECT a FROM t") is None

    def test_parameters_are_bound_not_interpolated(self) -> None:
        with open_book() as book:
            book.execute("CREATE TABLE t (a TEXT)")
            book.execute("INSERT INTO t VALUES (?)", ("'; DROP TABLE t; --",))
            assert book.tables == ["t"]

    def test_tables_are_listed_in_order(self) -> None:
        with open_book() as book:
            book.execute("CREATE TABLE zebra (a INTEGER)")
            book.execute("CREATE TABLE alpha (a INTEGER)")
            assert book.tables == ["alpha", "zebra"]


class TestTransactions:
    def test_a_write_block_commits(self, tmp_path: Path) -> None:
        target = tmp_path / "shop.sqlite3"
        with open_book(target) as book:
            book.execute("CREATE TABLE t (a INTEGER)")
            with book.write():
                book.execute("INSERT INTO t VALUES (1)")
        with open_book(target) as book:
            assert book.scalar("SELECT count(*) FROM t") == 1

    def test_a_raise_inside_a_write_block_rolls_back(self, tmp_path: Path) -> None:
        target = tmp_path / "shop.sqlite3"
        with open_book(target) as book:
            book.execute("CREATE TABLE t (a INTEGER)")
            book.connection.commit()

            def insert_then_fail() -> None:
                with book.write():
                    book.execute("INSERT INTO t VALUES (1)")
                    raise RuntimeError("boom")

            with pytest.raises(RuntimeError, match="boom"):
                insert_then_fail()
            assert book.scalar("SELECT count(*) FROM t") == 0

    def test_the_rollback_survives_a_reopen(self, tmp_path: Path) -> None:
        target = tmp_path / "shop.sqlite3"
        with open_book(target) as book:
            book.execute("CREATE TABLE t (a INTEGER)")
            book.connection.commit()

            def insert_then_fail() -> None:
                with book.write():
                    book.execute("INSERT INTO t VALUES (1)")
                    raise ValueError("no thank you")

            with pytest.raises(ValueError, match="no thank you"):
                insert_then_fail()
        with open_book(target) as book:
            assert book.scalar("SELECT count(*) FROM t") == 0


class TestDdlIsInsideTheTransaction:
    def test_a_created_table_is_rolled_back(self) -> None:
        with open_book() as book:

            def create_then_fail() -> None:
                with book.write():
                    book.execute("CREATE TABLE gone (a INTEGER)")
                    raise RuntimeError("boom")

            with pytest.raises(RuntimeError, match="boom"):
                create_then_fail()
            assert "gone" not in book.tables

    def test_a_created_table_survives_a_clean_exit(self) -> None:
        with open_book() as book:
            with book.write():
                book.execute("CREATE TABLE kept (a INTEGER)")
            assert "kept" in book.tables

    def test_nested_write_blocks_commit_once_at_the_outer_boundary(self) -> None:
        with open_book() as book:

            def inner_then_fail() -> None:
                with book.write():
                    book.execute("CREATE TABLE outer_t (a INTEGER)")
                    with book.write():
                        book.execute("CREATE TABLE inner_t (a INTEGER)")
                    raise RuntimeError("boom")

            with pytest.raises(RuntimeError, match="boom"):
                inner_then_fail()
            assert "inner_t" not in book.tables
            assert "outer_t" not in book.tables
