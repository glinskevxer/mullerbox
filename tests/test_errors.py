from __future__ import annotations

import pytest

from mullerbox.errors import (
    BadInputError,
    ConfigError,
    DuplicateError,
    NotFoundError,
    RuleError,
    SandError,
    StateError,
)

EVERY = [BadInputError, ConfigError, DuplicateError, NotFoundError, RuleError, StateError]


@pytest.mark.parametrize("cls", EVERY)
def test_everything_descends_from_the_one_base(cls: type[SandError]) -> None:
    assert issubclass(cls, SandError)


def test_the_base_is_an_exception() -> None:
    assert issubclass(SandError, Exception)


def test_not_found_names_the_kind_and_the_key() -> None:
    exc = NotFoundError("screen series", "AFS-11")
    assert exc.kind == "screen series"
    assert exc.key == "AFS-11"
    assert "screen series" in str(exc)
    assert "AFS-11" in str(exc)


def test_duplicate_names_the_kind_and_the_key() -> None:
    exc = DuplicateError("instrument", "GCS-2")
    assert exc.kind == "instrument"
    assert exc.key == "GCS-2"
    assert "already on the book" in str(exc)


def test_a_caller_can_catch_the_base_alone() -> None:
    with pytest.raises(SandError):
        raise RuleError("the retained masses do not close")


@pytest.mark.parametrize("cls", EVERY)
def test_each_kind_is_distinct(cls: type[SandError]) -> None:
    others = [c for c in EVERY if c is not cls]
    assert not any(issubclass(cls, other) for other in others)
