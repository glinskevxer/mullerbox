"""Turning what the operator typed into what the package works in.

Six command modules had grown their own copy of "read a date off the command
line", and the copies had already started to differ: some stripped surrounding
space and some did not, and two of them named a different format in the error.
An operator who types a date with spaces around it gets a refusal from one
command and a date from another, which is the kind of inconsistency that makes
people stop trusting the tool rather than report a bug.

There is one copy now, and the error messages name the format because that is
the only useful thing to say to somebody who has just typed one wrong.

Enum lookups list the real members in the refusal. A command line is a discovery
surface: the person who typed ``strength`` when the enum says ``STRENGTH`` and
the person who has no idea what the kinds are get the same message, and it
serves both.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import TypeVar

from mullerbox.errors import BadInputError

_Member = TypeVar("_Member", bound=Enum)

DATE_FORMAT = "yyyy-mm-dd"


def today() -> date:
    """The one place the command line reads the clock.

    Two commands default a date to today and each read the clock where it
    stood. That was two reads, both of them inside a command function
    where nothing can reach them, and it made the default behaviour of those
    commands the only part of the surface with no test.

    Everything below this line takes a date as an argument, which is the habit
    the rest of the package keeps: a question about a moment takes the moment.
    This function is the seam where that habit meets a real clock, and having
    exactly one of them means the default path can be exercised on any day of
    the year rather than on whichever day the suite happens to run.
    """
    return date.today()


def date_or_today(text: str | None, what: str = "a date") -> date:
    """An option's date, or today when the option was not given."""
    return read_date(text, what) if text else today()


def read_date(text: str, what: str = "a date") -> date:
    """Read an ISO date, naming the format on a refusal."""
    if not isinstance(text, str):
        raise BadInputError(f"{what} is text")
    try:
        return date.fromisoformat(text.strip())
    except ValueError:
        raise BadInputError(f"{text!r} is not {what} in {DATE_FORMAT} form") from None


def read_decimal(text: str, what: str) -> Decimal:
    """Read a bare number, naming what it was meant to be."""
    if not isinstance(text, str):
        raise BadInputError(f"a {what} is text on the command line")
    try:
        return Decimal(text.strip())
    except InvalidOperation:
        raise BadInputError(f"{text!r} is not a {what}") from None


def read_member(text: str, members: type[_Member], what: str) -> _Member:
    """Read an enum member by name, listing the real ones on a refusal.

    Separators are levelled first, so ``sieve shaker``, ``sieve-shaker`` and
    ``SIEVE_SHAKER`` all reach the same member. Operators type all three and
    none of them is wrong.
    """
    if not isinstance(text, str):
        raise BadInputError(f"a {what} is text on the command line")
    key = text.strip().upper().replace("-", "_").replace(" ", "_")
    try:
        return members[key]
    except KeyError:
        known = ", ".join(sorted(m.name.lower() for m in members))
        raise BadInputError(f"{text!r} is not {what}; try {known}") from None


__all__ = ["DATE_FORMAT", "date_or_today", "read_date", "read_decimal", "read_member", "today"]
