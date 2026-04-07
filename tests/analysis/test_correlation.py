from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from mullerbox.analysis.correlation import MIN_PAIRS, Strength, correlate, paired
from mullerbox.errors import BadInputError, RuleError
from mullerbox.props.kind import PropertyKind

COMP = PropertyKind.COMPACTABILITY
MOISTURE = PropertyKind.MOISTURE
PERM = PropertyKind.PERMEABILITY


def readings(
    n: int = 20, together: bool = True, noise: str = "0"
) -> dict[str, dict[PropertyKind, Decimal]]:
    """Samples where compactability follows moisture, or does not."""
    out: dict[str, dict[PropertyKind, Decimal]] = {}
    for i in range(n):
        moisture = Decimal("3.0") + Decimal("0.05") * i
        step = Decimal("0.5") * i if together else Decimal("-0.5") * i
        wobble = Decimal(noise) * (1 if i % 2 else -1)
        out[f"S-{i:03d}"] = {
            MOISTURE: moisture,
            COMP: Decimal("38") + step + wobble,
        }
    return out


class TestPairingIsBySample:
    def test_only_samples_carrying_both_are_paired(self) -> None:
        data = readings(12)
        data["S-099"] = {MOISTURE: Decimal("3.5")}
        assert len(paired(data, MOISTURE, COMP)) == 12

    def test_a_sample_with_neither_is_skipped(self) -> None:
        data = readings(12)
        data["S-098"] = {PERM: Decimal("110")}
        assert len(paired(data, MOISTURE, COMP)) == 12

    def test_no_overlap_pairs_nothing(self) -> None:
        data: Any = {
            "S-1": {MOISTURE: Decimal("3.0")},
            "S-2": {COMP: Decimal("41")},
        }
        assert paired(data, MOISTURE, COMP) == []

    def test_a_property_against_itself_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="correlated with itself"):
            paired(readings(), MOISTURE, MOISTURE)

    def test_it_wants_property_kinds(self) -> None:
        bad: Any = "moisture"
        with pytest.raises(BadInputError, match="two property kinds"):
            paired(readings(), bad, COMP)

    def test_a_reading_that_is_not_a_decimal_is_refused(self) -> None:
        data: Any = dict(readings(12))
        data["S-000"] = {MOISTURE: 3.0, COMP: Decimal("38")}
        with pytest.raises(BadInputError, match="not a decimal"):
            paired(data, MOISTURE, COMP)


class TestTheCoefficient:
    def test_two_properties_moving_together_read_strong_and_positive(self) -> None:
        got = correlate(readings(together=True), MOISTURE, COMP)
        assert got.moves_together
        assert got.strength is Strength.STRONG
        assert got.coefficient > Decimal("0.9")

    def test_two_moving_against_each_other_read_strong_and_negative(self) -> None:
        got = correlate(readings(together=False), MOISTURE, COMP)
        assert not got.moves_together
        assert got.strength is Strength.STRONG
        assert got.coefficient < Decimal("-0.9")

    def test_noise_weakens_it(self) -> None:
        clean = correlate(readings(noise="0"), MOISTURE, COMP)
        noisy = correlate(readings(noise="8"), MOISTURE, COMP)
        assert abs(noisy.coefficient) < abs(clean.coefficient)

    def test_the_pair_count_is_carried(self) -> None:
        assert correlate(readings(20), MOISTURE, COMP).pairs == 20

    def test_every_strength_has_a_label(self) -> None:
        assert all(s.label for s in Strength)


class TestItMakesNoClaimAboutCause:
    def test_the_finding_says_so(self) -> None:
        got = correlate(readings(), MOISTURE, COMP)
        assert "nothing about why" in got.finding()

    def test_it_says_where_to_look(self) -> None:
        assert "where to look" in correlate(readings(), MOISTURE, COMP).finding()

    def test_the_direction_is_named_plainly(self) -> None:
        assert "move together" in str(correlate(readings(together=True), MOISTURE, COMP))
        assert "against each other" in str(correlate(readings(together=False), MOISTURE, COMP))


class TestAFlatRunCannotSay:
    def test_it_is_refused_rather_than_returning_zero(self) -> None:
        data = {
            f"S-{i:03d}": {MOISTURE: Decimal("3.0"), COMP: Decimal("38") + Decimal(i)}
            for i in range(20)
        }
        with pytest.raises(RuleError, match="cannot say"):
            correlate(data, MOISTURE, COMP)

    def test_it_names_which_one_was_flat(self) -> None:
        data = {
            f"S-{i:03d}": {MOISTURE: Decimal("3.0"), COMP: Decimal("38") + Decimal(i)}
            for i in range(20)
        }
        with pytest.raises(RuleError, match="moisture did not move"):
            correlate(data, MOISTURE, COMP)

    def test_either_side_being_flat_is_caught(self) -> None:
        data = {
            f"S-{i:03d}": {MOISTURE: Decimal("3.0") + Decimal(i), COMP: Decimal("38")}
            for i in range(20)
        }
        with pytest.raises(RuleError, match="compactability did not move"):
            correlate(data, MOISTURE, COMP)


class TestTooFewPairs:
    def test_it_is_refused_with_the_floor(self) -> None:
        with pytest.raises(RuleError, match=f"{MIN_PAIRS} is the"):
            correlate(readings(MIN_PAIRS - 1), MOISTURE, COMP)

    def test_exactly_the_floor_is_allowed(self) -> None:
        assert correlate(readings(MIN_PAIRS), MOISTURE, COMP).pairs == MIN_PAIRS
