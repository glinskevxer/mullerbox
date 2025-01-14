"""Every exception the package raises on purpose.

The hierarchy splits on why the caller is wrong rather than on which module
noticed, because the command layer is the only place that has to map these to
anything and it maps on the kind, not on the source. ``SandError`` is the only
class a caller ever has to catch; the CLI prints ``str(exc)`` and exits without
a traceback for anything descended from it, and lets everything else escape so
that a genuine bug still shows up as one.
"""

from __future__ import annotations


class SandError(Exception):
    """Base for everything raised deliberately."""


class BadInputError(SandError):
    """A value the caller supplied cannot be used at all.

    For arguments that are malformed rather than merely awkward: a negative
    retained mass, a compactability that is not a number, a mesh that is not on
    the series being used.
    """


class NotFoundError(SandError):
    """A record was looked up by key and is not on the book."""

    def __init__(self, kind: str, key: str) -> None:
        super().__init__(f"no {kind} on the book with key {key!r}")
        self.kind = kind
        self.key = key


class DuplicateError(SandError):
    """A record would collide with one already on the book."""

    def __init__(self, kind: str, key: str) -> None:
        super().__init__(f"{kind} {key!r} is already on the book")
        self.kind = kind
        self.key = key


class RuleError(SandError):
    """Well formed values that the lab's rules forbid.

    A sieve analysis whose retained masses do not close against the charged
    specimen mass, a property result from an instrument that was out of
    calibration, an addition worked out against a band that does not apply to
    the pattern class on the line. The message names the rule, not the field.
    """


class StateError(SandError):
    """A record is in the wrong state for what was asked of it.

    Discharging a muller cycle that was never charged, closing a shift with an
    unresolved defect on it, testing a specimen that was never rammed.
    """


class ConfigError(SandError):
    """The book itself is wrong: a missing migration, an unreadable schema."""


__all__ = [
    "BadInputError",
    "ConfigError",
    "DuplicateError",
    "NotFoundError",
    "RuleError",
    "SandError",
    "StateError",
]
