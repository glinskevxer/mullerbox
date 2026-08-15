"""The shared helper, tested, because three modules now spell a sand through it.

A test helper that quietly changes meaning takes the tests with it, and the
version of this one that lived in three files had already drifted. So the sands
the other modules rely on are pinned here: their fineness, their grading, and
the fact that two of them share a fineness and differ only in spread, which is
the whole point of the permeability seam.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from mullerbox.gfn.distribution import Distribution, Grading
from tests.gfn.helpers import CHARGED, distribution_of

D = Decimal


class TestTheSandsTheOtherModulesUse:
    def test_a_coarse_sand_is_coarse(self) -> None:
        got = distribution_of(**{"40": "50.00"})
        assert got.fineness.value == D("30.00")

    def test_a_fine_sand_is_fine(self) -> None:
        got = distribution_of(**{"140": "50.00"})
        assert got.fineness.value == D("100.00")

    def test_the_reference_sand_lands_on_the_reference(self) -> None:
        got = distribution_of(**{"70": "12.50", "100": "37.50"})
        assert got.fineness.value == D("65.00")

    def test_a_single_screen_sand_is_three_screen_graded(self) -> None:
        assert distribution_of(**{"50": "50.00"}).grading is Grading.THREE_SCREEN

    def test_a_split_sand_is_spread(self) -> None:
        got = distribution_of(**{"20": "25.00", "100": "25.00"})
        assert got.grading is Grading.SPREAD

    def test_the_two_of_them_share_a_fineness(self) -> None:
        tight = distribution_of(**{"50": "50.00"})
        spread = distribution_of(**{"20": "25.00", "100": "25.00"})
        assert tight.fineness.value == spread.fineness.value
        assert tight.grading is not spread.grading


class TestTheHelperItself:
    def test_it_returns_a_distribution(self) -> None:
        assert isinstance(distribution_of(**{"50": "50.00"}), Distribution)

    def test_the_charge_is_fixed(self) -> None:
        assert CHARGED == "50.00"

    def test_naming_no_screen_is_all_pan(self) -> None:
        assert distribution_of(PAN="50.00").fineness.value > D("100")

    def test_a_sheet_that_does_not_add_up_is_refused(self) -> None:
        with pytest.raises(Exception, match="."):
            distribution_of(**{"50": "10.00"})
