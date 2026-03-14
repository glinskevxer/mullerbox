from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest

from mullerbox.errors import BadInputError, DuplicateError, NotFoundError
from mullerbox.muller.history import RecordedCycle
from mullerbox.store.connection import Book
from mullerbox.store.cycle_repo import (
    cycle_exists,
    history_between,
    history_on,
    load_cycle,
    record_cycle,
)
from mullerbox.units.bulk import Pounds
from mullerbox.units.duration import Seconds
from tests.store.helpers import migrated_book

MONDAY = date(2026, 3, 16)
TUESDAY = date(2026, 3, 17)


@pytest.fixture
def book() -> Iterator[Book]:
    with migrated_book() as opened:
        yield opened


def cycle(
    batch_id: str = "B-1",
    dry: int = 60,
    wet: int = 120,
    discharged: bool = True,
) -> RecordedCycle:
    return RecordedCycle(
        batch_id=batch_id,
        dry_mull=Seconds(dry),
        wet_mull=Seconds(wet),
        bentonite=Pounds(140),
        water=Pounds(180),
        discharged=discharged,
    )


class TestItWritesWhatWasRecorded:
    def test_a_cycle_round_trips(self, book: Book) -> None:
        record_cycle(book, cycle(), MONDAY)
        assert load_cycle(book, "B-1") == cycle()

    def test_a_schedule_the_plan_would_refuse_is_stored_unchanged(self, book: Book) -> None:
        short = cycle("B-9", dry=5, wet=5)
        record_cycle(book, short, MONDAY)
        loaded = load_cycle(book, "B-9")
        assert loaded.dry_mull == Seconds(5)
        assert loaded.mulled_short

    def test_the_discharged_flag_survives_both_ways(self, book: Book) -> None:
        record_cycle(book, cycle("B-1", discharged=True), MONDAY)
        record_cycle(book, cycle("B-2", discharged=False), MONDAY)
        assert load_cycle(book, "B-1").discharged
        assert not load_cycle(book, "B-2").discharged

    def test_the_masses_survive_exactly(self, book: Book) -> None:
        record_cycle(book, cycle(), MONDAY)
        assert load_cycle(book, "B-1").water == Pounds(180)


class TestHistories:
    def test_a_day_gathers_its_cycles(self, book: Book) -> None:
        record_cycle(book, cycle("B-1"), MONDAY)
        record_cycle(book, cycle("B-2"), MONDAY)
        record_cycle(book, cycle("B-3"), TUESDAY)
        assert len(history_on(book, MONDAY)) == 2

    def test_a_quiet_day_gathers_nothing(self, book: Book) -> None:
        assert len(history_on(book, MONDAY)) == 0

    def test_a_span_covers_both_days(self, book: Book) -> None:
        record_cycle(book, cycle("B-1"), MONDAY)
        record_cycle(book, cycle("B-3"), TUESDAY)
        assert len(history_between(book, MONDAY, TUESDAY)) == 2

    def test_a_span_is_inclusive_at_both_ends(self, book: Book) -> None:
        record_cycle(book, cycle("B-1"), MONDAY)
        assert len(history_between(book, MONDAY, MONDAY)) == 1

    def test_a_backwards_span_is_refused(self, book: Book) -> None:
        with pytest.raises(BadInputError, match="which is backwards"):
            history_between(book, TUESDAY, MONDAY)

    def test_the_history_can_then_be_read(self, book: Book) -> None:
        for n in range(5):
            record_cycle(book, cycle(f"S-{n}", wet=5), MONDAY)
        found = history_on(book, MONDAY)
        assert found.is_running_short
        assert any("outrunning the muller" in x for x in found.findings(Pounds(180)))


class TestBookkeeping:
    def test_the_same_batch_twice_is_refused(self, book: Book) -> None:
        record_cycle(book, cycle(), MONDAY)
        with pytest.raises(DuplicateError, match="recorded cycle"):
            record_cycle(book, cycle(), TUESDAY)

    def test_loading_something_absent(self, book: Book) -> None:
        with pytest.raises(NotFoundError, match="recorded cycle"):
            load_cycle(book, "B-9")

    def test_exists(self, book: Book) -> None:
        assert not cycle_exists(book, "B-1")
        record_cycle(book, cycle(), MONDAY)
        assert cycle_exists(book, "B-1")

    def test_the_arguments_are_checked(self, book: Book) -> None:
        bad: Any = "B-1"
        with pytest.raises(BadInputError, match="recorded cycle is expected"):
            record_cycle(book, bad, MONDAY)
        with pytest.raises(BadInputError, match="a cycle is dated"):
            record_cycle(book, cycle(), bad)
        with pytest.raises(BadInputError, match="a date is expected"):
            history_on(book, bad)
        with pytest.raises(BadInputError, match="two dates are expected"):
            history_between(book, bad, MONDAY)
