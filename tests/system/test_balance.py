from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from mullerbox.errors import BadInputError
from mullerbox.system.balance import RESIDUAL_TOLERANCE, Balance
from mullerbox.units.bulk import Pounds
from mullerbox.units.percent import Percent
from tests.system.helpers import system

SHIFT = date(2025, 5, 2)


def balance(
    new_sand: str = "4000",
    core: str = "1200",
    shipped: str = "3800",
    dust: str = "1400",
    swept: str = "100",
    throughput: str = "350000",
) -> Balance:
    return Balance(
        system=system(),
        shift_on=SHIFT,
        new_sand=Pounds(new_sand),
        core_sand_returned=Pounds(core),
        shipped_on_castings=Pounds(shipped),
        dust_collected=Pounds(dust),
        swept_up=Pounds(swept),
        throughput=Pounds(throughput),
    )


class TestTheTwoSides:
    def test_in_is_new_sand_plus_returned_core(self) -> None:
        assert balance().additions_in == Pounds(5200)

    def test_out_is_everything_weighed_on_the_way(self) -> None:
        assert balance().measured_out == Pounds(5300)

    def test_the_net_change_is_signed(self) -> None:
        assert balance().net_change == Decimal("-100.00")
        assert balance(new_sand="6000").net_change == Decimal("1900.00")


class TestClosing:
    def test_a_tight_balance_closes(self) -> None:
        assert balance().closes
        assert "balance closes" in balance().finding()

    def test_a_wide_one_does_not(self) -> None:
        wide = balance(new_sand="20000")
        assert not wide.closes
        assert "does not close" in wide.finding()

    def test_the_finding_names_the_direction(self) -> None:
        assert "more sand in than out" in balance(new_sand="20000").finding()
        assert "more out than in" in balance(shipped="20000").finding()

    def test_the_residual_is_a_share_of_throughput(self) -> None:
        assert balance().residual == Decimal("-0.0003")

    def test_exactly_on_the_tolerance_closes(self) -> None:
        edge = balance(
            new_sand="4000", core="1200", shipped="0", dust="0", swept="0", throughput="260000"
        )
        assert edge.residual == RESIDUAL_TOLERANCE
        assert edge.closes


class TestDustVariance:
    def test_the_collector_taking_its_rate_reads_zero(self) -> None:
        # 0.4% of 350,000 lb is 1,400 lb.
        assert balance().expected_dust == Pounds(1400)
        assert balance().dust_variance == Decimal("0.0000")

    def test_a_full_hopper_reads_negative(self) -> None:
        assert balance(dust="700").dust_variance == Decimal("-0.5000")

    def test_no_expected_dust_has_no_variance(self) -> None:
        quiet = Balance(
            system=system(),
            shift_on=SHIFT,
            new_sand=Pounds(1),
            core_sand_returned=Pounds.zero(),
            shipped_on_castings=Pounds(1),
            dust_collected=Pounds.zero(),
            swept_up=Pounds.zero(),
            throughput=Pounds(1),
        )
        with pytest.raises(BadInputError, match="no dust was expected"):
            assert quiet.dust_variance


class TestTheResidualIsNotDistributed:
    def test_dust_is_estimated_independently_of_the_gap(self) -> None:
        tight = balance()
        wide = balance(new_sand="20000")
        assert tight.expected_dust == wide.expected_dust

    def test_the_gap_stays_visible(self) -> None:
        wide = balance(new_sand="20000")
        assert abs(wide.residual) > RESIDUAL_TOLERANCE


class TestImpliedChange:
    def test_it_is_against_the_believed_system_mass(self) -> None:
        assert balance(new_sand="7000").implied_system_change == Percent("0.97")

    def test_a_closed_balance_barely_moves_the_system(self) -> None:
        assert balance().implied_system_change < Percent("0.1")


class TestGuards:
    def test_a_shift_that_handled_nothing_has_no_balance(self) -> None:
        with pytest.raises(BadInputError, match="handled no sand"):
            balance(throughput="0")

    def test_the_pieces_are_checked(self) -> None:
        bad_system: Any = "number two"
        with pytest.raises(BadInputError, match="struck against a sand system"):
            Balance(
                system=bad_system,
                shift_on=SHIFT,
                new_sand=Pounds(1),
                core_sand_returned=Pounds(1),
                shipped_on_castings=Pounds(1),
                dust_collected=Pounds(1),
                swept_up=Pounds(1),
                throughput=Pounds(1),
            )
        bad_date: Any = "2025-05-02"
        with pytest.raises(BadInputError, match="a balance is dated"):
            Balance(
                system=system(),
                shift_on=bad_date,
                new_sand=Pounds(1),
                core_sand_returned=Pounds(1),
                shipped_on_castings=Pounds(1),
                dust_collected=Pounds(1),
                swept_up=Pounds(1),
                throughput=Pounds(1),
            )
        bad_mass: Any = 4000
        with pytest.raises(BadInputError, match="new sand is a bulk mass"):
            Balance(
                system=system(),
                shift_on=SHIFT,
                new_sand=bad_mass,
                core_sand_returned=Pounds(1),
                shipped_on_castings=Pounds(1),
                dust_collected=Pounds(1),
                swept_up=Pounds(1),
                throughput=Pounds(1),
            )

    def test_str_carries_the_finding(self) -> None:
        assert str(balance()).startswith("2025-05-02 number two system:")
