from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from mullerbox.errors import BadInputError, DuplicateError, NotFoundError
from mullerbox.heat.heat import Disposition, Heat
from mullerbox.spec.pattern import PatternClass
from mullerbox.store.connection import Book
from mullerbox.store.heat_repo import (
    heat_exists,
    list_heats,
    load_heat,
    load_pours,
    pour_from_heat,
    save_heat,
    save_pour,
)
from mullerbox.units.bulk import Pounds
from tests.burnout.helpers import pour
from tests.heat.helpers import casting, heat, mold
from tests.store.helpers import migrated_book

HEAVY = PatternClass.HEAVY_JOBBING
THIN = PatternClass.THIN_WALL


@pytest.fixture
def book() -> Iterator[Book]:
    with migrated_book() as opened:
        yield opened


def sample_heat() -> Heat:
    return heat(
        mold(
            "M-1",
            pattern=HEAVY,
            sand="700",
            castings=(
                casting("C-1", "120", Disposition.SHIPPED),
                casting("C-2", "80", Disposition.SCRAPPED),
            ),
        ),
        mold("M-2", pattern=THIN, sand="300", castings=(casting("C-3", "40"),)),
    )


class TestHeatRoundTrip:
    def test_a_heat_comes_back_identical(self, book: Book) -> None:
        original = sample_heat()
        save_heat(book, original)
        assert load_heat(book, original.heat_number) == original

    def test_the_molds_keep_their_classes(self, book: Book) -> None:
        save_heat(book, sample_heat())
        loaded = load_heat(book, "H-1001")
        assert {m.mold_id: m.pattern for m in loaded.molds} == {
            "M-1": HEAVY,
            "M-2": THIN,
        }

    def test_the_dispositions_survive(self, book: Book) -> None:
        save_heat(book, sample_heat())
        loaded = load_heat(book, "H-1001")
        assert [c.casting_id for c in loaded.molds[0].scrapped] == ["C-2"]

    def test_the_masses_survive_exactly(self, book: Book) -> None:
        save_heat(book, sample_heat())
        loaded = load_heat(book, "H-1001")
        assert loaded.metal == Pounds(240)
        assert loaded.sand == Pounds(1000)
        assert loaded.scrap_rate == Decimal("0.3333")

    def test_a_heat_with_no_molds_round_trips(self, book: Book) -> None:
        bare = Heat(heat_number="H-2", poured_on=date(2025, 5, 9))
        save_heat(book, bare)
        assert load_heat(book, "H-2") == bare


class TestHeatBookkeeping:
    def test_saving_twice_is_refused(self, book: Book) -> None:
        save_heat(book, sample_heat())
        with pytest.raises(DuplicateError, match="heat"):
            save_heat(book, sample_heat())

    def test_loading_something_absent_is_refused(self, book: Book) -> None:
        with pytest.raises(NotFoundError, match="heat"):
            load_heat(book, "H-9999")

    def test_exists(self, book: Book) -> None:
        assert not heat_exists(book, "H-1001")
        save_heat(book, sample_heat())
        assert heat_exists(book, "H-1001")

    def test_it_wants_a_heat(self, book: Book) -> None:
        bad: Any = "H-1001"
        with pytest.raises(BadInputError, match="a heat is expected"):
            save_heat(book, bad)

    def test_listing_all_and_by_day(self, book: Book) -> None:
        save_heat(book, sample_heat())
        second = heat(
            mold("M-9", castings=(casting("C-9"),)),
            number="H-1002",
            when=date(2025, 5, 9),
        )
        save_heat(book, second)
        assert list_heats(book) == ["H-1001", "H-1002"]
        assert list_heats(book, date(2025, 5, 9)) == ["H-1002"]

    def test_listing_wants_a_date(self, book: Book) -> None:
        bad: Any = "2025-05-09"
        with pytest.raises(BadInputError, match="a date is expected"):
            list_heats(book, bad)

    def test_a_casting_number_is_unique_across_the_book(self, book: Book) -> None:
        import sqlite3

        save_heat(book, sample_heat())
        clash = heat(
            mold("M-9", castings=(casting("C-1"),)),
            number="H-1002",
            when=date(2025, 5, 9),
        )
        with pytest.raises(sqlite3.IntegrityError):
            save_heat(book, clash)

    def test_a_corrupt_class_on_the_book_is_refused(self, book: Book) -> None:
        save_heat(book, sample_heat())
        book.execute("UPDATE mold SET pattern = 'PROTOTYPE'")
        with pytest.raises(BadInputError, match="which is not one"):
            load_heat(book, "H-1001")

    def test_a_corrupt_disposition_on_the_book_is_refused(self, book: Book) -> None:
        save_heat(book, sample_heat())
        book.execute("UPDATE casting SET disposition = 'MAYBE'")
        with pytest.raises(BadInputError, match="which is not one"):
            load_heat(book, "H-1001")


class TestPours:
    def test_a_pour_round_trips(self, book: Book) -> None:
        original = pour()
        save_pour(book, original)
        assert load_pours(book, original.poured_on) == [original]

    def test_the_same_day_and_class_twice_is_refused(self, book: Book) -> None:
        save_pour(book, pour())
        with pytest.raises(DuplicateError, match="pour"):
            save_pour(book, pour())

    def test_two_classes_on_one_day_are_both_kept(self, book: Book) -> None:
        save_pour(book, pour(pattern=PatternClass.MEDIUM_JOBBING))
        save_pour(book, pour(pattern=HEAVY))
        assert len(load_pours(book, pour().poured_on)) == 2

    def test_nothing_on_a_quiet_day(self, book: Book) -> None:
        assert load_pours(book, date(2025, 1, 1)) == []

    def test_it_is_guarded(self, book: Book) -> None:
        bad: Any = "6:1"
        with pytest.raises(BadInputError, match="a pour is expected"):
            save_pour(book, bad)
        with pytest.raises(BadInputError, match="a date is expected"):
            load_pours(book, bad)


class TestDerivingAPourFromAHeat:
    def test_it_counts_only_the_molds_of_that_class(self, book: Book) -> None:
        save_heat(book, sample_heat())
        derived = pour_from_heat(book, "H-1001", HEAVY)
        assert derived.metal == Pounds(200)
        assert derived.sand == Pounds(700)
        assert derived.sand_to_metal == Decimal("3.50")

    def test_a_second_class_gives_a_different_ratio(self, book: Book) -> None:
        save_heat(book, sample_heat())
        heavy = pour_from_heat(book, "H-1001", HEAVY)
        thin = pour_from_heat(book, "H-1001", THIN)
        assert heavy.sand_to_metal != thin.sand_to_metal

    def test_a_class_the_heat_did_not_run_is_refused(self, book: Book) -> None:
        save_heat(book, sample_heat())
        with pytest.raises(NotFoundError, match="molds on heat"):
            pour_from_heat(book, "H-1001", PatternClass.CORED_HEAVY)

    def test_it_wants_a_class(self, book: Book) -> None:
        bad: Any = "heavy"
        with pytest.raises(BadInputError, match="pattern class is expected"):
            pour_from_heat(book, "H-1001", bad)
