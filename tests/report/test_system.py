from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from mullerbox.errors import BadInputError
from mullerbox.report.system import RETURN_LIMIT_F, hottest_acceptable, system_report
from mullerbox.system.balance import Balance
from mullerbox.system.state import MassBasis, SandSystem
from mullerbox.units.bulk import Pounds
from mullerbox.units.percent import Percent
from mullerbox.units.thermal import Temperature
from tests.system.helpers import ESTABLISHED, system

AS_OF = date(2025, 3, 1)
STALE = date(2025, 12, 1)


def balance(new_sand: str = "4000", built: SandSystem | None = None) -> Balance:
    return Balance(
        system=built or system(),
        shift_on=AS_OF,
        new_sand=Pounds(new_sand),
        core_sand_returned=Pounds(1200),
        shipped_on_castings=Pounds(3800),
        dust_collected=Pounds(1400),
        swept_up=Pounds(100),
        throughput=Pounds(350000),
    )


class TestTheMassComesFirst:
    def test_a_nameplate_figure_leads_the_report(self) -> None:
        report = system_report(system(basis=MassBasis.NAMEPLATE), AS_OF)
        assert not report.mass_is_trustworthy
        assert report.findings()[0].startswith("THE SYSTEM MASS CANNOT BE DOSED")

    def test_it_says_every_addition_is_wrong_by_the_same_proportion(self) -> None:
        report = system_report(system(basis=MassBasis.NAMEPLATE), AS_OF)
        assert "same proportion" in report.findings()[0]

    def test_a_stale_inventory_leads_it_too(self) -> None:
        report = system_report(system(), STALE)
        assert not report.mass_is_trustworthy
        assert "past the 180 day limit" in report.findings()[0]

    def test_a_fresh_measurement_has_no_caveat(self) -> None:
        report = system_report(system(), AS_OF)
        assert report.mass_is_trustworthy
        assert report.mass_caveat is None

    def test_the_caveat_is_above_the_table(self) -> None:
        lines = system_report(system(basis=MassBasis.NAMEPLATE), AS_OF).render()
        caveat_at = next(i for i, x in enumerate(lines) if "CANNOT BE DOSED" in x)
        table_at = next(i for i, x in enumerate(lines) if x.startswith("reading"))
        assert caveat_at < table_at


class TestReturnSandTemperature:
    def test_a_cool_system_says_nothing(self) -> None:
        report = system_report(system(), AS_OF)
        assert not report.return_sand_too_hot

    def test_a_hot_one_explains_what_it_costs(self) -> None:
        hot = SandSystem(
            name="hot system",
            mass=Pounds(300000),
            basis=MassBasis.MEASURED,
            established_on=ESTABLISHED,
            batch_size=Pounds(6000),
            return_temperature=Temperature.fahrenheit(140),
            dust_loss_rate=Percent("0.4"),
        )
        report = system_report(hot, AS_OF)
        assert report.return_sand_too_hot
        assert any("flash off" in x for x in report.findings())

    def test_the_limit_is_published(self) -> None:
        # To a tenth: the temperature type stores Celsius, so a Fahrenheit
        # round trip costs one, the same as it does in the cooler.
        gap = hottest_acceptable().fahrenheit_value - RETURN_LIMIT_F
        assert abs(gap) <= Decimal("0.1")


class TestTheBalance:
    def test_a_closing_balance_says_nothing(self) -> None:
        report = system_report(system(), AS_OF, balance())
        assert "nothing about the system needs attention" in report.findings()

    def test_a_wide_one_is_reported(self) -> None:
        report = system_report(system(), AS_OF, balance(new_sand="40000"))
        assert any("does not close" in x for x in report.findings())

    def test_the_residual_is_on_the_table(self) -> None:
        text = str(system_report(system(), AS_OF, balance()))
        assert "balance residual" in text
        assert "within tolerance" in text

    def test_without_a_balance_those_rows_are_absent(self) -> None:
        text = str(system_report(system(), AS_OF))
        assert "balance residual" not in text


class TestTheTable:
    def test_it_carries_the_basis_and_the_inventory_date(self) -> None:
        text = str(system_report(system(), AS_OF))
        assert "mass basis" in text
        assert "measured" in text
        assert str(ESTABLISHED) in text

    def test_it_carries_the_derived_numbers(self) -> None:
        text = str(system_report(system(), AS_OF))
        assert "turns per pass" in text
        assert "dust loss rate" in text

    def test_no_line_has_trailing_space(self) -> None:
        for line in system_report(system(), AS_OF, balance()).render():
            assert line == line.rstrip()


class TestGuards:
    def test_the_pieces_are_checked(self) -> None:
        bad: Any = "number two"
        with pytest.raises(BadInputError, match="sand system is expected"):
            system_report(bad, AS_OF)
        with pytest.raises(BadInputError, match="report is dated"):
            system_report(system(), bad)
        with pytest.raises(BadInputError, match="a balance is expected"):
            system_report(system(), AS_OF, bad)
