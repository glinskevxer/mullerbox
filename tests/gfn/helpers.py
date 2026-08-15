from __future__ import annotations

from mullerbox.gfn.distribution import Distribution, grade
from mullerbox.gfn.fineness import fineness_of
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


def distribution_of(**held: str) -> Distribution:
    """A graded distribution from the screens named, everything else zero.

    Three test modules had grown their own copy of this three line chain, and
    the copies had already drifted on the charged mass, so a sand that was
    65 GFN in one module was 65 GFN in another for a different reason. The
    charge is fixed here because the fineness is a weighted average over the
    retained masses and the charge is what it is weighted against.
    """
    return grade(fineness_of(analysis_of(sheet(**held), CHARGED)))


# The bench charges fifty grams, and every helper here weighs against that.
CHARGED = "50.00"
