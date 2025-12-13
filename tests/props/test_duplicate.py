from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from mullerbox.errors import BadInputError, RuleError
from mullerbox.props.duplicate import REPEATABILITY, check, limit_for, worst
from mullerbox.props.kind import PropertyKind

COMP = PropertyKind.COMPACTABILITY
GCS = PropertyKind.GREEN_COMPRESSION
PERM = PropertyKind.PERMEABILITY


class TestEveryPropertyHasALimit:
    @pytest.mark.parametrize("kind", list(PropertyKind))
    def test_it_is_published(self, kind: PropertyKind) -> None:
        assert limit_for(kind) > 0

    def test_the_table_covers_every_property(self) -> None:
        assert set(REPEATABILITY) == set(PropertyKind)

    def test_the_limits_reflect_the_method_not_the_sand(self) -> None:
        assert limit_for(PERM) > limit_for(PropertyKind.MOISTURE)

    def test_it_wants_a_property(self) -> None:
        bad: Any = "comp"
        with pytest.raises(BadInputError, match="property kind is expected"):
            limit_for(bad)


class TestAgreement:
    def test_a_tight_pair_agrees(self) -> None:
        pair = check(COMP, Decimal("41.0"), Decimal("41.5"))
        assert pair.agrees
        assert "agrees" in str(pair)

    def test_exactly_on_the_limit_agrees(self) -> None:
        pair = check(COMP, Decimal("41.0"), Decimal("41.0") + limit_for(COMP))
        assert pair.agrees

    def test_a_hair_past_it_does_not(self) -> None:
        pair = check(COMP, Decimal("41.0"), Decimal("41.0") + limit_for(COMP) + Decimal("0.1"))
        assert not pair.agrees
        assert "DOES NOT REPEAT" in str(pair)

    def test_the_spread_is_unsigned(self) -> None:
        assert check(COMP, Decimal("43"), Decimal("41")).spread == Decimal(2)
        assert check(COMP, Decimal("41"), Decimal("43")).spread == Decimal(2)


class TestNeitherHalfSurvivesADisagreement:
    def test_the_mean_is_refused(self) -> None:
        pair = check(COMP, Decimal("38"), Decimal("45"))
        with pytest.raises(RuleError, match="neither one stands"):
            assert pair.mean

    def test_the_refusal_names_the_spread_and_the_limit(self) -> None:
        pair = check(COMP, Decimal("38"), Decimal("45"))
        with pytest.raises(RuleError, match="differ by 7"):
            pair.require_agreement()

    def test_it_says_to_run_the_test_again(self) -> None:
        pair = check(COMP, Decimal("38"), Decimal("45"))
        with pytest.raises(RuleError, match="the test is run again"):
            pair.require_agreement()

    def test_there_is_no_way_to_pick_a_survivor(self) -> None:
        """No API hands back one half of a disagreeing pair."""
        pair = check(COMP, Decimal("38"), Decimal("45"))
        assert not hasattr(pair, "best")
        assert not hasattr(pair, "keep")


class TestTheMeanOfAGoodPair:
    def test_it_is_the_average(self) -> None:
        assert check(COMP, Decimal("41.0"), Decimal("42.0")).mean == Decimal("41.5000")

    def test_a_pair_that_agrees_passes_quietly(self) -> None:
        check(COMP, Decimal("41.0"), Decimal("41.5")).require_agreement()

    def test_two_identical_readings_average_to_themselves(self) -> None:
        assert check(GCS, Decimal("23.0"), Decimal("23.0")).mean == Decimal("23.0000")


class TestRankingIsRelativeToTheLimit:
    def test_the_worst_is_the_one_furthest_past_its_own_limit(self) -> None:
        # A permeability spread of 12 is twice its limit of 6; a moisture
        # spread of 0.6 is four times its limit of 0.15.
        loose = check(PERM, Decimal("100"), Decimal("112"))
        tight = check(PropertyKind.MOISTURE, Decimal("3.0"), Decimal("3.6"))
        assert worst([loose, tight]) == tight

    def test_a_raw_spread_ranking_would_pick_the_other(self) -> None:
        loose = check(PERM, Decimal("100"), Decimal("112"))
        tight = check(PropertyKind.MOISTURE, Decimal("3.0"), Decimal("3.6"))
        assert loose.spread > tight.spread

    def test_agreeing_pairs_are_not_ranked(self) -> None:
        assert worst([check(COMP, Decimal("41.0"), Decimal("41.5"))]) is None

    def test_nothing_to_rank(self) -> None:
        assert worst([]) is None

    def test_it_wants_pairs(self) -> None:
        bad: Any = ["41 and 43"]
        with pytest.raises(BadInputError, match="only pairs"):
            worst(bad)


class TestConstruction:
    def test_the_pieces_are_checked(self) -> None:
        bad: Any = 41.0
        with pytest.raises(BadInputError, match="first reading is a decimal"):
            check(COMP, bad, Decimal("41.5"))
        with pytest.raises(BadInputError, match="second reading is a decimal"):
            check(COMP, Decimal("41.0"), bad)
        bad_kind: Any = "comp"
        with pytest.raises(BadInputError, match="property kind is expected"):
            check(bad_kind, Decimal("41"), Decimal("42"))
