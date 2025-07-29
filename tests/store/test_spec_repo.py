from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest

from mullerbox.errors import BadInputError, DuplicateError, NotFoundError
from mullerbox.props.kind import PropertyKind
from mullerbox.spec.band import Band
from mullerbox.spec.pattern import PatternClass
from mullerbox.spec.sheet import SpecSheet, resolve
from mullerbox.store.connection import Book
from mullerbox.store.spec_repo import (
    current_sheet,
    list_sheets,
    load_sheet,
    published_on,
    save_sheet,
    sheet_exists,
)
from mullerbox.units.percent import Percent
from tests.spec.helpers import PUBLISHED, sheet
from tests.store.helpers import migrated_book

JAN = date(2025, 1, 6)
JUNE = date(2025, 6, 2)


@pytest.fixture
def book() -> Iterator[Book]:
    with migrated_book() as opened:
        yield opened


class TestRoundTrip:
    def test_a_sheet_comes_back_identical(self, book: Book) -> None:
        save_sheet(book, sheet(), JAN)
        loaded = load_sheet(book, "system sand 2025")
        assert loaded.covers == sheet().covers
        for kind in loaded.covers:
            assert loaded.band_for(kind) == sheet().band_for(kind)

    def test_a_two_ended_band_survives(self, book: Book) -> None:
        save_sheet(book, sheet(), JAN)
        band = load_sheet(book, "system sand 2025").band_for(PropertyKind.COMPACTABILITY)
        assert band.is_two_ended
        assert band.low == Percent(38)

    def test_a_ceiling_keeps_its_missing_floor(self, book: Book) -> None:
        save_sheet(book, sheet(), JAN)
        band = load_sheet(book, "system sand 2025").band_for(PropertyKind.LOI)
        assert band.low is None
        assert band.high == PUBLISHED[PropertyKind.LOI].high

    def test_a_floor_keeps_its_missing_ceiling(self, book: Book) -> None:
        save_sheet(book, sheet(), JAN)
        band = load_sheet(book, "system sand 2025").band_for(PropertyKind.WET_TENSILE)
        assert band.high is None
        assert band.low is not None

    def test_a_zero_limit_is_not_the_same_as_no_limit(self, book: Book) -> None:
        odd = SpecSheet(
            name="odd",
            bands={PropertyKind.FRIABILITY: Band.at_least(PropertyKind.FRIABILITY, Percent(0))},
        )
        save_sheet(book, odd, JAN)
        band = load_sheet(book, "odd").band_for(PropertyKind.FRIABILITY)
        assert band.low == Percent(0)
        assert band.high is None

    def test_the_scale_survives(self, book: Book) -> None:
        save_sheet(book, sheet(), JAN)
        band = load_sheet(book, "system sand 2025").band_for(PropertyKind.PERMEABILITY)
        assert band.low is not None
        assert type(band.low).__name__ == "Permeability"

    def test_it_still_resolves_after_a_round_trip(self, book: Book) -> None:
        save_sheet(book, sheet(), JAN)
        resolved = resolve(load_sheet(book, "system sand 2025"), PatternClass.THIN_WALL)
        assert resolved.judges(PropertyKind.MOLD_HARDNESS)


class TestBookkeeping:
    def test_saving_twice_is_refused(self, book: Book) -> None:
        save_sheet(book, sheet(), JAN)
        with pytest.raises(DuplicateError, match="spec sheet"):
            save_sheet(book, sheet(), JAN)

    def test_loading_something_absent_is_refused(self, book: Book) -> None:
        with pytest.raises(NotFoundError, match="spec sheet"):
            load_sheet(book, "nothing")

    def test_exists(self, book: Book) -> None:
        assert not sheet_exists(book, "system sand 2025")
        save_sheet(book, sheet(), JAN)
        assert sheet_exists(book, "system sand 2025")

    def test_the_publication_date_is_kept(self, book: Book) -> None:
        save_sheet(book, sheet(), JAN)
        assert published_on(book, "system sand 2025") == JAN

    def test_a_date_for_something_absent_is_refused(self, book: Book) -> None:
        with pytest.raises(NotFoundError, match="spec sheet"):
            published_on(book, "nothing")

    def test_listing_puts_the_newest_first(self, book: Book) -> None:
        save_sheet(book, sheet("old"), JAN)
        save_sheet(book, sheet("new"), JUNE)
        assert list_sheets(book) == ["new", "old"]

    def test_the_arguments_are_checked(self, book: Book) -> None:
        bad_sheet: Any = "system sand"
        with pytest.raises(BadInputError, match="spec sheet is expected"):
            save_sheet(book, bad_sheet, JAN)
        bad_date: Any = "2025-01-06"
        with pytest.raises(BadInputError, match="published on a date"):
            save_sheet(book, sheet(), bad_date)


class TestWhichSheetApplied:
    def test_a_shift_gets_the_sheet_in_force_at_the_time(self, book: Book) -> None:
        save_sheet(book, sheet("january"), JAN)
        save_sheet(book, sheet("june"), JUNE)
        assert current_sheet(book, date(2025, 3, 1)).name == "january"

    def test_a_later_revision_does_not_reach_back(self, book: Book) -> None:
        save_sheet(book, sheet("january"), JAN)
        save_sheet(book, sheet("june"), JUNE)
        assert current_sheet(book, date(2025, 7, 1)).name == "june"

    def test_the_day_of_publication_counts(self, book: Book) -> None:
        save_sheet(book, sheet("january"), JAN)
        assert current_sheet(book, JAN).name == "january"

    def test_before_any_sheet_there_is_none(self, book: Book) -> None:
        save_sheet(book, sheet("january"), JAN)
        with pytest.raises(NotFoundError, match="published on or before"):
            current_sheet(book, date(2024, 12, 1))

    def test_it_wants_a_date(self, book: Book) -> None:
        bad: Any = "2025-03-01"
        with pytest.raises(BadInputError, match="a date is expected"):
            current_sheet(book, bad)


class TestCorruptRows:
    def test_an_unknown_property_is_refused(self, book: Book) -> None:
        save_sheet(book, sheet(), JAN)
        book.execute("UPDATE spec_band SET property = 'STICKINESS' WHERE property = 'LOI'")
        with pytest.raises(BadInputError, match="which is not a property"):
            load_sheet(book, "system sand 2025")

    def test_an_unknown_scale_is_refused(self, book: Book) -> None:
        save_sheet(book, sheet(), JAN)
        book.execute("UPDATE spec_band SET scale = 'Furlongs'")
        with pytest.raises(BadInputError, match="on scale 'Furlongs'"):
            load_sheet(book, "system sand 2025")
