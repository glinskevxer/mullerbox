from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from mullerbox.errors import BadInputError, RuleError
from mullerbox.heat.heat import Casting, Disposition, Heat, Mold
from mullerbox.spec.pattern import PatternClass
from mullerbox.units.bulk import Pounds
from tests.heat.helpers import WHEN, casting, heat, mold


class TestDisposition:
    def test_pending_is_not_decided(self) -> None:
        assert not Disposition.PENDING.is_decided

    def test_the_others_are(self) -> None:
        assert Disposition.SHIPPED.is_decided
        assert Disposition.SCRAPPED.is_decided

    def test_every_disposition_has_a_label(self) -> None:
        assert all(d.label for d in Disposition)


class TestCasting:
    def test_the_pieces_are_checked(self) -> None:
        with pytest.raises(BadInputError, match="needs an identifier"):
            Casting(casting_id=" ", weight=Pounds(1))
        with pytest.raises(BadInputError, match="weight is a bulk mass"):
            Casting(casting_id="C-1", weight=120)  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="no weight is not a casting"):
            Casting(casting_id="C-1", weight=Pounds.zero())
        with pytest.raises(BadInputError, match="has a disposition"):
            Casting(casting_id="C-1", weight=Pounds(1), disposition="shipped")  # type: ignore[arg-type]

    def test_it_defaults_to_pending(self) -> None:
        assert Casting(casting_id="C-1", weight=Pounds(1)).disposition is (Disposition.PENDING)

    def test_scrap(self) -> None:
        assert casting(disposition=Disposition.SCRAPPED).is_scrap
        assert not casting(disposition=Disposition.SHIPPED).is_scrap


class TestMold:
    def test_the_pieces_are_checked(self) -> None:
        with pytest.raises(BadInputError, match="needs an identifier"):
            Mold(mold_id=" ", pattern=PatternClass.LIGHT_JOBBING, sand=Pounds(1))
        with pytest.raises(BadInputError, match="names the pattern class"):
            Mold(mold_id="M-1", pattern="light", sand=Pounds(1))  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="sand in a mold is a bulk mass"):
            Mold(mold_id="M-1", pattern=PatternClass.LIGHT_JOBBING, sand=700)  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="no sand in it is not a mold"):
            Mold(mold_id="M-1", pattern=PatternClass.LIGHT_JOBBING, sand=Pounds.zero())

    def test_two_castings_cannot_share_a_number(self) -> None:
        with pytest.raises(RuleError, match="two castings with one number"):
            mold(castings=(casting("C-1"), casting("C-1")))

    def test_the_metal_is_the_sum_of_what_came_out(self) -> None:
        assert mold(castings=(casting("C-1", "120"), casting("C-2", "80"))).metal == (Pounds(200))

    def test_an_empty_mold_poured_nothing(self) -> None:
        empty = Mold(mold_id="M-9", pattern=PatternClass.LIGHT_JOBBING, sand=Pounds(700))
        assert empty.metal == Pounds.zero()

    def test_scrapped_castings_are_picked_out(self) -> None:
        built = mold(
            castings=(
                casting("C-1", disposition=Disposition.SHIPPED),
                casting("C-2", disposition=Disposition.SCRAPPED),
            )
        )
        assert [c.casting_id for c in built.scrapped] == ["C-2"]

    def test_a_pending_casting_leaves_the_mold_unjudged(self) -> None:
        assert not mold(castings=(casting("C-1", disposition=Disposition.PENDING),)).is_fully_judged
        assert mold(castings=(casting("C-1"),)).is_fully_judged


class TestHeat:
    def test_the_pieces_are_checked(self) -> None:
        with pytest.raises(BadInputError, match="needs a number"):
            Heat(heat_number="  ", poured_on=WHEN)
        with pytest.raises(BadInputError, match="a heat is dated"):
            Heat(heat_number="H-1", poured_on="2025-04-02")  # type: ignore[arg-type]

    def test_two_molds_cannot_share_a_number(self) -> None:
        with pytest.raises(RuleError, match="two molds with one number"):
            heat(mold("M-1"), mold("M-1"))

    def test_the_totals_roll_up(self) -> None:
        built = heat(
            mold("M-1", sand="700", castings=(casting("C-1", "120"),)),
            mold("M-2", sand="800", castings=(casting("C-2", "150"),)),
        )
        assert built.sand == Pounds(1500)
        assert built.metal == Pounds(270)
        assert len(built.castings) == 2


class TestAHeatCanRunSeveralPatterns:
    def test_one_pattern(self) -> None:
        built = heat(mold("M-1"), mold("M-2"))
        assert built.is_single_pattern
        assert built.patterns == frozenset({PatternClass.MEDIUM_JOBBING})

    def test_the_tail_of_a_ladle_on_something_else(self) -> None:
        built = heat(
            mold("M-1", pattern=PatternClass.MEDIUM_JOBBING),
            mold("M-2", pattern=PatternClass.THIN_WALL),
        )
        assert not built.is_single_pattern
        assert len(built.patterns) == 2

    def test_molds_can_be_picked_out_by_class(self) -> None:
        built = heat(
            mold("M-1", pattern=PatternClass.MEDIUM_JOBBING),
            mold("M-2", pattern=PatternClass.THIN_WALL),
        )
        assert [m.mold_id for m in built.molds_of(PatternClass.THIN_WALL)] == ["M-2"]

    def test_picking_wants_a_class(self) -> None:
        with pytest.raises(BadInputError, match="pattern class is expected"):
            heat().molds_of("thin wall")  # type: ignore[arg-type]


class TestScrapIsWeighted:
    def test_one_heavy_scrap_beats_forty_light_shipments(self) -> None:
        heavy = casting("C-0", "800", Disposition.SCRAPPED)
        light = tuple(casting(f"C-{n}", "20", Disposition.SHIPPED) for n in range(1, 41))
        built = heat(mold("M-1", castings=(heavy, *light)))
        assert built.scrap_rate == Decimal("0.5000")

    def test_a_clean_heat_scraps_nothing(self) -> None:
        assert heat().scrap_rate == Decimal("0.0000")

    def test_everything_scrapped(self) -> None:
        built = heat(mold("M-1", castings=(casting("C-1", "120", Disposition.SCRAPPED),)))
        assert built.scrap_rate == Decimal("1.0000")

    def test_a_heat_that_poured_nothing_has_no_rate(self) -> None:
        empty = Heat(
            heat_number="H-2",
            poured_on=date(2025, 4, 3),
            molds=(
                Mold(
                    mold_id="M-1",
                    pattern=PatternClass.LIGHT_JOBBING,
                    sand=Pounds(700),
                ),
            ),
        )
        with pytest.raises(RuleError, match="poured no metal"):
            assert empty.scrap_rate

    def test_pending_castings_are_not_counted_as_good(self) -> None:
        built = heat(mold("M-1", castings=(casting("C-1", "120", Disposition.PENDING),)))
        assert not built.is_fully_judged
        assert built.scrap_rate == Decimal("0.0000")


def test_str_names_the_heat_and_the_mold_count() -> None:
    assert str(heat(mold("M-1"), mold("M-2"))) == "heat H-1001 on 2025-04-02, 2 molds"
