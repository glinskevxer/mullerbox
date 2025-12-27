from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest

from mullerbox.errors import BadInputError, DuplicateError, NotFoundError, RuleError
from mullerbox.screens.series import ScreenSeries, Step
from mullerbox.screens.wear import Check
from mullerbox.store.connection import Book
from mullerbox.store.series_repo import save_series
from mullerbox.store.wear_repo import (
    history,
    latest_checks,
    oldest_check,
    record_check,
    stack_as_of,
)
from mullerbox.units.mesh import Mesh
from tests.store.helpers import migrated_book

COARSE = Mesh(30, 600)
FINE = Mesh(70, 212)
SMALL = ScreenSeries(
    name="three screen rig",
    steps=(Step(COARSE, 20), Step(FINE, 50), Step(Mesh.pan(), 300)),
)
JAN = date(2025, 1, 6)
JUNE = date(2025, 6, 2)


@pytest.fixture
def book() -> Iterator[Book]:
    with migrated_book() as opened:
        save_series(opened, SMALL)
        yield opened


def check(mesh: Mesh, measured: int, when: date = JAN) -> Check:
    return Check(mesh=mesh, measured_micrometres=measured, checked_on=when)


class TestRecording:
    def test_one_check_goes_on(self, book: Book) -> None:
        record_check(book, SMALL.name, check(COARSE, 600))
        assert latest_checks(book, SMALL, JAN)[COARSE].measured_micrometres == 600

    def test_the_same_screen_and_day_twice_is_refused(self, book: Book) -> None:
        record_check(book, SMALL.name, check(COARSE, 600))
        with pytest.raises(DuplicateError, match="wear check on screen 30"):
            record_check(book, SMALL.name, check(COARSE, 601))

    def test_an_unknown_series_is_refused(self, book: Book) -> None:
        with pytest.raises(NotFoundError, match="screen series"):
            record_check(book, "nothing", check(COARSE, 600))

    def test_it_wants_a_check(self, book: Book) -> None:
        bad: Any = "30"
        with pytest.raises(BadInputError, match="wear check is expected"):
            record_check(book, SMALL.name, bad)


class TestScreensAreMeasuredSeparately:
    def test_measuring_one_leaves_the_other_unchecked(self, book: Book) -> None:
        record_check(book, SMALL.name, check(COARSE, 600))
        stack = stack_as_of(book, SMALL, JAN)
        assert stack.unchecked == (FINE,)
        assert not stack.is_fit_to_use

    def test_measuring_both_makes_the_stack_fit(self, book: Book) -> None:
        record_check(book, SMALL.name, check(COARSE, 600))
        record_check(book, SMALL.name, check(FINE, 212))
        stack_as_of(book, SMALL, JAN).require_fit()

    def test_they_can_be_measured_on_different_days(self, book: Book) -> None:
        record_check(book, SMALL.name, check(COARSE, 600, JAN))
        record_check(book, SMALL.name, check(FINE, 212, JUNE))
        assert stack_as_of(book, SMALL, JUNE).is_fit_to_use

    def test_a_check_after_the_cutoff_is_not_used(self, book: Book) -> None:
        record_check(book, SMALL.name, check(COARSE, 600, JUNE))
        assert latest_checks(book, SMALL, JAN) == {}

    def test_the_most_recent_check_wins(self, book: Book) -> None:
        record_check(book, SMALL.name, check(COARSE, 600, JAN))
        record_check(book, SMALL.name, check(COARSE, 630, JUNE))
        assert latest_checks(book, SMALL, JUNE)[COARSE].measured_micrometres == 630

    def test_a_worn_screen_fails_the_assembled_stack(self, book: Book) -> None:
        record_check(book, SMALL.name, check(COARSE, 660))
        record_check(book, SMALL.name, check(FINE, 212))
        with pytest.raises(RuleError, match="retire it"):
            stack_as_of(book, SMALL, JAN).require_fit()


class TestStaleness:
    def test_the_oldest_check_is_named(self, book: Book) -> None:
        record_check(book, SMALL.name, check(COARSE, 600, JAN))
        record_check(book, SMALL.name, check(FINE, 212, JUNE))
        found = oldest_check(book, SMALL, JUNE)
        assert found is not None
        assert found == (COARSE, JAN)

    def test_nothing_measured_has_no_oldest(self, book: Book) -> None:
        assert oldest_check(book, SMALL, JUNE) is None


class TestHistory:
    def test_it_shows_the_wear_over_time(self, book: Book) -> None:
        record_check(book, SMALL.name, check(COARSE, 600, JAN))
        record_check(book, SMALL.name, check(COARSE, 615, JUNE))
        assert history(book, SMALL.name, COARSE) == [(JAN, 600), (JUNE, 615)]

    def test_a_screen_never_measured_has_none(self, book: Book) -> None:
        assert history(book, SMALL.name, FINE) == []

    def test_it_wants_a_screen(self, book: Book) -> None:
        bad: Any = 30
        with pytest.raises(BadInputError, match="a screen is expected"):
            history(book, SMALL.name, bad)


class TestGuards:
    def test_the_arguments_are_checked(self, book: Book) -> None:
        bad: Any = "series"
        with pytest.raises(BadInputError, match="screen series is expected"):
            latest_checks(book, bad, JAN)
        with pytest.raises(BadInputError, match="a date is expected"):
            latest_checks(book, SMALL, bad)
