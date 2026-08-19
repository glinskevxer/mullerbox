from __future__ import annotations

from pathlib import Path

from mullerbox import __version__
from mullerbox.cli.context import EXIT_RULE
from mullerbox.cli.main import _COUNTED
from mullerbox.store.connection import open_book
from mullerbox.store.migrations import MIGRATIONS, migrate
from tests.cli.helpers import initialised, run


class TestTheRootGroup:
    def test_help_works_without_a_book(self, tmp_path: Path) -> None:
        result = run("--help", book=tmp_path / "nothing.sqlite3")
        assert result.exit_code == 0
        assert "Green sand control" in result.output

    def test_help_creates_no_file(self, tmp_path: Path) -> None:
        target = tmp_path / "nothing.sqlite3"
        run("--help", book=target)
        assert not target.exists()

    def test_the_short_help_flag(self, tmp_path: Path) -> None:
        assert run("-h", book=tmp_path / "x.sqlite3").exit_code == 0

    def test_the_version(self, tmp_path: Path) -> None:
        result = run("--version", book=tmp_path / "x.sqlite3")
        assert __version__ in result.output

    def test_the_groups_are_listed(self, tmp_path: Path) -> None:
        result = run("--help", book=tmp_path / "x.sqlite3")
        for command in ("init", "status", "migrate"):
            assert command in result.output


class TestInit:
    def test_it_creates_the_book(self, tmp_path: Path) -> None:
        target = tmp_path / "shop.sqlite3"
        result = run("init", book=target)
        assert result.exit_code == 0
        assert target.exists()

    def test_it_reports_the_migration_it_reached(self, tmp_path: Path) -> None:
        result = run("init", book=tmp_path / "shop.sqlite3")
        assert f"migration {len(MIGRATIONS)}" in result.output

    def test_running_it_twice_is_harmless(self, tmp_path: Path) -> None:
        target = initialised(tmp_path)
        assert run("init", book=target).exit_code == 0

    def test_quiet_says_nothing(self, tmp_path: Path) -> None:
        result = run("--quiet", "init", book=tmp_path / "shop.sqlite3")
        assert result.exit_code == 0
        assert result.output == ""

    def test_a_book_in_a_missing_directory_is_refused_cleanly(self, tmp_path: Path) -> None:
        result = run("init", book=tmp_path / "nowhere" / "shop.sqlite3")
        assert result.exit_code == EXIT_RULE
        assert "there is no directory at" in result.output
        assert "Traceback" not in result.output


class TestStatus:
    def test_a_fresh_book_reads_as_behind(self, tmp_path: Path) -> None:
        result = run("status", book=tmp_path / "shop.sqlite3")
        assert result.exit_code == 0
        assert "schema: 0 of" in result.output
        assert "migrations outstanding" in result.output

    def test_an_initialised_book_reads_as_up_to_date(self, tmp_path: Path) -> None:
        target = initialised(tmp_path)
        result = run("status", book=target)
        assert "up to date" in result.output

    def test_it_lists_what_has_been_applied(self, tmp_path: Path) -> None:
        target = initialised(tmp_path)
        result = run("status", "--verbose", book=target)
        for migration in MIGRATIONS:
            assert migration.name in result.output

    def test_it_names_the_book(self, tmp_path: Path) -> None:
        target = initialised(tmp_path)
        assert str(target) in run("status", book=target).output


class TestMigrate:
    def test_it_applies_everything_outstanding(self, tmp_path: Path) -> None:
        result = run("migrate", book=tmp_path / "shop.sqlite3")
        assert result.exit_code == 0
        assert "applied 1" in result.output

    def test_a_current_book_has_nothing_outstanding(self, tmp_path: Path) -> None:
        target = initialised(tmp_path)
        assert "nothing outstanding" in run("migrate", book=target).output

    def test_it_leaves_the_book_usable(self, tmp_path: Path) -> None:
        target = tmp_path / "shop.sqlite3"
        run("migrate", book=target)
        assert "up to date" in run("status", book=target).output


class TestStatusSaysWhatTheBookHolds:
    def test_an_empty_book_says_so(self, tmp_path: Path) -> None:
        book = initialised(tmp_path)
        result = run("status", book=book)
        assert result.exit_code == 0, result.output
        assert "the book is empty" in result.output

    def test_a_book_with_a_sample_counts_it(self, tmp_path: Path) -> None:
        book = initialised(tmp_path)
        run(
            "lab",
            "sample-add",
            "S-1",
            "--on",
            "2025-11-03",
            "--point",
            "muller",
            "--system",
            "two",
            book=book,
        )
        result = run("status", book=book)
        assert "samples" in result.output
        assert "the book is empty" not in result.output

    def test_an_empty_table_is_left_off(self, tmp_path: Path) -> None:
        book = initialised(tmp_path)
        run(
            "lab",
            "sample-add",
            "S-1",
            "--on",
            "2025-11-03",
            "--point",
            "muller",
            "--system",
            "two",
            book=book,
        )
        result = run("status", book=book)
        assert "heats" not in result.output

    def test_the_migration_list_is_behind_a_flag(self, tmp_path: Path) -> None:
        book = initialised(tmp_path)
        plain = run("status", book=book)
        assert "applied 1:" not in plain.output
        verbose = run("status", "--verbose", book=book)
        assert "applied 1:" in verbose.output

    def test_a_book_behind_the_code_gets_no_counts(self, tmp_path: Path) -> None:
        """A partial answer here would read as a whole one."""
        book = tmp_path / "old.sqlite3"
        with open_book(book) as opened:
            migrate(opened, MIGRATIONS[:2])
        result = run("status", book=book)
        assert "migrations outstanding" in result.output
        assert "the book is empty" not in result.output
        assert "holds" not in result.output

    def test_the_counted_tables_all_exist(self, tmp_path: Path) -> None:
        book = initialised(tmp_path)
        with open_book(book) as opened:
            present = set(opened.tables)
        assert {table for _, table in _COUNTED} <= present
