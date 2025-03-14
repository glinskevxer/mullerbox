from __future__ import annotations

from datetime import date

from mullerbox.burnout.pour import Pour
from mullerbox.spec.pattern import PatternClass
from mullerbox.units.bulk import Pounds

WHEN = date(2025, 3, 10)


def pour(
    sand: str = "60000",
    metal: str = "10000",
    pattern: PatternClass = PatternClass.MEDIUM_JOBBING,
    when: date = WHEN,
) -> Pour:
    return Pour(
        poured_on=when,
        pattern=pattern,
        metal=Pounds(metal),
        sand=Pounds(sand),
    )
