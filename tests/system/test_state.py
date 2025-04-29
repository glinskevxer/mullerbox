from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest

from mullerbox.errors import BadInputError, RuleError
from mullerbox.system.state import INVENTORY_STALE_DAYS, MassBasis, SandSystem
from mullerbox.units.bulk import Pounds
from mullerbox.units.percent import Percent
from mullerbox.units.thermal import Temperature
from tests.system.helpers import ESTABLISHED, system

SOON = date(2025, 3, 1)
LATE = date(2025, 12, 1)


class TestBasis:
    def test_only_a_measurement_is_trustworthy(self) -> None:
        assert MassBasis.MEASURED.is_trustworthy
        assert not MassBasis.NAMEPLATE.is_trustworthy

    def test_the_system_reports_it(self) -> None:
        assert system().is_measured
        assert not system(basis=MassBasis.NAMEPLATE).is_measured

    def test_every_basis_has_a_label(self) -> None:
        assert all(b.label for b in MassBasis)


class TestDosingAgainstTheMass:
    def test_a_fresh_measurement_is_handed_over(self) -> None:
        assert system().require_trustworthy(SOON) == Pounds(300000)

    def test_a_nameplate_figure_is_refused_by_name(self) -> None:
        with pytest.raises(RuleError, match="design figure and not an inventory"):
            system(basis=MassBasis.NAMEPLATE).require_trustworthy(SOON)

    def test_a_stale_measurement_is_refused_with_the_age(self) -> None:
        with pytest.raises(RuleError, match="days ago, past the 180 day limit"):
            system().require_trustworthy(LATE)

    def test_staleness_is_measured_in_days(self) -> None:
        edge = ESTABLISHED + timedelta(days=INVENTORY_STALE_DAYS)
        assert not system().is_stale_at(edge)
        assert system().is_stale_at(edge + timedelta(days=1))

    def test_staleness_cannot_be_asked_before_the_inventory(self) -> None:
        with pytest.raises(BadInputError, match="after"):
            system().is_stale_at(date(2024, 12, 1))

    def test_staleness_wants_a_date(self) -> None:
        bad: Any = "2025-03-01"
        with pytest.raises(BadInputError, match="checked against a date"):
            system().is_stale_at(bad)


class TestRecordingAnInventory:
    def test_it_promotes_the_basis(self) -> None:
        after = system(basis=MassBasis.NAMEPLATE).inventoried(Pounds(210000), SOON)
        assert after.is_measured
        assert after.mass == Pounds(210000)
        assert after.established_on == SOON

    def test_the_earlier_system_is_untouched(self) -> None:
        before = system(basis=MassBasis.NAMEPLATE)
        before.inventoried(Pounds(210000), SOON)
        assert not before.is_measured

    def test_a_backdated_inventory_is_refused(self) -> None:
        with pytest.raises(RuleError, match="already carries a figure"):
            system().inventoried(Pounds(210000), date(2024, 1, 1))

    def test_an_empty_inventory_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="not an inventory"):
            system().inventoried(Pounds.zero(), SOON)

    def test_it_is_guarded(self) -> None:
        bad_mass: Any = 210000
        with pytest.raises(BadInputError, match="system mass is a bulk mass"):
            system().inventoried(bad_mass, SOON)
        bad_date: Any = "2025-03-01"
        with pytest.raises(BadInputError, match="an inventory is dated"):
            system().inventoried(Pounds(210000), bad_date)


class TestDerivedNumbers:
    def test_turns_per_batch(self) -> None:
        assert system(mass="300000", batch="6000").turns_per_batch == Decimal("50.00")

    def test_dust_loss_over_a_throughput(self) -> None:
        assert system().dust_loss_over(Pounds(100000)) == Pounds(400)

    def test_dust_loss_wants_a_mass(self) -> None:
        bad: Any = 100000
        with pytest.raises(BadInputError, match="throughput is a bulk mass"):
            system().dust_loss_over(bad)


class TestConstruction:
    def test_a_muller_bigger_than_the_system_is_refused(self) -> None:
        with pytest.raises(RuleError, match="more than the system"):
            system(mass="5000", batch="6000")

    def test_the_pieces_are_checked(self) -> None:
        base = {
            "name": "s",
            "mass": Pounds(300000),
            "basis": MassBasis.MEASURED,
            "established_on": ESTABLISHED,
            "batch_size": Pounds(6000),
            "return_temperature": Temperature.fahrenheit(118),
            "dust_loss_rate": Percent("0.4"),
        }
        for field, value, message in [
            ("name", "  ", "needs a name"),
            ("mass", 300000, "system mass is a bulk mass"),
            ("mass", Pounds.zero(), "no sand in it is not a system"),
            ("basis", "measured", "mass has a basis"),
            ("established_on", "2025-01-06", "mass figure is dated"),
            ("batch_size", 6000, "batch size is a bulk mass"),
            ("batch_size", Pounds.zero(), "takes no batch is not a muller"),
            ("return_temperature", 48, "temperature is a temperature"),
            ("dust_loss_rate", "0.4", "dust loss rate is a percentage"),
        ]:
            kwargs: Any = {**base, field: value}
            with pytest.raises(BadInputError, match=message):
                SandSystem(**kwargs)

    def test_str_names_the_basis(self) -> None:
        assert str(system()) == "number two system: 150.000 t (measured)"
