from __future__ import annotations

import pytest

from mullerbox.screens.analysis import SieveAnalysis
from mullerbox.screens.series import AFS_US_SERIES, ScreenSeries

# A well graded system sand piling on 50, 70 and 100. The masses sum to 50.00 g
# exactly so closure is not accidentally part of every other test.
SYSTEM_SAND: dict[str, object] = {
    "6": "0.00",
    "12": "0.00",
    "20": "0.05",
    "30": "0.35",
    "40": "2.10",
    "50": "8.40",
    "70": "15.60",
    "100": "13.20",
    "140": "6.30",
    "200": "2.55",
    "270": "1.05",
    "PAN": "0.40",
}


@pytest.fixture
def sheet() -> dict[str, object]:
    return dict(SYSTEM_SAND)


@pytest.fixture
def series() -> ScreenSeries:
    return AFS_US_SERIES


@pytest.fixture
def analysis(series: ScreenSeries) -> SieveAnalysis:
    return SieveAnalysis.of(series, "50.00", SYSTEM_SAND)
