from __future__ import annotations

from datetime import date

from mullerbox.system.state import MassBasis, SandSystem
from mullerbox.units.bulk import Pounds
from mullerbox.units.percent import Percent
from mullerbox.units.thermal import Temperature

ESTABLISHED = date(2025, 1, 6)


def system(
    mass: str = "300000",
    basis: MassBasis = MassBasis.MEASURED,
    established: date = ESTABLISHED,
    batch: str = "6000",
) -> SandSystem:
    return SandSystem(
        name="number two system",
        mass=Pounds(mass),
        basis=basis,
        established_on=established,
        batch_size=Pounds(batch),
        return_temperature=Temperature.fahrenheit(118),
        dust_loss_rate=Percent("0.4"),
    )
