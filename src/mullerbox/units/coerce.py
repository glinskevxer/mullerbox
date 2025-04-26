"""One way in, for every quantity in the package.

Each unit module grew its own copy of "turn whatever the caller passed into a
Decimal", and the copies drifted. Two of them tested for ``bool`` before ``int``
and four did not, which matters more than it looks: ``bool`` is a subclass of
``int`` in Python, so ``Grams(True)`` quietly came back as one gram and
``Percent(True)`` as one percent. Neither is a value anybody meant to write, and
both came from the same place, a flag threaded through a call chain into a
numeric argument. That is exactly the fault a coercion layer exists to catch,
and half the coercion layer was letting it through.

There is one copy now. It takes the article with the noun, because the message
reads ``cannot read an aperture`` or ``cannot read a mass`` and building that
from the noun alone needs a vowel rule that is wrong for the interesting cases.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from mullerbox.errors import BadInputError


def to_decimal(
    value: object,
    what: str,
    *,
    prefixes: tuple[str, ...] = (),
    suffixes: tuple[str, ...] = (),
    strip_commas: bool = False,
) -> Decimal:
    """Read a Decimal off anything the shop might hand over.

    ``suffixes`` are unit spellings to tolerate at the end of a string, tried
    longest first so that ``lbs`` is not left as a stray ``s`` after ``lb``
    matched. ``prefixes`` does the same at the front, which is where a currency
    symbol lives: a unit written after the number and a symbol written before it
    are the same problem and it is worth only solving it once.

    Floats go through ``repr`` so a value that was typed as 12.005 quantises
    from 12.005 rather than from 12.004999999999999.
    """
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise BadInputError(f"cannot read {what} from a boolean")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(repr(value))
    if isinstance(value, str):
        text = value.strip().lower()
        for prefix in sorted(prefixes, key=len, reverse=True):
            if text.startswith(prefix):
                text = text[len(prefix) :].strip()
                break
        for suffix in sorted(suffixes, key=len, reverse=True):
            if text.endswith(suffix):
                text = text[: -len(suffix)].strip()
                break
        if strip_commas:
            text = text.replace(",", "")
        try:
            return Decimal(text)
        except InvalidOperation:
            raise BadInputError(f"{value!r} is not {what}") from None
    raise BadInputError(f"cannot read {what} from {type(value).__name__}")


def to_int(value: object, what: str) -> int:
    """Read a whole number, refusing anything that would have to be rounded."""
    if isinstance(value, bool):
        raise BadInputError(f"cannot read {what} from a boolean")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            raise BadInputError(f"{value!r} is not {what}") from None
    raise BadInputError(f"cannot read {what} from {type(value).__name__}")


__all__ = ["to_decimal", "to_int"]
