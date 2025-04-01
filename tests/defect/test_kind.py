from __future__ import annotations

import pytest

from mullerbox.defect.kind import Culprit, DefectKind, Family, parse_defect
from mullerbox.errors import BadInputError
from mullerbox.props.kind import PropertyKind
from mullerbox.spec.pattern import PatternClass

MELT_DEFECTS: list[DefectKind] = [
    DefectKind.COLD_SHUT,
    DefectKind.MISRUN,
    DefectKind.SHRINKAGE,
    DefectKind.SLAG,
]


class TestEveryDefectIsWiredUp:
    @pytest.mark.parametrize("defect", list(DefectKind))
    def test_it_has_a_family_a_label_and_a_fallback(self, defect: DefectKind) -> None:
        assert isinstance(defect.family, Family)
        assert defect.label.strip()
        assert isinstance(defect.fallback, Culprit)

    @pytest.mark.parametrize("defect", list(DefectKind))
    def test_the_fallback_is_never_sand(self, defect: DefectKind) -> None:
        """The fallback is where it goes when the sand is cleared."""
        assert defect.fallback is not Culprit.SAND


class TestTheTwoQuestionsAreIndependent:
    def test_a_defect_can_be_sand_caused_and_not_attributable_here(self) -> None:
        # Veining is an expansion defect with real sand candidates, and on
        # uncored work there is no core to vein.
        assert DefectKind.VEINING.can_ever_be_sand
        assert not DefectKind.VEINING.attributable_on(PatternClass.LIGHT_JOBBING)
        assert DefectKind.VEINING.attributable_on(PatternClass.CORED_LIGHT)

    def test_penetration_is_a_heavy_section_call_only(self) -> None:
        assert DefectKind.PENETRATION.attributable_on(PatternClass.HEAVY_JOBBING)
        assert DefectKind.PENETRATION.attributable_on(PatternClass.CORED_HEAVY)
        assert not DefectKind.PENETRATION.attributable_on(PatternClass.THIN_WALL)
        assert not DefectKind.PENETRATION.attributable_on(PatternClass.LIGHT_JOBBING)

    def test_expansion_defects_skip_thin_wall(self) -> None:
        for defect in (DefectKind.SCAB, DefectKind.RAT_TAIL, DefectKind.BUCKLE):
            assert not defect.attributable_on(PatternClass.THIN_WALL)
            assert defect.attributable_on(PatternClass.HEAVY_JOBBING)

    def test_gas_defects_are_everybody_s(self) -> None:
        for defect in (DefectKind.BLOW, DefectKind.PINHOLE):
            for cls in PatternClass:
                assert defect.attributable_on(cls)

    def test_attribution_wants_a_class(self) -> None:
        with pytest.raises(BadInputError, match="pattern class is expected"):
            DefectKind.BLOW.attributable_on("thin wall")


class TestMeltDefectsAreNeverSand:
    @pytest.mark.parametrize("defect", MELT_DEFECTS)
    def test_no_sand_property_is_listed(self, defect: DefectKind) -> None:
        assert defect.candidate_properties == frozenset()
        assert not defect.can_ever_be_sand

    @pytest.mark.parametrize("defect", MELT_DEFECTS)
    def test_no_pattern_class_allows_the_charge(self, defect: DefectKind) -> None:
        assert defect.classes_that_allow_it() == frozenset()
        for cls in PatternClass:
            assert not defect.attributable_on(cls)

    @pytest.mark.parametrize("defect", MELT_DEFECTS)
    def test_they_are_in_the_melt_family(self, defect: DefectKind) -> None:
        assert defect.family is Family.MELT


class TestTheCandidatesAreMechanistic:
    def test_gas_defects_reach_permeability_and_not_strength(self) -> None:
        candidates = DefectKind.BLOW.candidate_properties
        assert PropertyKind.PERMEABILITY in candidates
        assert PropertyKind.GREEN_COMPRESSION not in candidates

    def test_breakage_defects_reach_strength_and_not_permeability(self) -> None:
        candidates = DefectKind.CUT_AND_WASH.candidate_properties
        assert PropertyKind.GREEN_COMPRESSION in candidates
        assert PropertyKind.PERMEABILITY not in candidates

    def test_expansion_defects_reach_the_carbon(self) -> None:
        assert PropertyKind.LOI in DefectKind.SCAB.candidate_properties

    def test_penetration_reaches_the_squeeze(self) -> None:
        assert PropertyKind.MOLD_HARDNESS in DefectKind.PENETRATION.candidate_properties

    def test_every_sand_defect_lists_at_least_two_candidates(self) -> None:
        for defect in DefectKind:
            if defect.can_ever_be_sand:
                assert len(defect.candidate_properties) >= 2


class TestFamilies:
    def test_every_family_is_used(self) -> None:
        used = {d.family for d in DefectKind}
        assert used == set(Family)

    def test_every_family_has_a_label(self) -> None:
        assert all(f.label for f in Family)

    def test_every_culprit_has_a_label(self) -> None:
        assert all(c.label for c in Culprit)


class TestParsing:
    @pytest.mark.parametrize(
        ("text", "want"),
        [
            ("scab", DefectKind.SCAB),
            ("RAT_TAIL", DefectKind.RAT_TAIL),
            ("cut-and-wash", DefectKind.CUT_AND_WASH),
            ("  sand   inclusion ", DefectKind.SAND_INCLUSION),
        ],
    )
    def test_the_separators_do_not_matter(self, text: str, want: DefectKind) -> None:
        assert parse_defect(text) is want

    def test_anything_else_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="not a defect on the shop's list"):
            parse_defect("ugly")

    def test_every_label_parses(self) -> None:
        for defect in DefectKind:
            assert parse_defect(defect.label) is defect
