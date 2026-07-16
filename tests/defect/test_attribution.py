from __future__ import annotations

from typing import Any

import pytest

from mullerbox.defect.attribution import (
    Excursion,
    attribute,
    band_in_force,
    charged_to_sand,
    excursions_for,
)
from mullerbox.defect.kind import Culprit, DefectKind
from mullerbox.errors import BadInputError
from mullerbox.gfn.distribution import grade
from mullerbox.gfn.fineness import fineness_of
from mullerbox.props.kind import PropertyKind
from mullerbox.spec.band import Band, Verdict
from mullerbox.spec.pattern import PatternClass
from mullerbox.spec.sheet import SpecSheet, resolve
from mullerbox.units.percent import Percent
from mullerbox.units.pressure import Psi
from mullerbox.units.scales import Permeability
from tests.defect.helpers import readings, spec_for
from tests.gfn.helpers import analysis_of
from tests.gfn.helpers import sheet as bench_sheet

HEAVY = PatternClass.HEAVY_JOBBING
LIGHT = PatternClass.LIGHT_JOBBING
CORED = PatternClass.CORED_LIGHT
THIN = PatternClass.THIN_WALL


def distribution_of(**held: str):  # type: ignore[no-untyped-def]
    return grade(fineness_of(analysis_of(bench_sheet(**held), "50.00")))


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


class TestThePermeabilityBandIsShiftedBeforeItJudges:
    def test_the_sheet_band_is_used_when_no_analysis_is_given(self) -> None:
        got = band_in_force(spec_for(HEAVY), PropertyKind.PERMEABILITY)
        assert got == spec_for(HEAVY).band_for(PropertyKind.PERMEABILITY)

    def test_an_analysis_moves_it(self) -> None:
        coarse = distribution_of(**{"40": "50.00"})
        shifted = band_in_force(spec_for(HEAVY), PropertyKind.PERMEABILITY, coarse)
        assert shifted.floor > spec_for(HEAVY).band_for(PropertyKind.PERMEABILITY).floor

    def test_every_other_property_is_left_alone(self) -> None:
        coarse = distribution_of(**{"40": "50.00"})
        for kind in (PropertyKind.MOISTURE, PropertyKind.GREEN_COMPRESSION):
            assert band_in_force(spec_for(HEAVY), kind, coarse) == spec_for(HEAVY).band_for(kind)

    def test_a_coarse_sand_reading_in_the_sheet_band_is_now_an_excursion(self) -> None:
        # 110 AFS is comfortably inside the published band, and on a 30 GFN sand
        # it is nowhere near what that sand should vent at.
        coarse = distribution_of(**{"40": "50.00"})
        sand = readings(PERMEABILITY=Permeability(110))
        assert excursions_for(DefectKind.BLOW, spec_for(HEAVY), sand) == ()
        with_analysis = excursions_for(DefectKind.BLOW, spec_for(HEAVY), sand, coarse)
        assert PropertyKind.PERMEABILITY in tuple(e.kind for e in with_analysis)

    def test_and_the_defect_follows_it(self) -> None:
        coarse = distribution_of(**{"40": "50.00"})
        sand = readings(PERMEABILITY=Permeability(110))
        assert not attribute(DefectKind.BLOW, spec_for(HEAVY), sand).is_sand
        assert attribute(DefectKind.BLOW, spec_for(HEAVY), sand, coarse).is_sand

    def test_a_fine_sand_reading_below_the_sheet_band_is_no_longer_one(self) -> None:
        # The other direction, which is the one that costs a shop money: a fine
        # sand judged against a band written for coarser sand fails every shift.
        fine = distribution_of(**{"140": "50.00"})
        sand = readings(PERMEABILITY=Permeability(40))
        assert excursions_for(DefectKind.BLOW, spec_for(HEAVY), sand) != ()
        assert excursions_for(DefectKind.BLOW, spec_for(HEAVY), sand, fine) == ()

    def test_the_excursion_carries_the_shifted_band_not_the_anchor(self) -> None:
        coarse = distribution_of(**{"40": "50.00"})
        sand = readings(PERMEABILITY=Permeability(110))
        found = excursions_for(DefectKind.BLOW, spec_for(HEAVY), sand, coarse)
        perm = next(e for e in found if e.kind is PropertyKind.PERMEABILITY)
        assert perm.band != spec_for(HEAVY).band_for(PropertyKind.PERMEABILITY)
        assert perm.verdict is Verdict.BELOW

    def test_charged_to_sand_passes_the_analysis_through(self) -> None:
        coarse = distribution_of(**{"40": "50.00"})
        sand = readings(PERMEABILITY=Permeability(110))
        assert charged_to_sand([DefectKind.BLOW], spec_for(HEAVY), sand) == []
        assert charged_to_sand([DefectKind.BLOW], spec_for(HEAVY), sand, coarse) != []

    def test_it_wants_a_property_kind(self) -> None:
        bad: Any = "permeability"
        with pytest.raises(BadInputError, match="property kind is expected"):
            band_in_force(spec_for(HEAVY), bad)

    def test_it_wants_a_resolved_spec(self) -> None:
        bad: Any = "spec"
        with pytest.raises(BadInputError, match="resolved spec is expected"):
            band_in_force(bad, PropertyKind.PERMEABILITY)

    def test_it_wants_a_real_distribution(self) -> None:
        bad: Any = "coarse"
        with pytest.raises(BadInputError, match="graded distribution is expected"):
            band_in_force(spec_for(HEAVY), PropertyKind.PERMEABILITY, bad)

    def test_a_one_ended_anchor_is_left_where_it_is(self) -> None:
        one_ended = resolve(
            SpecSheet(
                name="floor only",
                bands={
                    PropertyKind.PERMEABILITY: Band.at_least(
                        PropertyKind.PERMEABILITY, Permeability(60)
                    )
                },
            ),
            HEAVY,
        )
        coarse = distribution_of(**{"40": "50.00"})
        got = band_in_force(one_ended, PropertyKind.PERMEABILITY, coarse)
        assert got == one_ended.band_for(PropertyKind.PERMEABILITY)
