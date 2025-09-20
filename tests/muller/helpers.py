from __future__ import annotations

from typing import Any

from mullerbox.burnout.loss import burnout_of
from mullerbox.muller.plan import BatchPlan, plan_batch
from mullerbox.units.bulk import Pounds
from mullerbox.units.percent import Percent
from mullerbox.units.thermal import Temperature
from tests.burnout.helpers import pour

SYSTEM = Pounds.of_tons(150)
BATCH = Pounds(6000)


def plan(**overrides: Any) -> BatchPlan:
    settings: dict[str, Any] = {
        "burnout": burnout_of(pour(), Percent("8.0"), Percent("3.0")),
        "system_mass": SYSTEM,
        "batch_size": BATCH,
        "measured_clay": Percent("7.5"),
        "clay_target": Percent("8.0"),
        "measured_loi": Percent("2.4"),
        "loi_ceiling": Percent("3.5"),
        "measured_total_clay": Percent("10.5"),
        "dead_clay_target": Percent("2.0"),
        "losses": Pounds(2000),
        "measured_compactability": Percent("38"),
        "compactability_target": Percent("42"),
        "return_temperature": Temperature.fahrenheit(118),
    }
    settings.update(overrides)
    return plan_batch(**settings)
