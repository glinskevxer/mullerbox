from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

import pytest

from mullerbox.defect.kind import DefectKind
from mullerbox.defect.pareto import VITAL_SHARE, pareto_of
from mullerbox.defect.scrap import ScrapReport, report_on
from mullerbox.errors import BadInputError
from mullerbox.heat.heat import Casting, Disposition
from mullerbox.spec.pattern import PatternClass
from mullerbox.units.scales import Permeability
from tests.defect.helpers import readings, spec_for
from tests.heat.helpers import casting, heat, mold

HEAVY = PatternClass.HEAVY_JOBBING
SPECS = {cls: spec_for(cls) for cls in PatternClass}
BAD_SAND = readings(PERMEABILITY=Permeability(40))


def scrapped(name: str, weight: str) -> Casting:
    return casting(name, weight, Disposition.SCRAPPED)


def report(
    castings: list[Casting],
    defects: Mapping[str, tuple[DefectKind, ...]],
    number: str = "H-1",
) -> ScrapReport:
    built = heat(mold("M-1", pattern=HEAVY, castings=tuple(castings)), number=number)
    return report_on(built, defects, SPECS, BAD_SAND)


class TestWeightBeatsCount:
    def test_the_heavy_defect_ranks_first(self) -> None:
        castings = [scrapped("C-1", "800")] + [scrapped(f"C-{n}", "20") for n in range(2, 32)]
        defects = {"C-1": (DefectKind.PENETRATION,)}
        defects.update({f"C-{n}": (DefectKind.PINHOLE,) for n in range(2, 32)})
        ranked = pareto_of([report(castings, defects)])
        assert ranked.bands[0].defect is DefectKind.PENETRATION

    def test_the_count_ranking_puts_the_other_first(self) -> None:
        castings = [scrapped("C-1", "800")] + [scrapped(f"C-{n}", "20") for n in range(2, 32)]
        defects = {"C-1": (DefectKind.PENETRATION,)}
        defects.update({f"C-{n}": (DefectKind.PINHOLE,) for n in range(2, 32)})
        ranked = pareto_of([report(castings, defects)])
        assert ranked.by_count[0].defect is DefectKind.PINHOLE

    def test_the_disagreement_is_reported(self) -> None:
        castings = [scrapped("C-1", "800")] + [scrapped(f"C-{n}", "20") for n in range(2, 32)]
        defects = {"C-1": (DefectKind.PENETRATION,)}
        defects.update({f"C-{n}": (DefectKind.PINHOLE,) for n in range(2, 32)})
        assert pareto_of([report(castings, defects)]).ranking_disagrees

    def test_agreement_is_not_reported_as_disagreement(self) -> None:
        castings = [scrapped("C-1", "100"), scrapped("C-2", "100")]
        defects = {"C-1": (DefectKind.BLOW,), "C-2": (DefectKind.BLOW,)}
        assert not pareto_of([report(castings, defects)]).ranking_disagrees

    def test_the_counts_are_carried(self) -> None:
        castings = [scrapped("C-1", "100"), scrapped("C-2", "100")]
        defects = {"C-1": (DefectKind.BLOW,), "C-2": (DefectKind.BLOW,)}
        band = pareto_of([report(castings, defects)]).band_for(DefectKind.BLOW)
        assert band is not None
        assert band.count == 2


class TestTheVitalFew:
    def test_the_cumulative_share_runs_to_one(self) -> None:
        castings = [scrapped("C-1", "100"), scrapped("C-2", "50")]
        defects = {"C-1": (DefectKind.BLOW,), "C-2": (DefectKind.SCAB,)}
        ranked = pareto_of([report(castings, defects)])
        assert ranked.bands[-1].cumulative == Decimal("1.0000")

    def test_the_first_band_is_always_vital(self) -> None:
        castings = [scrapped("C-1", "100"), scrapped("C-2", "50")]
        defects = {"C-1": (DefectKind.BLOW,), "C-2": (DefectKind.SCAB,)}
        assert pareto_of([report(castings, defects)]).bands[0].is_vital

    def test_a_long_tail_falls_outside(self) -> None:
        castings = [scrapped("C-1", "1000")] + [scrapped(f"C-{n}", "10") for n in range(2, 12)]
        defects: dict[str, tuple[DefectKind, ...]] = {"C-1": (DefectKind.BLOW,)}
        for n in range(2, 12):
            defects[f"C-{n}"] = (DefectKind.SCAB,)
        ranked = pareto_of([report(castings, defects)])
        assert len(ranked.vital_few) == 1
        assert ranked.vital_few[0].defect is DefectKind.BLOW

    def test_str_names_the_vital_few(self) -> None:
        castings = [scrapped("C-1", "100")]
        defects = {"C-1": (DefectKind.BLOW,)}
        text = str(pareto_of([report(castings, defects)]))
        assert "blow" in text
        assert f"{VITAL_SHARE:.0%}" in text


