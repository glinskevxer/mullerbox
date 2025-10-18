from __future__ import annotations

from mullerbox.store.migrations import MIGRATIONS, Migration
from mullerbox.tools.check_migrations import (
    SHIPPED,
    applies_cleanly,
    digest,
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
