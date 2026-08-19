from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest

from mullerbox.cal.instrument import Instrument, InstrumentKind
from mullerbox.cal.window import CalibrationWindow
from mullerbox.errors import BadInputError
from mullerbox.props.kind import PropertyKind
from mullerbox.props.result import Result
from mullerbox.store.connection import Book
from mullerbox.store.instrument_repo import save_instrument
from mullerbox.store.reading_repo import gather, uncounted
from mullerbox.store.result_repo import Sample, save_result, save_sample
from mullerbox.units.percent import Percent
from mullerbox.units.scales import Permeability
from tests.store.helpers import migrated_book

GOOD = CalibrationWindow(date(2025, 1, 6), date(2025, 4, 6), "C-1")
LATE = CalibrationWindow(date(2025, 4, 20), date(2025, 7, 20), "C-2")
CUTOFF = date(2025, 5, 1)


@pytest.fixture
def book() -> Iterator[Book]:
    with migrated_book() as opened:
        save_instrument(
            opened,
            Instrument(tag="RAM-1", kind=InstrumentKind.COMPACTABILITY, windows=(GOOD, LATE)),
        )
        yield opened


def add(book: Book, sample_id: str, when: date, reading: str) -> None:
    save_sample(book, Sample(sample_id=sample_id, taken_on=when, point="muller", system_name="two"))
    save_result(
        book,
        Result(
            kind=PropertyKind.COMPACTABILITY,
            reading=Percent(reading),
            instrument_tag="RAM-1",
            tested_on=when,
            sample_id=sample_id,
        ),
    )


class TestGathering:
    def test_it_takes_the_most_recent_countable_reading(self, book: Book) -> None:
        add(book, "S-1", date(2025, 2, 1), "40")
        add(book, "S-2", date(2025, 3, 1), "42")
        found = gather(book, CUTOFF)
        assert found.readings[PropertyKind.COMPACTABILITY] == Percent(42)

    def test_a_reading_in_a_lapse_falls_back_to_an_older_valid_one(self, book: Book) -> None:
        add(book, "S-1", date(2025, 3, 1), "40")
        add(book, "S-2", date(2025, 4, 10), "44")
        found = gather(book, CUTOFF)
        assert found.readings[PropertyKind.COMPACTABILITY] == Percent(40)

    def test_it_ignores_readings_after_the_cutoff(self, book: Book) -> None:
        add(book, "S-1", date(2025, 2, 1), "40")
        add(book, "S-2", date(2025, 6, 1), "44")
        found = gather(book, CUTOFF)
        assert found.readings[PropertyKind.COMPACTABILITY] == Percent(40)

    def test_a_property_never_tested_is_absent(self, book: Book) -> None:
        add(book, "S-1", date(2025, 2, 1), "40")
        assert PropertyKind.PERMEABILITY not in gather(book, CUTOFF).readings

    def test_a_property_only_ever_tested_in_a_lapse_is_absent(self, book: Book) -> None:
        add(book, "S-1", date(2025, 4, 10), "44")
        assert gather(book, CUTOFF).results == {}

    def test_an_empty_book_gathers_nothing(self, book: Book) -> None:
        assert len(gather(book, CUTOFF)) == 0

    def test_it_wants_a_date(self, book: Book) -> None:
        bad: Any = "2025-05-01"
        with pytest.raises(BadInputError, match="a date is expected"):
            gather(book, bad)


class TestAge:
    def test_it_counts_days_back_from_the_cutoff(self, book: Book) -> None:
        add(book, "S-1", date(2025, 3, 1), "40")
        assert gather(book, date(2025, 3, 8)).age_of(PropertyKind.COMPACTABILITY) == 7

    def test_a_week_old_reading_is_not_stale(self, book: Book) -> None:
        add(book, "S-1", date(2025, 3, 1), "40")
        assert gather(book, date(2025, 3, 8)).stale == ()

    def test_older_than_a_week_is_stale(self, book: Book) -> None:
        add(book, "S-1", date(2025, 3, 1), "40")
        found = gather(book, date(2025, 3, 9))
        assert found.stale == (PropertyKind.COMPACTABILITY,)

    def test_asking_the_age_of_something_absent_is_refused(self, book: Book) -> None:
        with pytest.raises(BadInputError, match="no compactability reading in force"):
            gather(book, CUTOFF).age_of(PropertyKind.COMPACTABILITY)


class TestUncounted:
    def test_a_reading_in_a_lapse_is_listed(self, book: Book) -> None:
        add(book, "S-1", date(2025, 4, 10), "44")
        found = uncounted(book, CUTOFF)
        assert [r.sample_id for r in found] == ["S-1"]

    def test_a_good_reading_is_not(self, book: Book) -> None:
        add(book, "S-1", date(2025, 2, 1), "40")
        assert uncounted(book, CUTOFF) == []

    def test_a_reading_off_an_unknown_instrument_is_listed(self, book: Book) -> None:
        save_sample(
            book,
            Sample(sample_id="S-9", taken_on=date(2025, 2, 1), point="m", system_name="t"),
        )
        save_instrument(book, Instrument(tag="RAM-9", kind=InstrumentKind.COMPACTABILITY))
        save_result(
            book,
            Result(
                kind=PropertyKind.COMPACTABILITY,
                reading=Percent(41),
                instrument_tag="RAM-9",
                tested_on=date(2025, 2, 1),
                sample_id="S-9",
            ),
        )
        assert [r.sample_id for r in uncounted(book, CUTOFF)] == ["S-9"]

    def test_it_wants_a_date(self, book: Book) -> None:
        bad: Any = "2025-05-01"
        with pytest.raises(BadInputError, match="a date is expected"):
            uncounted(book, bad)


class TestAReadingWhoseInstrumentIsTheWrongKind:
    """A permeability read off a rammer is not a slightly odd number."""

    def perm_on(self, book: Book, tag: str, kind: InstrumentKind) -> None:
        covering = CalibrationWindow(date(2025, 1, 6), date(2025, 4, 6), f"C-{tag}")
        save_instrument(book, Instrument(tag=tag, kind=kind, windows=(covering,)))
        save_sample(
            book,
            Sample(sample_id="S-9", taken_on=date(2025, 2, 3), point="muller", system_name="two"),
        )
        save_result(
            book,
            Result(
                sample_id="S-9",
                kind=PropertyKind.PERMEABILITY,
                reading=Permeability(110),
                instrument_tag=tag,
                tested_on=date(2025, 2, 3),
            ),
        )

    def test_one_on_the_wrong_kind_does_not_count(self, book: Book) -> None:
        self.perm_on(book, "RAM-2", InstrumentKind.COMPACTABILITY)
        found = uncounted(book, date(2025, 3, 1))
        assert [r.instrument_tag for r in found] == ["RAM-2"]

    def test_one_on_the_right_kind_does(self, book: Book) -> None:
        self.perm_on(book, "PERM-1", InstrumentKind.PERMEABILITY)
        assert uncounted(book, date(2025, 3, 1)) == []

    def test_an_unknown_instrument_cannot_get_onto_the_book_at_all(self, book: Book) -> None:
        """The branch above it guards against a row the schema will not accept."""
        save_sample(
            book,
            Sample(sample_id="S-8", taken_on=date(2025, 2, 3), point="muller", system_name="two"),
        )
        with pytest.raises(Exception, match="FOREIGN KEY"):
            save_result(
                book,
                Result(
                    sample_id="S-8",
                    kind=PropertyKind.PERMEABILITY,
                    reading=Permeability(110),
                    instrument_tag="NOBODY",
                    tested_on=date(2025, 2, 3),
                ),
            )
