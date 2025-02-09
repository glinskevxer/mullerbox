from __future__ import annotations

from decimal import Decimal

import pytest

from mullerbox.errors import BadInputError
from mullerbox.units.scales import Hardness, Permeability


class TestPermeability:
    def test_reads_an_int_and_a_string(self) -> None:
        assert Permeability(120) == Permeability("120")

    def test_it_is_a_whole_number_by_definition(self) -> None:
        with pytest.raises(BadInputError, match="cannot read a permeability"):
            Permeability(120.5)

    def test_negative_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="cannot be negative"):
            Permeability(-1)

    def test_a_wrong_orifice_reading_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="not a green sand permeability"):
            Permeability(1001)

    def test_unreadable_values_are_refused(self) -> None:
        with pytest.raises(BadInputError, match="is not a permeability"):
            Permeability("high")
        with pytest.raises(BadInputError, match="cannot read a permeability"):
            Permeability(None)
        with pytest.raises(BadInputError, match="from a boolean"):
            Permeability(True)

    def test_the_venting_rule_of_thumb(self) -> None:
        assert Permeability(40).vents_freely
        assert not Permeability(39).vents_freely

    def test_orders_and_hashes(self) -> None:
        assert Permeability(90) < Permeability(120)
        assert len({Permeability(120), Permeability("120")}) == 1

    def test_str_names_the_scale(self) -> None:
        assert str(Permeability(120)) == "120 AFS"


class TestHardness:
    def test_reads_the_usual_shapes(self) -> None:
        assert Hardness(88) == Hardness("88") == Hardness(88.0) == Hardness(Decimal(88))

    def test_rounds_to_a_tenth(self) -> None:
        assert Hardness("88.25").value == Decimal("88.3")

    def test_negative_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="cannot be negative"):
            Hardness(-1)

    def test_the_scale_stops_at_a_hundred(self) -> None:
        with pytest.raises(BadInputError, match="stops at a hundred"):
            Hardness("100.1")
        assert Hardness(100).value == Decimal("100.0")

    def test_unreadable_values_are_refused(self) -> None:
        with pytest.raises(BadInputError, match="is not a hardness"):
            Hardness("hard")
        with pytest.raises(BadInputError, match="cannot read a hardness"):
            Hardness(None)
        with pytest.raises(BadInputError, match="from a boolean"):
            Hardness(True)

    def test_orders_and_hashes(self) -> None:
        assert Hardness(80) < Hardness(88)
        assert len({Hardness("88.0"), Hardness(88)}) == 1

    def test_str_names_the_scale(self) -> None:
        assert str(Hardness(88)) == "88.0 B"


class TestTheScalesDoNotMix:
    def test_a_hardness_is_not_a_permeability(self) -> None:
        assert Permeability(88) != Hardness(88)
        assert Hardness(88) != Permeability(88)

    def test_they_cannot_be_ordered_against_each_other(self) -> None:
        with pytest.raises(TypeError):
            _ = Permeability(88) < Hardness(90)
