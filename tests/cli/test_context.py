from __future__ import annotations

from pathlib import Path
from typing import Any

import click
import pytest
from click.testing import CliRunner

from mullerbox.cli.context import (
    DEFAULT_BOOK,
    EXIT_RULE,
    Context,
    RuleFailure,
    handle,
    resolve_book,
)
from mullerbox.errors import ConfigError, RuleError
from mullerbox.store.migrations import current_version


class TestResolvingTheBook:
    def test_no_option_gives_the_default(self) -> None:
        assert resolve_book(None) == DEFAULT_BOOK

    def test_memory_is_passed_through(self) -> None:
        assert resolve_book(":memory:") == ":memory:"

    def test_a_path_is_expanded(self) -> None:
        assert resolve_book("~/shop.sqlite3").startswith("/")

    def test_an_empty_path_is_refused(self) -> None:
        with pytest.raises(ConfigError, match="book path is empty"):
            resolve_book("   ")


class TestOpeningTheBook:
    def test_a_fresh_book_is_migrated(self, tmp_path: Path) -> None:
        context = Context(book_path=str(tmp_path / "shop.sqlite3"))
        with context.fresh_book() as book:
            assert current_version(book) > 0

    def test_an_unmigrated_book_is_refused(self, tmp_path: Path) -> None:
        context = Context(book_path=str(tmp_path / "shop.sqlite3"))
        opening = context.book()
        with pytest.raises(ConfigError, match="the book is behind"):
            opening.__enter__()

    def test_a_migrated_book_opens(self, tmp_path: Path) -> None:
        context = Context(book_path=str(tmp_path / "shop.sqlite3"))
        with context.fresh_book():
            pass
        with context.book() as book:
            assert current_version(book) > 0

    def test_it_can_be_opened_without_the_check(self, tmp_path: Path) -> None:
        context = Context(book_path=str(tmp_path / "shop.sqlite3"))
        with context.book(migrated=False) as book:
            assert current_version(book) == 0


class TestSpeaking:
    def test_it_echoes(self) -> None:
        runner = CliRunner()

        @click.command()
        def speak() -> None:
            Context(book_path=":memory:").say("hello")

        assert runner.invoke(speak).output == "hello\n"

    def test_quiet_holds_its_tongue(self) -> None:
        runner = CliRunner()

        @click.command()
        def speak() -> None:
            Context(book_path=":memory:", quiet=True).say("hello")

        assert runner.invoke(speak).output == ""

    def test_a_warning_goes_to_stderr_even_when_quiet(self) -> None:
        runner = CliRunner()

        @click.command()
        def speak() -> None:
            Context(book_path=":memory:", quiet=True).warn("careful")

        result = runner.invoke(speak)
        assert "careful" in result.output


class TestErrorHandling:
    def test_a_rule_error_prints_one_line_and_exits_two(self) -> None:
        runner = CliRunner()

        @click.command()
        @handle
        def boom() -> None:
            raise RuleError("the standard was out of calibration")

        result = runner.invoke(boom)
        assert result.exit_code == EXIT_RULE
        assert "out of calibration" in result.output
        assert "Traceback" not in result.output

    def test_an_unexpected_error_keeps_its_traceback(self) -> None:
        runner = CliRunner()

        @click.command()
        @handle
        def boom() -> None:
            raise KeyError("a real bug")

        result = runner.invoke(boom)
        assert result.exit_code == 1
        assert isinstance(result.exception, KeyError)

    def test_a_clean_command_returns_zero(self) -> None:
        runner = CliRunner()

        @click.command()
        @handle
        def fine() -> None:
            click.echo("done")

        result = runner.invoke(fine)
        assert result.exit_code == 0
        assert "done" in result.output

    def test_the_wrapper_keeps_the_name_and_the_docstring(self) -> None:
        def original() -> None:
            """Do the thing."""

        wrapped: Any = handle(original)
        assert wrapped.__name__ == "original"
        assert wrapped.__doc__ == "Do the thing."

    def test_it_wants_a_callable(self) -> None:
        bad: Any = "command"
        with pytest.raises(ConfigError, match="command body is expected"):
            handle(bad)

    def test_the_failure_formats_as_its_message(self) -> None:
        assert RuleFailure("plain").format_message() == "plain"
        assert RuleFailure("plain").exit_code == EXIT_RULE
