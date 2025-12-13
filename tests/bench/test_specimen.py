from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from mullerbox.bench.specimen import (
    HEIGHT_TOLERANCE,
    NOMINAL_HEIGHT,
    STANDARD_RAMS,
    Specimen,
    acceptable,
    ram,
)
from mullerbox.errors import BadInputError, RuleError
from mullerbox.units.percent import Percent


class TestTheHeightIsTheCheckOnTheRamming:
    def test_a_specimen_on_nominal_is_acceptable(self) -> None:
        made = ram("SP-1", 3400, NOMINAL_HEIGHT)
        assert made.height_error == 0
        assert made.is_acceptable

    def test_exactly_on_the_tolerance_is_acceptable(self) -> None:
        assert ram("SP-1", 3400, NOMINAL_HEIGHT + HEIGHT_TOLERANCE).within_tolerance
        assert ram("SP-1", 3400, NOMINAL_HEIGHT - HEIGHT_TOLERANCE).within_tolerance

    def test_a_thousandth_past_it_is_not(self) -> None:
        assert not ram("SP-1", 3400, NOMINAL_HEIGHT + HEIGHT_TOLERANCE + 1).is_acceptable

    def test_a_short_specimen_is_refused_by_name(self) -> None:
        made = ram("SP-1", 3400, 1900)
        with pytest.raises(RuleError, match="thousandths short"):
            made.require_acceptable()

    def test_a_tall_specimen_is_refused_by_name(self) -> None:
        made = ram("SP-1", 3400, 2100)
        with pytest.raises(RuleError, match="thousandths tall"):
            made.require_acceptable()

    def test_a_good_specimen_passes_quietly(self) -> None:
        ram("SP-1", 3400, NOMINAL_HEIGHT).require_acceptable()

    def test_the_error_carries_its_sign(self) -> None:
        assert ram("SP-1", 3400, 1950).height_error == -50
        assert ram("SP-1", 3400, 2050).height_error == 50


class TestTheRamCount:
    def test_the_standard_count_is_three(self) -> None:
        assert STANDARD_RAMS == 3
        assert ram("SP-1", 3400, NOMINAL_HEIGHT).was_rammed_to_standard

    def test_another_count_is_not_comparable(self) -> None:
        made = ram("SP-1", 3400, NOMINAL_HEIGHT, rams=4)
        assert not made.was_rammed_to_standard
        assert not made.is_acceptable
        with pytest.raises(RuleError, match="took 4 rams, not 3"):
            made.require_acceptable()

    def test_the_ram_count_is_checked_before_the_height(self) -> None:
        """A specimen made wrong in both ways is reported on the ramming."""
        made = ram("SP-1", 3400, 1900, rams=2)
        with pytest.raises(RuleError, match="took 2 rams"):
            made.require_acceptable()

    def test_never_rammed_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="never rammed is loose sand"):
            ram("SP-1", 3400, NOMINAL_HEIGHT, rams=0)


class TestCompactability:
    def test_it_is_taken_against_the_loose_column(self) -> None:
        made = ram("SP-1", 3400, NOMINAL_HEIGHT)
        assert made.compactability == Percent("41.18")

    def test_a_taller_loose_column_reads_higher(self) -> None:
        loose = ram("SP-1", 3600, NOMINAL_HEIGHT)
        tight = ram("SP-2", 3200, NOMINAL_HEIGHT)
        assert loose.compactability > tight.compactability

    def test_no_shrink_reads_zero(self) -> None:
        made = ram("SP-1", 2400, 2400)
        assert made.compactability == Percent.zero()

    def test_it_is_not_taken_against_the_nominal_height(self) -> None:
        """The shortcut that makes it wrong on an under-filled tube."""
        made = ram("SP-1", 2400, 1900)
        against_loose = made.compactability
        against_nominal = Percent(
            (2400 - 1900) / NOMINAL_HEIGHT * 100  # what the shortcut would give
        )
        assert against_loose != against_nominal


class TestConstruction:
    def test_an_under_filled_tube_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="under-filled tube"):
            ram("SP-1", 2100, NOMINAL_HEIGHT)

    def test_an_over_filled_tube_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="over-filled tube"):
            ram("SP-1", 6100, NOMINAL_HEIGHT)

    def test_ramming_taller_than_loose_is_refused(self) -> None:
        with pytest.raises(RuleError, match="which is taller"):
            ram("SP-1", 3000, 3200)

    def test_a_zero_rammed_height_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="above zero"):
            ram("SP-1", 3400, 0)

    def test_the_pieces_have_to_be_whole_numbers(self) -> None:
        bad: Any = 2000.5
        with pytest.raises(BadInputError, match="rammed height is a whole number"):
            ram("SP-1", 3400, bad)
        with pytest.raises(BadInputError, match="loose height is a whole number"):
            ram("SP-1", bad, NOMINAL_HEIGHT)
        with pytest.raises(BadInputError, match="rams is a whole number"):
            ram("SP-1", 3400, NOMINAL_HEIGHT, rams=bad)

    def test_a_specimen_needs_an_identifier(self) -> None:
        with pytest.raises(BadInputError, match="needs an identifier"):
            ram("  ", 3400, NOMINAL_HEIGHT)

    def test_str_marks_a_reject(self) -> None:
        assert "good" in str(ram("SP-1", 3400, NOMINAL_HEIGHT))
        assert "REJECT" in str(ram("SP-1", 3400, 1900))


class TestFiltering:
    def test_it_keeps_only_the_good_ones(self) -> None:
        good = ram("SP-1", 3400, NOMINAL_HEIGHT)
        short = ram("SP-2", 3400, 1900)
        over_rammed = ram("SP-3", 3400, NOMINAL_HEIGHT, rams=4)
        assert acceptable([good, short, over_rammed]) == [good]

    def test_nothing_in_nothing_out(self) -> None:
        assert acceptable([]) == []

    def test_it_wants_specimens(self) -> None:
        bad: Any = ["SP-1"]
        with pytest.raises(BadInputError, match="only specimens"):
            acceptable(bad)


def test_a_specimen_is_frozen() -> None:
    """A measured specimen cannot be edited into an acceptable one."""
    made = ram("SP-1", 3400, NOMINAL_HEIGHT)
    with pytest.raises(dataclasses.FrozenInstanceError):
        made.rammed_height = 1900  # type: ignore[misc]
    assert isinstance(made, Specimen)
