from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest

from mullerbox.cal.instrument import Instrument, InstrumentKind
from mullerbox.cal.window import CalibrationWindow
from mullerbox.errors import BadInputError, NotFoundError
from mullerbox.programme.schedule import Frequency
from mullerbox.props.kind import PropertyKind
from mullerbox.props.result import Result
from mullerbox.store.connection import Book
from mullerbox.store.instrument_repo import save_instrument
from mullerbox.store.programme_repo import (
    changes,
    is_on_programme,
    last_tested,
    load_schedule,
    set_interval,
)
from mullerbox.store.result_repo import Sample, save_result, save_sample
from mullerbox.units.percent import Percent
from tests.store.helpers import migrated_book

COMP = PropertyKind.COMPACTABILITY
LOI = PropertyKind.LOI
JAN = date(2025, 1, 6)
JUNE = date(2025, 6, 2)


@pytest.fixture
def book() -> Iterator[Book]:
    with migrated_book() as opened:
        yield opened


class TestSettingIntervals:
    def test_a_new_property_goes_on_the_programme(self, book: Book) -> None:
        set_interval(book, COMP, Frequency.EVERY_SHIFT, JAN, "line critical")
        assert is_on_programme(book, COMP)
        assert load_schedule(book).frequency_of(COMP) is Frequency.EVERY_SHIFT

    def test_an_empty_programme_is_refused(self, book: Book) -> None:
        with pytest.raises(NotFoundError, match="testing programme"):
            load_schedule(book)

    def test_several_properties(self, book: Book) -> None:
        set_interval(book, COMP, Frequency.EVERY_SHIFT, JAN, "line critical")
        set_interval(book, LOI, Frequency.MONTHLY, JAN, "slow to move")
        assert load_schedule(book).covers == {COMP, LOI}


class TestTheChangeTrail:
    def test_a_move_is_logged(self, book: Book) -> None:
        set_interval(book, LOI, Frequency.MONTHLY, JAN, "slow to move")
        set_interval(book, LOI, Frequency.QUARTERLY, JUNE, "in control all year")
        trail = changes(book, LOI)
        assert len(trail) == 1
        when, was, became, because = trail[0]
        assert when == JUNE
        assert was == "MONTHLY"
        assert became == "QUARTERLY"
        assert because == "in control all year"

    def test_the_first_setting_is_not_a_change(self, book: Book) -> None:
        set_interval(book, LOI, Frequency.MONTHLY, JAN, "slow to move")
        assert changes(book, LOI) == []

    def test_setting_it_to_what_it_already_is_logs_nothing(self, book: Book) -> None:
        set_interval(book, LOI, Frequency.MONTHLY, JAN, "slow to move")
        set_interval(book, LOI, Frequency.MONTHLY, JUNE, "reviewed, no change")
        assert changes(book, LOI) == []

    def test_the_trail_is_oldest_first(self, book: Book) -> None:
        set_interval(book, LOI, Frequency.MONTHLY, JAN, "a")
        set_interval(book, LOI, Frequency.QUARTERLY, date(2025, 3, 1), "b")
        set_interval(book, LOI, Frequency.WEEKLY, JUNE, "c")
        assert [w for w, _, _, _ in changes(book, LOI)] == [date(2025, 3, 1), JUNE]

    def test_a_reason_is_required(self, book: Book) -> None:
        with pytest.raises(BadInputError, match="records why it was made"):
            set_interval(book, LOI, Frequency.MONTHLY, JAN, "   ")

    def test_a_property_never_moved_has_no_trail(self, book: Book) -> None:
        assert changes(book, COMP) == []


class TestLastTested:
    def test_it_comes_off_the_results(self, book: Book) -> None:
        save_instrument(
            book,
            Instrument(
                tag="RAM-1",
                kind=InstrumentKind.COMPACTABILITY,
                windows=(CalibrationWindow(JAN, date(2026, 1, 6), "C-1"),),
            ),
        )
        for sample_id, when in (("S-1", JAN), ("S-2", JUNE)):
            save_sample(
                book,
                Sample(sample_id=sample_id, taken_on=when, point="m", system_name="t"),
            )
            save_result(
                book,
                Result(
                    kind=COMP,
                    reading=Percent(41),
                    instrument_tag="RAM-1",
                    tested_on=when,
                    sample_id=sample_id,
                ),
            )
        assert last_tested(book)[COMP] == JUNE

    def test_a_property_never_tested_is_absent(self, book: Book) -> None:
        assert last_tested(book) == {}


class TestCorruptRows:
    def test_an_unknown_property_is_refused(self, book: Book) -> None:
        set_interval(book, COMP, Frequency.EVERY_SHIFT, JAN, "line critical")
        book.execute("UPDATE test_interval SET property = 'STICKINESS'")
        with pytest.raises(BadInputError, match="as a property, which is not one of"):
            load_schedule(book)

    def test_an_unknown_frequency_is_refused(self, book: Book) -> None:
        set_interval(book, COMP, Frequency.EVERY_SHIFT, JAN, "line critical")
        book.execute("UPDATE test_interval SET frequency = 'FORTNIGHTLY'")
        with pytest.raises(BadInputError, match="as a testing frequency, which is not one of"):
            load_schedule(book)

    def test_a_stray_property_in_the_results_is_skipped(self, book: Book) -> None:
        assert last_tested(book) == {}


class TestGuards:
    def test_the_arguments_are_checked(self, book: Book) -> None:
        bad: Any = "comp"
        with pytest.raises(BadInputError, match="property kind is expected"):
            set_interval(book, bad, Frequency.DAILY, JAN, "x")
        with pytest.raises(BadInputError, match="a frequency is expected"):
            set_interval(book, COMP, bad, JAN, "x")
        with pytest.raises(BadInputError, match="a date is expected"):
            set_interval(book, COMP, Frequency.DAILY, bad, "x")
        with pytest.raises(BadInputError, match="property kind is expected"):
            changes(book, bad)
        with pytest.raises(BadInputError, match="property kind is expected"):
            is_on_programme(book, bad)
