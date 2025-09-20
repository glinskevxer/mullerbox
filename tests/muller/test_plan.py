from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from mullerbox.addition.material import Addition, Material
from mullerbox.addition.water import response_at, water_for
from mullerbox.errors import BadInputError
from mullerbox.muller.plan import project_clay
from mullerbox.units.bulk import Pounds
from mullerbox.units.percent import Percent
from mullerbox.units.thermal import Temperature
from tests.muller.helpers import BATCH, SYSTEM, plan


class TestTheOrderIsWaterLast:
    def test_the_water_is_sized_against_the_projected_bond(self) -> None:
        built = plan()
        assert built.projected_clay > built.bond.measured
        assert built.water.response == response_at(built.projected_clay)

    def test_sizing_against_the_measured_bond_would_give_less_water(self) -> None:
        built = plan()
        naive = water_for(
            Percent("38"),
            Percent("42"),
            built.bond.measured,
            BATCH,
            Temperature.fahrenheit(118),
        )
        assert built.water.addition.mass > naive.addition.mass

    def test_a_plan_that_adds_no_bond_projects_no_change(self) -> None:
        built = plan(measured_clay=Percent("9.0"))
        assert not built.adds_bond
        assert built.projected_clay == Percent("9.0")

    def test_the_projection_is_on_the_plan_rather_than_hidden(self) -> None:
        assert "bond projected from" in str(plan())


class TestTheFourAdditions:
    def test_all_four_materials_appear(self) -> None:
        materials = {a.material for a in plan().additions}
        assert materials == set(Material)

    def test_they_are_in_charging_order_with_water_last(self) -> None:
        order = [a.material for a in plan().additions]
        assert order[-1] is Material.WATER
        assert order[0] is Material.BENTONITE

    def test_a_zero_addition_still_appears_with_its_reason(self) -> None:
        built = plan(measured_clay=Percent("9.0"))
        bond = built.addition_of(Material.BENTONITE)
        assert bond.is_nothing
        assert bond.reason.strip()

    def test_real_additions_drop_the_zeroes(self) -> None:
        built = plan(measured_clay=Percent("9.0"))
        assert Material.BENTONITE not in {a.material for a in built.real_additions}

    def test_the_dry_charge_leaves_the_water_out(self) -> None:
        built = plan()
        everything = sum((a.mass.value for a in built.additions), Decimal(0))
        assert built.dry_charge.value < everything
        water = built.addition_of(Material.WATER)
        assert built.dry_charge.value == everything - water.mass.value

    def test_looking_up_a_material_that_is_not_there(self) -> None:
        built = plan()
        assert built.addition_of(Material.SEACOAL).material is Material.SEACOAL


class TestProjection:
    def test_bentonite_raises_the_live_clay(self) -> None:
        addition = Addition(material=Material.BENTONITE, mass=Pounds(3000), reason="test")
        projected = project_clay(Percent("7.5"), addition, SYSTEM)
        assert projected > Percent("7.5")

    def test_a_zero_addition_moves_nothing(self) -> None:
        nothing = Addition.nothing(Material.BENTONITE, "at target")
        assert project_clay(Percent("7.5"), nothing, SYSTEM) == Percent("7.5")

    def test_the_projection_inverts_the_sizing(self) -> None:
        """Sizing an addition and then projecting it should land on the target."""
        built = plan(measured_clay=Percent("7.5"), clay_target=Percent("8.0"))
        assert abs(built.projected_clay.value - built.bond.working_target.value) <= Decimal("0.02")

    def test_it_is_guarded(self) -> None:
        bad: Any = "7.5"
        addition = Addition(material=Material.BENTONITE, mass=Pounds(3000), reason="test")
        with pytest.raises(BadInputError, match="measured clay is a percentage"):
            project_clay(bad, addition, SYSTEM)
        with pytest.raises(BadInputError, match="an addition is expected"):
            project_clay(Percent("7.5"), bad, SYSTEM)
        with pytest.raises(BadInputError, match="only bentonite moves"):
            project_clay(
                Percent("7.5"),
                Addition(material=Material.WATER, mass=Pounds(1), reason="x"),
                SYSTEM,
            )
        with pytest.raises(BadInputError, match="system mass is a bulk mass"):
            project_clay(Percent("7.5"), addition, bad)
        with pytest.raises(BadInputError, match="no clay level"):
            project_clay(Percent("7.5"), addition, Pounds.zero())


class TestGuards:
    def test_a_batch_of_nothing_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="not a batch"):
            plan(batch_size=Pounds.zero())

    def test_the_batch_size_has_to_be_a_mass(self) -> None:
        bad: Any = 6000
        with pytest.raises(BadInputError, match="batch size is a bulk mass"):
            plan(batch_size=bad)

    def test_the_plan_renders(self) -> None:
        lines = plan().render()
        assert lines[0].startswith("batch of")
        assert any("bentonite" in line for line in lines)
