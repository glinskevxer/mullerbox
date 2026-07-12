from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from mullerbox.errors import BadInputError, DuplicateError, NotFoundError
from mullerbox.store import inventory_repo
from mullerbox.store.connection import Book
from mullerbox.system.inventory import Count, Vessel
from mullerbox.units.bulk import Pounds
from tests.store.helpers import migrated_book

D = Decimal
WHEN = date(2026, 7, 15)


@pytest.fixture
def book() -> Iterator[Book]:
    with migrated_book() as opened:
        yield opened


def vessel(name: str = "silo", density: str | None = "95") -> Vessel:
    return Vessel(
        name=name,
        capacity_cubic_feet=D(1000),
        filled_fraction=D("0.80"),
        density_pounds_per_cubic_foot=None if density is None else D(density),
    )


def count(vessels: tuple[Vessel, ...] = (), when: date = WHEN, system: str = "two") -> Count:
    return Count(
        system_name=system,
        counted_on=when,
        vessels=vessels or (vessel(),),
        moulds_standing=40,
        sand_per_mould=Pounds(300),
    )


class TestRoundTrip:
    def test_a_count_comes_back_as_it_went_in(self, book: Book) -> None:
        inventory_repo.save_count(book, count())
        assert inventory_repo.load_count(book, "two", WHEN) == count()

    def test_the_missing_density_stays_missing(self, book: Book) -> None:
        original = count(vessels=(vessel(), vessel(name="hopper", density=None)))
        inventory_repo.save_count(book, original)
        back = inventory_repo.load_count(book, "two", WHEN)
        assert back.uncounted_vessels[0].name == "hopper"
        assert not back.is_complete

    def test_a_null_density_is_not_a_zero(self, book: Book) -> None:
        inventory_repo.save_count(book, count(vessels=(vessel(density=None),)))
        back = inventory_repo.load_count(book, "two", WHEN)
        assert back.vessels[0].density_pounds_per_cubic_foot is None

    def test_the_total_survives(self, book: Book) -> None:
        inventory_repo.save_count(book, count())
        assert inventory_repo.load_count(book, "two", WHEN).total == Pounds(88000)

    def test_the_vessels_come_back_in_name_order(self, book: Book) -> None:
        inventory_repo.save_count(book, count(vessels=(vessel(name="silo"), vessel(name="belt"))))
        back = inventory_repo.load_count(book, "two", WHEN)
        assert [v.name for v in back.vessels] == ["belt", "silo"]


class TestRefusals:
    def test_the_same_day_twice(self, book: Book) -> None:
        inventory_repo.save_count(book, count())
        with pytest.raises(DuplicateError):
            inventory_repo.save_count(book, count())

    def test_a_count_that_is_not_there(self, book: Book) -> None:
        with pytest.raises(NotFoundError, match="inventory of two"):
            inventory_repo.load_count(book, "two", WHEN)

    def test_it_wants_a_count(self, book: Book) -> None:
        bad: Any = "count"
        with pytest.raises(BadInputError, match="count is expected"):
            inventory_repo.save_count(book, bad)

    def test_it_wants_a_date_to_load(self, book: Book) -> None:
        bad: Any = "2026-07-15"
        with pytest.raises(BadInputError, match="looked up by date"):
            inventory_repo.load_count(book, "two", bad)

    def test_it_wants_a_date_to_delete(self, book: Book) -> None:
        bad: Any = "2026-07-15"
        with pytest.raises(BadInputError, match="looked up by date"):
            inventory_repo.delete_count(book, "two", bad)

    def test_it_wants_a_date_for_the_latest(self, book: Book) -> None:
        bad: Any = "2026-07-15"
        with pytest.raises(BadInputError, match="looked up by date"):
            inventory_repo.latest_count(book, "two", bad)


class TestListingAndLatest:
    def test_the_dates_come_back_oldest_first(self, book: Book) -> None:
        for when in (date(2026, 7, 15), date(2026, 1, 4), date(2026, 4, 2)):
            inventory_repo.save_count(book, count(when=when))
        assert inventory_repo.count_dates(book, "two") == [
            date(2026, 1, 4),
            date(2026, 4, 2),
            date(2026, 7, 15),
        ]

    def test_a_system_never_counted_has_no_dates(self, book: Book) -> None:
        assert inventory_repo.count_dates(book, "two") == []

    def test_the_latest_is_the_one_on_or_before(self, book: Book) -> None:
        inventory_repo.save_count(book, count(when=date(2026, 1, 4)))
        inventory_repo.save_count(book, count(when=date(2026, 7, 15)))
        found = inventory_repo.latest_count(book, "two", date(2026, 5, 1))
        assert found is not None
        assert found.counted_on == date(2026, 1, 4)

    def test_a_count_on_the_day_itself_counts(self, book: Book) -> None:
        inventory_repo.save_count(book, count(when=date(2026, 1, 4)))
        found = inventory_repo.latest_count(book, "two", date(2026, 1, 4))
        assert found is not None

    def test_nothing_before_the_date_comes_back_as_nothing(self, book: Book) -> None:
        inventory_repo.save_count(book, count(when=date(2026, 7, 15)))
        assert inventory_repo.latest_count(book, "two", date(2026, 1, 1)) is None

    def test_another_system_is_not_mixed_in(self, book: Book) -> None:
        inventory_repo.save_count(book, count(system="one"))
        assert inventory_repo.count_dates(book, "two") == []


class TestDeleting:
    def test_it_takes_the_vessels_with_it(self, book: Book) -> None:
        inventory_repo.save_count(book, count())
        inventory_repo.delete_count(book, "two", WHEN)
        left = book.all("SELECT name FROM inventory_vessel", ())
        assert left == []

    def test_deleting_one_that_is_not_there(self, book: Book) -> None:
        with pytest.raises(NotFoundError):
            inventory_repo.delete_count(book, "two", WHEN)

    def test_the_day_can_be_counted_again_after(self, book: Book) -> None:
        inventory_repo.save_count(book, count())
        inventory_repo.delete_count(book, "two", WHEN)
        inventory_repo.save_count(book, count())
        assert inventory_repo.count_dates(book, "two") == [WHEN]
