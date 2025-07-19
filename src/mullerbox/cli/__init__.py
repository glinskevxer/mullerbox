"""The command line: one entry point, one group per part of the shop."""

from __future__ import annotations

from mullerbox.cli import catalogue as _catalogue
from mullerbox.cli.main import main

# Importing the group modules is what registers their commands on the root.
_REGISTERED = (_catalogue,)

__all__ = ["main"]
