"""A calibration window: the span over which an instrument's readings count.

This is a half open interval and the closing end is the one that matters. An
instrument calibrated on the 3rd and due on the 3rd of the following quarter is
good *up to* the due date, and a reading taken on the due date itself is the one
everybody argues about. The lab's rule is that the due date is the first day it
is not good, because a certificate that expires "on" a date has already expired
when that date starts. Written down once, here, so that no caller invents its
own answer.

The other half of the rule is subtler. A window is checked against the moment
the *test ran*, never against now. Calibration records get entered late, so a
test that was valid when it was run stays valid, and a test run inside a lapse
stays void even after the instrument is put right. That makes validity a
function of two dates rather than one, and it means the same stored result can
answer differently as the calibration record changes underneath it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from mullerbox.errors import BadInputError

# A lab instrument that has not been touched in two years has not been
# calibrated, it has been forgotten.
MAX_INTERVAL_DAYS = 730


@dataclass(frozen=True)
class CalibrationWindow:
    """Calibrated on one date, due on a later one."""

    calibrated_on: date
    due_on: date
    certificate: str

    def __post_init__(self) -> None:
        if not isinstance(self.calibrated_on, date):
            raise BadInputError("a calibration date is a date")
        if not isinstance(self.due_on, date):
            raise BadInputError("a due date is a date")
        if self.due_on <= self.calibrated_on:
            raise BadInputError("a calibration is due after it was done, not before")
        if (self.due_on - self.calibrated_on).days > MAX_INTERVAL_DAYS:
            raise BadInputError(
                f"a {(self.due_on - self.calibrated_on).days} day interval is not a "
                "calibration interval"
            )
        if not self.certificate.strip():
            raise BadInputError("a calibration needs a certificate number")

    @classmethod
    def opened(cls, calibrated_on: date, days: int, certificate: str) -> CalibrationWindow:
        """Build from an interval rather than an end date."""
        if isinstance(days, bool) or not isinstance(days, int):
            raise BadInputError("a calibration interval is a whole number of days")
        if days <= 0:
            raise BadInputError("a calibration interval has to be at least a day")
        return cls(
            calibrated_on=calibrated_on,
            due_on=calibrated_on + timedelta(days=days),
            certificate=certificate,
        )

    @property
    def interval_days(self) -> int:
        return (self.due_on - self.calibrated_on).days

    @property
    def last_good_day(self) -> date:
        """The last date a reading counts, which is the day before it is due."""
        return self.due_on - timedelta(days=1)

    def covers(self, when: date) -> bool:
        """True when a test run on that date counts.

        Closed at the calibration date and open at the due date: good on the day
        it was calibrated, not good on the day it falls due.
        """
        if not isinstance(when, date):
            raise BadInputError("a calibration window is checked against a date")
        return self.calibrated_on <= when < self.due_on

    def days_left_on(self, when: date) -> int:
        """How many days the window still has, counting from a date. Negative past due."""
        if not isinstance(when, date):
            raise BadInputError("a calibration window is checked against a date")
        return (self.due_on - when).days

    def overlaps(self, other: CalibrationWindow) -> bool:
        """Whether two windows cover any day in common."""
        if not isinstance(other, CalibrationWindow):
            raise BadInputError("a window only compares against a window")
        return self.calibrated_on < other.due_on and other.calibrated_on < self.due_on

    def __str__(self) -> str:
        return f"{self.certificate} {self.calibrated_on} to {self.last_good_day}"


__all__ = ["CalibrationWindow", "MAX_INTERVAL_DAYS"]
