from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from mullerbox.errors import BadInputError
from mullerbox.props.bias import Comparison, average_bias, cross_check_limit
from mullerbox.props.duplicate import limit_for
from mullerbox.props.kind import PropertyKind

COMP = PropertyKind.COMPACTABILITY
GCS = PropertyKind.GREEN_COMPRESSION


def compare(first: str, second: str, kind: PropertyKind = COMP, sample: str = "S-1") -> Comparison:
    return Comparison(
        kind=kind,
        sample_id=sample,
        first_tag="RAM-1",
        first_reading=Decimal(first),
        second_tag="RAM-2",
        second_reading=Decimal(second),
    )


class TestTheLimitIsWiderThanForOneBench:
    def test_it_is_the_repeatability_limit_times_root_two(self) -> None:
        assert cross_check_limit(COMP) > limit_for(COMP)

    def test_by_about_forty_one_percent(self) -> None:
        ratio = cross_check_limit(COMP) / limit_for(COMP)
        assert Decimal("1.41") < ratio < Decimal("1.42")

    def test_every_property_has_one(self) -> None:
        for kind in PropertyKind:
            assert cross_check_limit(kind) > 0

    def test_a_pair_inside_the_one_bench_limit_certainly_agrees(self) -> None:
        assert compare("41.0", "41.5").agrees

    def test_a_pair_between_the_two_limits_still_agrees(self) -> None:
        gap = (limit_for(COMP) + cross_check_limit(COMP)) / 2
        assert compare("41.0", str(Decimal("41.0") + gap)).agrees

    def test_it_wants_a_property(self) -> None:
        bad: Any = "comp"
        with pytest.raises(BadInputError, match="property kind is expected"):
            cross_check_limit(bad)


class TestBiasIsDirectional:
    def test_the_second_reading_higher_is_positive(self) -> None:
        assert compare("41.0", "43.0").bias == Decimal("2.0")

    def test_the_first_reading_higher_is_negative(self) -> None:
        assert compare("43.0", "41.0").bias == Decimal("-2.0")

    def test_the_high_bench_is_named(self) -> None:
        assert compare("41.0", "45.0").high_bench == "RAM-2"
        assert compare("45.0", "41.0").high_bench == "RAM-1"

    def test_identical_readings_name_no_bench(self) -> None:
        assert compare("41.0", "41.0").high_bench is None


class TestItRefusesToNominateACulprit:
    def test_a_disagreement_says_one_of_them_is_off(self) -> None:
        finding = compare("41.0", "48.0").finding()
        assert "One of them is off" in finding
        assert "cannot say which" in finding

    def test_it_still_says_which_reads_higher(self) -> None:
        assert "RAM-2 reads higher" in compare("41.0", "48.0").finding()

    def test_agreement_says_so_plainly(self) -> None:
        finding = compare("41.0", "41.2").finding()
        assert "agree on compactability" in finding
        assert "One of them is off" not in finding

    def test_there_is_no_api_that_picks_one(self) -> None:
        pair = compare("41.0", "48.0")
        assert not hasattr(pair, "culprit")
        assert not hasattr(pair, "wrong_bench")


class TestAveragingSeveralComparisons:
    def test_a_consistent_bias_averages_to_itself(self) -> None:
        found = average_bias(
            [compare("41.0", "43.0", sample="S-1"), compare("40.0", "42.0", sample="S-2")]
        )
        assert found == Decimal("2.0000")

    def test_opposite_biases_cancel(self) -> None:
        found = average_bias(
            [compare("41.0", "43.0", sample="S-1"), compare("43.0", "41.0", sample="S-2")]
        )
        assert found == Decimal("0.0000")

    def test_nothing_to_average(self) -> None:
        with pytest.raises(BadInputError, match="no comparisons to average"):
            average_bias([])

    def test_two_different_properties_do_not_average(self) -> None:
        with pytest.raises(BadInputError, match="do not average"):
            average_bias([compare("41.0", "43.0"), compare("20.0", "22.0", kind=GCS)])

    def test_two_different_pairs_of_benches_do_not_average(self) -> None:
        other = Comparison(
            kind=COMP,
            sample_id="S-2",
            first_tag="RAM-1",
            first_reading=Decimal("41.0"),
            second_tag="RAM-3",
            second_reading=Decimal("43.0"),
        )
        with pytest.raises(BadInputError, match="same two"):
            average_bias([compare("41.0", "43.0"), other])

    def test_it_wants_comparisons(self) -> None:
        bad: Any = ["41 and 43"]
        with pytest.raises(BadInputError, match="only comparisons"):
            average_bias(bad)


class TestConstruction:
    def test_two_readings_off_one_bench_is_a_duplicate_not_a_cross_check(self) -> None:
        with pytest.raises(BadInputError, match="rather than a cross check"):
            Comparison(
                kind=COMP,
                sample_id="S-1",
                first_tag="RAM-1",
                first_reading=Decimal("41"),
                second_tag="RAM-1",
                second_reading=Decimal("43"),
            )

    def test_the_pieces_are_checked(self) -> None:
        bad: Any = 41.0
        with pytest.raises(BadInputError, match="names the sample"):
            Comparison(
                kind=COMP,
                sample_id=" ",
                first_tag="A",
                first_reading=Decimal(1),
                second_tag="B",
                second_reading=Decimal(1),
            )
        with pytest.raises(BadInputError, match="names both instruments"):
            Comparison(
                kind=COMP,
                sample_id="S-1",
                first_tag=" ",
                first_reading=Decimal(1),
                second_tag="B",
                second_reading=Decimal(1),
            )
        with pytest.raises(BadInputError, match="first reading is a decimal"):
            Comparison(
                kind=COMP,
                sample_id="S-1",
                first_tag="A",
                first_reading=bad,
                second_tag="B",
                second_reading=Decimal(1),
            )
