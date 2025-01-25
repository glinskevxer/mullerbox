from __future__ import annotations

from decimal import Decimal

import pytest

from mullerbox.errors import BadInputError
from mullerbox.units.pressure import Psi, WetTensile


class TestPsi:
    def test_reads_the_usual_shapes(self) -> None:
        assert Psi(22) == Psi("22") == Psi(22.0) == Psi(Decimal(22))

    def test_a_trailing_unit_is_allowed(self) -> None:
        assert Psi("22.4 psi") == Psi("22.4")

    def test_rounds_to_a_tenth(self) -> None:
        assert Psi("22.45").value == Decimal("22.5")
        assert Psi("22.44").value == Decimal("22.4")

    def test_negative_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="cannot be negative"):
            Psi(-1)

    def test_a_bonded_sand_number_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="not a green sand strength"):
            Psi(1001)

    def test_unreadable_values_are_refused(self) -> None:
        with pytest.raises(BadInputError, match="is not a pressure"):
            Psi("strong")
        with pytest.raises(BadInputError, match="cannot read a pressure"):
            Psi(None)
        with pytest.raises(BadInputError, match="from a boolean"):
            Psi(True)

    def test_addition(self) -> None:
        assert Psi("20.0") + Psi("2.5") == Psi("22.5")

    def test_subtraction_floors_at_zero(self) -> None:
        assert Psi(20) - Psi(25) == Psi.zero()
        assert Psi(25) - Psi(20) == Psi(5)

    def test_arithmetic_against_another_type_is_not_implemented(self) -> None:
        with pytest.raises(TypeError):
            Psi(1) + 1
        with pytest.raises(TypeError):
            Psi(1) - 1

    def test_scaling(self) -> None:
        assert Psi(20).scaled("1.1") == Psi(22)

    def test_scaling_by_a_pressure_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="is not a pressure"):
            Psi(1).scaled(Psi(2))

    def test_scaling_by_a_negative_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="negative ratio"):
            Psi(1).scaled(-1)

    def test_scaling_by_a_bad_type_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="cannot scale a pressure"):
            Psi(1).scaled(None)

    def test_orders_and_hashes(self) -> None:
        assert Psi(20) < Psi(22)
        assert len({Psi("22.0"), Psi(22)}) == 1

    def test_str_carries_the_unit(self) -> None:
        assert str(Psi("22.4")) == "22.4 psi"


class TestWetTensile:
    def test_rounds_to_a_hundredth(self) -> None:
        assert WetTensile("0.285").value == Decimal("0.29")

    def test_a_trailing_unit_is_allowed(self) -> None:
        assert WetTensile("0.28 g/cm2") == WetTensile("0.28")

    def test_negative_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="cannot be negative"):
            WetTensile(-1)

    def test_a_psi_scale_number_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="not a wet tensile reading"):
            WetTensile(101)

    def test_orders_and_hashes(self) -> None:
        assert WetTensile("0.20") < WetTensile("0.30")
        assert len({WetTensile("0.30"), WetTensile(0.3)}) == 1

    def test_str_carries_the_unit(self) -> None:
        assert str(WetTensile("0.28")) == "0.28 g/cm2"

    def test_zero(self) -> None:
        assert WetTensile.zero() == WetTensile(0)


class TestTheScalesDoNotMix:
    def test_a_wet_tensile_is_not_a_psi(self) -> None:
        assert Psi(1) != WetTensile(1)
        assert WetTensile(1) != Psi(1)

    def test_they_cannot_be_added(self) -> None:
        with pytest.raises(TypeError):
            Psi(1) + WetTensile(1)

    def test_they_cannot_be_ordered_against_each_other(self) -> None:
        with pytest.raises(TypeError):
            _ = Psi(1) < WetTensile(2)
