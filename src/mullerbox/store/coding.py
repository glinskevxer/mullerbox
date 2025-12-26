"""Turning what is on the book back into the types the package works in.

Every repository stores an enum as its member name and has to decode it on the
way back. Ten of those decoders had grown, one per enum per module, and they had
already drifted: some said "which is not one", some named the enum, and one
said "which is not a kind" about an instrument. An operator reading a corrupt
book gets a different sentence depending on which table the corruption is in,
which makes the corruption harder to place rather than easier.

There is one decoder now and it names the enum every time, because that is the
one piece of information the reader does not already have.

**A decode failure is a BadInputError, not a ConfigError**, and the distinction
is deliberate. The book is not misconfigured; it holds a value that is not a
member, which is a data fault and reads to the caller as bad input arriving from
storage rather than from a user. The command layer prints both the same way, so
the choice only matters to code that catches one and not the other.

**Values are stored as ``name``, never as ``value``.** The name is the code's
own identifier and changing it is a visible edit; the value is a human label and
gets reworded. A book keyed on labels breaks the day somebody improves one.
"""

from __future__ import annotations

from enum import Enum
from typing import TypeVar

from mullerbox.errors import BadInputError

_Member = TypeVar("_Member", bound=Enum)


def encode(member: Enum) -> str:
    """The string a book stores for an enum member."""
    if not isinstance(member, Enum):
        raise BadInputError("only enum members are encoded")
    return member.name


def decode(name: object, members: type[_Member], what: str) -> _Member:
    """Turn a stored name back into its member, naming the enum on a failure.

    ``what`` is the enum as the shop would say it: "a pattern class", "a lot
    state". It goes into the message, which is the whole reason the parameter
    exists rather than the function reading ``members.__name__``: ``LotState``
    means nothing to somebody reading a log at two in the morning.
    """
    if not isinstance(name, str):
        raise BadInputError(f"the book carries {name!r} where {what} should be, which is not text")
    try:
        return members[name]
    except KeyError:
        known = ", ".join(sorted(m.name for m in members))
        raise BadInputError(
            f"the book carries {name!r} as {what}, which is not one of {known}"
        ) from None


def decode_optional(name: object, members: type[_Member], what: str) -> _Member | None:
    """The same, but a stored NULL comes back as nothing rather than a refusal."""
    if name is None:
        return None
    return decode(name, members, what)


__all__ = ["decode", "decode_optional", "encode"]
