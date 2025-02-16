"""A property result, and the two questions you can ask about one.

The first question is what it says: a number, on a scale, for a property. That
part is settled the moment the technician writes it down and never changes.

The second question is whether it counts, and that part is not settled and can
change afterwards. A result counts when the instrument it came off was inside a
calibration window on the day the test ran. Calibration records get entered
late, get corrected, and occasionally get withdrawn, so the same stored result
can be countable today and void tomorrow without anybody touching the result.

The consequence worth naming: a result cannot cache its own validity. Every
answer is computed against an instrument passed in at the point of asking, and
that instrument carries whatever history is currently recorded. Anything that
stores "valid" as a field on the result is storing the answer to a question that
was asked at a moment nobody wrote down.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from mullerbox.cal.instrument import Instrument
from mullerbox.errors import BadInputError, RuleError
from mullerbox.props.kind import PropertyKind, Reading


@dataclass(frozen=True)
class Result:
    """One property, measured once, on one instrument, on one day."""

    kind: PropertyKind
    reading: Reading
    instrument_tag: str
    tested_on: date
    sample_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, PropertyKind):
            raise BadInputError("a result is a result for a property")
        self.kind.require_reading(self.reading)
        if not self.instrument_tag.strip():
            raise BadInputError("a result names the instrument it came off")
        if not isinstance(self.tested_on, date):
            raise BadInputError("a result is dated")
        if not self.sample_id.strip():
            raise BadInputError("a result names the sample it was run on")

    def counts_for(self, instrument: Instrument) -> bool:
        """Whether this result may be used, given what is known about the instrument."""
        self._require_matching(instrument)
        return instrument.was_calibrated_on(self.tested_on)

    def require_counts(self, instrument: Instrument) -> None:
        """Raise unless this result may be used."""
        self._require_matching(instrument)
        if not instrument.was_calibrated_on(self.tested_on):
            raise RuleError(
                f"the {self.kind.label} on sample {self.sample_id} was run on "
                f"{self.tested_on}, when {instrument.tag} had no calibration"
            )

    def certificate_for(self, instrument: Instrument) -> str | None:
        """The certificate number that backs this result, if there is one."""
        self._require_matching(instrument)
        covering = instrument.window_covering(self.tested_on)
        return None if covering is None else covering.certificate

    def _require_matching(self, instrument: Instrument) -> None:
        """The instrument handed in has to be the one named on the result."""
        if not isinstance(instrument, Instrument):
            raise BadInputError("a result is checked against an instrument")
        if instrument.tag != self.instrument_tag:
            raise BadInputError(f"this result came off {self.instrument_tag}, not {instrument.tag}")
        self.kind.require_instrument_kind(instrument.kind)

    def __str__(self) -> str:
        return f"{self.sample_id} {self.kind.label} {self.reading} on {self.tested_on}"


def countable(results: list[Result], instruments: dict[str, Instrument]) -> list[Result]:
    """Filter to the results that may be used, given the instruments on the book.

    A result whose instrument is not on the book is dropped rather than raised
    on. The caller is usually walking a shift's worth of readings and one
    unknown tag should not take the shift with it; the reporting layer names
    what was dropped.
    """
    kept: list[Result] = []
    for result in results:
        instrument = instruments.get(result.instrument_tag)
        if instrument is None:
            continue
        if instrument.kind is not result.kind.measured_by:
            continue
        if result.counts_for(instrument):
            kept.append(result)
    return kept


def latest_countable(
    results: list[Result],
    instruments: dict[str, Instrument],
    kind: PropertyKind,
    on_or_before: date,
) -> Result | None:
    """The most recent usable reading of one property, as at a date.

    Ties on the same day are broken by taking the last one in the list, which is
    the order the bench sheet was entered in. A lab that runs a property twice
    in a day means the second one to supersede the first.
    """
    if not isinstance(kind, PropertyKind):
        raise BadInputError("a property kind is expected")
    if not isinstance(on_or_before, date):
        raise BadInputError("a cutoff date is expected")
    candidates = [
        r for r in countable(results, instruments) if r.kind is kind and r.tested_on <= on_or_before
    ]
    if not candidates:
        return None
    newest = max(r.tested_on for r in candidates)
    return [r for r in candidates if r.tested_on == newest][-1]


__all__ = ["Result", "countable", "latest_countable"]
