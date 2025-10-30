from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest

from mullerbox.addition.material import Material
from mullerbox.errors import BadInputError, DuplicateError, NotFoundError, RuleError
from mullerbox.store.connection import Book
from mullerbox.store.price_repo import (
    history,
    price_list_on,
    price_on,
    priced_materials,
    set_price,
)
from mullerbox.units.money import PricePerTon
from tests.store.helpers import migrated_book

JAN = date(2025, 1, 6)
JUNE = date(2025, 6, 2)


@pytest.fixture
def book() -> Iterator[Book]:
    with migrated_book() as opened:
        yield opened


def price_everything(book: Book, when: date = JAN) -> None:
    for material, rate in (
        (Material.BENTONITE, "142.00"),
        (Material.SEACOAL, "196.50"),
        (Material.NEW_SAND, "38.25"),
        (Material.WATER, "0"),
    ):
        set_price(book, material, PricePerTon(rate), when)


class TestThePriceInForce:
    def test_it_comes_back(self, book: Book) -> None:
        price_everything(book)
        assert price_on(book, Material.BENTONITE, JAN) == PricePerTon("142.00")

    def test_a_later_date_still_gets_the_january_price(self, book: Book) -> None:
        price_everything(book)
        assert price_on(book, Material.BENTONITE, JUNE) == PricePerTon("142.00")

    def test_a_rise_takes_effect_from_its_date(self, book: Book) -> None:
        price_everything(book)
        set_price(book, Material.BENTONITE, PricePerTon("158.00"), JUNE)
        assert price_on(book, Material.BENTONITE, date(2025, 5, 1)) == PricePerTon("142.00")
        assert price_on(book, Material.BENTONITE, JUNE) == PricePerTon("158.00")

    def test_march_stays_at_the_march_price_after_a_june_rise(self, book: Book) -> None:
        price_everything(book)
        march = price_on(book, Material.BENTONITE, date(2025, 3, 1))
        set_price(book, Material.BENTONITE, PricePerTon("158.00"), JUNE)
        assert price_on(book, Material.BENTONITE, date(2025, 3, 1)) == march

    def test_before_any_price_is_refused_rather_than_free(self, book: Book) -> None:
        price_everything(book)
        with pytest.raises(NotFoundError, match="on or before"):
            price_on(book, Material.BENTONITE, date(2024, 12, 1))

    def test_zero_is_a_real_price(self, book: Book) -> None:
        price_everything(book)
        assert price_on(book, Material.WATER, JAN).dollars == 0


class TestTheAssembledList:
    def test_it_covers_every_material(self, book: Book) -> None:
        price_everything(book)
        listed = price_list_on(book, JUNE)
        for material in Material:
            assert listed.price_of(material) is not None

    def test_a_hole_is_refused_and_names_the_material(self, book: Book) -> None:
        set_price(book, Material.BENTONITE, PricePerTon("142.00"), JAN)
        with pytest.raises(NotFoundError, match="seacoal price"):
            price_list_on(book, JUNE)

    def test_an_empty_book_has_no_list(self, book: Book) -> None:
        with pytest.raises(NotFoundError):
            price_list_on(book, JUNE)

    def test_the_list_refuses_a_partial_set_by_construction(self, book: Book) -> None:
        """PriceList's own check is what makes a hole impossible to ignore."""
        from mullerbox.charge.cost import PriceList

        with pytest.raises(RuleError, match="no price for"):
            PriceList(prices={Material.BENTONITE: PricePerTon("142.00")})


class TestHistory:
    def test_it_is_oldest_first(self, book: Book) -> None:
        set_price(book, Material.BENTONITE, PricePerTon("158.00"), JUNE)
        set_price(book, Material.BENTONITE, PricePerTon("142.00"), JAN)
        found = history(book, Material.BENTONITE)
        assert [when for when, _ in found] == [JAN, JUNE]

    def test_a_material_never_priced_has_none(self, book: Book) -> None:
        assert history(book, Material.SEACOAL) == []

    def test_priced_materials_names_the_holes(self, book: Book) -> None:
        set_price(book, Material.BENTONITE, PricePerTon("142.00"), JAN)
        assert priced_materials(book, JUNE) == [Material.BENTONITE]


class TestGuards:
    def test_the_same_material_and_day_twice_is_refused(self, book: Book) -> None:
        set_price(book, Material.BENTONITE, PricePerTon("142.00"), JAN)
        with pytest.raises(DuplicateError, match="bentonite price effective"):
            set_price(book, Material.BENTONITE, PricePerTon("158.00"), JAN)

    def test_the_arguments_are_checked(self, book: Book) -> None:
        bad: Any = "bentonite"
        with pytest.raises(BadInputError, match="a material is expected"):
            set_price(book, bad, PricePerTon("142.00"), JAN)
        with pytest.raises(BadInputError, match="price per ton is expected"):
            set_price(book, Material.BENTONITE, bad, JAN)
        with pytest.raises(BadInputError, match="effective from a date"):
            set_price(book, Material.BENTONITE, PricePerTon("142.00"), bad)
        with pytest.raises(BadInputError, match="a date is expected"):
            price_on(book, Material.BENTONITE, bad)
        with pytest.raises(BadInputError, match="a date is expected"):
            price_list_on(book, bad)
        with pytest.raises(BadInputError, match="a material is expected"):
            history(book, bad)
        with pytest.raises(BadInputError, match="a date is expected"):
            priced_materials(book, bad)
