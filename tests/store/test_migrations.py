from __future__ import annotations

from collections.abc import Iterator

import pytest

from mullerbox.errors import ConfigError
from mullerbox.store.connection import Book, open_book
from mullerbox.store.migrations import (
    MIGRATIONS,
    Migration,
    applied,
    current_version,
    migrate,
    pending,
    require_current,
)


@pytest.fixture
def book() -> Iterator[Book]:
    with open_book() as opened:
        yield opened


def one_step(version: int = 1, name: str = "first") -> Migration:
    return Migration(
        version=version,
        name=name,
        statements=(f"CREATE TABLE step_{version} (a INTEGER)",),
    )


class TestMigrationConstruction:
    def test_numbering_starts_at_one(self) -> None:
        with pytest.raises(ConfigError, match="numbered from one"):
            Migration(version=0, name="zero", statements=("SELECT 1",))

    def test_a_migration_needs_a_name(self) -> None:
        with pytest.raises(ConfigError, match="has no name"):
            Migration(version=1, name=" ", statements=("SELECT 1",))

    def test_a_migration_that_does_nothing_is_refused(self) -> None:
        with pytest.raises(ConfigError, match="does nothing"):
            Migration(version=1, name="empty", statements=())


class TestTheListIsChecked:
    def test_a_gap_is_refused(self, book: Book) -> None:
        with pytest.raises(ConfigError, match="not a run from one"):
            migrate(book, (one_step(1), one_step(3)))

    def test_a_repeat_is_refused(self, book: Book) -> None:
        with pytest.raises(ConfigError, match="share a version number"):
            migrate(book, (one_step(1), one_step(1, "again")))

    def test_out_of_order_is_refused(self, book: Book) -> None:
        with pytest.raises(ConfigError, match="not in version order"):
            migrate(book, (one_step(2), one_step(1)))

    def test_a_list_starting_above_one_is_refused(self, book: Book) -> None:
        with pytest.raises(ConfigError, match="not a run from one"):
            migrate(book, (one_step(2), one_step(3)))

    def test_the_shipped_list_passes_its_own_check(self, book: Book) -> None:
        assert [m.version for m in MIGRATIONS] == list(range(1, len(MIGRATIONS) + 1))


class TestApplying:
    def test_an_untouched_book_is_at_zero(self, book: Book) -> None:
        assert current_version(book) == 0
        assert applied(book) == []

    def test_migrating_moves_the_version(self, book: Book) -> None:
        assert migrate(book, (one_step(1),)) == [1]
        assert current_version(book) == 1

    def test_migrating_twice_does_nothing_the_second_time(self, book: Book) -> None:
        migrate(book, (one_step(1),))
        assert migrate(book, (one_step(1),)) == []

    def test_only_the_outstanding_ones_run(self, book: Book) -> None:
        migrate(book, (one_step(1),))
        assert migrate(book, (one_step(1), one_step(2, "second"))) == [2]

    def test_pending_names_what_is_left(self, book: Book) -> None:
        steps = (one_step(1), one_step(2, "second"))
        assert [m.version for m in pending(book, steps)] == [1, 2]
        migrate(book, steps)
        assert pending(book, steps) == []

    def test_the_bookkeeping_records_the_name(self, book: Book) -> None:
        migrate(book, (one_step(1, "screens"),))
        assert applied(book) == [(1, "screens")]

    def test_it_wants_a_book(self) -> None:
        with pytest.raises(ConfigError, match="against an open book"):
            migrate("book")  # type: ignore[arg-type]


class TestAFailedMigrationLeavesTheOldVersion:
    def test_a_broken_statement_does_not_advance_the_version(self, book: Book) -> None:
        broken = Migration(
            version=1, name="broken", statements=("CREATE TABLE ok (a INTEGER)", "NOT SQL")
        )
        with pytest.raises(Exception, match="syntax error"):
            migrate(book, (broken,))
        assert current_version(book) == 0

    def test_the_half_applied_table_is_rolled_back(self, book: Book) -> None:
        broken = Migration(
            version=1, name="broken", statements=("CREATE TABLE ok (a INTEGER)", "NOT SQL")
        )
        with pytest.raises(Exception, match="syntax error"):
            migrate(book, (broken,))
        assert "ok" not in book.tables


class TestTheShippedSchema:
    def test_it_applies_to_an_empty_book(self, book: Book) -> None:
        assert migrate(book) == [m.version for m in MIGRATIONS]

    def test_it_creates_the_catalogue_tables(self, book: Book) -> None:
        migrate(book)
        for table in (
            "screen_series",
            "screen_step",
            "instrument",
            "calibration",
        ):
            assert table in book.tables

    def test_the_calibration_reference_is_enforced(self, book: Book) -> None:
        import sqlite3

        migrate(book)
        with pytest.raises(sqlite3.IntegrityError):
            book.execute(
                "INSERT INTO calibration"
                " (certificate, instrument_tag, calibrated_on, due_on)"
                " VALUES ('C-1', 'MISSING', '2025-01-06', '2025-04-06')"
            )

    def test_two_steps_cannot_share_a_mesh_on_one_series(self, book: Book) -> None:
        import sqlite3

        migrate(book)
        book.execute("INSERT INTO screen_series (name) VALUES ('afs')")
        book.execute("INSERT INTO screen_step VALUES ('afs', 0, 50, 300, 40)")
        with pytest.raises(sqlite3.IntegrityError):
            book.execute("INSERT INTO screen_step VALUES ('afs', 1, 50, 300, 41)")


class TestRequireCurrent:
    def test_a_current_book_passes(self, book: Book) -> None:
        migrate(book)
        require_current(book)

    def test_a_behind_book_names_the_versions(self, book: Book) -> None:
        with pytest.raises(ConfigError, match="the book is behind: migrations 1"):
            require_current(book)
