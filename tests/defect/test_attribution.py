from __future__ import annotations

import pytest

from mullerbox.defect.attribution import (
    Excursion,
    attribute,
    charged_to_sand,
    excursions_for,
)
from mullerbox.defect.kind import Culprit, DefectKind
from mullerbox.errors import BadInputError
from mullerbox.props.kind import PropertyKind
from mullerbox.spec.band import Band, Verdict
from mullerbox.spec.pattern import PatternClass
from mullerbox.units.percent import Percent
from mullerbox.units.pressure import Psi
from mullerbox.units.scales import Permeability
from tests.defect.helpers import readings, spec_for

HEAVY = PatternClass.HEAVY_JOBBING
LIGHT = PatternClass.LIGHT_JOBBING
CORED = PatternClass.CORED_LIGHT
THIN = PatternClass.THIN_WALL


class TestTheClassIsCheckedFirst:
    def test_veining_on_uncored_work_is_not_a_sand_question(self) -> None:
        wet = readings(MOISTURE=Percent("4.5"))
        got = attribute(DefectKind.VEINING, spec_for(LIGHT), wet)
        assert not got.is_sand
        assert got.culprit is Culprit.PATTERN
        assert "does not produce it from the sand" in got.reason
        assert got.excursions == ()

    def test_the_same_defect_on_cored_work_is(self) -> None:
        wet = readings(MOISTURE=Percent("4.5"))
        got = attribute(DefectKind.VEINING, spec_for(CORED), wet)
        assert got.is_sand
        assert got.properties == (PropertyKind.MOISTURE,)

    def test_a_melt_defect_says_no_sand_property_can_cause_it(self) -> None:
        got = attribute(DefectKind.SHRINKAGE, spec_for(HEAVY), readings())
        assert got.culprit is Culprit.MELT
        assert "no sand property can cause it" in got.reason

    def test_penetration_is_refused_on_light_work_however_bad_the_sand(self) -> None:
        got = attribute(
            DefectKind.PENETRATION, spec_for(LIGHT), readings(PERMEABILITY=Permeability(300))
        )
        assert not got.is_sand


class TestOnlyMechanisticPropertiesCount:
    def test_a_blow_ignores_a_strength_excursion(self) -> None:
        got = attribute(DefectKind.BLOW, spec_for(HEAVY), readings(GREEN_COMPRESSION=Psi(50)))
        assert not got.is_sand
        assert "was in band" in got.reason

    def test_a_blow_picks_up_a_permeability_excursion(self) -> None:
        got = attribute(DefectKind.BLOW, spec_for(HEAVY), readings(PERMEABILITY=Permeability(40)))
        assert got.is_sand
        assert got.properties == (PropertyKind.PERMEABILITY,)

    def test_every_supporting_excursion_is_named(self) -> None:
        got = attribute(
            DefectKind.BLOW,
            spec_for(HEAVY),
            readings(PERMEABILITY=Permeability(40), MOISTURE=Percent("4.5")),
        )
        assert set(got.properties) == {
            PropertyKind.PERMEABILITY,
            PropertyKind.MOISTURE,
        }
        assert len(got.excursions) == 2


class TestTheBandInForceDecides:
    def test_one_reading_is_guilty_on_thin_wall_and_innocent_on_heavy(self) -> None:
        # 44.5 sits inside the widened heavy band and outside the tight one.
        sand = readings(COMPACTABILITY=Percent("44.5"))
        on_heavy = attribute(DefectKind.SCAB, spec_for(HEAVY), sand)
        on_cored = attribute(DefectKind.SCAB, spec_for(PatternClass.CORED_LIGHT), sand)
        assert not on_heavy.is_sand
        assert on_cored.is_sand

    def test_the_excursion_carries_the_band_it_was_judged_against(self) -> None:
        got = attribute(DefectKind.BLOW, spec_for(HEAVY), readings(PERMEABILITY=Permeability(40)))
        excursion = got.excursions[0]
        assert excursion.band == spec_for(HEAVY).band_for(PropertyKind.PERMEABILITY)
        assert excursion.verdict is Verdict.BELOW


class TestUnjudgedProperties:
    def test_a_property_the_class_does_not_control_is_skipped(self) -> None:
        # Light jobbing does not control LOI, so a wild LOI supports nothing.
        got = attribute(DefectKind.SCAB, spec_for(LIGHT), readings(LOI=Percent("9")))
        assert not got.is_sand
        assert "was in band" in got.reason

    def test_a_missing_reading_is_skipped(self) -> None:
        sand = readings()
        del sand[PropertyKind.PERMEABILITY]
        got = attribute(DefectKind.BLOW, spec_for(HEAVY), sand)
        assert not got.is_sand


class TestExcursion:
    def test_an_in_band_reading_is_not_an_excursion(self) -> None:
        band = spec_for(HEAVY).band_for(PropertyKind.PERMEABILITY)
        with pytest.raises(BadInputError, match="is not an excursion"):
            Excursion(
                kind=PropertyKind.PERMEABILITY,
                reading=Permeability(110),
                verdict=Verdict.INSIDE,
                band=band,
            )

    def test_str_names_the_reading_and_the_side(self) -> None:
        got = attribute(DefectKind.BLOW, spec_for(HEAVY), readings(PERMEABILITY=Permeability(40)))
        assert "permeability 40 AFS below" in str(got.excursions[0])


class TestRollUp:
    def test_it_keeps_only_the_sand_charges(self) -> None:
        sand = readings(PERMEABILITY=Permeability(40))
        found = charged_to_sand(
            [DefectKind.BLOW, DefectKind.SHRINKAGE, DefectKind.VEINING],
            spec_for(HEAVY),
            sand,
        )
        assert [a.defect for a in found] == [DefectKind.BLOW]

    def test_nothing_charged_gives_an_empty_list(self) -> None:
        assert charged_to_sand([DefectKind.SHRINKAGE], spec_for(HEAVY), readings()) == []


class TestGuards:
    def test_the_arguments_are_checked(self) -> None:
        with pytest.raises(BadInputError, match="defect kind is expected"):
            attribute("blow", spec_for(HEAVY), readings())  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="resolved spec is expected"):
            attribute(DefectKind.BLOW, "heavy", readings())  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="defect kind is expected"):
            excursions_for("blow", spec_for(HEAVY), readings())  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="resolved spec is expected"):
            excursions_for(DefectKind.BLOW, "heavy", readings())  # type: ignore[arg-type]

    def test_str_names_the_defect_the_class_and_the_culprit(self) -> None:
        got = attribute(DefectKind.SHRINKAGE, spec_for(HEAVY), readings())
        assert str(got).startswith("shrinkage on heavy jobbing: melt")


def test_a_band_is_still_a_band() -> None:
    assert isinstance(spec_for(HEAVY).band_for(PropertyKind.MOISTURE), Band)
