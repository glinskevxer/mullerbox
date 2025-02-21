from __future__ import annotations

import pytest

from mullerbox.errors import BadInputError, NotFoundError
from mullerbox.props.kind import PropertyKind
from mullerbox.spec.band import Band, Verdict
from mullerbox.spec.pattern import PatternClass
from mullerbox.spec.sheet import SpecSheet, resolve
from mullerbox.units.percent import Percent
from mullerbox.units.pressure import Psi
from tests.spec.helpers import PUBLISHED, sheet

COMP = PropertyKind.COMPACTABILITY
LOI = PropertyKind.LOI


class TestSheetConstruction:
    def test_a_sheet_needs_a_name(self) -> None:
        with pytest.raises(BadInputError, match="needs a name"):
            SpecSheet(name=" ", bands=dict(PUBLISHED))

    def test_an_empty_sheet_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="no bands is not a spec sheet"):
            SpecSheet(name="empty", bands={})

    def test_it_is_keyed_by_property(self) -> None:
        with pytest.raises(BadInputError, match="keyed by property"):
            SpecSheet(name="s", bands={"comp": PUBLISHED[COMP]})  # type: ignore[dict-item]

    def test_it_holds_bands(self) -> None:
        with pytest.raises(BadInputError, match="holds bands"):
            SpecSheet(name="s", bands={COMP: Percent(40)})  # type: ignore[dict-item]

    def test_the_key_and_the_band_have_to_agree(self) -> None:
        crossed = {COMP: Band.between(PropertyKind.GREEN_COMPRESSION, Psi(20), Psi(26))}
        with pytest.raises(BadInputError, match="entry holds a green compression"):
            SpecSheet(name="s", bands=crossed)


class TestSheetLookup:
    def test_a_published_band_comes_back(self) -> None:
        assert sheet().band_for(COMP) == PUBLISHED[COMP]

    def test_an_unpublished_band_is_not_found(self) -> None:
        thin = SpecSheet(name="thin", bands={COMP: PUBLISHED[COMP]})
        with pytest.raises(NotFoundError, match="published band"):
            thin.band_for(LOI)

    def test_lookup_wants_a_property(self) -> None:
        with pytest.raises(BadInputError, match="property kind is expected"):
            sheet().band_for("comp")  # type: ignore[arg-type]

    def test_it_reports_what_a_class_needs_and_it_lacks(self) -> None:
        thin = SpecSheet(name="thin", bands={COMP: PUBLISHED[COMP]})
        missing = thin.missing_for(PatternClass.LIGHT_JOBBING)
        assert PropertyKind.PERMEABILITY in missing
        assert COMP not in missing

    def test_a_full_sheet_lacks_nothing(self) -> None:
        for cls in PatternClass:
            assert sheet().missing_for(cls) == frozenset()

    def test_missing_wants_a_class(self) -> None:
        with pytest.raises(BadInputError, match="pattern class is expected"):
            sheet().missing_for("light")  # type: ignore[arg-type]


class TestResolutionNarrowsToWhatTheClassControls:
    def test_it_drops_what_the_class_does_not_control(self) -> None:
        light = resolve(sheet(), PatternClass.LIGHT_JOBBING)
        assert not light.judges(LOI)
        assert light.judges(COMP)

    def test_a_heavier_class_keeps_more(self) -> None:
        light = resolve(sheet(), PatternClass.LIGHT_JOBBING)
        heavy = resolve(sheet(), PatternClass.HEAVY_JOBBING)
        assert light.covers < heavy.covers

    def test_it_never_adds_a_band_the_sheet_did_not_publish(self) -> None:
        thin = SpecSheet(name="thin", bands={COMP: PUBLISHED[COMP]})
        resolved = resolve(thin, PatternClass.LIGHT_JOBBING)
        assert resolved.covers == frozenset({COMP})
        assert not resolved.judges(PropertyKind.PERMEABILITY)

    def test_asking_for_a_dropped_band_names_the_class(self) -> None:
        light = resolve(sheet(), PatternClass.LIGHT_JOBBING)
        with pytest.raises(NotFoundError, match="band in force for light jobbing"):
            light.band_for(LOI)


class TestTheSameReadingIsJudgedDifferentlyByClass:
    def test_a_compactability_in_band_for_heavy_work_is_out_for_thin_wall(self) -> None:
        heavy = resolve(sheet(), PatternClass.HEAVY_JOBBING)
        thin = resolve(sheet(), PatternClass.THIN_WALL)
        reading = Percent("44.5")
        assert heavy.holds(COMP, reading)
        assert not thin.holds(COMP, reading)
        assert thin.verdict(COMP, reading) is Verdict.ABOVE

    def test_the_aim_does_not_move_between_classes(self) -> None:
        aims = {cls: resolve(sheet(), cls).band_for(COMP).midpoint for cls in PatternClass}
        assert len(set(aims.values())) == 1

    def test_the_width_does_move(self) -> None:
        widths = {cls: resolve(sheet(), cls).band_for(COMP).width for cls in PatternClass}
        assert len(set(widths.values())) > 1

    def test_the_tolerance_factor_is_what_moved_it(self) -> None:
        published = PUBLISHED[COMP]
        for cls in PatternClass:
            band = resolve(sheet(), cls).band_for(COMP)
            assert band.width == published.width * cls.tolerance_factor


class TestOneEndedBandsPassThrough:
    def test_a_ceiling_is_not_rescaled(self) -> None:
        heavy = resolve(sheet(), PatternClass.HEAVY_JOBBING)
        assert heavy.band_for(LOI) == PUBLISHED[LOI]

    def test_a_floor_is_not_rescaled(self) -> None:
        cored = resolve(sheet(), PatternClass.CORED_LIGHT)
        assert cored.band_for(PropertyKind.WET_TENSILE) == PUBLISHED[PropertyKind.WET_TENSILE]


class TestResolutionGuards:
    def test_it_wants_a_sheet_and_a_class(self) -> None:
        with pytest.raises(BadInputError, match="starts from a spec sheet"):
            resolve(PUBLISHED, PatternClass.LIGHT_JOBBING)  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="against a pattern class"):
            resolve(sheet(), "light")  # type: ignore[arg-type]

    def test_judges_wants_a_property(self) -> None:
        light = resolve(sheet(), PatternClass.LIGHT_JOBBING)
        with pytest.raises(BadInputError, match="property kind is expected"):
            light.judges("comp")

    def test_the_resolution_remembers_where_it_came_from(self) -> None:
        light = resolve(sheet(), PatternClass.LIGHT_JOBBING)
        assert light.sheet_name == "system sand 2025"
        assert light.pattern is PatternClass.LIGHT_JOBBING
