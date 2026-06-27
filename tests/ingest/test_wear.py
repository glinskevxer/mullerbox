from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from mullerbox.errors import BadInputError, ConfigError
from mullerbox.ingest.reader import read_text
from mullerbox.ingest.wear import WearLoad, load_wear, unmeasured
from mullerbox.screens.series import AFS_US_SERIES, ScreenSeries, Step
from mullerbox.units.mesh import Mesh

WHEN = date(2026, 7, 1)
HEADER = "screen,measured,checked\n"
SMALL = ScreenSeries(
    name="rig",
    steps=(Step(Mesh(30, 600), 20), Step(Mesh(70, 212), 50), Step(Mesh.pan(), 300)),
)


def load(text: str, series: ScreenSeries = SMALL) -> WearLoad:
    return load_wear(read_text(text), series)


class TestTheSeriesCannotBeGuessed:
    def test_a_screen_on_the_series_loads(self) -> None:
        got = load(HEADER + "30,600,2026-07-01\n")
        assert got.is_clean
        assert got.checks[0].mesh == Mesh(30, 600)

    def test_a_screen_from_another_series_is_named(self) -> None:
        got = load(HEADER + "100,150,2026-07-01\n")
        assert got.checks == ()
        assert "wrong drawer" in got.problems[0].reason

    def test_the_same_number_means_different_apertures_across_series(self) -> None:
        on_small = load(HEADER + "70,212,2026-07-01\n", SMALL)
        on_afs = load(HEADER + "70,212,2026-07-01\n", AFS_US_SERIES)
        assert on_small.checks[0].mesh == on_afs.checks[0].mesh

    def test_it_wants_a_series(self) -> None:
        bad: Any = "rig"
        with pytest.raises(BadInputError, match="screen series is expected"):
            load_wear(read_text(HEADER), bad)


class TestRowProblems:
    def test_the_pan_cannot_be_measured(self) -> None:
        got = load(HEADER + "PAN,0,2026-07-01\n")
        assert "no aperture to measure" in got.problems[0].reason

    def test_a_screen_that_is_not_a_number(self) -> None:
        got = load(HEADER + "coarse,600,2026-07-01\n")
        assert "is not a screen number" in got.problems[0].reason

    def test_an_aperture_that_is_not_a_number(self) -> None:
        got = load(HEADER + "30,wide,2026-07-01\n")
        assert "aperture in micrometres" in got.problems[0].reason

    def test_a_bad_date(self) -> None:
        got = load(HEADER + "30,600,01/07/2026\n")
        assert "yyyy-mm-dd" in got.problems[0].reason

    def test_the_same_screen_twice(self) -> None:
        got = load(HEADER + "30,600,2026-07-01\n30,601,2026-07-01\n")
        assert len(got.checks) == 1
        assert "measured twice" in got.problems[0].reason

    def test_a_missing_column_is_refused_outright(self) -> None:
        with pytest.raises(ConfigError, match="no 'checked' column"):
            load("screen,measured\n30,600\n")


class TestWhatWasLoaded:
    def test_a_worn_screen_is_picked_out(self) -> None:
        got = load(HEADER + "30,660,2026-07-01\n")
        assert len(got.worn) == 1

    def test_a_good_one_is_not(self) -> None:
        assert load(HEADER + "30,600,2026-07-01\n").worn == ()

    def test_the_unmeasured_screens_are_named(self) -> None:
        got = load(HEADER + "30,600,2026-07-01\n")
        assert unmeasured(got, SMALL) == (Mesh(70, 212),)

    def test_a_full_sheet_leaves_none(self) -> None:
        got = load(HEADER + "30,600,2026-07-01\n70,212,2026-07-01\n")
        assert unmeasured(got, SMALL) == ()

    def test_the_stack_says_what_is_missing(self) -> None:
        got = load(HEADER + "30,600,2026-07-01\n")
        stack = got.stack(SMALL, WHEN)
        assert stack.unchecked == (Mesh(70, 212),)
        assert not stack.is_fit_to_use

    def test_a_full_sheet_makes_a_fit_stack(self) -> None:
        got = load(HEADER + "30,600,2026-07-01\n70,212,2026-07-01\n")
        got.stack(SMALL, WHEN).require_fit()

    def test_unmeasured_wants_a_series(self) -> None:
        bad: Any = "rig"
        with pytest.raises(BadInputError, match="screen series is expected"):
            unmeasured(load(HEADER), bad)

    def test_str_summarises(self) -> None:
        assert str(load(HEADER + "30,600,2026-07-01\n")) == ("1 screens measured, 0 problems")
