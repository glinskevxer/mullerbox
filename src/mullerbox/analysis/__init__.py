"""Reading a run of results as a process rather than as a list of numbers."""

from __future__ import annotations

from mullerbox.analysis.capability import Capability, capability_of
from mullerbox.analysis.control import ControlChart, chart_of
from mullerbox.analysis.summary import State, Summary, summarise, worst_first
from mullerbox.analysis.trend import Trend, project, trend_of

__all__ = [
    "Capability",
    "ControlChart",
    "State",
    "Summary",
    "Trend",
    "capability_of",
    "chart_of",
    "project",
    "summarise",
    "trend_of",
    "worst_first",
]
