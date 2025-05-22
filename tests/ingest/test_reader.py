from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from mullerbox.errors import BadInputError, ConfigError, RuleError
from mullerbox.ingest.reader import (
    Row,
    collect,
    problem_lines,
    read_sheet,
    read_text,
)

SIMPLE = "sample,property,reading\nS-1,comp,42\nS-2,comp,43\n"


class TestParsing:
    def test_it_reads_rows_and_columns(self) -> None:
        sheet = read_text(SIMPLE)
        assert sheet.columns == ("sample", "property", "reading")
        assert len(sheet) == 2
        assert [r.text("sample") for r in sheet] == ["S-1", "S-2"]

    def test_headers_are_normalised(self) -> None:
        sheet = read_text(" Sample , PROPERTY \nS-1,comp\n")
        assert sheet.columns == ("sample", "property")
        assert sheet.rows[0].text("Sample") == "S-1"

    def test_line_numbers_count_the_header(self) -> None:
        assert [r.line for r in read_text(SIMPLE)] == [2, 3]

    def test_blank_rows_are_skipped_rather_than_flagged(self) -> None:
        sheet = read_text("sample,reading\nS-1,42\n,\nS-2,43\n")
        assert len(sheet) == 2
        assert sheet.is_clean

    def test_an_empty_file_reads_as_nothing(self) -> None:
        sheet = read_text("")
        assert sheet.columns == ()
        assert len(sheet) == 0

    def test_a_ragged_row_becomes_a_problem_rather_than_a_raise(self) -> None:
        sheet = read_text("sample,reading\nS-1,42,extra\nS-2,43\n")
        assert len(sheet) == 1
        assert not sheet.is_clean
        assert "more values" in sheet.problems[0].reason
        assert sheet.problems[0].line == 2

    def test_duplicate_columns_are_refused_outright(self) -> None:
        with pytest.raises(ConfigError, match="two columns with the same name"):
            read_text("sample,sample\nS-1,S-2\n")

    def test_it_wants_text(self) -> None:
        bad: Any = 42
        with pytest.raises(BadInputError, match="parsed from text"):
            read_text(bad)


class TestRow:
    def test_a_required_column(self) -> None:
        row = read_text(SIMPLE).rows[0]
        assert row.text("reading") == "42"

    def test_a_missing_column_is_named(self) -> None:
        row = read_text(SIMPLE).rows[0]
        with pytest.raises(BadInputError, match="no 'moisture' column"):
            row.text("moisture")

    def test_an_empty_required_column_is_named(self) -> None:
        row = read_text("sample,reading\nS-1,\n").rows[0]
        with pytest.raises(BadInputError, match="'reading' is empty"):
            row.text("reading")

    def test_optional_falls_back(self) -> None:
        row = read_text("sample,reading\nS-1,\n").rows[0]
        assert row.optional("reading", "unknown") == "unknown"
        assert row.optional("nothing") == ""

    def test_has(self) -> None:
        row = read_text(SIMPLE).rows[0]
        assert row.has("Reading")
        assert not row.has("moisture")


class TestRequirements:
    def test_required_columns(self) -> None:
        sheet = read_text(SIMPLE)
        sheet.require_columns("sample", "reading")
        with pytest.raises(ConfigError, match="no 'moisture' column"):
            sheet.require_columns("moisture")

    def test_require_clean_passes_on_a_good_file(self) -> None:
        read_text(SIMPLE).require_clean("the bench sheet")

    def test_require_clean_names_the_first_problem(self) -> None:
        sheet = read_text("sample,reading\nS-1,42,extra\n")
        with pytest.raises(ConfigError, match="the spec sheet will not load"):
            sheet.require_clean("the spec sheet")


class TestCollecting:
    def test_good_rows_are_built_and_bad_ones_kept(self) -> None:
        sheet = read_text("sample,reading\nS-1,42\nS-2,not a number\nS-3,44\n")

        def guarded(row: Row) -> int:
            try:
                return int(row.text("reading"))
            except ValueError:
                raise BadInputError(f"{row.text('reading')!r} is not a number") from None

        built, problems = collect(sheet, guarded)
        assert built == [42, 44]
        assert len(problems) == 1
        assert problems[0].line == 3
        assert "not a number" in problems[0].reason

    def test_parse_problems_are_carried_through(self) -> None:
        sheet = read_text("sample,reading\nS-1,42,extra\nS-2,43\n")

        def build(row: Row) -> str:
            return row.text("sample")

        built, problems = collect(sheet, build)
        assert built == ["S-2"]
        assert len(problems) == 1

    def test_problems_come_back_in_line_order(self) -> None:
        sheet = read_text("sample,reading\nS-1,\nS-2,43,extra\nS-3,\n")

        def build(row: Row) -> str:
            return row.text("reading")

        _, problems = collect(sheet, build)
        assert [p.line for p in problems] == sorted(p.line for p in problems)

    def test_an_unexpected_error_is_not_swallowed(self) -> None:
        def broken(row: Row) -> str:
            raise KeyError("a bug in the builder")

        with pytest.raises(KeyError):
            collect(read_text(SIMPLE), broken)

    def test_a_package_error_from_deeper_is_kept(self) -> None:
        def rule_bound(row: Row) -> str:
            raise RuleError("the shop forbids it")

        with pytest.raises(RuleError):
            collect(read_text(SIMPLE), rule_bound)

    def test_it_wants_a_builder(self) -> None:
        bad: Any = "build"
        with pytest.raises(BadInputError, match="a builder is expected"):
            collect(read_text(SIMPLE), bad)


class TestFromDisk:
    def test_it_reads_a_file(self, tmp_path: Path) -> None:
        target = tmp_path / "bench.csv"
        target.write_text(SIMPLE, encoding="utf-8")
        assert len(read_sheet(target)) == 2

    def test_a_byte_order_mark_is_stripped(self, tmp_path: Path) -> None:
        target = tmp_path / "bench.csv"
        target.write_bytes(b"\xef\xbb\xbf" + SIMPLE.encode("utf-8"))
        assert read_sheet(target).columns[0] == "sample"

    def test_a_missing_file_is_named(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="there is no file at"):
            read_sheet(tmp_path / "nothing.csv")

    def test_a_directory_is_named(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="is a directory"):
            read_sheet(tmp_path)

    def test_binary_rubbish_is_named(self, tmp_path: Path) -> None:
        target = tmp_path / "bench.csv"
        target.write_bytes(b"\xff\xfe\x00\x01")
        with pytest.raises(ConfigError, match="is not utf-8 text"):
            read_sheet(target)


def test_problem_lines_are_readable() -> None:
    sheet = read_text("sample,reading\nS-1,42,extra\n")
    assert problem_lines(sheet.problems) == ["line 2: more values than there are columns"]
