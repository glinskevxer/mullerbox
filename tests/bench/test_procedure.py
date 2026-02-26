from __future__ import annotations

from typing import Any

import pytest

from mullerbox.bench.procedure import (
    PROCEDURES,
    Preparation,
    Procedure,
    one_specimen_only,
    procedure_for,
    sand_needed,
)
from mullerbox.errors import BadInputError, RuleError
from mullerbox.props.kind import PropertyKind
from mullerbox.units.mass import Grams

GCS = PropertyKind.GREEN_COMPRESSION
PERM = PropertyKind.PERMEABILITY
HARDNESS = PropertyKind.MOLD_HARDNESS
MB = PropertyKind.MB_CLAY


class TestEveryPropertyHasAMethod:
    @pytest.mark.parametrize("kind", list(PropertyKind))
    def test_it_is_published(self, kind: PropertyKind) -> None:
        assert isinstance(procedure_for(kind), Procedure)

    def test_the_table_covers_every_property(self) -> None:
        assert set(PROCEDURES) == set(PropertyKind)

    @pytest.mark.parametrize("kind", list(PropertyKind))
    def test_it_names_a_preparation_and_a_mass(self, kind: PropertyKind) -> None:
        found = procedure_for(kind)
        assert isinstance(found.preparation, Preparation)
        assert not found.sample_mass.is_zero

    def test_it_wants_a_property(self) -> None:
        bad: Any = "gcs"
        with pytest.raises(BadInputError, match="property kind is expected"):
            procedure_for(bad)


class TestTheRequirementsAreAskable:
    def test_they_name_the_preparation_and_the_instrument(self) -> None:
        lines = procedure_for(GCS).requirements()
        assert any("rammed specimen" in x for x in lines)
        assert any("universal strength machine" in x for x in lines)
        assert any("in calibration" in x for x in lines)

    def test_a_destructive_test_says_so(self) -> None:
        assert any("destroyed" in x for x in procedure_for(GCS).requirements())

    def test_a_non_destructive_one_does_not(self) -> None:
        assert not any("destroyed" in x for x in procedure_for(PERM).requirements())

    def test_the_titration_needs_bench_temperature(self) -> None:
        assert procedure_for(MB).bench_temperature
        assert any("bench temperature" in x for x in procedure_for(MB).requirements())

    def test_nothing_else_does(self) -> None:
        needing = [k for k in PropertyKind if procedure_for(k).bench_temperature]
        assert needing == [MB]


class TestSpecimensAreSharedWhereTheyCanBe:
    def test_three_tests_use_a_rammed_specimen_without_destroying_it(self) -> None:
        sharing = [
            k
            for k in PropertyKind
            if procedure_for(k).needs_specimen and not procedure_for(k).destructive
        ]
        assert set(sharing) == {PERM, HARDNESS}

    def test_two_non_destructive_tests_count_the_specimen_once(self) -> None:
        one = sand_needed([PERM])
        both = sand_needed([PERM, HARDNESS])
        assert both == one

    def test_a_destructive_test_adds_its_own_sand(self) -> None:
        assert sand_needed([PERM, GCS]) > sand_needed([PERM])

    def test_loose_tests_simply_add_up(self) -> None:
        assert sand_needed([MB, MB]) == Grams(procedure_for(MB).sample_mass.grams * 2)

    def test_nothing_needs_no_sand(self) -> None:
        assert sand_needed([]) == Grams.zero()


class TestOneSpecimenCannotCarryTwoDestructiveTests:
    def test_two_of_them_is_refused(self) -> None:
        with pytest.raises(RuleError, match="need 2 specimens and not one"):
            one_specimen_only([GCS, PropertyKind.WET_TENSILE])

    def test_the_refusal_names_them(self) -> None:
        with pytest.raises(RuleError, match="green compression strength"):
            one_specimen_only([GCS, PropertyKind.WET_TENSILE])

    def test_one_destructive_test_is_fine(self) -> None:
        one_specimen_only([GCS, PERM, HARDNESS])

    def test_no_specimen_tests_at_all_is_fine(self) -> None:
        one_specimen_only([MB, PropertyKind.LOI])

    def test_three_destructive_tests_says_three(self) -> None:
        with pytest.raises(RuleError, match="need 3 specimens"):
            one_specimen_only([GCS, PropertyKind.WET_TENSILE, PropertyKind.FRIABILITY])


class TestConstruction:
    def test_the_pieces_are_checked(self) -> None:
        bad: Any = "gcs"
        with pytest.raises(BadInputError, match="is for a property"):
            Procedure(
                kind=bad,
                preparation=Preparation.LOOSE_SPLIT,
                sample_mass=Grams(50),
                destructive=False,
            )
        with pytest.raises(BadInputError, match="names a preparation"):
            Procedure(kind=GCS, preparation=bad, sample_mass=Grams(50), destructive=False)
        with pytest.raises(BadInputError, match="sample mass is a mass"):
            Procedure(
                kind=GCS,
                preparation=Preparation.LOOSE_SPLIT,
                sample_mass=bad,
                destructive=False,
            )
        with pytest.raises(BadInputError, match="no sand is not a test"):
            Procedure(
                kind=GCS,
                preparation=Preparation.LOOSE_SPLIT,
                sample_mass=Grams.zero(),
                destructive=False,
            )

    def test_every_preparation_has_a_label(self) -> None:
        assert all(p.label for p in Preparation)

    def test_str_reads_as_a_method_line(self) -> None:
        assert str(procedure_for(MB)).startswith("methylene blue clay:")
