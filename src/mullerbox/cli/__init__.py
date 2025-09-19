"""The command line: one entry point, one group per part of the shop."""

from __future__ import annotations

from mullerbox.cli import catalogue as _catalogue
from mullerbox.cli import importing as _importing
from mullerbox.cli import lab as _lab
from mullerbox.cli import materials as _materials
from mullerbox.cli import reports as _reports
from mullerbox.cli import specs as _specs
from mullerbox.cli.main import main

# Importing the group modules is what registers their commands on the root.
_REGISTERED = (_catalogue, _importing, _lab, _materials, _reports, _specs)

__all__ = ["main"]
