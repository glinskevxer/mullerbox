from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from mullerbox.errors import BadInputError, RuleError
from mullerbox.heat.heat import Disposition, Heat
from mullerbox.heat.yields import Yields, yields_of
from mullerbox.units.bulk import Pounds
from tests.heat.helpers import casting, heat, mold

SAND = Pounds(100000)


def built(shipped: str = "800", scrapped: str = "200") -> Heat:
    castings = [casting("C-1", shipped, Disposition.SHIPPED)]
    if Pounds(scrapped).value > 0:
        castings.append(casting("C-2", scrapped, Disposition.SCRAPPED))
    return heat(mold("M-1", castings=tuple(castings)))


class TestTheThreeAreNamedSeparately:
    def test_casting_yield_is_castings_over_poured(self) -> None:
        found = yields_of(built(), SAND)
        assert found.casting_yield == Decimal("1.0000")

    def test_good_casting_yield_is_shipped_over_poured(self) -> None:
        found = yields_of(built(), SAND)
        assert found.good_casting_yield == Decimal("0.8000")

    def test_they_differ_by_the_scrap(self) -> None:
        found = yields_of(built(), SAND)
        assert found.scrap_share == Decimal("0.2000")

    def test_the_sand_ratio_is_a_different_thing_entirely(self) -> None:
        found = yields_of(built(), SAND)
        assert found.sand_ratio == Decimal("125.00")

    def test_a_clean_heat_has_the_two_yields_equal(self) -> None:
        found = yields_of(built(scrapped="0"), SAND)
        assert found.casting_yield == found.good_casting_yield
        assert found.scrap_share == Decimal("0.0000")


class TestTheSummarySaysWhichIsWhich:
    def test_every_ratio_is_named(self) -> None:
        lines = yields_of(built(), SAND).summary()
        assert any("what melting is judged on" in x for x in lines)
        assert any("what the plant is paid on" in x for x in lines)
        assert any("what the sand is judged on" in x for x in lines)

    def test_the_gap_is_spelled_out(self) -> None:
        lines = yields_of(built(), SAND).summary()
        assert any("the gap between the first two" in x for x in lines)

    def test_str_carries_all_three(self) -> None:
        text = str(yields_of(built(), SAND))
        assert "casting" in text
        assert "good" in text
        assert "sand" in text

    def test_there_is_no_bare_yield(self) -> None:
        found = yields_of(built(), SAND)
        assert not hasattr(found, "yield")
        assert not hasattr(found, "ratio")


class TestGuards:
    def test_more_castings_than_metal_is_refused(self) -> None:
        with pytest.raises(RuleError, match="cannot come out of"):
            Yields(
                poured=Pounds(100),
                casting_weight=Pounds(200),
                shipped=Pounds(100),
                sand_handled=SAND,
            )

    def test_more_shipped_than_made_is_refused(self) -> None:
        with pytest.raises(RuleError, match="is more than the"):
            Yields(
                poured=Pounds(200),
                casting_weight=Pounds(100),
                shipped=Pounds(150),
                sand_handled=SAND,
            )

    def test_a_heat_that_poured_nothing_has_no_yields(self) -> None:
        from mullerbox.heat.heat import Mold
        from mullerbox.spec.pattern import PatternClass

        empty = Heat(
            heat_number="H-9",
            poured_on=heat().poured_on,
            molds=(
                Mold(
                    mold_id="M-1",
                    pattern=PatternClass.LIGHT_JOBBING,
                    sand=Pounds(700),
                ),
            ),
        )
        found = yields_of(empty, SAND)
        with pytest.raises(RuleError, match="no casting yield"):
            assert found.casting_yield
        with pytest.raises(RuleError, match="no good casting yield"):
            assert found.good_casting_yield
        with pytest.raises(RuleError, match="no sand ratio"):
            assert found.sand_ratio
        with pytest.raises(RuleError, match="no scrap share"):
            assert found.scrap_share

    def test_the_types_are_checked(self) -> None:
        bad: Any = "H-1"
        with pytest.raises(BadInputError, match="a heat is expected"):
            yields_of(bad, SAND)
        with pytest.raises(BadInputError, match="sand handled is a bulk mass"):
            yields_of(built(), bad)
        with pytest.raises(BadInputError, match="poured is a bulk mass"):
            Yields(
                poured=bad,
                casting_weight=Pounds(1),
                shipped=Pounds(1),
                sand_handled=SAND,
            )
