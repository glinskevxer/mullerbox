"""The quantities the sand lab measures in.

Nothing in here knows about storage or about the lab's rules. The types exist so
that a retained mass and a percentage cannot be added together by accident, and
so that every number that reaches a control chart has been through one rounding
policy rather than whichever one the caller happened to feel like.
"""

from __future__ import annotations

from mullerbox.units.duration import Seconds
from mullerbox.units.mass import Grams
from mullerbox.units.mesh import Mesh
from mullerbox.units.percent import Percent, Points
from mullerbox.units.pressure import Psi, WetTensile
from mullerbox.units.thermal import Temperature

__all__ = [
    "Grams",
    "Mesh",
    "Percent",
    "Points",
    "Psi",
    "Seconds",
    "Temperature",
    "WetTensile",
]
