from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from mullerbox.analysis.capability import CAPABLE, capability_of, sigma_from
from mullerbox.analysis.control import MIN_POINTS
from mullerbox.errors import BadInputError, RuleError
from mullerbox.props.kind import PropertyKind
from mullerbox.spec.band import Band
from mullerbox.units.percent import Percent

COMP = PropertyKind.COMPACTABILITY
LOI = PropertyKind.LOI
BAND = Band.between(COMP, Percent(38), Percent(44))
CEILING = Band.at_most(LOI, Percent("3.5"))


def run(centre: str, step: str = "0.1", n: int = 25) -> list[Decimal]:
    """A tight run alternating either side of a centre."""
    mid = Decimal(centre)
    jump = Decimal(step)
    return [mid + (jump if i % 2 else -jump) for i in range(n)]


class TestSigma:
    def test_it_comes_from_the_moving_range(self) -> None:
        assert sigma_from(run("41", "0.1")) > 0

    def test_a_tighter_run_has_a_smaller_sigma(self) -> None:
        assert sigma_from(run("41", "0.05")) < sigma_from(run("41", "0.5"))

    def test_it_measures_the_step_and_not_the_span(self) -> None:
        """A drifting run and a tight one with the same step share a sigma.

        The drifting run covers 2.4 points end to end and the tight one covers
        0.1, and both move a tenth between neighbours. Sigma from the moving
        range sees only the step, so it reports them identically. That is why
        capability alone cannot tell them apart and has to be read beside a
        control chart, which flags the drift as a trend.
        """
        drifting = [Decimal("38") + Decimal("0.1") * i for i in range(25)]
        tight = run("41", "0.05")
        assert max(drifting) - min(drifting) == Decimal("2.4")
        assert max(tight) - min(tight) == Decimal("0.1")
        assert sigma_from(drifting) == sigma_from(tight)

    def test_the_control_chart_is_what_separates_them(self) -> None:
        from mullerbox.analysis.control import chart_of

        drifting = [Decimal("38") + Decimal("0.1") * i for i in range(25)]
        assert not chart_of(drifting).in_control
        assert chart_of(run("41", "0.05")).in_control

    def test_one_reading_has_no_moving_range(self) -> None:
        with pytest.raises(RuleError, match="fewest that have a moving range"):
            sigma_from([Decimal(41)])


class TestControlAndCapabilityAreIndependent:
    def test_a_tight_run_inside_the_band_is_capable(self) -> None:
        got = capability_of(COMP, BAND, run("41", "0.1"))
        assert got.is_capable
        assert "capable at" in got.verdict()

    def test_a_tight_run_outside_the_band_is_not(self) -> None:
        got = capability_of(COMP, BAND, run("50", "0.1"))
        assert not got.is_capable
        assert got.cpk < 0

    def test_the_stable_but_wrong_case_still_has_a_good_cp(self) -> None:
        got = capability_of(COMP, BAND, run("50", "0.1"))
        assert got.cp is not None
        assert got.cp > CAPABLE
        assert got.is_off_centre
        assert "would fit if it were centred" in got.verdict()

    def test_a_wide_run_centred_well_has_a_poor_cp(self) -> None:
        got = capability_of(COMP, BAND, run("41", "2.0"))
        assert got.cp is not None
        assert got.cp < CAPABLE
        assert not got.is_off_centre


class TestCpAndCpkTogether:
    def test_a_centred_process_has_them_about_equal(self) -> None:
        got = capability_of(COMP, BAND, run("41", "0.2"))
        assert got.cp is not None
        assert abs(got.cp - got.cpk) < Decimal("0.1")

    def test_moving_off_centre_drops_cpk_and_not_cp(self) -> None:
        centred = capability_of(COMP, BAND, run("41", "0.2"))
        skewed = capability_of(COMP, BAND, run("43.5", "0.2"))
        assert centred.cp == skewed.cp
        assert skewed.cpk < centred.cpk

    def test_cpk_takes_the_worse_side(self) -> None:
        high = capability_of(COMP, BAND, run("43.8", "0.2"))
        low = capability_of(COMP, BAND, run("38.2", "0.2"))
        assert high.cpk < CAPABLE
        assert low.cpk < CAPABLE


class TestOneEndedBands:
    def test_a_ceiling_has_no_cp(self) -> None:
        got = capability_of(LOI, CEILING, run("2.5", "0.05"))
        assert got.cp is None
        assert not got.is_off_centre

    def test_it_still_has_a_cpk(self) -> None:
        got = capability_of(LOI, CEILING, run("2.5", "0.05"))
        assert got.cpk > 0

    def test_running_close_to_the_ceiling_drops_it(self) -> None:
        far = capability_of(LOI, CEILING, run("2.0", "0.05"))
        near = capability_of(LOI, CEILING, run("3.4", "0.05"))
        assert near.cpk < far.cpk


class TestVerdicts:
    def test_marginal_sits_between_the_two_lines(self) -> None:
        got = capability_of(COMP, BAND, run("41", "0.75"))
        if got.is_marginal:
            assert "marginal at" in got.verdict()
        assert not (got.is_capable and got.is_marginal)

    def test_the_worst_case_says_the_spread_will_not_fit(self) -> None:
        got = capability_of(COMP, BAND, run("41", "4.0"))
        assert "spread alone will not fit" in got.verdict()

    def test_str_names_the_property(self) -> None:
        assert str(capability_of(COMP, BAND, run("41"))).startswith("compactability:")


class TestGuards:
    def test_the_band_has_to_be_for_the_property(self) -> None:
        with pytest.raises(BadInputError, match="cannot be judged against"):
            capability_of(LOI, BAND, run("41"))

    def test_too_few_readings(self) -> None:
        with pytest.raises(RuleError, match=f"{MIN_POINTS} is the floor"):
            capability_of(COMP, BAND, run("41", n=MIN_POINTS - 1))

    def test_a_run_with_no_spread_at_all(self) -> None:
        flat = [Decimal(41)] * 25
        with pytest.raises(RuleError, match="no measurable spread"):
            capability_of(COMP, BAND, flat)

    def test_the_types_are_checked(self) -> None:
        bad: Any = "comp"
        with pytest.raises(BadInputError, match="property kind is expected"):
            capability_of(bad, BAND, run("41"))
        with pytest.raises(BadInputError, match="a band is expected"):
            capability_of(COMP, bad, run("41"))
        with pytest.raises(BadInputError, match="run of readings is expected"):
            capability_of(COMP, BAND, bad)
        bad_values: Any = [41.0] * 25
        with pytest.raises(BadInputError, match="worked out from decimals"):
            capability_of(COMP, BAND, bad_values)
