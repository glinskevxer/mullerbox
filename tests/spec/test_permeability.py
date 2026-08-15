from __future__ import annotations

from decimal import Decimal

import pytest

from mullerbox.errors import BadInputError
from mullerbox.gfn.distribution import Grading
from mullerbox.props.kind import PropertyKind
from mullerbox.spec.band import Band, Verdict
from mullerbox.spec.pattern import PatternClass
from mullerbox.spec.permeability import (
    AFS_PER_GFN,
    REFERENCE_GFN,
    expected_permeability,
)
from mullerbox.spec.sheet import SpecSheet, resolve
from mullerbox.units.scales import Permeability
from tests.gfn.helpers import distribution_of
from tests.spec.helpers import PUBLISHED, sheet

PERM = PropertyKind.PERMEABILITY


def resolved(cls: PatternClass = PatternClass.MEDIUM_JOBBING):  # type: ignore[no-untyped-def]
    return resolve(sheet(), cls)


# A tight sand sitting exactly on the reference fineness: screen 50 at 40 and
# screen 70 at 50 average to 45, so pile on 70 and 100 to reach 65 GFN.
AT_REFERENCE = {"70": "12.50", "100": "37.50"}


class TestTheReferenceSandDoesNotMoveTheBand:
    def test_a_three_screen_sand_at_reference_fineness_gets_the_grading_step(
        self,
    ) -> None:
        dist = distribution_of(**AT_REFERENCE)
        assert dist.fineness.value == Decimal("65.00")
        assert dist.grading is Grading.THREE_SCREEN
        got = expected_permeability(resolved(), dist)
        assert got.fineness_shift == Decimal(0)
        assert got.grading_shift == Decimal(8)

    def test_the_anchor_is_kept_alongside_the_shifted_band(self) -> None:
        got = expected_permeability(resolved(), distribution_of(**AT_REFERENCE))
        assert got.anchor == PUBLISHED[PERM]
        assert got.band != got.anchor


class TestFinenessMovesTheBandDown:
    def test_a_finer_sand_is_expected_to_vent_worse(self) -> None:
        fine = distribution_of(**{"140": "50.00"})
        got = expected_permeability(resolved(), fine)
        assert fine.fineness.value == Decimal("100.00")
        assert got.fineness_shift == (REFERENCE_GFN - Decimal(100)) * AFS_PER_GFN
        assert got.fineness_shift < 0
        assert got.band.ceiling < got.anchor.ceiling

    def test_a_coarser_sand_is_expected_to_vent_better(self) -> None:
        coarse = distribution_of(**{"40": "50.00"})
        got = expected_permeability(resolved(), coarse)
        assert coarse.fineness.value == Decimal("30.00")
        assert got.fineness_shift > 0
        assert got.band.floor > got.anchor.floor

    def test_the_band_keeps_its_width(self) -> None:
        for held in ({"40": "50.00"}, {"140": "50.00"}, AT_REFERENCE):
            got = expected_permeability(resolved(), distribution_of(**held))
            assert got.band.width == got.anchor.width

    def test_the_band_never_goes_below_zero(self) -> None:
        very_fine = distribution_of(PAN="50.00")
        got = expected_permeability(resolved(), very_fine)
        assert got.band.floor == Permeability(0)


class TestDistributionMovesTheBandAtEqualFineness:
    def test_two_sands_of_one_fineness_get_different_bands(self) -> None:
        tight = distribution_of(**{"50": "50.00"})
        spread = distribution_of(**{"20": "25.00", "100": "25.00"})
        assert tight.fineness.value == spread.fineness.value
        assert tight.grading is not spread.grading

        tight_band = expected_permeability(resolved(), tight)
        spread_band = expected_permeability(resolved(), spread)
        assert tight_band.fineness_shift == spread_band.fineness_shift
        assert tight_band.grading_shift > spread_band.grading_shift
        assert tight_band.band.floor > spread_band.band.floor

    def test_the_same_reading_lands_differently_on_the_two_bands(self) -> None:
        tight = distribution_of(**{"50": "50.00"})
        spread = distribution_of(**{"20": "25.00", "100": "25.00"})
        # Both sands are 65 - 40 = 25 GFN points coarse, so both bands shift up
        # by 45. The tight one then gains 8 more and the spread one loses 10,
        # which puts them at 143-183 and 125-165. This reading falls between.
        reading = Permeability(130)
        assert expected_permeability(resolved(), tight).band.verdict(reading) is Verdict.BELOW
        assert expected_permeability(resolved(), spread).band.verdict(reading) is Verdict.INSIDE

    def test_a_four_screen_sand_gets_no_grading_step(self) -> None:
        four = distribution_of(
            **{"40": "10.00", "50": "12.00", "70": "12.00", "100": "10.00", "200": "6.00"}
        )
        assert four.grading is Grading.FOUR_SCREEN
        assert expected_permeability(resolved(), four).grading_shift == Decimal(0)


class TestTheTwoCorrectionsCompose:
    def test_the_total_shift_is_the_sum(self) -> None:
        got = expected_permeability(resolved(), distribution_of(**{"140": "50.00"}))
        assert got.total_shift == got.fineness_shift + got.grading_shift

    def test_the_pattern_class_still_sets_the_width(self) -> None:
        dist = distribution_of(**AT_REFERENCE)
        wide = expected_permeability(resolved(PatternClass.HEAVY_JOBBING), dist)
        tight = expected_permeability(resolved(PatternClass.THIN_WALL), dist)
        assert wide.band.width > tight.band.width

    def test_str_names_the_anchor_and_the_shift(self) -> None:
        got = expected_permeability(resolved(), distribution_of(**AT_REFERENCE))
        assert "anchor" in str(got)
        assert "+8" in str(got)


class TestGuards:
    def test_it_wants_a_resolved_spec_and_a_distribution(self) -> None:
        dist = distribution_of(**AT_REFERENCE)
        with pytest.raises(BadInputError, match="starts from a resolved spec"):
            expected_permeability(sheet(), dist)  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="needs a graded distribution"):
            expected_permeability(resolved(), dist.fineness)  # type: ignore[arg-type]

    def test_a_one_ended_anchor_is_refused(self) -> None:
        odd = SpecSheet(
            name="odd",
            bands={PERM: Band.at_least(PERM, Permeability(90))},
        )
        with pytest.raises(BadInputError, match="anchor needs both limits"):
            expected_permeability(
                resolve(odd, PatternClass.LIGHT_JOBBING),
                distribution_of(**AT_REFERENCE),
            )
