from __future__ import annotations

from datetime import date

from mullerbox.heat.heat import Casting, Disposition, Heat, Mold
from mullerbox.spec.pattern import PatternClass
from mullerbox.units.bulk import Pounds

WHEN = date(2025, 4, 2)


def casting(
    casting_id: str = "C-1",
    weight: str = "120",
    disposition: Disposition = Disposition.SHIPPED,
) -> Casting:
    return Casting(casting_id=casting_id, weight=Pounds(weight), disposition=disposition)


def mold(
    mold_id: str = "M-1",
    pattern: PatternClass = PatternClass.MEDIUM_JOBBING,
    sand: str = "700",
    castings: tuple[Casting, ...] = (),
) -> Mold:
    return Mold(
        mold_id=mold_id,
        pattern=pattern,
        sand=Pounds(sand),
        castings=castings or (casting(),),
    )


def heat(*molds: Mold, number: str = "H-1001", when: date = WHEN) -> Heat:
    return Heat(heat_number=number, poured_on=when, molds=molds or (mold(),))
