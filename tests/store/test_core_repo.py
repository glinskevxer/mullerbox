from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Any

import pytest

from mullerbox.core.batch import CoreBatch
from mullerbox.core.binder import Binder, BinderSystem
from mullerbox.core.testing import TensileResult, batch_verdict
from mullerbox.errors import BadInputError, DuplicateError, NotFoundError
from mullerbox.store.connection import Book
from mullerbox.store.core_repo import (
    list_systems,
    load_batch,
    load_system,
    load_tensiles,
    save_batch,
    save_system,
    save_tensile,
    system_exists,
    update_batch,
)
from mullerbox.units.bulk import Pounds
from mullerbox.units.duration import Seconds
from mullerbox.units.percent import Percent
from mullerbox.units.pressure import Psi
from tests.store.helpers import migrated_book

MIXED = datetime(2025, 11, 20, 7, 30, 0)

SYSTEM = BinderSystem(
    binder=Binder.PHENOLIC_URETHANE,
    resin=Percent("1.2"),
    catalyst=Percent("0.06"),
    bench_life=Seconds(300),
    strip_time=Seconds(120),
    full_cure=Seconds(900),
    tensile_floor=Psi(180),
)


@pytest.fixture
def book() -> Iterator[Book]:
    with migrated_book() as opened:
        save_system(opened, "pep standard", SYSTEM)
        save_batch(opened, batch(), "pep standard")
        yield opened


def batch(charged: str = "400", blown: str = "0") -> CoreBatch:
    return CoreBatch(
        batch_id="CB-1",
        system=SYSTEM,
        mixed_at=MIXED,
        charged=Pounds(charged),
        blown=Pounds(blown),
    )


def tensile(specimen_id: str, age: int = 900, psi: str = "210") -> TensileResult:
    return TensileResult(
        specimen_id=specimen_id,
        system=SYSTEM,
        mixed_at=MIXED,
        broken_at=MIXED + timedelta(seconds=age),
        tensile=Psi(psi),
    )


class TestBinderSystems:
    def test_one_round_trips(self, book: Book) -> None:
        assert load_system(book, "pep standard") == SYSTEM

    def test_the_three_times_survive(self, book: Book) -> None:
        loaded = load_system(book, "pep standard")
        assert loaded.bench_life == Seconds(300)
        assert loaded.strip_time == Seconds(120)
        assert loaded.full_cure == Seconds(900)

    def test_saving_twice_is_refused(self, book: Book) -> None:
        with pytest.raises(DuplicateError, match="binder system"):
            save_system(book, "pep standard", SYSTEM)

    def test_a_system_needs_a_name(self, book: Book) -> None:
        with pytest.raises(BadInputError, match="needs a name"):
            save_system(book, "  ", SYSTEM)

    def test_loading_something_absent(self, book: Book) -> None:
        with pytest.raises(NotFoundError, match="binder system"):
            load_system(book, "nothing")

    def test_listing_and_exists(self, book: Book) -> None:
        assert list_systems(book) == ["pep standard"]
        assert system_exists(book, "pep standard")
        assert not system_exists(book, "nothing")

    def test_an_unknown_binder_is_refused(self, book: Book) -> None:
        book.execute("UPDATE binder_system SET binder = 'EPOXY'")
        with pytest.raises(BadInputError, match="which is not one"):
            load_system(book, "pep standard")

    def test_it_wants_a_system(self, book: Book) -> None:
        bad: Any = "pep"
        with pytest.raises(BadInputError, match="binder system is expected"):
            save_system(book, "another", bad)


class TestBatches:
    def test_one_round_trips_with_its_system(self, book: Book) -> None:
        loaded = load_batch(book, "CB-1")
        assert loaded == batch()
        assert loaded.system == SYSTEM

    def test_blowing_is_written_back(self, book: Book) -> None:
        drawn = load_batch(book, "CB-1").blow(Pounds(100), MIXED + timedelta(seconds=60))
        update_batch(book, drawn)
        assert load_batch(book, "CB-1").remaining == Pounds(300)

    def test_a_batch_against_a_missing_system_is_refused(self, book: Book) -> None:
        with pytest.raises(NotFoundError, match="binder system"):
            save_batch(book, batch(), "nothing")

    def test_saving_twice_is_refused(self, book: Book) -> None:
        with pytest.raises(DuplicateError, match="core batch"):
            save_batch(book, batch(), "pep standard")

    def test_loading_something_absent(self, book: Book) -> None:
        with pytest.raises(NotFoundError, match="core batch"):
            load_batch(book, "CB-9")

    def test_updating_something_absent(self, book: Book) -> None:
        other = CoreBatch(batch_id="CB-9", system=SYSTEM, mixed_at=MIXED, charged=Pounds(100))
        with pytest.raises(NotFoundError, match="core batch"):
            update_batch(book, other)


class TestTensiles:
    def test_the_age_is_derived_from_the_batch(self, book: Book) -> None:
        save_tensile(book, "CB-1", "T-1", tensile("T-1", age=900))
        loaded = load_tensiles(book, "CB-1")[0]
        assert loaded.age == Seconds(900)
        assert loaded.at_full_cure

    def test_a_specimen_cannot_disagree_with_its_batch_about_the_binder(self, book: Book) -> None:
        save_tensile(book, "CB-1", "T-1", tensile("T-1"))
        assert load_tensiles(book, "CB-1")[0].system == load_batch(book, "CB-1").system

    def test_several_specimens_come_back_in_order(self, book: Book) -> None:
        save_tensile(book, "CB-1", "T-2", tensile("T-2", age=1000))
        save_tensile(book, "CB-1", "T-1", tensile("T-1", age=900))
        assert [t.specimen_id for t in load_tensiles(book, "CB-1")] == ["T-1", "T-2"]

    def test_the_batch_can_then_be_judged(self, book: Book) -> None:
        save_tensile(book, "CB-1", "T-1", tensile("T-1", psi="200"))
        save_tensile(book, "CB-1", "T-2", tensile("T-2", psi="220"))
        assert batch_verdict(load_tensiles(book, "CB-1")).startswith("passes")

    def test_a_specimen_against_a_missing_batch_is_refused(self, book: Book) -> None:
        with pytest.raises(NotFoundError, match="core batch"):
            save_tensile(book, "CB-9", "T-1", tensile("T-1"))

    def test_the_same_specimen_twice_is_refused(self, book: Book) -> None:
        save_tensile(book, "CB-1", "T-1", tensile("T-1"))
        with pytest.raises(DuplicateError, match="specimen"):
            save_tensile(book, "CB-1", "T-1", tensile("T-1"))

    def test_a_batch_with_no_specimens(self, book: Book) -> None:
        assert load_tensiles(book, "CB-1") == []

    def test_it_wants_a_result(self, book: Book) -> None:
        bad: Any = "210"
        with pytest.raises(BadInputError, match="tensile result is expected"):
            save_tensile(book, "CB-1", "T-1", bad)
