from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from mullerbox.addition.material import Addition, Material
from mullerbox.addition.order import (
    CHARGE_ORDER,
    ChargeOrder,
    Step,
    charge_order,
    diluted,
    dilution_factor,
)
from mullerbox.errors import BadInputError, RuleError
from mullerbox.system.state import MassBasis, SandSystem
from mullerbox.units.bulk import Pounds
from mullerbox.units.percent import Percent
from mullerbox.units.thermal import Temperature

D = Decimal
WHEN = date(2026, 3, 2)


def system(basis: MassBasis = MassBasis.MEASURED, on: date = date(2026, 2, 2)) -> SandSystem:
    return SandSystem(
        name="two",
        mass=Pounds(100000),
        basis=basis,
        established_on=on,
        batch_size=Pounds(2000),
        return_temperature=Temperature.fahrenheit(120),
        dust_loss_rate=Percent("1.5"),
    )


def add(material: Material, mass: str) -> Addition:
    return Addition(material=material, mass=Pounds(mass), reason="the shift sheet")


def order(new_sand: str = "0", water: str = "60", **kwargs: Any) -> ChargeOrder:
    return charge_order(
        kwargs.get("system", system()),
        kwargs.get("when", WHEN),
        add(Material.NEW_SAND, new_sand),
        add(Material.BENTONITE, "80"),
        add(Material.SEACOAL, "30"),
        add(Material.WATER, water),
    )


class TestTheOrderIsFixed:
    def test_new_sand_leads_and_water_follows(self) -> None:
        got = order()
        assert [s.addition.material for s in got.steps] == list(CHARGE_ORDER)

    def test_the_positions_run_from_one(self) -> None:
        assert [s.position for s in order().steps] == [1, 2, 3, 4]

    def test_only_the_water_waits_for_the_mull(self) -> None:
        waiting = [s.addition.material for s in order().steps if s.wait_for_mull]
        assert waiting == [Material.WATER]

    def test_the_dry_charge_goes_in_together(self) -> None:
        dry = [s.addition.material for s in order().steps if not s.wait_for_mull]
        assert dry == [Material.NEW_SAND, Material.BENTONITE, Material.SEACOAL]


class TestDilution:
    def test_no_new_sand_leaves_the_readings_alone(self) -> None:
        got = order(new_sand="0")
        assert got.dilution == D(1)
        assert not got.is_dilutive

    def test_new_sand_moves_every_reading_down(self) -> None:
        got = order(new_sand="5000")
        assert got.dilution == D("0.952381")
        assert got.is_dilutive

    def test_the_factor_is_the_share_of_old_sand_left(self) -> None:
        assert dilution_factor(Pounds(25000), Pounds(75000)) == D("0.750000")

    def test_a_reading_diluted_is_the_reading_to_chase(self) -> None:
        assert diluted(Percent("8.00"), D("0.75")) == Percent("6.00")

    def test_a_factor_of_one_changes_nothing(self) -> None:
        assert diluted(Percent("8.00"), D(1)) == Percent("8.00")

    def test_nothing_dilutes_into_an_empty_system(self) -> None:
        with pytest.raises(BadInputError, match="system with no sand"):
            dilution_factor(Pounds(100), Pounds(0))

    def test_a_factor_above_one_is_not_a_dilution(self) -> None:
        with pytest.raises(BadInputError, match="at most one"):
            diluted(Percent("8.00"), D("1.2"))

    def test_a_factor_of_zero_is_not_one_either(self) -> None:
        with pytest.raises(BadInputError, match="above zero"):
            diluted(Percent("8.00"), D(0))

    def test_it_wants_bulk_masses(self) -> None:
        bad: Any = 5000
        with pytest.raises(BadInputError, match="new sand is a bulk mass"):
            dilution_factor(bad, Pounds(100000))

    def test_and_a_real_system_mass(self) -> None:
        bad: Any = 100000
        with pytest.raises(BadInputError, match="system mass is a bulk mass"):
            dilution_factor(Pounds(5000), bad)

    def test_it_wants_a_percentage_to_dilute(self) -> None:
        bad: Any = "8.00"
        with pytest.raises(BadInputError, match="diluted reading is a percentage"):
            diluted(bad, D("0.75"))

    def test_and_a_decimal_factor(self) -> None:
        bad: Any = 0.75
        with pytest.raises(BadInputError, match="dilution factor is a decimal"):
            diluted(Percent("8.00"), bad)


class TestAGuessedMassIsRefused:
    def test_a_nameplate_system_will_not_charge(self) -> None:
        with pytest.raises(RuleError, match="nameplate mass"):
            order(system=system(basis=MassBasis.NAMEPLATE))

    def test_a_stale_inventory_will_not_either(self) -> None:
        with pytest.raises(RuleError, match="last inventoried"):
            order(system=system(on=date(2024, 1, 1)))

    def test_a_current_measured_one_charges(self) -> None:
        assert order().steps != ()


class TestTheSheet:
    def test_it_totals_the_dry_and_the_water(self) -> None:
        got = order(new_sand="1000")
        assert got.dry == Pounds(1110)
        assert got.water == Pounds(60)

    def test_a_batch_with_no_water_still_has_a_water_step(self) -> None:
        got = order(water="0")
        assert got.water == Pounds(0)
        assert len(got.steps) == 4
        assert len(got.acting) == 2

    def test_the_sheet_names_the_dilution_when_there_is_one(self) -> None:
        lines = order(new_sand="5000").render()
        assert any("dilutes every reading" in line for line in lines)

    def test_and_says_nothing_about_it_when_there_is_not(self) -> None:
        lines = order().render()
        assert not any("dilutes" in line for line in lines)

    def test_the_water_line_says_it_waits(self) -> None:
        lines = order().render()
        assert lines[3].endswith("after the dry mull")

    def test_str_summarises_the_batch(self) -> None:
        assert str(order()) == "3 additions, 110.00 lb dry and 60.00 lb water"


class TestRefusals:
    def test_a_material_in_the_wrong_slot(self) -> None:
        with pytest.raises(RuleError, match="given as the new sand one"):
            charge_order(
                system(),
                WHEN,
                add(Material.BENTONITE, "80"),
                add(Material.BENTONITE, "80"),
                add(Material.SEACOAL, "30"),
                add(Material.WATER, "60"),
            )

    def test_a_missing_addition(self) -> None:
        bad: Any = None
        with pytest.raises(BadInputError, match="water addition is missing"):
            charge_order(
                system(),
                WHEN,
                add(Material.NEW_SAND, "0"),
                add(Material.BENTONITE, "80"),
                add(Material.SEACOAL, "30"),
                bad,
            )

    def test_it_wants_a_system(self) -> None:
        bad: Any = "two"
        with pytest.raises(BadInputError, match="against a sand system"):
            order(system=bad)

    def test_it_wants_a_date(self) -> None:
        bad: Any = "2026-03-02"
        with pytest.raises(BadInputError, match="charge order is dated"):
            order(when=bad)

    def test_a_step_needs_an_addition(self) -> None:
        bad: Any = "80 lb bentonite"
        with pytest.raises(BadInputError, match="holds an addition"):
            Step(position=1, addition=bad, wait_for_mull=False)

    def test_a_step_starts_at_one(self) -> None:
        with pytest.raises(BadInputError, match="starts at position one"):
            Step(position=0, addition=add(Material.WATER, "60"), wait_for_mull=True)

    def test_a_position_is_a_whole_number(self) -> None:
        bad: Any = 1.5
        with pytest.raises(BadInputError, match="whole number"):
            Step(position=bad, addition=add(Material.WATER, "60"), wait_for_mull=True)
