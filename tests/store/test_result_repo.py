from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest

from mullerbox.cal.instrument import Instrument, InstrumentKind
from mullerbox.cal.window import CalibrationWindow
from mullerbox.errors import BadInputError, DuplicateError, NotFoundError
from mullerbox.props.kind import PropertyKind
from mullerbox.props.result import Result
from mullerbox.store.connection import Book
from mullerbox.store.instrument_repo import save_instrument
from mullerbox.store.result_repo import (
    Sample,
    load_results,
    load_sample,
    results_of,
    sample_exists,
    save_result,
    save_sample,
)
from mullerbox.units.percent import Percent
from mullerbox.units.pressure import Psi
from mullerbox.units.scales import Hardness, Permeability
from tests.store.helpers import migrated_book

TAKEN = date(2025, 5, 6)
Q1 = CalibrationWindow(date(2025, 1, 6), date(2025, 12, 6), "C-1")


@pytest.fixture
def book() -> Iterator[Book]:
    with migrated_book() as opened:
        save_instrument(
            opened,
            Instrument(tag="RAM-1", kind=InstrumentKind.COMPACTABILITY, windows=(Q1,)),
        )
        save_instrument(
            opened,
            Instrument(tag="USM-1", kind=InstrumentKind.STRENGTH, windows=()),
        )
        save_instrument(
            opened,
            Instrument(tag="PERM-1", kind=InstrumentKind.PERMEABILITY, windows=()),
        )
        save_sample(opened, sample())
        yield opened


def sample(sample_id: str = "S-100") -> Sample:
    return Sample(
        sample_id=sample_id,
        taken_on=TAKEN,
        point="muller discharge",
        system_name="number two system",
    )


def result(
    kind: PropertyKind = PropertyKind.COMPACTABILITY,
    reading: Any = None,
    tag: str = "RAM-1",
    sample_id: str = "S-100",
    when: date = TAKEN,
) -> Result:
    return Result(
        kind=kind,
        reading=Percent("42") if reading is None else reading,
        instrument_tag=tag,
        tested_on=when,
        sample_id=sample_id,
    )


class TestSamples:
    def test_a_sample_round_trips(self, book: Book) -> None:
        assert load_sample(book, "S-100") == sample()

    def test_saving_twice_is_refused(self, book: Book) -> None:
        with pytest.raises(DuplicateError, match="sample"):
            save_sample(book, sample())

    def test_loading_something_absent_is_refused(self, book: Book) -> None:
        with pytest.raises(NotFoundError, match="sample"):
            load_sample(book, "S-999")

    def test_exists(self, book: Book) -> None:
        assert sample_exists(book, "S-100")
        assert not sample_exists(book, "S-999")

    def test_the_pieces_are_checked(self) -> None:
        with pytest.raises(BadInputError, match="needs an identifier"):
            Sample(sample_id=" ", taken_on=TAKEN, point="p", system_name="s")
        bad: Any = "2025-05-06"
        with pytest.raises(BadInputError, match="a sample is dated"):
            Sample(sample_id="S-1", taken_on=bad, point="p", system_name="s")
        with pytest.raises(BadInputError, match="names where it was pulled"):
            Sample(sample_id="S-1", taken_on=TAKEN, point=" ", system_name="s")
        with pytest.raises(BadInputError, match="names its sand system"):
            Sample(sample_id="S-1", taken_on=TAKEN, point="p", system_name=" ")


class TestTheScaleIsStoredWithTheReading:
    def test_a_percentage_comes_back_a_percentage(self, book: Book) -> None:
        save_result(book, result())
        got = load_results(book, "S-100")[0]
        assert isinstance(got.reading, Percent)
        assert got.reading == Percent("42")

    def test_the_exact_value_survives(self, book: Book) -> None:
        save_result(book, result(reading=Percent("42.00")))
        assert load_results(book, "S-100")[0].reading == Percent("42.00")

    def test_two_scales_that_share_a_number_do_not_confuse_the_loader(self, book: Book) -> None:
        save_result(
            book,
            result(
                kind=PropertyKind.PERMEABILITY,
                reading=Permeability(88),
                tag="PERM-1",
            ),
        )
        save_result(
            book,
            result(
                kind=PropertyKind.MOLD_HARDNESS,
                reading=Hardness(88),
                tag="USM-1",
            ),
        )
        by_kind = {r.kind: r.reading for r in load_results(book, "S-100")}
        assert isinstance(by_kind[PropertyKind.PERMEABILITY], Permeability)
        assert isinstance(by_kind[PropertyKind.MOLD_HARDNESS], Hardness)

    def test_a_scale_the_book_does_not_know_is_refused_on_load(self, book: Book) -> None:
        save_result(book, result())
        book.execute("UPDATE result SET scale = 'Furlongs'")
        with pytest.raises(BadInputError, match="on scale 'Furlongs'"):
            load_results(book, "S-100")

    def test_a_property_the_book_does_not_know_is_refused_on_load(self, book: Book) -> None:
        save_result(book, result())
        book.execute("UPDATE result SET property = 'STICKINESS'")
        with pytest.raises(BadInputError, match="which is not a property"):
            load_results(book, "S-100")


class TestResults:
    def test_a_result_round_trips_whole(self, book: Book) -> None:
        original = result()
        save_result(book, original)
        assert load_results(book, "S-100") == [original]

    def test_two_properties_on_one_sample(self, book: Book) -> None:
        save_result(book, result())
        save_result(
            book,
            result(kind=PropertyKind.GREEN_COMPRESSION, reading=Psi(23), tag="USM-1"),
        )
        assert len(load_results(book, "S-100")) == 2

    def test_the_same_property_twice_is_refused(self, book: Book) -> None:
        save_result(book, result())
        with pytest.raises(DuplicateError, match="compactability on sample"):
            save_result(book, result(reading=Percent("43")))

    def test_a_result_against_a_missing_sample_is_refused(self, book: Book) -> None:
        with pytest.raises(NotFoundError, match="sample"):
            save_result(book, result(sample_id="S-999"))

    def test_a_result_against_a_missing_instrument_is_refused(self, book: Book) -> None:
        with pytest.raises(sqlite3.IntegrityError):
            save_result(book, result(tag="RAM-9"))

    def test_nothing_stored_gives_nothing_back(self, book: Book) -> None:
        assert load_results(book, "S-100") == []


class TestByProperty:
    def test_it_gathers_across_samples_oldest_first(self, book: Book) -> None:
        save_sample(book, sample("S-101"))
        save_result(book, result(when=date(2025, 5, 8)))
        save_result(book, result(sample_id="S-101", when=date(2025, 5, 6)))
        found = results_of(book, PropertyKind.COMPACTABILITY)
        assert [r.sample_id for r in found] == ["S-101", "S-100"]

    def test_another_property_is_not_returned(self, book: Book) -> None:
        save_result(book, result())
        assert results_of(book, PropertyKind.PERMEABILITY) == []

    def test_it_wants_a_property(self, book: Book) -> None:
        bad: Any = "comp"
        with pytest.raises(BadInputError, match="property kind is expected"):
            results_of(book, bad)
