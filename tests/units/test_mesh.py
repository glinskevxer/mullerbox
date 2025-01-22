from __future__ import annotations

from decimal import Decimal

import pytest

from mullerbox.errors import BadInputError
from mullerbox.units.mesh import Mesh, parse_mesh_label


class TestConstruction:
    def test_a_screen_carries_its_own_aperture(self) -> None:
        screen = Mesh(50, 300)
        assert screen.number == 50
        assert screen.micrometres == 300

    def test_reads_numbers_as_text(self) -> None:
        assert Mesh("50", "300") == Mesh(50, 300)

    def test_the_pan_has_no_aperture(self) -> None:
        assert Mesh.pan().is_pan
        assert Mesh.pan().micrometres == 0

    def test_a_pan_with_an_aperture_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="pan has no aperture"):
            Mesh(0, 45)

    def test_a_screen_needs_an_aperture(self) -> None:
        with pytest.raises(BadInputError, match="aperture above zero"):
            Mesh(50, 0)

    def test_a_mesh_off_the_scale_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="not a sand lab screen"):
            Mesh(500, 20)
        with pytest.raises(BadInputError, match="not a sand lab screen"):
            Mesh(2, 9000)

    def test_unreadable_values_are_refused(self) -> None:
        with pytest.raises(BadInputError, match="not a mesh number"):
            Mesh("fifty", 300)
        with pytest.raises(BadInputError, match="cannot read a mesh number"):
            Mesh(None, 300)
        with pytest.raises(BadInputError, match="cannot read an aperture"):
            Mesh(50, None)

    def test_a_boolean_is_not_a_mesh_number(self) -> None:
        with pytest.raises(BadInputError, match="from a boolean"):
            Mesh(True, 300)


class TestOrderingRunsCoarseToFine:
    def test_a_lower_number_is_coarser(self) -> None:
        assert Mesh(30, 600).is_coarser_than(Mesh(50, 300))
        assert Mesh(50, 300).is_finer_than(Mesh(30, 600))

    def test_sorting_puts_the_coarse_screen_first(self) -> None:
        stack = [Mesh(100, 150), Mesh(30, 600), Mesh.pan(), Mesh(50, 300)]
        assert [s.label for s in sorted(stack)] == ["30", "50", "100", "PAN"]

    def test_the_pan_sorts_to_the_bottom(self) -> None:
        assert max(Mesh(30, 600), Mesh.pan()) == Mesh.pan()

    def test_comparison_wants_a_screen(self) -> None:
        with pytest.raises(BadInputError, match="only compares against a screen"):
            Mesh(30, 600).is_coarser_than(30)  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="only compares against a screen"):
            Mesh(30, 600).is_finer_than(30)  # type: ignore[arg-type]

    def test_two_series_disagreeing_on_an_aperture_are_not_equal(self) -> None:
        assert Mesh(70, 212) != Mesh(70, 210)


class TestPresentation:
    def test_millimetres(self) -> None:
        assert Mesh(50, 300).millimetres == Decimal("0.300")

    def test_str_names_the_opening(self) -> None:
        assert str(Mesh(50, 300)) == "50 (300 um)"
        assert str(Mesh.pan()) == "PAN"

    def test_label(self) -> None:
        assert Mesh(50, 300).label == "50"
        assert Mesh.pan().label == "PAN"

    def test_hashes_by_value(self) -> None:
        assert len({Mesh(50, 300), Mesh("50", "300")}) == 1

    def test_unequal_against_another_type(self) -> None:
        assert Mesh(50, 300) != 50


class TestParsing:
    @pytest.mark.parametrize("text", ["PAN", "pan", " Pan. ", "p"])
    def test_the_pan_is_spelled_several_ways(self, text: str) -> None:
        assert parse_mesh_label(text, 0).is_pan

    def test_a_number_needs_its_aperture(self) -> None:
        assert parse_mesh_label(" 70 ", 212) == Mesh(70, 212)

    def test_anything_else_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="not a screen designation"):
            parse_mesh_label("coarse", 600)
