from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from mullerbox.errors import BadInputError
from mullerbox.props.kind import PropertyKind
from mullerbox.spec.band import Band
from mullerbox.spec.revision import compare
from mullerbox.spec.sheet import SpecSheet
from mullerbox.units.percent import Percent
from tests.spec.helpers import PUBLISHED

COMP = PropertyKind.COMPACTABILITY
LOI = PropertyKind.LOI


def sheet_with(name: str, **bands: Band) -> SpecSheet:
    built = dict(PUBLISHED)
    for key, band in bands.items():
        built[PropertyKind[key]] = band
    return SpecSheet(name=name, bands=built)


def base() -> SpecSheet:
    return SpecSheet(name="january", bands=dict(PUBLISHED))


class TestNoChange:
    def test_the_same_bands_change_nothing(self) -> None:
        revision = compare(base(), SpecSheet(name="june", bands=dict(PUBLISHED)))
        assert revision.is_empty
        assert "changes nothing" in str(revision)

    def test_it_names_both_sheets(self) -> None:
        revision = compare(base(), SpecSheet(name="june", bands=dict(PUBLISHED)))
        assert revision.was == "january"
        assert revision.now == "june"


class TestAMovedAim:
    def test_it_is_reported_with_the_direction(self) -> None:
        moved = sheet_with("june", COMPACTABILITY=Band.between(COMP, Percent(40), Percent(46)))
        change = compare(base(), moved).change_for(COMP)
        assert change is not None
        assert change.aim_moved == Decimal(2)
        assert "aim moved +2" in str(change)

    def test_it_is_material(self) -> None:
        moved = sheet_with("june", COMPACTABILITY=Band.between(COMP, Percent(40), Percent(46)))
        revision = compare(base(), moved)
        assert revision.material
        assert "MATERIAL" in str(revision)

    def test_a_downward_move_carries_its_sign(self) -> None:
        moved = sheet_with("june", COMPACTABILITY=Band.between(COMP, Percent(36), Percent(42)))
        change = compare(base(), moved).change_for(COMP)
        assert change is not None
        assert change.aim_moved == Decimal(-2)


class TestAWidthChange:
    def test_a_narrowing_is_material(self) -> None:
        narrowed = sheet_with("june", COMPACTABILITY=Band.between(COMP, Percent(39), Percent(43)))
        change = compare(base(), narrowed).change_for(COMP)
        assert change is not None
        assert change.width_changed == Decimal(-2)
        assert change.is_material

    def test_a_widening_is_not(self) -> None:
        widened = sheet_with("june", COMPACTABILITY=Band.between(COMP, Percent(37), Percent(45)))
        change = compare(base(), widened).change_for(COMP)
        assert change is not None
        assert change.width_changed == Decimal(2)
        assert not change.is_material

    def test_the_aim_did_not_move_in_either(self) -> None:
        widened = sheet_with("june", COMPACTABILITY=Band.between(COMP, Percent(37), Percent(45)))
        change = compare(base(), widened).change_for(COMP)
        assert change is not None
        assert change.aim_moved == Decimal(0)


class TestAddedAndDropped:
    def test_an_added_band_is_material(self) -> None:
        thin = SpecSheet(name="january", bands={COMP: PUBLISHED[COMP]})
        revision = compare(thin, base())
        added = revision.added
        assert len(added) == len(PUBLISHED) - 1
        assert all(change.is_material for change in added)

    def test_a_dropped_band_is_reported(self) -> None:
        thin = SpecSheet(name="june", bands={COMP: PUBLISHED[COMP]})
        revision = compare(base(), thin)
        assert len(revision.dropped) == len(PUBLISHED) - 1
        assert "no longer controlled" in str(revision)

    def test_a_dropped_band_is_not_material(self) -> None:
        """Nothing goes out of band because a band was removed."""
        thin = SpecSheet(name="june", bands={COMP: PUBLISHED[COMP]})
        revision = compare(base(), thin)
        assert revision.material == ()

    def test_an_added_band_names_the_new_limits(self) -> None:
        thin = SpecSheet(name="january", bands={COMP: PUBLISHED[COMP]})
        revision = compare(thin, base())
        assert "is now controlled" in str(revision)


class TestOneEndedBands:
    def test_a_moved_ceiling_has_no_aim_or_width(self) -> None:
        moved = sheet_with("june", LOI=Band.at_most(LOI, Percent("3.0")))
        change = compare(base(), moved).change_for(LOI)
        assert change is not None
        assert change.aim_moved is None
        assert change.width_changed is None

    def test_it_is_still_reported(self) -> None:
        moved = sheet_with("june", LOI=Band.at_most(LOI, Percent("3.0")))
        change = compare(base(), moved).change_for(LOI)
        assert change is not None
        assert "limits changed" in str(change)

    def test_it_is_not_flagged_material_without_a_measurable_move(self) -> None:
        moved = sheet_with("june", LOI=Band.at_most(LOI, Percent("3.0")))
        assert compare(base(), moved).material == ()


class TestGuards:
    def test_it_wants_two_sheets(self) -> None:
        bad: Any = "january"
        with pytest.raises(BadInputError, match="two spec sheets are expected"):
            compare(bad, base())
        with pytest.raises(BadInputError, match="two spec sheets are expected"):
            compare(base(), bad)

    def test_a_property_that_did_not_change_has_no_entry(self) -> None:
        moved = sheet_with("june", COMPACTABILITY=Band.between(COMP, Percent(40), Percent(46)))
        assert compare(base(), moved).change_for(LOI) is None

    def test_material_changes_render_first(self) -> None:
        mixed = sheet_with(
            "june",
            COMPACTABILITY=Band.between(COMP, Percent(40), Percent(46)),
            MOISTURE=Band.between(PropertyKind.MOISTURE, Percent("2.6"), Percent("3.8")),
        )
        lines = compare(base(), mixed).render()
        material_at = next(i for i, x in enumerate(lines) if "MATERIAL" in x)
        other_at = next(i for i, x in enumerate(lines) if "moisture" in x)
        assert material_at < other_at
