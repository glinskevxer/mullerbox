from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest

from mullerbox.cal.instrument import Instrument, InstrumentKind
from mullerbox.cal.window import CalibrationWindow
from mullerbox.errors import BadInputError, DuplicateError, NotFoundError, RuleError
from mullerbox.store.connection import Book
from mullerbox.store.instrument_repo import (
    add_calibration,
    exists,
    list_instruments,
    load_all,
    load_instrument,
    save_instrument,
)
from tests.store.helpers import migrated_book

Q1 = CalibrationWindow(date(2025, 1, 6), date(2025, 4, 6), "C-1")
Q2 = CalibrationWindow(date(2025, 4, 20), date(2025, 7, 20), "C-2")


@pytest.fixture
def book() -> Iterator[Book]:
    with migrated_book() as opened:
        yield opened


def usm(*windows: CalibrationWindow) -> Instrument:
    return Instrument(tag="USM-1", kind=InstrumentKind.STRENGTH, windows=windows)


class TestRoundTrip:
    def test_an_instrument_comes_back_identical(self, book: Book) -> None:
        save_instrument(book, usm(Q1, Q2))
        assert load_instrument(book, "USM-1") == usm(Q1, Q2)

    def test_an_instrument_with_no_history_round_trips(self, book: Book) -> None:
        save_instrument(book, usm())
        assert load_instrument(book, "USM-1").windows == ()

    def test_the_kind_survives(self, book: Book) -> None:
        save_instrument(book, usm(Q1))
        assert load_instrument(book, "USM-1").kind is InstrumentKind.STRENGTH

    def test_the_history_comes_back_in_order(self, book: Book) -> None:
        save_instrument(book, usm(Q1, Q2))
        loaded = load_instrument(book, "USM-1")
        assert [w.certificate for w in loaded.windows] == ["C-1", "C-2"]

    def test_the_lapse_survives_the_round_trip(self, book: Book) -> None:
        save_instrument(book, usm(Q1, Q2))
        loaded = load_instrument(book, "USM-1")
        assert loaded.lapses() == ((date(2025, 4, 6), date(2025, 4, 20)),)
        assert not loaded.was_calibrated_on(date(2025, 4, 10))


class TestAddingACalibration:
    def test_it_lands_on_the_book(self, book: Book) -> None:
        save_instrument(book, usm(Q1))
        add_calibration(book, "USM-1", Q2)
        assert len(load_instrument(book, "USM-1").windows) == 2

    def test_it_returns_the_updated_instrument(self, book: Book) -> None:
        save_instrument(book, usm(Q1))
        updated = add_calibration(book, "USM-1", Q2)
        assert updated == load_instrument(book, "USM-1")

    def test_a_late_entry_closes_a_lapse(self, book: Book) -> None:
        save_instrument(book, usm(Q1, Q2))
        filler = CalibrationWindow(date(2025, 4, 6), date(2025, 4, 20), "C-3")
        add_calibration(book, "USM-1", filler)
        assert load_instrument(book, "USM-1").was_calibrated_on(date(2025, 4, 10))

    def test_an_overlapping_certificate_is_refused_before_it_is_written(self, book: Book) -> None:
        save_instrument(book, usm(Q1))
        clash = CalibrationWindow(date(2025, 3, 1), date(2025, 6, 1), "C-9")
        with pytest.raises(RuleError, match="both cover"):
            add_calibration(book, "USM-1", clash)
        assert len(load_instrument(book, "USM-1").windows) == 1

    def test_adding_to_something_absent_is_refused(self, book: Book) -> None:
        with pytest.raises(NotFoundError, match="instrument"):
            add_calibration(book, "USM-9", Q1)


class TestCertificateNumbersAreUniqueAcrossTheBook:
    def test_the_same_number_on_two_devices_is_refused(self, book: Book) -> None:
        save_instrument(book, usm(Q1))
        other = Instrument(tag="PERM-1", kind=InstrumentKind.PERMEABILITY)
        save_instrument(book, other)
        same_paper = CalibrationWindow(date(2025, 5, 1), date(2025, 8, 1), "C-1")
        with pytest.raises(DuplicateError, match="certificate"):
            add_calibration(book, "PERM-1", same_paper)


class TestBookkeeping:
    def test_saving_twice_is_refused(self, book: Book) -> None:
        save_instrument(book, usm(Q1))
        with pytest.raises(DuplicateError, match="instrument"):
            save_instrument(book, usm(Q1))

    def test_loading_something_absent_is_refused(self, book: Book) -> None:
        with pytest.raises(NotFoundError, match="instrument"):
            load_instrument(book, "USM-9")

    def test_exists(self, book: Book) -> None:
        assert not exists(book, "USM-1")
        save_instrument(book, usm())
        assert exists(book, "USM-1")

    def test_listing_is_alphabetical(self, book: Book) -> None:
        save_instrument(book, usm())
        save_instrument(book, Instrument(tag="AAA-1", kind=InstrumentKind.MUFFLE))
        assert list_instruments(book) == ["AAA-1", "USM-1"]

    def test_load_all_keys_by_tag(self, book: Book) -> None:
        save_instrument(book, usm(Q1))
        save_instrument(book, Instrument(tag="PERM-1", kind=InstrumentKind.PERMEABILITY))
        everything = load_all(book)
        assert set(everything) == {"USM-1", "PERM-1"}
        assert everything["USM-1"].windows == (Q1,)

    def test_an_unrecognised_kind_on_the_book_is_refused(self, book: Book) -> None:
        save_instrument(book, usm())
        book.execute("UPDATE instrument SET kind = 'DOWSING_ROD' WHERE tag = 'USM-1'")
        with pytest.raises(BadInputError, match="as an instrument kind, which is not one of"):
            load_instrument(book, "USM-1")
