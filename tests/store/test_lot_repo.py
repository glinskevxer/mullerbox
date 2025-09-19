from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from mullerbox.addition.material import Material
from mullerbox.errors import BadInputError, DuplicateError, NotFoundError
from mullerbox.store.connection import Book
from mullerbox.store.lot_repo import (
    held,
    list_lots,
    load_lot,
    lot_exists,
    save_lot,
    update_lot,
)
from mullerbox.supplier.lot import Certificate, Lot, LotState
from mullerbox.units.bulk import Pounds
from mullerbox.units.percent import Percent
from tests.store.helpers import migrated_book

DELIVERED = date(2025, 9, 22)


@pytest.fixture
def book() -> Iterator[Book]:
    with migrated_book() as opened:
        yield opened


def lot(lot_id: str = "L-1", **claims: Any) -> Lot:
    return Lot(
        lot_id=lot_id,
        material=Material.NEW_SAND,
        mass=Pounds.of_tons(24),
        delivered_on=DELIVERED,
        certificate=Certificate(number="COA-1", **claims),
    )


class TestRoundTrip:
    def test_a_lot_comes_back_identical(self, book: Book) -> None:
        original = lot(grain_fineness=Decimal("58.0"), clay=Percent("0.30"))
        save_lot(book, original)
        assert load_lot(book, "L-1") == original

    def test_a_bare_certificate_round_trips_as_bare(self, book: Book) -> None:
        save_lot(book, lot())
        loaded = load_lot(book, "L-1")
        assert loaded.certificate.is_bare
        assert loaded.certificate.number == "COA-1"

    def test_a_zero_claim_is_not_the_same_as_no_claim(self, book: Book) -> None:
        save_lot(book, lot(clay=Percent(0)))
        loaded = load_lot(book, "L-1")
        assert loaded.certificate.clay == Percent(0)
        assert not loaded.certificate.is_bare
        assert loaded.certificate.moisture is None

    def test_the_scales_survive(self, book: Book) -> None:
        save_lot(book, lot(grain_fineness=Decimal("58.0"), moisture=Percent("0.20")))
        loaded = load_lot(book, "L-1")
        assert isinstance(loaded.certificate.grain_fineness, Decimal)
        assert isinstance(loaded.certificate.moisture, Percent)

    def test_the_mass_survives_exactly(self, book: Book) -> None:
        save_lot(book, lot())
        assert load_lot(book, "L-1").mass == Pounds.of_tons(24)


class TestState:
    def test_the_state_is_written_back(self, book: Book) -> None:
        save_lot(book, lot())
        tested = load_lot(book, "L-1").tested("ran a shaker on it")
        update_lot(book, tested)
        assert load_lot(book, "L-1").state is LotState.TESTED

    def test_a_release_keeps_who_released_it(self, book: Book) -> None:
        save_lot(book, lot())
        released = load_lot(book, "L-1").tested().released(by="j.mercer")
        update_lot(book, released)
        loaded = load_lot(book, "L-1")
        assert loaded.may_be_used
        assert loaded.released_by == "j.mercer"

    def test_a_quarantine_keeps_its_reason(self, book: Book) -> None:
        save_lot(book, lot())
        update_lot(book, load_lot(book, "L-1").quarantined("too fine"))
        assert load_lot(book, "L-1").note == "too fine"

    def test_updating_something_absent_is_refused(self, book: Book) -> None:
        with pytest.raises(NotFoundError, match="lot"):
            update_lot(book, lot("L-9"))


class TestHeldLots:
    def test_everything_not_released_is_listed(self, book: Book) -> None:
        save_lot(book, lot("L-1"))
        save_lot(book, lot("L-2"))
        update_lot(book, load_lot(book, "L-2").quarantined("no certificate"))
        assert [x.lot_id for x in held(book)] == ["L-1", "L-2"]

    def test_a_released_lot_drops_off_the_list(self, book: Book) -> None:
        save_lot(book, lot("L-1"))
        update_lot(book, load_lot(book, "L-1").tested().released(by="j.mercer"))
        assert held(book) == []

    def test_an_empty_book_holds_nothing(self, book: Book) -> None:
        assert held(book) == []


class TestBookkeeping:
    def test_saving_twice_is_refused(self, book: Book) -> None:
        save_lot(book, lot())
        with pytest.raises(DuplicateError, match="lot"):
            save_lot(book, lot())

    def test_loading_something_absent_is_refused(self, book: Book) -> None:
        with pytest.raises(NotFoundError, match="lot"):
            load_lot(book, "L-9")

    def test_exists(self, book: Book) -> None:
        assert not lot_exists(book, "L-1")
        save_lot(book, lot())
        assert lot_exists(book, "L-1")

    def test_listing_all_and_by_material(self, book: Book) -> None:
        save_lot(book, lot("L-1"))
        bentonite = Lot(
            lot_id="L-2",
            material=Material.BENTONITE,
            mass=Pounds(4000),
            delivered_on=DELIVERED,
            certificate=Certificate(number="COA-2"),
        )
        save_lot(book, bentonite)
        assert list_lots(book) == ["L-1", "L-2"]
        assert list_lots(book, Material.BENTONITE) == ["L-2"]

    def test_listing_wants_a_material(self, book: Book) -> None:
        bad: Any = "bentonite"
        with pytest.raises(BadInputError, match="a material is expected"):
            list_lots(book, bad)

    def test_it_wants_a_lot(self, book: Book) -> None:
        bad: Any = "L-1"
        with pytest.raises(BadInputError, match="a lot is expected"):
            save_lot(book, bad)
        with pytest.raises(BadInputError, match="a lot is expected"):
            update_lot(book, bad)


class TestCorruptRows:
    def test_an_unknown_claim_field_is_refused(self, book: Book) -> None:
        save_lot(book, lot(clay=Percent("0.30")))
        book.execute("UPDATE lot_claim SET field = 'stickiness'")
        with pytest.raises(BadInputError, match="not on a certificate"):
            load_lot(book, "L-1")

    def test_a_claim_that_is_not_a_number_is_refused(self, book: Book) -> None:
        save_lot(book, lot(clay=Percent("0.30")))
        book.execute("UPDATE lot_claim SET value = 'quite a lot'")
        with pytest.raises(BadInputError, match="which is not a number"):
            load_lot(book, "L-1")

    def test_an_unknown_material_is_refused(self, book: Book) -> None:
        save_lot(book, lot())
        book.execute("UPDATE material_lot SET material = 'GRAVEL'")
        with pytest.raises(BadInputError, match="which is not one"):
            load_lot(book, "L-1")

    def test_an_unknown_state_is_refused(self, book: Book) -> None:
        save_lot(book, lot())
        book.execute("UPDATE material_lot SET state = 'MAYBE'")
        with pytest.raises(BadInputError, match="which is not one"):
            load_lot(book, "L-1")
