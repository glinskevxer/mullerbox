"""The lab instruments, and the history of calibrations behind each one.

An instrument is not calibrated or uncalibrated. It has a *history* of windows,
and the question is always which window, if any, covered a particular moment.
That framing is what lets a late-entered certificate correct the record without
rewriting any result: the result keeps pointing at the instrument and the date,
and the answer to "did this count" is recomputed from whatever the history says
now.

Windows on one instrument are kept in calibration order and are not allowed to
overlap. Two overlapping certificates for one device mean somebody entered the
same calibration twice or calibrated a different device, and either way the
question "which certificate covered this test" stops having one answer, which is
the whole point of keeping them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from mullerbox.cal.window import CalibrationWindow
from mullerbox.errors import BadInputError, RuleError


class InstrumentKind(Enum):
    """What a device measures, which decides what it may be used for.

    A result names the property it measured and the instrument it came off, and
    those two have to agree. A green compression reading taken on the
    permeability meter is not a slightly odd reading, it is not a reading.
    """

    STRENGTH = "universal strength machine"
    PERMEABILITY = "permeability meter"
    MOISTURE = "moisture teller"
    COMPACTABILITY = "compactability rammer"
    SIEVE_SHAKER = "sieve shaker"
    BALANCE = "balance"
    MUFFLE = "muffle furnace"
    CLAY = "methylene blue titrator"

    @property
    def label(self) -> str:
        return self.value


@dataclass(frozen=True)
class Instrument:
    """A device in the lab and every calibration ever recorded against it."""

    tag: str
    kind: InstrumentKind
    windows: tuple[CalibrationWindow, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.tag.strip():
            raise BadInputError("an instrument needs a tag")
        if not isinstance(self.kind, InstrumentKind):
            raise BadInputError("an instrument needs a kind")
        for w in self.windows:
            if not isinstance(w, CalibrationWindow):
                raise BadInputError("an instrument carries calibration windows")
        ordered = sorted(self.windows, key=lambda w: w.calibrated_on)
        if list(self.windows) != ordered:
            raise BadInputError("calibration windows are kept in calibration order")
        for earlier, later in zip(ordered, ordered[1:], strict=False):
            if earlier.overlaps(later):
                raise RuleError(
                    f"certificates {earlier.certificate} and {later.certificate} "
                    f"both cover {later.calibrated_on}"
                )
        certificates = [w.certificate for w in self.windows]
        if len(set(certificates)) != len(certificates):
            raise RuleError("the same certificate number is recorded twice")

    def with_window(self, window: CalibrationWindow) -> Instrument:
        """A copy carrying one more calibration, re-sorted and re-checked."""
        if not isinstance(window, CalibrationWindow):
            raise BadInputError("an instrument carries calibration windows")
        merged = sorted([*self.windows, window], key=lambda w: w.calibrated_on)
        return Instrument(tag=self.tag, kind=self.kind, windows=tuple(merged))

    def window_covering(self, when: date) -> CalibrationWindow | None:
        """The certificate that covered a moment, or nothing if there was a lapse."""
        if not isinstance(when, date):
            raise BadInputError("an instrument is checked against a date")
        for w in self.windows:
            if w.covers(when):
                return w
        return None

    def was_calibrated_on(self, when: date) -> bool:
        return self.window_covering(when) is not None

    def require_calibrated(self, when: date) -> CalibrationWindow:
        """The covering certificate, or a refusal naming the gap."""
        covering = self.window_covering(when)
        if covering is None:
            raise RuleError(f"{self.tag} had no calibration covering {when}")
        return covering

    def lapses(self) -> tuple[tuple[date, date], ...]:
        """The gaps between consecutive windows, as half open spans."""
        gaps: list[tuple[date, date]] = []
        for earlier, later in zip(self.windows, self.windows[1:], strict=False):
            if earlier.due_on < later.calibrated_on:
                gaps.append((earlier.due_on, later.calibrated_on))
        return tuple(gaps)

    @property
    def latest(self) -> CalibrationWindow | None:
        return self.windows[-1] if self.windows else None

    def __str__(self) -> str:
        return f"{self.tag} ({self.kind.label})"


__all__ = ["Instrument", "InstrumentKind"]
