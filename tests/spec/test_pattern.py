from __future__ import annotations

from decimal import Decimal

import pytest

from mullerbox.errors import BadInputError
from mullerbox.props.kind import PropertyKind
from mullerbox.spec.pattern import PatternClass, Section, parse_pattern_class

CORE_FOUR = {
    PropertyKind.COMPACTABILITY,
    PropertyKind.GREEN_COMPRESSION,
    PropertyKind.MOISTURE,
    PropertyKind.MB_CLAY,
}


class TestEveryClassIsWiredUp:
    @pytest.mark.parametrize("cls", list(PatternClass))
    def test_it_names_a_section(self, cls: PatternClass) -> None:
        assert isinstance(cls.section, Section)

    @pytest.mark.parametrize("cls", list(PatternClass))
    def test_it_controls_at_least_the_core_four(self, cls: PatternClass) -> None:
        assert cls.controlled >= CORE_FOUR

    @pytest.mark.parametrize("cls", list(PatternClass))
    def test_it_has_a_tolerance_factor_in_a_sane_range(self, cls: PatternClass) -> None:
        assert Decimal("0.5") <= cls.tolerance_factor <= Decimal("2.0")

    @pytest.mark.parametrize("cls", list(PatternClass))
    def test_it_has_a_label(self, cls: PatternClass) -> None:
        assert cls.label.strip()


class TestWhatEachClassHolds:
    def test_light_work_holds_the_least(self) -> None:
        assert PatternClass.LIGHT_JOBBING.controlled == CORE_FOUR | {PropertyKind.PERMEABILITY}

    def test_cored_work_adds_friability_and_wet_tensile(self) -> None:
        for cls in (PatternClass.CORED_LIGHT, PatternClass.CORED_HEAVY):
            assert cls.controls(PropertyKind.FRIABILITY)
            assert cls.controls(PropertyKind.WET_TENSILE)

    def test_uncored_work_does_not_hold_friability(self) -> None:
        for cls in (
            PatternClass.LIGHT_JOBBING,
            PatternClass.MEDIUM_JOBBING,
            PatternClass.HEAVY_JOBBING,
        ):
            assert not cls.controls(PropertyKind.FRIABILITY)

    def test_heavy_work_holds_the_burnt_carbon(self) -> None:
        assert PatternClass.HEAVY_JOBBING.controls(PropertyKind.LOI)
        assert PatternClass.HEAVY_JOBBING.controls(PropertyKind.VOLATILES)

    def test_light_work_does_not_hold_the_burnt_carbon(self) -> None:
        assert not PatternClass.LIGHT_JOBBING.controls(PropertyKind.LOI)

    def test_the_two_hardest_classes_hold_the_same_number_by_different_routes(
        self,
    ) -> None:
        # Cored heavy gets there through the core properties, thin wall through
        # the gas properties and the squeeze. Neither is a superset.
        thin = PatternClass.THIN_WALL.controlled
        cored = PatternClass.CORED_HEAVY.controlled
        assert len(thin) == len(cored) == 9
        assert len(thin) == max(len(c.controlled) for c in PatternClass)
        assert not thin <= cored
        assert not cored <= thin
        assert PropertyKind.MOLD_HARDNESS in thin - cored
        assert PropertyKind.FRIABILITY in cored - thin

    def test_only_thin_wall_holds_mold_hardness(self) -> None:
        holders = [c for c in PatternClass if c.controls(PropertyKind.MOLD_HARDNESS)]
        assert holders == [PatternClass.THIN_WALL]


class TestCored:
    def test_the_cored_classes_report_cored(self) -> None:
        assert PatternClass.CORED_LIGHT.is_cored
        assert PatternClass.CORED_HEAVY.is_cored

    def test_the_others_do_not(self) -> None:
        assert not PatternClass.LIGHT_JOBBING.is_cored
        assert not PatternClass.THIN_WALL.is_cored


class TestSections:
    def test_thin_covers_three_classes(self) -> None:
        thin = [c for c in PatternClass if c.section is Section.THIN]
        assert set(thin) == {
            PatternClass.LIGHT_JOBBING,
            PatternClass.CORED_LIGHT,
            PatternClass.THIN_WALL,
        }

    def test_every_section_has_a_label(self) -> None:
        assert all(s.label for s in Section)


class TestTolerance:
    def test_thin_wall_is_held_tightest(self) -> None:
        tightest = min(PatternClass, key=lambda c: c.tolerance_factor)
        assert tightest is PatternClass.THIN_WALL

    def test_heavy_plain_work_gets_the_widest_band(self) -> None:
        loosest = max(PatternClass, key=lambda c: c.tolerance_factor)
        assert loosest is PatternClass.HEAVY_JOBBING

    def test_the_same_property_is_held_differently_by_class(self) -> None:
        thin = PatternClass.THIN_WALL.tolerance_factor
        heavy = PatternClass.HEAVY_JOBBING.tolerance_factor
        assert thin < heavy


class TestGuards:
    def test_requiring_an_uncontrolled_property_names_the_class(self) -> None:
        with pytest.raises(BadInputError, match="light jobbing work does not control"):
            PatternClass.LIGHT_JOBBING.require_controls(PropertyKind.LOI)

    def test_requiring_a_controlled_property_hands_it_back(self) -> None:
        got = PatternClass.LIGHT_JOBBING.require_controls(PropertyKind.MOISTURE)
        assert got is PropertyKind.MOISTURE

    def test_it_wants_a_property_kind(self) -> None:
        with pytest.raises(BadInputError, match="property kind is expected"):
            PatternClass.LIGHT_JOBBING.controls("moisture")
        with pytest.raises(BadInputError, match="property kind is expected"):
            PatternClass.LIGHT_JOBBING.require_controls("moisture")


class TestParsing:
    @pytest.mark.parametrize(
        ("text", "want"),
        [
            ("thin wall", PatternClass.THIN_WALL),
            ("THIN_WALL", PatternClass.THIN_WALL),
            ("cored-heavy", PatternClass.CORED_HEAVY),
            ("  light   jobbing ", PatternClass.LIGHT_JOBBING),
        ],
    )
    def test_the_separators_do_not_matter(self, text: str, want: PatternClass) -> None:
        assert parse_pattern_class(text) is want

    def test_anything_else_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="is not a pattern class"):
            parse_pattern_class("prototype")

    def test_every_label_parses(self) -> None:
        for cls in PatternClass:
            assert parse_pattern_class(cls.label) is cls
