from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from mullerbox.errors import BadInputError, RuleError
from mullerbox.screens.series import AFS_US_SERIES, ScreenSeries, Step
from mullerbox.screens.wear import WEAR_LIMIT, Check, StackCheck
from mullerbox.units.mesh import Mesh

WHEN = date(2025, 12, 29)
SMALL = ScreenSeries(
    name="three screen rig",
    steps=(Step(Mesh(30, 600), 20), Step(Mesh(70, 212), 50), Step(Mesh.pan(), 300)),
)


FIFTY = Mesh(50, 300)


def check(mesh: Mesh | None = None, measured: int = 300) -> Check:
    return Check(
        mesh=FIFTY if mesh is None else mesh,
        measured_micrometres=measured,
        checked_on=WHEN,
    )


class TestDrift:
    def test_a_screen_on_nominal_has_no_drift(self) -> None:
        assert check(measured=300).drift == Decimal(0)

    def test_an_opened_screen_drifts_positive(self) -> None:
        assert check(measured=306).drift == Decimal("0.0200")

    def test_a_tighter_screen_drifts_negative(self) -> None:
        assert check(measured=294).drift == Decimal("-0.0200")

    def test_a_small_drift_is_not_wear(self) -> None:
        assert not check(measured=306).is_worn
        assert "within" in check(measured=306).verdict()

    def test_past_the_limit_is_wear(self) -> None:
        worn = check(measured=int(300 * (1 + float(WEAR_LIMIT))) + 1)
        assert worn.is_worn
        assert "retire it" in worn.verdict()


class TestTheWrongScreenIsNotWear:
    def test_far_too_open_is_the_wrong_cloth(self) -> None:
        wrong = check(measured=400)
        assert wrong.is_wrong_screen
        assert "not wear" in wrong.verdict()
        assert "right cloth" in wrong.verdict()

    def test_tighter_than_nominal_is_the_wrong_cloth(self) -> None:
        """Wear opens a screen. It never closes one."""
        wrong = check(measured=250)
        assert wrong.is_wrong_screen
        assert "not wear" in wrong.verdict()

    def test_a_worn_screen_is_not_reported_as_the_wrong_one(self) -> None:
        worn = check(measured=320)
        assert worn.is_worn
        assert not worn.is_wrong_screen

    def test_the_wrong_screen_verdict_names_both_apertures(self) -> None:
        text = check(measured=400).verdict()
        assert "400" in text
        assert "300" in text


class TestTheStack:
    def test_a_fully_measured_good_stack_is_fit(self) -> None:
        stack = StackCheck(
            series=SMALL,
            checks=(check(Mesh(30, 600), 600), check(Mesh(70, 212), 212)),
            checked_on=WHEN,
        )
        assert stack.is_fit_to_use
        stack.require_fit()

    def test_an_unmeasured_screen_is_not_a_pass(self) -> None:
        stack = StackCheck(series=SMALL, checks=(check(Mesh(30, 600), 600),), checked_on=WHEN)
        assert not stack.is_fit_to_use
        assert stack.unchecked == (Mesh(70, 212),)
        with pytest.raises(RuleError, match="were not measured"):
            stack.require_fit()

    def test_the_pan_does_not_need_measuring(self) -> None:
        stack = StackCheck(
            series=SMALL,
            checks=(check(Mesh(30, 600), 600), check(Mesh(70, 212), 212)),
            checked_on=WHEN,
        )
        assert Mesh.pan() not in stack.unchecked

    def test_a_worn_screen_fails_the_stack(self) -> None:
        stack = StackCheck(
            series=SMALL,
            checks=(check(Mesh(30, 600), 640), check(Mesh(70, 212), 212)),
            checked_on=WHEN,
        )
        assert stack.worn
        with pytest.raises(RuleError, match="retire it"):
            stack.require_fit()

    def test_the_wrong_screen_is_reported_before_wear(self) -> None:
        stack = StackCheck(
            series=SMALL,
            checks=(check(Mesh(30, 600), 640), check(Mesh(70, 212), 300)),
            checked_on=WHEN,
        )
        assert stack.worn
        assert stack.wrong
        with pytest.raises(RuleError, match="right cloth"):
            stack.require_fit()

    def test_a_screen_off_the_series_is_refused(self) -> None:
        with pytest.raises(RuleError, match="is not on series"):
            StackCheck(series=SMALL, checks=(check(Mesh(100, 150), 150),), checked_on=WHEN)

    def test_measuring_one_screen_twice_is_refused(self) -> None:
        with pytest.raises(RuleError, match="measured twice"):
            StackCheck(
                series=SMALL,
                checks=(check(Mesh(30, 600), 600), check(Mesh(30, 600), 601)),
                checked_on=WHEN,
            )

    def test_the_full_afs_stack_needs_eleven_measurements(self) -> None:
        stack = StackCheck(series=AFS_US_SERIES, checks=(), checked_on=WHEN)
        assert len(stack.unchecked) == 11


class TestConstruction:
    def test_the_pan_cannot_be_wear_checked(self) -> None:
        with pytest.raises(BadInputError, match="pan has no aperture to wear"):
            check(Mesh.pan(), 0)

    def test_the_pieces_are_checked(self) -> None:
        bad: Any = "50"
        with pytest.raises(BadInputError, match="against a screen"):
            Check(mesh=bad, measured_micrometres=300, checked_on=WHEN)
        with pytest.raises(BadInputError, match="whole number"):
            Check(mesh=Mesh(50, 300), measured_micrometres=300.5, checked_on=WHEN)  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="above zero"):
            Check(mesh=Mesh(50, 300), measured_micrometres=0, checked_on=WHEN)
        with pytest.raises(BadInputError, match="is dated"):
            Check(mesh=Mesh(50, 300), measured_micrometres=300, checked_on=bad)

    def test_a_stack_check_wants_a_series_and_checks(self) -> None:
        bad: Any = "afs"
        with pytest.raises(BadInputError, match="against a series"):
            StackCheck(series=bad, checks=(), checked_on=WHEN)
        with pytest.raises(BadInputError, match="built from screen checks"):
            StackCheck(series=SMALL, checks=(bad,), checked_on=WHEN)
