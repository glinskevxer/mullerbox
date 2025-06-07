from __future__ import annotations

from typing import Any

import pytest

from mullerbox.errors import BadInputError
from mullerbox.report.layout import Align, Column, Table, heading, rule, wrap


def table() -> Table:
    built = Table(
        columns=(
            Column("property"),
            Column.number("reading"),
            Column.number("band"),
        )
    )
    built.add("compactability", "42.00%", "38 to 44")
    built.add("permeability", "110", "90 to 130")
    return built


class TestAlignment:
    def test_numbers_go_right_and_text_goes_left(self) -> None:
        lines = table().render()
        assert lines[2].startswith("compactability")
        assert lines[2].endswith("38 to 44")

    def test_a_number_column_lines_up_by_place_value(self) -> None:
        built = Table(columns=(Column("x"), Column.number("n")))
        built.add("a", "9")
        built.add("b", "1234")
        rendered = built.render()
        assert rendered[2].endswith("   9")
        assert rendered[3].endswith("1234")

    def test_alignment_belongs_to_the_column(self) -> None:
        assert Column.number("n").align is Align.RIGHT
        assert Column("n").align is Align.LEFT

    def test_padding(self) -> None:
        assert Align.LEFT.pad("a", 3) == "a  "
        assert Align.RIGHT.pad("a", 3) == "  a"


class TestRendering:
    def test_the_heading_row_and_the_rule(self) -> None:
        lines = table().render()
        assert lines[0].startswith("property")
        assert set(lines[1]) <= {"-", " "}

    def test_no_line_has_trailing_space(self) -> None:
        for line in table().render():
            assert line == line.rstrip()

    def test_widths_grow_to_the_widest_cell(self) -> None:
        built = Table(columns=(Column("x"),))
        built.add("a very long cell indeed")
        assert built.widths == (len("a very long cell indeed"),)

    def test_an_empty_table_still_renders_its_headings(self) -> None:
        empty = Table(columns=(Column("property"),))
        assert empty.render()[0] == "property"
        assert len(empty) == 0

    def test_the_total_width_counts_the_gutters(self) -> None:
        built = Table(columns=(Column("ab"), Column("cd")))
        assert built.width == 2 + 2 + 2

    def test_str_joins_the_lines(self) -> None:
        assert str(table()) == "\n".join(table().render())

    def test_a_none_cell_renders_empty(self) -> None:
        built = Table(columns=(Column("x"), Column("y")))
        built.add("a", None)
        assert built.render()[2] == "a"


class TestGuards:
    def test_a_table_needs_columns(self) -> None:
        with pytest.raises(BadInputError, match="at least one column"):
            Table(columns=())

    def test_a_table_is_built_from_columns(self) -> None:
        bad: Any = ("property",)
        with pytest.raises(BadInputError, match="built from columns"):
            Table(columns=bad)

    def test_a_column_needs_a_heading_and_an_alignment(self) -> None:
        with pytest.raises(BadInputError, match="needs a heading"):
            Column("  ")
        bad: Any = "right"
        with pytest.raises(BadInputError, match="needs an alignment"):
            Column("n", bad)

    def test_a_row_of_the_wrong_width_is_refused(self) -> None:
        built = table()
        with pytest.raises(BadInputError, match="has 3 columns and the row has 2"):
            built.add("a", "b")


class TestRule:
    def test_it_draws(self) -> None:
        assert rule(4) == "----"
        assert rule(3, "=") == "==="

    def test_it_is_guarded(self) -> None:
        with pytest.raises(BadInputError, match="shorter than nothing"):
            rule(-1)
        with pytest.raises(BadInputError, match="one character"):
            rule(4, "--")


class TestWrap:
    def test_it_breaks_at_a_space(self) -> None:
        assert wrap("one two three four", 9) == ["one two", "three", "four"]

    def test_a_long_word_overruns_rather_than_being_cut(self) -> None:
        assert wrap("supercalifragilistic", 5) == ["supercalifragilistic"]

    def test_it_indents_every_line(self) -> None:
        assert wrap("one two three", 10, indent="  ") == ["  one two", "  three"]

    def test_nothing_wraps_to_nothing(self) -> None:
        assert wrap("   ", 10) == []

    def test_it_is_guarded(self) -> None:
        with pytest.raises(BadInputError, match="width above zero"):
            wrap("x", 0)


class TestHeading:
    def test_it_rules_under_the_title(self) -> None:
        lines = heading("shift report", 20)
        assert lines[0] == "shift report"
        assert lines[1] == "-" * 20

    def test_a_long_title_widens_the_rule(self) -> None:
        title = "a very long report title indeed"
        assert len(heading(title, 5)[1]) == len(title)

    def test_it_needs_a_title(self) -> None:
        with pytest.raises(BadInputError, match="needs a title"):
            heading("  ")
