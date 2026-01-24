from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from mullerbox.errors import BadInputError
from mullerbox.gfn.fineness import fineness_of
from mullerbox.system.dust import (
    BARELY_CAPTURED_ABOVE,
    FULLY_CAPTURED_BELOW,
    capture_fraction,
    collector_take,
    fineness_after,
)
from mullerbox.units.bulk import Pounds
from mullerbox.units.mesh import Mesh
from tests.gfn.helpers import analysis_of, sheet

THROUGHPUT = Pounds(100000)


def fineness(**held: str):  # type: ignore[no-untyped-def]
    return fineness_of(analysis_of(sheet(**held), "50.00"))


class TestTheCollectorIsAScreenNotAPercentage:
    def test_it_takes_everything_at_the_pan(self) -> None:
        assert capture_fraction(Mesh.pan()) == Decimal(1)

    def test_it_takes_everything_at_the_finest_screen(self) -> None:
        assert capture_fraction(Mesh(270, FULLY_CAPTURED_BELOW)) == Decimal(1)

    def test_it_takes_nothing_at_the_coarse_end(self) -> None:
        assert capture_fraction(Mesh(70, BARELY_CAPTURED_ABOVE)) == Decimal(0)
        assert capture_fraction(Mesh(20, 850)) == Decimal(0)

    def test_it_takes_part_of_the_middle(self) -> None:
        middle = capture_fraction(Mesh(200, 75))
        assert Decimal(0) < middle < Decimal(1)

    def test_a_finer_screen_loses_more(self) -> None:
        assert capture_fraction(Mesh(200, 75)) > capture_fraction(Mesh(140, 106))

    def test_it_wants_a_screen(self) -> None:
        bad: Any = 200
        with pytest.raises(BadInputError, match="a screen is expected"):
            capture_fraction(bad)


class TestTwoSystemsLoseDifferentAmounts:
    def test_a_finer_sand_loses_more_through_the_same_collector(self) -> None:
        coarse = collector_take(fineness(**{"40": "50.00"}), THROUGHPUT)
        fine = collector_take(fineness(**{"270": "50.00"}), THROUGHPUT)
        assert fine.removed > coarse.removed

    def test_a_coarse_sand_loses_nothing(self) -> None:
        take = collector_take(fineness(**{"20": "50.00"}), THROUGHPUT)
        assert take.removed.is_zero

    def test_all_fines_loses_everything(self) -> None:
        take = collector_take(fineness(PAN="50.00"), THROUGHPUT)
        assert take.removed == THROUGHPUT

    def test_the_share_is_reported(self) -> None:
        take = collector_take(fineness(**{"270": "50.00"}), THROUGHPUT)
        assert take.share_removed.value > 0

    def test_the_coarsest_screen_touched_is_named(self) -> None:
        take = collector_take(fineness(**{"70": "25.00", "200": "25.00"}), THROUGHPUT)
        touched = take.coarsest_touched
        assert touched is not None
        assert touched.number == 200

    def test_a_take_from_a_coarse_sand_touches_nothing(self) -> None:
        take = collector_take(fineness(**{"20": "50.00"}), THROUGHPUT)
        assert take.coarsest_touched is None

    def test_the_by_screen_breakdown_covers_the_series(self) -> None:
        take = collector_take(fineness(**{"70": "50.00"}), THROUGHPUT)
        assert len(take.by_screen) == 12


class TestTheSystemDriftsCoarser:
    def test_removing_fines_lowers_the_fineness_number(self) -> None:
        before = fineness(**{"70": "25.00", "270": "25.00"})
        take = collector_take(before, THROUGHPUT)
        after = fineness_after(before, take)
        assert after < before.value

    def test_a_sand_with_no_fines_does_not_move(self) -> None:
        before = fineness(**{"40": "50.00"})
        take = collector_take(before, THROUGHPUT)
        assert fineness_after(before, take) == before.value

    def test_it_never_moves_finer(self) -> None:
        for held in ({"70": "50.00"}, {"100": "50.00"}, {"200": "50.00"}):
            before = fineness(**held)
            take = collector_take(before, THROUGHPUT)
            assert fineness_after(before, take) <= before.value


class TestGuards:
    def test_a_collector_that_took_everything_leaves_no_sand(self) -> None:
        before = fineness(PAN="50.00")
        take = collector_take(before, THROUGHPUT)
        with pytest.raises(BadInputError, match="no sand left"):
            fineness_after(before, take)

    def test_nothing_through_has_no_share(self) -> None:
        take = collector_take(fineness(**{"70": "50.00"}), Pounds.zero())
        with pytest.raises(BadInputError, match="nothing went through"):
            assert take.share_removed

    def test_the_types_are_checked(self) -> None:
        bad: Any = "fine"
        with pytest.raises(BadInputError, match="fineness result is expected"):
            collector_take(bad, THROUGHPUT)
        with pytest.raises(BadInputError, match="throughput is a bulk mass"):
            collector_take(fineness(**{"70": "50.00"}), bad)
        take = collector_take(fineness(**{"70": "50.00"}), THROUGHPUT)
        with pytest.raises(BadInputError, match="collector take is expected"):
            fineness_after(fineness(**{"70": "50.00"}), bad)
        with pytest.raises(BadInputError, match="fineness result is expected"):
            fineness_after(bad, take)

    def test_str_names_both_masses(self) -> None:
        take = collector_take(fineness(**{"270": "50.00"}), THROUGHPUT)
        assert "to the collector" in str(take)
