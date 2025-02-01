from __future__ import annotations

from decimal import Decimal

import pytest

from mullerbox.errors import BadInputError, RuleError
from mullerbox.gfn.fineness import Fineness, fineness_of
from mullerbox.screens.analysis import SieveAnalysis
from mullerbox.screens.series import AFS_US_SERIES
from mullerbox.units.mesh import Mesh
from mullerbox.units.percent import Percent
from tests.gfn.helpers import analysis_of, sheet


class TestTheWeightedAverage:
    def test_all_on_one_screen_gives_that_screens_multiplier(self) -> None:
        one = analysis_of(sheet(**{"70": "50.00"}), "50.00")
        assert fineness_of(one).value == Decimal("50.00")

    def test_an_even_split_averages_the_two_multipliers(self) -> None:
        two = analysis_of(sheet(**{"50": "25.00", "70": "25.00"}), "50.00")
        assert fineness_of(two).value == Decimal("45.00")

    def test_a_worked_system_sand(self) -> None:
        run = analysis_of(
            sheet(
                **{
                    "40": "2.00",
                    "50": "8.00",
                    "70": "16.00",
                    "100": "14.00",
                    "140": "6.00",
                    "200": "3.00",
                    "270": "1.00",
                }
            ),
            "50.00",
        )
        # 4*30 + 16*40 + 32*50 + 28*70 + 12*100 + 6*140 + 2*200 = 6760, over 100
        assert fineness_of(run).value == Decimal("67.60")

    def test_a_finer_sand_carries_a_higher_number(self) -> None:
        coarse = fineness_of(analysis_of(sheet(**{"40": "50.00"}), "50.00"))
        fine = fineness_of(analysis_of(sheet(**{"140": "50.00"}), "50.00"))
        assert fine.value > coarse.value

    def test_the_pan_carries_the_heaviest_multiplier(self) -> None:
        pan = analysis_of(sheet(PAN="50.00"), "50.00")
        assert fineness_of(pan).value == Decimal("300.00")


class TestTheSpreadTravelsWithTheNumber:
    def test_the_result_carries_the_distribution(self) -> None:
        run = analysis_of(sheet(**{"50": "25.00", "70": "25.00"}), "50.00")
        result = fineness_of(run)
        assert len(result.spread) == len(AFS_US_SERIES)
        assert result.fraction_on(Mesh(50, 300)) == Percent(50)

    def test_two_different_sands_can_share_a_number(self) -> None:
        # Screen 50 carries multiplier 40. So does an even split of screen 20
        # at 10 and screen 100 at 70, which is a completely different sand.
        tight = analysis_of(sheet(**{"50": "50.00"}), "50.00")
        spread = analysis_of(sheet(**{"20": "25.00", "100": "25.00"}), "50.00")
        assert fineness_of(tight).value == fineness_of(spread).value
        assert fineness_of(tight).spread != fineness_of(spread).spread

    def test_retaining_screens_drops_the_empty_ones(self) -> None:
        run = analysis_of(sheet(**{"50": "25.00", "70": "25.00"}), "50.00")
        held = fineness_of(run).retaining_screens
        assert [m.label for m, _ in held] == ["50", "70"]

    def test_coarser_than_accumulates_down_the_stack(self) -> None:
        run = analysis_of(sheet(**{"30": "10.00", "50": "20.00", "70": "20.00"}), "50.00")
        result = fineness_of(run)
        assert result.coarser_than(Mesh(30, 600)) == Percent(0)
        assert result.coarser_than(Mesh(50, 300)) == Percent(20)
        assert result.coarser_than(Mesh(70, 212)) == Percent(60)

    def test_a_screen_off_the_distribution_is_refused(self) -> None:
        result = fineness_of(analysis_of(sheet(**{"70": "50.00"}), "50.00"))
        with pytest.raises(BadInputError, match="not in this distribution"):
            result.fraction_on(Mesh(50, 297))
        with pytest.raises(BadInputError, match="not in this distribution"):
            result.coarser_than(Mesh(50, 297))


class TestGuards:
    def test_it_wants_an_analysis(self) -> None:
        with pytest.raises(BadInputError, match="out of a sieve analysis"):
            fineness_of("50")  # type: ignore[arg-type]

    def test_a_void_analysis_gives_no_number(self) -> None:
        heavy = analysis_of(sheet(**{"70": "50.00"}), "60.00")
        with pytest.raises(RuleError, match="closure tolerance"):
            fineness_of(heavy)

    def test_an_empty_stack_gives_no_number(self) -> None:
        with pytest.raises(RuleError, match="nothing came back"):
            fineness_of(analysis_of(sheet(), "50.00"))

    def test_a_fineness_checks_its_own_pieces(self) -> None:
        spread = ((Mesh(70, 212), Percent(100)),)
        with pytest.raises(BadInputError, match="is a decimal"):
            Fineness(value=50, spread=spread)  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="above zero"):
            Fineness(value=Decimal(0), spread=spread)
        with pytest.raises(BadInputError, match="carries the spread"):
            Fineness(value=Decimal(50), spread=())


class TestTypicality:
    def test_a_system_sand_is_typical(self) -> None:
        run = analysis_of(sheet(**{"50": "25.00", "70": "25.00"}), "50.00")
        assert fineness_of(run).is_typical

    def test_all_fines_is_arithmetic_rather_than_sand(self) -> None:
        pan = analysis_of(sheet(PAN="50.00"), "50.00")
        assert not fineness_of(pan).is_typical

    def test_str_names_the_number(self) -> None:
        run = analysis_of(sheet(**{"70": "50.00"}), "50.00")
        assert str(fineness_of(run)) == "GFN 50.00"


def test_the_series_multipliers_are_what_drive_the_number() -> None:
    """A screen's weight belongs to the series, not to the sample."""
    run = SieveAnalysis.of(AFS_US_SERIES, "50.00", sheet(**{"100": "50.00"}))
    assert fineness_of(run).value == Decimal(AFS_US_SERIES.multiplier_for(Mesh(100, 150)))
