"""The sand system's own report: mass, balance, temperature and drift.

Every other report in this package is about the sand. This one is about the
system the sand lives in, and it exists because the two fail differently. Sand
that is out of band is a shift problem somebody notices. A system whose mass
figure is wrong is not a problem anybody notices, ever: it dopes every addition
by the same proportion, so the readings move together and nothing looks odd.

So the report leads with the mass figure and how it was arrived at, before any
of the numbers derived from it. A reader who takes nothing else from the sheet
should take away whether the number underneath everything was measured or
guessed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from mullerbox.errors import BadInputError
from mullerbox.report.layout import Column, Table, heading
from mullerbox.system.balance import RESIDUAL_TOLERANCE, Balance
from mullerbox.system.state import INVENTORY_STALE_DAYS, SandSystem
from mullerbox.units.thermal import Temperature

# Return sand above this cannot be tempered properly whatever the water says.
RETURN_LIMIT_F = Decimal("125")


@dataclass(frozen=True)
class SystemReport:
    """One system, read for the things that go wrong quietly."""

    system: SandSystem
    as_of: date
    balance: Balance | None

    def __post_init__(self) -> None:
        if not isinstance(self.system, SandSystem):
            raise BadInputError("a sand system is expected")
        if not isinstance(self.as_of, date):
            raise BadInputError("a system report is dated")
        if self.balance is not None and not isinstance(self.balance, Balance):
            raise BadInputError("a balance is expected")

    @property
    def mass_is_trustworthy(self) -> bool:
        return self.system.is_measured and not self.system.is_stale_at(self.as_of)

    @property
    def mass_caveat(self) -> str | None:
        """Why the mass figure should not be dosed against, if it should not."""
        if not self.system.is_measured:
            return (
                "this is a nameplate figure, not an inventory; every addition "
                "sized against it is wrong by the same proportion"
            )
        if self.system.is_stale_at(self.as_of):
            days = (self.as_of - self.system.established_on).days
            return (
                f"the last inventory was {days} days ago, past the {INVENTORY_STALE_DAYS} day limit"
            )
        return None

    @property
    def return_sand_too_hot(self) -> bool:
        return self.system.return_temperature.fahrenheit_value > RETURN_LIMIT_F

    def findings(self) -> list[str]:
        """Everything worth saying, mass first."""
        lines: list[str] = []
        caveat = self.mass_caveat
        if caveat is not None:
            lines.append(f"THE SYSTEM MASS CANNOT BE DOSED AGAINST: {caveat}")
        if self.return_sand_too_hot:
            lines.append(
                f"return sand at {self.system.return_temperature.fahrenheit_value} F "
                f"is past {RETURN_LIMIT_F} F; the temper water will flash off "
                "before the bond takes it up"
            )
        if self.balance is not None and not self.balance.closes:
            lines.append(f"the sand balance does not close: {self.balance.finding()}")
        if not lines:
            lines.append("nothing about the system needs attention")
        return lines

    def table(self) -> Table:
        """The readings, with the balance rows only when a balance was struck."""
        built = Table(columns=(Column("reading"), Column("value")))
        built.add("system mass", str(self.system.mass))
        built.add("mass basis", self.system.basis.label)
        built.add("inventoried", str(self.system.established_on))
        built.add("muller batch", str(self.system.batch_size))
        built.add("turns per pass", str(self.system.turns_per_batch))
        built.add(
            "return sand",
            f"{self.system.return_temperature.fahrenheit_value} F",
        )
        built.add("dust loss rate", str(self.system.dust_loss_rate))
        if self.balance is not None:
            built.add("balance residual", f"{self.balance.residual:+.2%}")
            built.add(
                "within tolerance",
                "yes" if self.balance.closes else f"NO ({RESIDUAL_TOLERANCE})",
            )
        return built

    def render(self) -> list[str]:
        """The report as lines, with the mass caveat above the table."""
        lines = heading(f"{self.system.name} as at {self.as_of}")
        for finding in self.findings():
            lines.append(finding)
        lines.append("")
        lines.extend(self.table().render())
        return lines

    def __str__(self) -> str:
        return "\n".join(self.render())


def system_report(system: SandSystem, as_of: date, balance: Balance | None = None) -> SystemReport:
    """Build the system report, with a balance if one was struck."""
    return SystemReport(system=system, as_of=as_of, balance=balance)


def hottest_acceptable() -> Temperature:
    """The warmest return sand that can still be tempered properly."""
    return Temperature.fahrenheit(RETURN_LIMIT_F)


__all__ = [
    "RETURN_LIMIT_F",
    "SystemReport",
    "hottest_acceptable",
    "system_report",
]