class TestSeveralDefectsOnOneCasting:
    def test_each_gets_the_whole_weight(self) -> None:
        castings = [scrapped("C-1", "100")]
        defects = {"C-1": (DefectKind.BLOW, DefectKind.SCAB)}
        ranked = pareto_of([report(castings, defects)])
        assert ranked.total.value == Decimal("200.00")
        for band in ranked.bands:
            assert band.weight.value == Decimal("100.00")

    def test_the_total_is_contributions_not_scrap(self) -> None:
        castings = [scrapped("C-1", "100")]
        defects = {"C-1": (DefectKind.BLOW, DefectKind.SCAB)}
        built = report(castings, defects)
        ranked = pareto_of([built])
        assert ranked.total > built.scrapped


class TestFiltering:
    def test_sand_only_drops_the_melt_charges(self) -> None:
        castings = [scrapped("C-1", "100"), scrapped("C-2", "100")]
        defects = {"C-1": (DefectKind.BLOW,), "C-2": (DefectKind.SHRINKAGE,)}
        everything = pareto_of([report(castings, defects)])
        sand = pareto_of([report(castings, defects)], sand_only=True)
        assert len(everything.bands) == 2
        assert len(sand.bands) == 1
        assert sand.bands[0].defect is DefectKind.BLOW

    def test_several_heats_combine(self) -> None:
        first = report([scrapped("C-1", "100")], {"C-1": (DefectKind.BLOW,)}, "H-1")
        second = report([scrapped("C-2", "100")], {"C-2": (DefectKind.BLOW,)}, "H-2")
        ranked = pareto_of([first, second])
        band = ranked.band_for(DefectKind.BLOW)
        assert band is not None
        assert band.count == 2


class TestEmptyAndGuards:
    def test_no_scrap_ranks_nothing(self) -> None:
        ranked = pareto_of([])
        assert ranked.bands == ()
        assert ranked.total.is_zero
        assert str(ranked) == "no scrap to rank"
        assert not ranked.ranking_disagrees

    def test_a_defect_never_seen_has_no_band(self) -> None:
        castings = [scrapped("C-1", "100")]
        ranked = pareto_of([report(castings, {"C-1": (DefectKind.BLOW,)})])
        assert ranked.band_for(DefectKind.VEINING) is None

    def test_it_wants_scrap_reports(self) -> None:
        bad: Any = ["H-1"]
        with pytest.raises(BadInputError, match="built from scrap reports"):
            pareto_of(bad)


class TestTheBandThatCrossesTheLineIsInside:
    def test_one_defect_making_all_the_scrap_is_its_own_vital_few(self) -> None:
        castings = [scrapped("C-1", "100")]
        ranked = pareto_of([report(castings, {"C-1": (DefectKind.BLOW,)})])
        assert ranked.bands[0].cumulative == Decimal("1.0000")
        assert ranked.bands[0].is_vital
        assert len(ranked.vital_few) == 1

    def test_a_first_band_over_the_line_alone_is_still_inside(self) -> None:
        castings = [scrapped("C-1", "900"), scrapped("C-2", "100")]
        defects = {"C-1": (DefectKind.BLOW,), "C-2": (DefectKind.SCAB,)}
        ranked = pareto_of([report(castings, defects)])
        assert ranked.bands[0].share > VITAL_SHARE
        assert ranked.bands[0].is_vital
        assert not ranked.bands[1].is_vital

    def test_two_bands_are_needed_to_cross(self) -> None:
        castings = [scrapped("C-1", "500"), scrapped("C-2", "400"), scrapped("C-3", "100")]
        defects = {
            "C-1": (DefectKind.BLOW,),
            "C-2": (DefectKind.SCAB,),
            "C-3": (DefectKind.VEINING,),
        }
        ranked = pareto_of([report(castings, defects)])
        assert [b.defect for b in ranked.vital_few] == [
            DefectKind.BLOW,
            DefectKind.SCAB,
        ]
