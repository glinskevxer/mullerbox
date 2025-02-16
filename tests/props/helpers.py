from __future__ import annotations

from datetime import date

from mullerbox.cal.instrument import Instrument, InstrumentKind
from mullerbox.cal.window import CalibrationWindow
from mullerbox.props.kind import PropertyKind, Reading
from mullerbox.props.result import Result

Q1 = CalibrationWindow(date(2025, 1, 6), date(2025, 4, 6), "C-1")
Q2 = CalibrationWindow(date(2025, 4, 20), date(2025, 7, 20), "C-2")


def rammer(*windows: CalibrationWindow) -> Instrument:
    return Instrument(tag="RAM-1", kind=InstrumentKind.COMPACTABILITY, windows=windows or (Q1,))


def usm(*windows: CalibrationWindow) -> Instrument:
    return Instrument(tag="USM-1", kind=InstrumentKind.STRENGTH, windows=windows or (Q1,))


def result(
    reading: Reading,
    kind: PropertyKind = PropertyKind.COMPACTABILITY,
    tag: str = "RAM-1",
    when: date = date(2025, 2, 3),
    sample: str = "S-100",
) -> Result:
    return Result(
        kind=kind,
        reading=reading,
        instrument_tag=tag,
        tested_on=when,
        sample_id=sample,
    )
