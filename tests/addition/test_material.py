from __future__ import annotations

from decimal import Decimal

import pytest

from mullerbox.addition.material import Addition, Material, dry_total
from mullerbox.errors import BadInputError
from mullerbox.units.bulk import Pounds


def addition(
    material: Material = Material.BENTONITE,
    mass: str = "140",
    reason: str = "bond deficit",
) -> Addition:
    return Addition(material=material, mass=Pounds(mass), reason=reason)


class TestMaterials:
    @pytest.mark.parametrize("material", list(Material))
    def test_every_material_has_a_label_and_a_yield(self, material: Material) -> None:
        assert material.label.strip()
        assert Decimal(0) < material.yield_factor <= Decimal(1)

    def test_bentonite_does_not_fully_develop(self) -> None:
        assert Material.BENTONITE.yield_factor < Decimal(1)

    def test_new_sand_and_water_are_what_they_are(self) -> None:
        assert Material.NEW_SAND.yield_factor == Decimal(1)
        assert Material.WATER.yield_factor == Decimal(1)

    def test_only_water_is_wet(self) -> None:
        wet = [m for m in Material if not m.is_dry]
        assert wet == [Material.WATER]


class TestAddition:
    def test_the_pieces_are_checked(self) -> None:
        with pytest.raises(BadInputError, match="of a material"):
            Addition(material="bentonite", mass=Pounds(1), reason="x")  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="is a bulk mass"):
            Addition(material=Material.BENTONITE, mass=1, reason="x")  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="records why"):
            Addition(material=Material.BENTONITE, mass=Pounds(1), reason="  ")

    def test_a_zero_addition_is_a_decision(self) -> None:
        nothing = Addition.nothing(Material.BENTONITE, "already at target")
        assert nothing.is_nothing
        assert nothing.reason == "already at target"

    def test_a_zero_addition_still_needs_a_reason(self) -> None:
        with pytest.raises(BadInputError, match="records why"):
            Addition.nothing(Material.BENTONITE, "")

    def test_str_carries_all_three(self) -> None:
        assert str(addition()) == "140.00 lb bentonite (bond deficit)"


class TestDryTotal:
    def test_water_is_left_out(self) -> None:
        charge = [
            addition(Material.BENTONITE, "140"),
            addition(Material.SEACOAL, "60"),
            addition(Material.WATER, "300"),
        ]
        assert dry_total(charge) == Pounds(200)

    def test_nothing_totals_to_zero(self) -> None:
        assert dry_total([]) == Pounds.zero()

    def test_it_wants_additions(self) -> None:
        with pytest.raises(BadInputError, match="only additions"):
            dry_total([addition(), Pounds(1)])  # type: ignore[list-item]
