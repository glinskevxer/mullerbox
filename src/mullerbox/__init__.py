"""Green sand control for a grey iron foundry.

The package is layered so that the parts that only do arithmetic can be tested
without a database and without a clock. ``units`` and ``model`` know nothing
about storage, ``store`` knows nothing about the shop's rules, and the rule
modules take model objects in and give model objects back.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
