"""The command line: one entry point, one group per part of the shop."""

from __future__ import annotations

from mullerbox.cli import bench_cmd as _bench
from mullerbox.cli import catalogue as _catalogue
from mullerbox.cli import cores as _cores
from mullerbox.cli import costing as _costing
from mullerbox.cli import doctor as _doctor
from mullerbox.cli import exporting as _exporting
from mullerbox.cli import importing as _importing
from mullerbox.cli import lab as _lab
from mullerbox.cli import materials as _materials
from mullerbox.cli import mulling as _mulling
from mullerbox.cli import patterns as _patterns
from mullerbox.cli import production as _production
from mullerbox.cli import programme_cmd as _programme
from mullerbox.cli import reports as _reports
from mullerbox.cli import screens_cmd as _screens
from mullerbox.cli import specs as _specs
from mullerbox.cli import systems as _systems
from mullerbox.cli.main import main

# Importing the group modules is what registers their commands on the root.
_REGISTERED = (
    _bench,
    _catalogue,
    _cores,
    _costing,
    _doctor,
    _exporting,
    _importing,
    _lab,
    _materials,
    _mulling,
    _patterns,
    _production,
    _programme,
    _reports,
    _screens,
    _specs,
    _systems,
)

__all__ = ["main"]
