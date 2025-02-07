"""Lab instruments and the calibration windows that decide whether they count."""

from __future__ import annotations

from mullerbox.cal.instrument import Instrument, InstrumentKind
from mullerbox.cal.window import CalibrationWindow

__all__ = ["CalibrationWindow", "Instrument", "InstrumentKind"]
