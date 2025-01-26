"""Durations in whole seconds, which is the resolution a muller is set in.

Mull time is set on a timer in seconds and the difference between a 90 second
wet mull and a 120 second wet mull is the difference between developed bond and
undeveloped bond. Holding it as a float invites a 89.99999 that formats as 90
and compares as less, so it is an integer.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from functools import total_ordering
from typing import Any

from mullerbox.errors import BadInputError

# A muller cycle over half an hour is a jammed timer, not a cycle.
MAX_SECONDS = 1800


def _seconds_from(value: object) -> int:
    if isinstance(value, bool):
        raise BadInputError("cannot read a duration from a boolean")
    if isinstance(value, Seconds):
        return value.value
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip().lower().removesuffix("s").strip()
        if ":" in text:
            parts = text.split(":")
            if len(parts) != 2:
                raise BadInputError(f"{value!r} is not a duration")
            try:
                minutes, secs = int(parts[0]), int(parts[1])
            except ValueError:
                raise BadInputError(f"{value!r} is not a duration") from None
            if secs < 0 or secs > 59:
                raise BadInputError(f"{value!r} has more than sixty seconds in a minute")
            return minutes * 60 + secs
        try:
            return int(text)
        except ValueError:
            raise BadInputError(f"{value!r} is not a duration") from None
    raise BadInputError(f"cannot read a duration from {type(value).__name__}")


@total_ordering
@dataclass(frozen=True, init=False, eq=False)
class Seconds:
    """A whole number of seconds."""

    value: int

    def __init__(self, value: object = 0) -> None:
        secs = _seconds_from(value)
        if secs < 0:
            raise BadInputError("a duration cannot be negative")
        if secs > MAX_SECONDS:
            raise BadInputError(f"{secs} s is longer than any muller cycle")
        object.__setattr__(self, "value", secs)

    @classmethod
    def zero(cls) -> Seconds:
        return cls(0)

    @classmethod
    def of_minutes(cls, minutes: object) -> Seconds:
        if isinstance(minutes, bool) or not isinstance(minutes, int):
            raise BadInputError("minutes have to be a whole number")
        return cls(minutes * 60)

    @property
    def minutes(self) -> Decimal:
        return (Decimal(self.value) / 60).quantize(Decimal("0.01"))

    @property
    def is_zero(self) -> bool:
        return self.value == 0

    def __add__(self, other: object) -> Seconds:
        if not isinstance(other, Seconds):
            return NotImplemented
        return Seconds(self.value + other.value)

    def __sub__(self, other: object) -> Seconds:
        if not isinstance(other, Seconds):
            return NotImplemented
        if other.value > self.value:
            raise BadInputError("subtracting that leaves a negative duration")
        return Seconds(self.value - other.value)

    def __str__(self) -> str:
        minutes, secs = divmod(self.value, 60)
        if minutes == 0:
            return f"{secs}s"
        return f"{minutes}:{secs:02d}"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Seconds):
            return self.value == other.value
        return NotImplemented

    def __hash__(self) -> int:
        return hash(("Seconds", self.value))

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Seconds):
            return bool(self.value < other.value)
        return NotImplemented


__all__ = ["MAX_SECONDS", "Seconds"]
