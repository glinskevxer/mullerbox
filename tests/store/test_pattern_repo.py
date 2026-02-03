from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest

from mullerbox.errors import BadInputError, DuplicateError, NotFoundError, RuleError
from mullerbox.heat.pattern import Pattern
from mullerbox.spec.pattern import PatternClass
from mullerbox.store.connection import Book
from mullerbox.store.pattern_repo import (
    load_pattern,
    load_register,
    pattern_exists,
    retire,
    save_pattern,
    update_pattern,
)
from mullerbox.units.bulk import Pounds
from tests.store.helpers import migrated_book


@pytest.fixture
def book() -> Iterator[Book]:
    with migrated_book() as opened:
        save_pattern(opened, pattern())
        yield opened


def pattern(
    pattern_id: str = "P-1",
    cubic_feet: str = "8.0",
    cavities: int = 2,
    weight: str = "60",
    cls: PatternClass = PatternClass.MEDIUM_JOBBING,
) -> Pattern:
    return Pattern(
        pattern_id=pattern_id,
        name="bearing housing",
        pattern_class=cls,
        flask_cubic_feet=Decimal(cubic_feet),
        cavities=cavities,
        casting_weight=Pounds(weight),
    )


class TestRoundTrip:
    def test_a_pattern_comes_back_identical(self, book: Book) -> None:
        assert load_pattern(book, "P-1") == pattern()

    def test_the_expected_ratio_survives(self, book: Book) -> None:
        assert load_pattern(book, "P-1").expected_ratio == pattern().expected_ratio

    def test_the_register_is_in_identifier_order(self, book: Book) -> None:
        save_pattern(book, pattern("P-3"))
        save_pattern(book, pattern("P-2"))
        register = load_register(book)
        assert [p.pattern_id for p in register.patterns] == ["P-1", "P-2", "P-3"]

    def test_an_empty_register(self, book: Book) -> None:
        retire(book, "P-1")
        assert len(load_register(book)) == 0


class TestCorrectingAMeasurement:
    def test_a_flask_measured_wrong_can_be_corrected(self, book: Book) -> None:
        update_pattern(book, pattern(cubic_feet="9.5"))
        assert load_pattern(book, "P-1").flask_cubic_feet == Decimal("9.5")

    def test_the_ratio_moves_with_it(self, book: Book) -> None:
        before = load_pattern(book, "P-1").expected_ratio
        update_pattern(book, pattern(cubic_feet="12.0"))
        assert load_pattern(book, "P-1").expected_ratio > before

    def test_updating_something_absent_is_refused(self, book: Book) -> None:
        with pytest.raises(NotFoundError, match="pattern"):
            update_pattern(book, pattern("P-9"))


class TestTheClassCannotBeMoved:
    def test_changing_it_is_refused(self, book: Book) -> None:
        with pytest.raises(RuleError, match="retire it and register a new one"):
            update_pattern(book, pattern(cls=PatternClass.THIN_WALL))

    def test_the_refusal_names_the_registered_class(self, book: Book) -> None:
        with pytest.raises(RuleError, match="registered as medium jobbing"):
            update_pattern(book, pattern(cls=PatternClass.THIN_WALL))

    def test_the_pattern_is_left_alone(self, book: Book) -> None:
        with pytest.raises(RuleError):
            update_pattern(book, pattern(cls=PatternClass.THIN_WALL, cubic_feet="99"))
        assert load_pattern(book, "P-1").flask_cubic_feet == Decimal("8.0")

    def test_retiring_and_registering_afresh_is_the_way(self, book: Book) -> None:
        retire(book, "P-1")
        save_pattern(book, pattern("P-1", cls=PatternClass.THIN_WALL))
        assert load_pattern(book, "P-1").pattern_class is PatternClass.THIN_WALL


class TestBookkeeping:
    def test_saving_twice_is_refused(self, book: Book) -> None:
        with pytest.raises(DuplicateError, match="pattern"):
            save_pattern(book, pattern())

    def test_loading_something_absent(self, book: Book) -> None:
        with pytest.raises(NotFoundError, match="pattern"):
            load_pattern(book, "P-9")

    def test_exists_and_retire(self, book: Book) -> None:
        assert pattern_exists(book, "P-1")
        retire(book, "P-1")
        assert not pattern_exists(book, "P-1")

    def test_retiring_something_absent(self, book: Book) -> None:
        with pytest.raises(NotFoundError, match="pattern"):
            retire(book, "P-9")

    def test_it_wants_a_pattern(self, book: Book) -> None:
        bad: Any = "P-1"
        with pytest.raises(BadInputError, match="a pattern is expected"):
            save_pattern(book, bad)
        with pytest.raises(BadInputError, match="a pattern is expected"):
            update_pattern(book, bad)

    def test_a_corrupt_class_is_refused(self, book: Book) -> None:
        book.execute("UPDATE pattern SET pattern_class = 'PROTOTYPE'")
        with pytest.raises(BadInputError, match="which is not one of"):
            load_pattern(book, "P-1")
