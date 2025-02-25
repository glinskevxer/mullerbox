from __future__ import annotations

from decimal import Decimal

import pytest

from mullerbox.errors import BadInputError
from mullerbox.props.kind import PropertyKind
from mullerbox.spec.band import Band, Verdict
from mullerbox.units.percent import Percent
from mullerbox.units.pressure import Psi
from mullerbox.units.scales import Permeability

COMP = PropertyKind.COMPACTABILITY
GCS = PropertyKind.GREEN_COMPRESSION
PERM = PropertyKind.PERMEABILITY
LOI = PropertyKind.LOI


def comp_band(low: str = "38", high: str = "44") -> Band:
    return Band.between(COMP, Percent(low), Percent(high))


class TestConstruction:
    def test_a_band_wants_a_property(self) -> None:
        with pytest.raises(BadInputError, match="band for a property"):
            Band(kind="comp", low=Percent(38), high=Percent(44))  # type: ignore[arg-type]

    def test_both_limits_have_to_be_on_the_right_scale(self) -> None:
        with pytest.raises(BadInputError, match="measured in Percent, not Psi"):
            Band.between(COMP, Psi(38), Psi(44))

    def test_a_band_needs_a_limit(self) -> None:
        with pytest.raises(BadInputError, match="at least one limit"):
            Band(kind=COMP, low=None, high=None)

    def test_the_limits_have_to_run_the_right_way(self) -> None:
        with pytest.raises(BadInputError, match="runs from 44.00% to 38.00%"):
            Band.between(COMP, Percent(44), Percent(38))

    def test_the_limits_may_be_equal(self) -> None:
        pinned = Band.between(COMP, Percent(40), Percent(40))
        assert pinned.holds(Percent(40))
        assert pinned.width == Decimal(0)


class TestTheLimitsAreInclusive:
    def test_a_reading_on_the_low_limit_is_in(self) -> None:
        assert comp_band().verdict(Percent(38)) is Verdict.INSIDE

    def test_a_reading_on_the_high_limit_is_in(self) -> None:
        assert comp_band().verdict(Percent(44)) is Verdict.INSIDE

    def test_a_reading_below_is_below(self) -> None:
        assert comp_band().verdict(Percent("37.99")) is Verdict.BELOW

    def test_a_reading_above_is_above(self) -> None:
        assert comp_band().verdict(Percent("44.01")) is Verdict.ABOVE

    def test_holds_is_the_short_answer(self) -> None:
        assert comp_band().holds(Percent(41))
        assert not comp_band().holds(Percent(50))

    def test_out_of_band_reports_out(self) -> None:
        assert Verdict.BELOW.is_out
        assert Verdict.ABOVE.is_out
        assert not Verdict.INSIDE.is_out

    def test_a_reading_on_the_wrong_scale_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="measured in Percent, not Psi"):
            comp_band().verdict(Psi(41))


class TestOneEndedBands:
    def test_a_ceiling_has_no_floor(self) -> None:
        ceiling = Band.at_most(LOI, Percent("3.5"))
        assert ceiling.verdict(Percent(0)) is Verdict.INSIDE
        assert ceiling.verdict(Percent("3.5")) is Verdict.INSIDE
        assert ceiling.verdict(Percent("3.6")) is Verdict.ABOVE
        assert not ceiling.is_two_ended

    def test_a_floor_has_no_ceiling(self) -> None:
        floor = Band.at_least(GCS, Psi(18))
        assert floor.verdict(Psi(100)) is Verdict.INSIDE
        assert floor.verdict(Psi(18)) is Verdict.INSIDE
        assert floor.verdict(Psi("17.9")) is Verdict.BELOW

    def test_a_one_ended_band_has_no_midpoint_or_width(self) -> None:
        ceiling = Band.at_most(LOI, Percent("3.5"))
        with pytest.raises(BadInputError, match="has no midpoint"):
            assert ceiling.midpoint
        with pytest.raises(BadInputError, match="has no width"):
            assert ceiling.width

    def test_a_one_ended_band_will_not_rescale(self) -> None:
        with pytest.raises(BadInputError, match="cannot be rescaled around a midpoint"):
            Band.at_most(LOI, Percent("3.5")).scaled("0.7")


class TestScalingHoldsTheAim:
    def test_narrowing_keeps_the_midpoint(self) -> None:
        tightened = comp_band().scaled("0.5")
        assert tightened.midpoint == comp_band().midpoint
        assert tightened.low == Percent("39.50")
        assert tightened.high == Percent("42.50")

    def test_widening_keeps_the_midpoint(self) -> None:
        loosened = comp_band().scaled("1.2")
        assert loosened.midpoint == comp_band().midpoint
        assert loosened.width == comp_band().width * Decimal("1.2")

    def test_scaling_by_one_changes_nothing(self) -> None:
        assert comp_band().scaled(1) == comp_band()

    def test_a_whole_number_scale_stays_whole(self) -> None:
        perm = Band.between(PERM, Permeability(90), Permeability(130))
        tightened = perm.scaled("0.7")
        assert tightened.low == Permeability(96)
        assert tightened.high == Permeability(124)
        assert isinstance(tightened.low, Permeability)

    def test_scaling_to_nothing_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="cannot be scaled to nothing"):
            comp_band().scaled(0)
        with pytest.raises(BadInputError, match="cannot be scaled to nothing"):
            comp_band().scaled(-1)

    def test_scaling_wants_a_ratio(self) -> None:
        with pytest.raises(BadInputError, match="scaled by a ratio"):
            comp_band().scaled(None)
        with pytest.raises(BadInputError, match="scaled by a ratio"):
            comp_band().scaled(True)


class TestMidpointAndWidth:
    def test_the_midpoint_is_the_aim(self) -> None:
        assert comp_band().midpoint == Percent(41)

    def test_the_width_is_the_span(self) -> None:
        assert comp_band().width == Decimal(6)


class TestPresentation:
    def test_a_two_ended_band_reads_as_a_range(self) -> None:
        assert str(comp_band()) == "compactability 38.00% to 44.00%"

    def test_a_ceiling_reads_as_at_most(self) -> None:
        assert str(Band.at_most(LOI, Percent("3.5"))) == "loss on ignition at most 3.50%"

    def test_a_floor_reads_as_at_least(self) -> None:
        assert str(Band.at_least(GCS, Psi(18))) == "green compression strength at least 18.0 psi"


class TestTheGuardedLimits:
    def test_floor_and_ceiling_hand_back_the_limits(self) -> None:
        assert comp_band().floor == Percent(38)
        assert comp_band().ceiling == Percent(44)

    def test_a_missing_floor_is_refused_by_name(self) -> None:
        with pytest.raises(BadInputError, match="loss on ignition band has no lower"):
            assert Band.at_most(LOI, Percent("3.5")).floor

    def test_a_missing_ceiling_is_refused_by_name(self) -> None:
        with pytest.raises(BadInputError, match="green compression .* has no upper"):
            assert Band.at_least(GCS, Psi(18)).ceiling
