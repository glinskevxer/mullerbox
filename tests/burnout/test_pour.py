from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from mullerbox.burnout.pour import Pour, combined
from mullerbox.errors import BadInputError
from mullerbox.spec.pattern import PatternClass
from mullerbox.units.bulk import Pounds
from tests.burnout.helpers import WHEN, pour


class TestConstruction:
    def test_the_pieces_are_checked(self) -> None:
        with pytest.raises(BadInputError, match="a pour is dated"):
            Pour(
                poured_on="2025-03-10",  # type: ignore[arg-type]
                pattern=PatternClass.MEDIUM_JOBBING,
                metal=Pounds(1),
                sand=Pounds(6),
            )
        with pytest.raises(BadInputError, match="names the pattern class"):
            Pour(
                poured_on=WHEN,
                pattern="medium",  # type: ignore[arg-type]
                metal=Pounds(1),
                sand=Pounds(6),
            )
        with pytest.raises(BadInputError, match="metal poured is a bulk mass"):
            Pour(
                poured_on=WHEN,
                pattern=PatternClass.MEDIUM_JOBBING,
                metal=1,  # type: ignore[arg-type]
                sand=Pounds(6),
            )
        with pytest.raises(BadInputError, match="sand in the molds is a bulk mass"):
            Pour(
                poured_on=WHEN,
                pattern=PatternClass.MEDIUM_JOBBING,
                metal=Pounds(1),
                sand=6,  # type: ignore[arg-type]
            )

    def test_an_empty_pour_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="no metal in it"):
            pour(metal="0")
        with pytest.raises(BadInputError, match="no sand in it"):
            pour(sand="0")


class TestTheRatio:
    def test_it_is_sand_over_metal(self) -> None:
        assert pour(sand="60000", metal="10000").sand_to_metal == Decimal("6.00")

    def test_a_heavy_shift_runs_low(self) -> None:
        assert pour(sand="30000", metal="10000").sand_to_metal == Decimal("3.00")

    def test_a_light_shift_runs_high(self) -> None:
        assert pour(sand="90000", metal="10000").sand_to_metal == Decimal("9.00")


class TestPlausibility:
    def test_the_jobbing_range_passes(self) -> None:
        for sand in ("20000", "60000", "200000"):
            assert pour(sand=sand).is_plausible

    def test_too_little_sand_is_refused(self) -> None:
        thin = pour(sand="19000", metal="10000")
        assert not thin.is_plausible
        with pytest.raises(BadInputError, match="is not a pour record"):
            thin.require_plausible()

    def test_too_much_sand_is_refused(self) -> None:
        assert not pour(sand="210000", metal="10000").is_plausible

    def test_the_refusal_names_both_masses(self) -> None:
        with pytest.raises(BadInputError, match="of sand against"):
            pour(sand="19000", metal="10000").require_plausible()


class TestSeverity:
    def test_the_reference_shift_reads_one(self) -> None:
        assert pour(sand="60000", metal="10000").severity == Decimal("1.000")

    def test_a_heavy_shift_reads_higher(self) -> None:
        assert pour(sand="30000", metal="10000").severity == Decimal("2.000")

    def test_a_light_shift_reads_lower(self) -> None:
        assert pour(sand="120000", metal="10000").severity == Decimal("0.500")

    def test_severity_refuses_an_implausible_pour(self) -> None:
        with pytest.raises(BadInputError, match="is not a pour record"):
            assert pour(sand="19000", metal="10000").severity


class TestCombining:
    def test_it_weights_by_metal_rather_than_averaging_ratios(self) -> None:
        big = pour(sand="90000", metal="10000")
        small = pour(sand="600", metal="200", when=date(2025, 3, 11))
        # Averaging the ratios would give (9 + 3) / 2 = 6.
        assert combined([big, small]) == Decimal("8.88")

    def test_one_pour_is_its_own_ratio(self) -> None:
        assert combined([pour()]) == Decimal("6.00")

    def test_nothing_to_combine_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="no pours to combine"):
            combined([])

    def test_it_wants_pours(self) -> None:
        with pytest.raises(BadInputError, match="only pours"):
            combined([pour(), "6:1"])  # type: ignore[list-item]


def test_str_reads_like_a_pour_line() -> None:
    assert str(pour()) == "2025-03-10 medium jobbing 6.00:1"
