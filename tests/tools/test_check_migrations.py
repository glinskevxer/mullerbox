from __future__ import annotations

from unittest import mock

import pytest

from mullerbox.store.connection import open_book
from mullerbox.store.migrations import MIGRATIONS, Migration, migrate
from mullerbox.tools import check_migrations
from mullerbox.tools.check_migrations import (
    EXPECTED_TABLES,
    SHIPPED,
    applies_cleanly,
    digest,
    main,
    problems,
)


class TestTheGatePassesOnThisPackage:
    def test_no_migration_has_changed(self) -> None:
        assert problems() == []

    def test_they_all_apply_to_an_empty_book(self) -> None:
        assert applies_cleanly() == []

    def test_every_shipped_migration_has_a_hash(self) -> None:
        assert {m.version for m in MIGRATIONS} == set(SHIPPED)


class TestTheDigest:
    def test_it_is_stable_for_the_same_statements(self) -> None:
        one = Migration(version=1, name="a", statements=("SELECT 1",))
        again = Migration(version=1, name="a", statements=("SELECT 1",))
        assert digest(one) == digest(again)

    def test_renaming_a_migration_does_not_change_it(self) -> None:
        one = Migration(version=1, name="original", statements=("SELECT 1",))
        renamed = Migration(version=1, name="renamed", statements=("SELECT 1",))
        assert digest(one) == digest(renamed)

    def test_reindenting_a_statement_does_not_change_it(self) -> None:
        """The real migrations are written spread over lines and get reindented."""
        flat = Migration(version=1, name="a", statements=("CREATE TABLE t ( a INTEGER )",))
        spread = Migration(
            version=1,
            name="a",
            statements=(
                """
                CREATE TABLE t (
                    a INTEGER
                )
                """,
            ),
        )
        assert digest(flat) == digest(spread)

    def test_changing_the_spacing_between_tokens_does_change_it(self) -> None:
        """Runs of whitespace collapse; whitespace that was not there does not appear.

        So ``t (a INTEGER)`` and ``t ( a INTEGER )`` hash differently. That is
        stricter than SQL needs and it is the right side to err on: the gate
        exists to notice edits, and a false alarm costs one line in SHIPPED
        while a miss costs a schema divergence nobody sees.
        """
        tight = Migration(version=1, name="a", statements=("CREATE TABLE t (a INTEGER)",))
        loose = Migration(version=1, name="a", statements=("CREATE TABLE t ( a INTEGER )",))
        assert digest(tight) != digest(loose)

    def test_changing_a_statement_does_change_it(self) -> None:
        one = Migration(version=1, name="a", statements=("CREATE TABLE t (a INTEGER)",))
        altered = Migration(version=1, name="a", statements=("CREATE TABLE t (a INTEGER, b TEXT)",))
        assert digest(one) != digest(altered)

    def test_adding_a_statement_changes_it(self) -> None:
        one = Migration(version=1, name="a", statements=("SELECT 1",))
        two = Migration(version=1, name="a", statements=("SELECT 1", "SELECT 2"))
        assert digest(one) != digest(two)

    def test_it_is_short_enough_to_read_in_a_diff(self) -> None:
        assert len(digest(MIGRATIONS[0])) == 16


class TestTheGateActuallyBites:
    def test_an_edited_migration_is_caught(self) -> None:
        """Proved by asking the digest, since the real list is the thing under test."""
        original = MIGRATIONS[0]
        edited = Migration(
            version=original.version,
            name=original.name,
            statements=(*original.statements, "CREATE TABLE sneaked (a INTEGER)"),
        )
        assert digest(edited) != SHIPPED[original.version]

    def test_a_new_migration_with_no_hash_would_be_caught(self) -> None:
        fresh = Migration(version=99, name="new", statements=("SELECT 1",))
        assert fresh.version not in SHIPPED

    def test_a_hash_with_no_migration_would_be_caught(self) -> None:
        stale = set(SHIPPED) - {m.version for m in MIGRATIONS}
        assert stale == set()


class TestTheTableListIsWrittenOutOnPurpose:
    def test_every_table_the_migrations_build_is_named(self) -> None:
        with open_book() as book:
            migrate(book)
            assert set(book.tables) == EXPECTED_TABLES

    def test_a_table_the_gate_does_not_name_is_reported(self) -> None:
        """The positive control: the unnamed branch has to be able to fire."""
        shrunk = EXPECTED_TABLES - {"inventory_vessel"}
        with mock.patch.object(check_migrations, "EXPECTED_TABLES", shrunk):
            found = applies_cleanly()
        assert found == ["the schema grew a 'inventory_vessel' table that this gate does not name"]

    def test_a_missing_table_is_reported_too(self) -> None:
        grown = EXPECTED_TABLES | {"never_created"}
        with mock.patch.object(check_migrations, "EXPECTED_TABLES", grown):
            found = applies_cleanly()
        assert found == ["the schema has no 'never_created' table"]

    def test_the_inventory_tables_are_on_it(self) -> None:
        assert {"inventory_count", "inventory_vessel"} <= EXPECTED_TABLES


class TestTheGateReportsRatherThanRaises:
    def test_a_migration_that_will_not_apply_comes_back_as_a_line(self) -> None:
        broken = (*MIGRATIONS, Migration(version=99, name="bad", statements=("NOT SQL",)))
        with mock.patch.object(check_migrations, "MIGRATIONS", broken):
            found = applies_cleanly()
        assert len(found) == 1
        assert found[0].startswith("the migrations do not apply")

    def test_a_run_that_stops_early_is_reported(self) -> None:
        """Patching migrate rather than the list, because a short list is legal."""

        def stops_early(book: object, migrations: object = None) -> list[int]:
            migrate(book, MIGRATIONS[:1])  # type: ignore[arg-type]
            return [1]

        with mock.patch.object(check_migrations, "migrate", stops_early):
            found = applies_cleanly()
        assert found
        assert "not every migration" in found[0]

    def test_a_book_left_behind_the_last_migration_is_reported(self) -> None:
        def claims_it_ran(book: object, migrations: object = None) -> list[int]:
            migrate(book, MIGRATIONS[:1])  # type: ignore[arg-type]
            return [m.version for m in MIGRATIONS]

        with mock.patch.object(check_migrations, "migrate", claims_it_ran):
            found = applies_cleanly()
        assert found == ["the book did not reach the last migration"]


class TestTheEntryPoint:
    def test_it_exits_zero_on_this_package(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main() == 0
        assert "apply cleanly" in capsys.readouterr().out

    def test_it_exits_non_zero_when_something_is_wrong(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with mock.patch.object(check_migrations, "SHIPPED", {}):
            code = main()
        assert code == 1
        assert "migration problems" in capsys.readouterr().out

    def test_it_names_a_changed_migration(self, capsys: pytest.CaptureFixture[str]) -> None:
        wrong = dict(SHIPPED)
        wrong[1] = "0000000000000000"
        with mock.patch.object(check_migrations, "SHIPPED", wrong):
            main()
        assert "has changed since it shipped" in capsys.readouterr().out

    def test_it_names_a_hash_with_no_migration(self, capsys: pytest.CaptureFixture[str]) -> None:
        extra = {**SHIPPED, 99: "0000000000000000"}
        with mock.patch.object(check_migrations, "SHIPPED", extra):
            main()
        assert "has a hash but is not in the list" in capsys.readouterr().out
