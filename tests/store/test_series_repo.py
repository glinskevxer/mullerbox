from __future__ import annotations

from collections.abc import Iterator

import pytest

from mullerbox.errors import DuplicateError, NotFoundError
from mullerbox.screens.series import AFS_US_SERIES, ScreenSeries, Step
from mullerbox.store.connection import Book
from mullerbox.store.series_repo import (
    delete_series,
    exists,
    list_series,
    load_series,
    save_series,
)
from mullerbox.units.mesh import Mesh
from tests.store.helpers import migrated_book


@pytest.fixture
def book() -> Iterator[Book]:
    with migrated_book() as opened:
        yield opened


SMALL = ScreenSeries(
    name="three screen rig",
    steps=(
        Step(Mesh(30, 600), 20),
        Step(Mesh(70, 212), 50),
        Step(Mesh.pan(), 300),
    ),
)


class TestRoundTrip:
    def test_a_series_comes_back_identical(self, book: Book) -> None:
        save_series(book, AFS_US_SERIES)
        assert load_series(book, AFS_US_SERIES.name) == AFS_US_SERIES

    def test_the_steps_keep_their_order(self, book: Book) -> None:
        save_series(book, AFS_US_SERIES)
        assert load_series(book, AFS_US_SERIES.name).labels == AFS_US_SERIES.labels

    def test_the_multipliers_survive(self, book: Book) -> None:
        save_series(book, AFS_US_SERIES)
        loaded = load_series(book, AFS_US_SERIES.name)
        assert loaded.multiplier_for(Mesh(50, 300)) == 40

    def test_the_pan_survives_as_the_pan(self, book: Book) -> None:
        save_series(book, SMALL)
        assert load_series(book, SMALL.name).pan.mesh.is_pan

    def test_two_series_do_not_mix(self, book: Book) -> None:
        save_series(book, AFS_US_SERIES)
        save_series(book, SMALL)
        assert len(load_series(book, SMALL.name)) == 3
        assert len(load_series(book, AFS_US_SERIES.name)) == 12


class TestTheTypeStillGuardsTheLoad:
    def test_a_tampered_ordering_is_caught_on_load(self, book: Book) -> None:
        save_series(book, SMALL)
        # Swap the two working screens so the fine one sits above the coarse
        # one, leaving the pan where it belongs so the ordering check is the
        # one that fires.
        for sql in (
            "UPDATE screen_step SET position = 9 WHERE series_name = ? AND mesh_number = 30",
            "UPDATE screen_step SET position = 0 WHERE series_name = ? AND mesh_number = 70",
            "UPDATE screen_step SET position = 1 WHERE series_name = ? AND mesh_number = 30",
        ):
            book.execute(sql, (SMALL.name,))
        with pytest.raises(Exception, match="does not sit under"):
            load_series(book, SMALL.name)

    def test_a_missing_pan_is_caught_on_load(self, book: Book) -> None:
        save_series(book, SMALL)
        book.execute(
            "DELETE FROM screen_step WHERE series_name = ? AND mesh_number = 0",
            (SMALL.name,),
        )
        with pytest.raises(Exception, match="ends at the pan"):
            load_series(book, SMALL.name)

    def test_a_tampered_multiplier_is_caught_on_load(self, book: Book) -> None:
        save_series(book, SMALL)
        book.execute(
            "UPDATE screen_step SET multiplier = 1 WHERE series_name = ? AND mesh_number = 70",
            (SMALL.name,),
        )
        with pytest.raises(Exception, match="rise from coarse to fine"):
            load_series(book, SMALL.name)


class TestBookkeeping:
    def test_saving_twice_is_refused(self, book: Book) -> None:
        save_series(book, SMALL)
        with pytest.raises(DuplicateError, match="already on the book"):
            save_series(book, SMALL)

    def test_loading_something_absent_is_refused(self, book: Book) -> None:
        with pytest.raises(NotFoundError, match="screen series"):
            load_series(book, "nothing")

    def test_exists(self, book: Book) -> None:
        assert not exists(book, SMALL.name)
        save_series(book, SMALL)
        assert exists(book, SMALL.name)

    def test_listing_is_alphabetical(self, book: Book) -> None:
        save_series(book, AFS_US_SERIES)
        save_series(book, SMALL)
        assert list_series(book) == sorted([AFS_US_SERIES.name, SMALL.name])

    def test_deleting_takes_the_steps_with_it(self, book: Book) -> None:
        save_series(book, SMALL)
        delete_series(book, SMALL.name)
        assert not exists(book, SMALL.name)
        assert book.scalar("SELECT count(*) FROM screen_step") == 0

    def test_deleting_something_absent_is_refused(self, book: Book) -> None:
        with pytest.raises(NotFoundError, match="screen series"):
            delete_series(book, "nothing")

    def test_a_failed_save_leaves_nothing_behind(self, book: Book) -> None:
        save_series(book, SMALL)
        with pytest.raises(DuplicateError):
            save_series(book, SMALL)
        assert book.scalar("SELECT count(*) FROM screen_series") == 1
