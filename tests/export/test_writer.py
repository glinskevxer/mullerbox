from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from mullerbox.errors import BadInputError, ConfigError
from mullerbox.export.writer import LINE_ENDING, Sheet, write_rows, write_sheet
from mullerbox.ingest.reader import read_sheet, read_text


class TestRendering:
    def test_a_header_and_rows(self) -> None:
        text = write_rows(["a", "b"], [["1", "2"], ["3", "4"]])
        assert text == "a,b\n1,2\n3,4\n"

    def test_the_line_ending_is_explicit(self) -> None:
        text = write_rows(["a"], [["1"]])
        assert "\r" not in text
        assert text.endswith(LINE_ENDING)

    def test_none_becomes_an_empty_field(self) -> None:
        assert write_rows(["a", "b"], [["1", None]]) == "a,b\n1,\n"

    def test_values_are_stringified(self) -> None:
        assert write_rows(["a"], [[42]]) == "a\n42\n"

    def test_a_comma_in_a_value_is_quoted(self) -> None:
        assert write_rows(["a"], [["one, two"]]) == 'a\n"one, two"\n'

    def test_no_rows_still_writes_the_header(self) -> None:
        assert write_rows(["a", "b"], []) == "a,b\n"


class TestTheSheetIsChecked:
    def test_it_needs_a_column(self) -> None:
        with pytest.raises(BadInputError, match="at least one column"):
            Sheet(columns=(), rows=())

    def test_two_columns_with_one_name_are_refused(self) -> None:
        with pytest.raises(BadInputError, match="two columns with one name"):
            Sheet(columns=("a", "a"), rows=())

    def test_a_row_of_the_wrong_width_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="has 2 columns and a row has 1"):
            Sheet(columns=("a", "b"), rows=(("1",),))

    def test_the_same_check_bites_through_write_rows(self) -> None:
        with pytest.raises(BadInputError, match="columns and a row has"):
            write_rows(["a", "b"], [["1"]])

    def test_length_counts_rows(self) -> None:
        assert len(Sheet(columns=("a",), rows=(("1",), ("2",)))) == 2


class TestWritingToDisk:
    def test_it_writes_and_counts(self, tmp_path: Path) -> None:
        target = tmp_path / "out.csv"
        assert write_sheet(target, ["a"], [["1"], ["2"]]) == 2
        assert target.read_text(encoding="utf-8") == "a\n1\n2\n"

    def test_an_empty_export_counts_zero(self, tmp_path: Path) -> None:
        target = tmp_path / "out.csv"
        assert write_sheet(target, ["a"], []) == 0

    def test_a_directory_is_refused(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="is a directory"):
            write_sheet(tmp_path, ["a"], [])

    def test_a_missing_parent_is_refused(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="there is no directory at"):
            write_sheet(tmp_path / "nowhere" / "out.csv", ["a"], [])

    def test_it_overwrites(self, tmp_path: Path) -> None:
        target = tmp_path / "out.csv"
        write_sheet(target, ["a"], [["1"]])
        write_sheet(target, ["a"], [["2"]])
        assert target.read_text(encoding="utf-8") == "a\n2\n"


class TestTheRoundTripHolds:
    def test_what_goes_out_reads_back_in(self) -> None:
        text = write_rows(["sample", "reading"], [["S-1", "42.00"], ["S-2", "43.00"]])
        sheet = read_text(text)
        assert sheet.is_clean
        assert sheet.columns == ("sample", "reading")
        assert [r.text("reading") for r in sheet] == ["42.00", "43.00"]

    def test_a_quoted_value_survives(self) -> None:
        sheet = read_text(write_rows(["note"], [["one, two"]]))
        assert sheet.rows[0].text("note") == "one, two"

    def test_an_empty_field_reads_as_optional(self) -> None:
        sheet = read_text(write_rows(["a", "b"], [["1", None]]))
        assert sheet.rows[0].optional("b") == ""

    def test_a_header_only_export_reads_as_no_rows(self) -> None:
        sheet = read_text(write_rows(["a", "b"], []))
        assert sheet.columns == ("a", "b")
        assert len(sheet) == 0

    def test_it_round_trips_through_a_file(self, tmp_path: Path) -> None:
        target = tmp_path / "out.csv"
        write_sheet(target, ["sample", "reading"], [["S-1", "42.00"]])
        sheet = read_sheet(target)
        assert sheet.is_clean
        assert sheet.rows[0].text("sample") == "S-1"

    def test_the_reader_and_the_writer_agree_on_blank_rows(self) -> None:
        """No stray blank line at the end, which the reader would skip anyway."""
        sheet = read_text(write_rows(["a"], [["1"], ["2"]]))
        assert len(sheet) == 2

    def test_it_wants_real_columns(self) -> None:
        bad: Any = None
        with pytest.raises(TypeError):
            write_rows(bad, [])
