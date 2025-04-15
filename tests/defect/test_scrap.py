from __future__ import annotations

from decimal import Decimal

import pytest

from mullerbox.defect.kind import Culprit, DefectKind
from mullerbox.defect.scrap import report_on
from mullerbox.errors import BadInputError, RuleError
from mullerbox.heat.heat import Disposition, Mold
from mullerbox.props.kind import PropertyKind
from mullerbox.spec.pattern import PatternClass
from mullerbox.units.bulk import Pounds
from mullerbox.units.percent import Percent
from mullerbox.units.scales import Permeability
from tests.defect.helpers import readings, spec_for
from tests.heat.helpers import casting, heat, mold

HEAVY = PatternClass.HEAVY_JOBBING
THIN = PatternClass.THIN_WALL
SPECS = {cls: spec_for(cls) for cls in PatternClass}
BAD_SAND = readings(PERMEABILITY=Permeability(40))


def scrapped(name: str, weight: str):  # type: ignore[no-untyped-def]
    return casting(name, weight, Disposition.SCRAPPED)


class TestChargingByWeight:
    def test_a_heavy_scrap_dominates_a_light_one(self) -> None:
        built = heat(
            mold(
                "M-1",
                pattern=HEAVY,
                castings=(scrapped("C-1", "800"), casting("C-2", "20")),
            )
        )
        got = report_on(built, {"C-1": (DefectKind.BLOW,)}, SPECS, BAD_SAND)
        assert got.scrapped == got.weight_charged_to(Culprit.SAND)
        assert got.sand_share == Decimal("0.9756")

    def test_a_clean_heat_charges_nothing(self) -> None:
        got = report_on(heat(mold("M-1", pattern=HEAVY)), {}, SPECS, BAD_SAND)
        assert got.charges == ()
        assert got.sand_share == Decimal("0.0000")

    def test_a_heat_that_poured_nothing_has_no_share(self) -> None:
        no_castings = Mold(mold_id="M-1", pattern=HEAVY, sand=Pounds(700))
        empty = heat(no_castings)
        got = report_on(empty, {}, SPECS, BAD_SAND)
        with pytest.raises(RuleError, match="poured no metal"):
            assert got.sand_share


class TestACastingIsChargedOnce:
    def test_two_defects_on_one_casting_do_not_double_count(self) -> None:
        built = heat(mold("M-1", pattern=HEAVY, castings=(scrapped("C-1", "100"),)))
        got = report_on(
            built,
            {"C-1": (DefectKind.BLOW, DefectKind.PINHOLE)},
            SPECS,
            BAD_SAND,
        )
        assert len(got.charges) == 1
        assert got.scrapped == got.weight_charged_to(Culprit.SAND)

    def test_sand_wins_when_any_defect_is_a_sand_call(self) -> None:
        built = heat(mold("M-1", pattern=HEAVY, castings=(scrapped("C-1", "100"),)))
        got = report_on(
            built,
            {"C-1": (DefectKind.SHRINKAGE, DefectKind.BLOW)},
            SPECS,
            BAD_SAND,
        )
        assert got.charges[0].culprit is Culprit.SAND

    def test_a_casting_with_no_sand_call_goes_elsewhere(self) -> None:
        built = heat(mold("M-1", pattern=HEAVY, castings=(scrapped("C-1", "100"),)))
        got = report_on(built, {"C-1": (DefectKind.SHRINKAGE,)}, SPECS, BAD_SAND)
        assert got.charges[0].culprit is Culprit.MELT

    def test_a_casting_with_no_defect_written_on_it_goes_to_the_pattern(self) -> None:
        built = heat(mold("M-1", pattern=HEAVY, castings=(scrapped("C-1", "100"),)))
        got = report_on(built, {}, SPECS, BAD_SAND)
        assert got.charges[0].culprit is Culprit.PATTERN
        assert got.charges[0].attributions == ()


class TestEachMoldIsJudgedAgainstItsOwnClass:
    def test_one_heat_two_classes_two_verdicts(self) -> None:
        wet = readings(COMPACTABILITY=Percent("44.5"))
        built = heat(
            mold("M-1", pattern=HEAVY, castings=(scrapped("C-1", "100"),)),
            mold("M-2", pattern=PatternClass.CORED_LIGHT, castings=(scrapped("C-2", "100"),)),
        )
        got = report_on(
            built,
            {"C-1": (DefectKind.SCAB,), "C-2": (DefectKind.SCAB,)},
            SPECS,
            wet,
        )
        by_id = {c.casting.casting_id: c for c in got.charges}
        assert by_id["C-1"].culprit is Culprit.PATTERN
        assert by_id["C-2"].culprit is Culprit.SAND

    def test_a_mold_with_no_resolved_spec_is_refused(self) -> None:
        built = heat(mold("M-1", pattern=THIN, castings=(scrapped("C-1", "100"),)))
        with pytest.raises(RuleError, match="and no spec was resolved for it"):
            report_on(built, {}, {HEAVY: spec_for(HEAVY)}, BAD_SAND)


class TestPending:
    def test_it_is_counted_separately(self) -> None:
        built = heat(
            mold(
                "M-1",
                pattern=HEAVY,
                castings=(
                    casting("C-1", "100", Disposition.PENDING),
                    scrapped("C-2", "50"),
                ),
            )
        )
        got = report_on(built, {"C-2": (DefectKind.BLOW,)}, SPECS, BAD_SAND)
        assert got.pending == Pounds(100)
        assert got.scrapped.value == Decimal("50.00")

    def test_it_is_not_charged_to_anyone(self) -> None:
        built = heat(
            mold(
                "M-1",
                pattern=HEAVY,
                castings=(casting("C-1", "100", Disposition.PENDING),),
            )
        )
        got = report_on(built, {}, SPECS, BAD_SAND)
        assert got.charges == ()
        for culprit in Culprit:
            assert got.weight_charged_to(culprit).is_zero


class TestPropertiesImplicated:
    def test_the_most_cited_property_comes_first(self) -> None:
        sand = readings(PERMEABILITY=Permeability(40), MOISTURE=Percent("4.5"))
        built = heat(
            mold(
                "M-1",
                pattern=HEAVY,
                castings=(scrapped("C-1", "100"), scrapped("C-2", "100")),
            )
        )
        got = report_on(
            built,
            {"C-1": (DefectKind.BLOW,), "C-2": (DefectKind.SCAB,)},
            SPECS,
            sand,
        )
        assert got.properties_implicated[0] is PropertyKind.MOISTURE

    def test_nothing_implicated_on_a_clean_heat(self) -> None:
        got = report_on(heat(mold("M-1", pattern=HEAVY)), {}, SPECS, readings())
        assert got.properties_implicated == ()


class TestGuards:
    def test_it_wants_a_heat(self) -> None:
        with pytest.raises(BadInputError, match="built from a heat"):
            report_on("H-1", {}, SPECS, BAD_SAND)  # type: ignore[arg-type]

    def test_charging_wants_a_culprit(self) -> None:
        got = report_on(heat(mold("M-1", pattern=HEAVY)), {}, SPECS, BAD_SAND)
        with pytest.raises(BadInputError, match="culprit is expected"):
            got.weight_charged_to("sand")  # type: ignore[arg-type]

    def test_str_names_the_heat_and_the_sand_share(self) -> None:
        built = heat(mold("M-1", pattern=HEAVY, castings=(scrapped("C-1", "100"),)))
        got = report_on(built, {"C-1": (DefectKind.BLOW,)}, SPECS, BAD_SAND)
        assert "to sand" in str(got)
