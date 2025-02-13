from __future__ import annotations

import pytest

from mullerbox.cal.instrument import InstrumentKind
from mullerbox.errors import BadInputError
from mullerbox.props.kind import Direction, PropertyKind, parse_property
from mullerbox.units.percent import Percent
from mullerbox.units.pressure import Psi, WetTensile
from mullerbox.units.scales import Hardness, Permeability


class TestEveryPropertyIsFullyWiredUp:
    @pytest.mark.parametrize("kind", list(PropertyKind))
    def test_it_names_an_instrument(self, kind: PropertyKind) -> None:
        assert isinstance(kind.measured_by, InstrumentKind)

    @pytest.mark.parametrize("kind", list(PropertyKind))
    def test_it_names_a_reading_type(self, kind: PropertyKind) -> None:
        assert kind.reading_type in {Percent, Psi, WetTensile, Permeability, Hardness}

    @pytest.mark.parametrize("kind", list(PropertyKind))
    def test_it_names_a_direction(self, kind: PropertyKind) -> None:
        assert isinstance(kind.direction, Direction)

    @pytest.mark.parametrize("kind", list(PropertyKind))
    def test_it_has_a_label(self, kind: PropertyKind) -> None:
        assert kind.label.strip()


class TestTheReadingTypeGuardsTheScale:
    def test_compactability_is_a_percentage(self) -> None:
        assert PropertyKind.COMPACTABILITY.reading_type is Percent
        assert PropertyKind.COMPACTABILITY.accepts(Percent(42))

    def test_green_compression_is_psi(self) -> None:
        assert PropertyKind.GREEN_COMPRESSION.accepts(Psi(22))
        assert not PropertyKind.GREEN_COMPRESSION.accepts(WetTensile("0.28"))

    def test_two_small_whole_numbers_are_not_interchangeable(self) -> None:
        assert not PropertyKind.PERMEABILITY.accepts(Hardness(88))
        assert not PropertyKind.MOLD_HARDNESS.accepts(Permeability(88))

    def test_a_mismatch_names_both_scales(self) -> None:
        with pytest.raises(BadInputError, match="measured in Psi, not WetTensile"):
            PropertyKind.GREEN_COMPRESSION.require_reading(WetTensile("0.28"))

    def test_a_good_reading_comes_straight_back(self) -> None:
        reading = Psi(22)
        assert PropertyKind.GREEN_COMPRESSION.require_reading(reading) is reading

    def test_a_bare_number_is_not_a_reading(self) -> None:
        with pytest.raises(BadInputError, match="measured in Percent, not int"):
            PropertyKind.COMPACTABILITY.require_reading(42)


class TestTheInstrumentGuardsTheEntry:
    def test_the_right_instrument_passes(self) -> None:
        kind = PropertyKind.PERMEABILITY.require_instrument_kind(InstrumentKind.PERMEABILITY)
        assert kind is InstrumentKind.PERMEABILITY

    def test_the_wrong_instrument_names_the_right_one(self) -> None:
        with pytest.raises(
            BadInputError,
            match="measured on the universal strength machine, not the permeability meter",
        ):
            PropertyKind.GREEN_COMPRESSION.require_instrument_kind(InstrumentKind.PERMEABILITY)

    def test_it_wants_an_instrument_kind(self) -> None:
        with pytest.raises(BadInputError, match="instrument kind is expected"):
            PropertyKind.GREEN_COMPRESSION.require_instrument_kind("strength")

    def test_the_strength_machine_carries_three_properties(self) -> None:
        on_the_usm = [k for k in PropertyKind if k.measured_by is InstrumentKind.STRENGTH]
        assert set(on_the_usm) == {
            PropertyKind.GREEN_COMPRESSION,
            PropertyKind.WET_TENSILE,
            PropertyKind.MOLD_HARDNESS,
        }


class TestDirections:
    def test_burnt_carbon_is_one_sided(self) -> None:
        assert PropertyKind.LOI.direction is Direction.HIGHER_IS_WORSE
        assert PropertyKind.VOLATILES.direction is Direction.HIGHER_IS_WORSE

    def test_wet_tensile_only_hurts_when_it_is_low(self) -> None:
        assert PropertyKind.WET_TENSILE.direction is Direction.LOWER_IS_WORSE

    def test_bond_and_water_hurt_both_ways(self) -> None:
        assert PropertyKind.MB_CLAY.direction is Direction.TWO_SIDED
        assert PropertyKind.MOISTURE.direction is Direction.TWO_SIDED


class TestParsing:
    @pytest.mark.parametrize(
        ("text", "want"),
        [
            ("comp", PropertyKind.COMPACTABILITY),
            ("Compactability", PropertyKind.COMPACTABILITY),
            ("GCS", PropertyKind.GREEN_COMPRESSION),
            ("green_compression", PropertyKind.GREEN_COMPRESSION),
            ("green-compression-strength", PropertyKind.GREEN_COMPRESSION),
            ("perm", PropertyKind.PERMEABILITY),
            ("H2O", PropertyKind.MOISTURE),
            ("MB", PropertyKind.MB_CLAY),
            ("afs clay", PropertyKind.TOTAL_CLAY),
            ("LOI", PropertyKind.LOI),
            ("  shatter  index ", PropertyKind.SHATTER_INDEX),
        ],
    )
    def test_the_lab_shorthand(self, text: str, want: PropertyKind) -> None:
        assert parse_property(text) is want

    def test_anything_else_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="is not a sand property"):
            parse_property("stickiness")

    def test_every_full_label_parses(self) -> None:
        for kind in PropertyKind:
            assert parse_property(kind.label) is kind
