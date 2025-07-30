from __future__ import annotations

from pathlib import Path

import pytest

from mullerbox.cli.context import EXIT_RULE
from mullerbox.spec.pattern import PatternClass
from tests.cli.helpers import initialised, run


@pytest.fixture
def book(tmp_path: Path) -> Path:
    target = initialised(tmp_path)
    assert run("spec", "load-default", "--on", "2025-01-06", book=target).exit_code == 0
    return target


class TestPublishing:
    def test_the_default_sheet_loads(self, tmp_path: Path) -> None:
        target = initialised(tmp_path)
        result = run("spec", "load-default", "--on", "2025-01-06", book=target)
        assert result.exit_code == 0
        assert "10 bands" in result.output

    def test_loading_it_twice_is_refused(self, book: Path) -> None:
        result = run("spec", "load-default", "--on", "2025-01-06", book=book)
        assert result.exit_code == EXIT_RULE

    def test_a_second_sheet_under_another_name(self, book: Path) -> None:
        result = run(
            "spec", "load-default", "--on", "2025-06-02", "--name", "june revision", book=book
        )
        assert result.exit_code == 0

    def test_listing_puts_the_newest_first(self, book: Path) -> None:
        run("spec", "load-default", "--on", "2025-06-02", "--name", "june revision", book=book)
        output = run("spec", "sheets", book=book).output
        assert output.index("june revision") < output.index("starting point")

    def test_an_empty_book_says_so(self, tmp_path: Path) -> None:
        target = initialised(tmp_path)
        assert "no spec sheets" in run("spec", "sheets", book=target).output

    def test_a_bad_date_names_the_format(self, tmp_path: Path) -> None:
        target = initialised(tmp_path)
        result = run("spec", "load-default", "--on", "06/01/2025", book=target)
        assert result.exit_code == EXIT_RULE
        assert "yyyy-mm-dd" in result.output


class TestShowNamesTheClass:
    def test_it_says_which_class_it_resolved_for(self, book: Path) -> None:
        result = run("spec", "show", "heavy jobbing", "--on", "2025-03-01", book=book)
        assert result.exit_code == 0
        assert "resolved for heavy jobbing" in result.output

    def test_two_classes_give_two_different_bands(self, book: Path) -> None:
        heavy = run("spec", "show", "heavy jobbing", "--on", "2025-03-01", book=book)
        thin = run("spec", "show", "thin wall", "--on", "2025-03-01", book=book)
        assert heavy.output != thin.output

    def test_the_published_and_in_force_columns_differ(self, book: Path) -> None:
        result = run("spec", "show", "thin wall", "--on", "2025-03-01", book=book)
        assert "published" in result.output
        assert "in force" in result.output

    def test_the_tolerance_factor_is_stated(self, book: Path) -> None:
        result = run("spec", "show", "thin wall", "--on", "2025-03-01", book=book)
        assert "tolerance factor 0.70" in result.output

    def test_an_unknown_class_is_refused(self, book: Path) -> None:
        result = run("spec", "show", "prototype", "--on", "2025-03-01", book=book)
        assert result.exit_code == EXIT_RULE
        assert "not a pattern class" in result.output

    def test_a_date_before_any_sheet_is_refused(self, book: Path) -> None:
        result = run("spec", "show", "heavy jobbing", "--on", "2024-01-01", book=book)
        assert result.exit_code == EXIT_RULE
        assert "published on or before" in result.output

    def test_it_uses_the_sheet_in_force_at_the_time(self, book: Path) -> None:
        run("spec", "load-default", "--on", "2025-06-02", "--name", "june revision", book=book)
        march = run("spec", "show", "heavy jobbing", "--on", "2025-03-01", book=book)
        july = run("spec", "show", "heavy jobbing", "--on", "2025-07-01", book=book)
        assert "starting point" in march.output
        assert "june revision" in july.output


class TestClasses:
    def test_every_class_is_listed(self, book: Path) -> None:
        result = run("spec", "classes", book=book)
        assert result.exit_code == 0
        for cls in PatternClass:
            assert cls.label in result.output

    def test_it_shows_the_tolerance_and_the_count(self, book: Path) -> None:
        result = run("spec", "classes", book=book)
        assert "tolerance" in result.output
        assert "controls" in result.output

    def test_it_works_without_a_sheet(self, tmp_path: Path) -> None:
        target = initialised(tmp_path)
        assert run("spec", "classes", book=target).exit_code == 0
