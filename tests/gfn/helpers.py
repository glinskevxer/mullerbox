from __future__ import annotations

from mullerbox.screens.analysis import SieveAnalysis
from mullerbox.screens.series import AFS_US_SERIES

LABELS = ["6", "12", "20", "30", "40", "50", "70", "100", "140", "200", "270", "PAN"]


def sheet(**held: str) -> dict[str, object]:
    """A bench sheet with every screen zero except the ones named."""
    out: dict[str, object] = dict.fromkeys(LABELS, "0.00")
    out.update(held)
    return out


def analysis_of(masses: dict[str, object], charged: str) -> SieveAnalysis:
    return SieveAnalysis.of(AFS_US_SERIES, charged, masses)
