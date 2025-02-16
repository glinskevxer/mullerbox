"""The property tests the sand lab runs, and what makes a result count."""

from __future__ import annotations

from mullerbox.props.kind import Direction, PropertyKind, Reading, parse_property
from mullerbox.props.result import Result, countable, latest_countable

__all__ = [
    "Direction",
    "PropertyKind",
    "Reading",
    "Result",
    "countable",
    "latest_countable",
    "parse_property",
]
