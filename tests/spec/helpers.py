from __future__ import annotations

from mullerbox.props.kind import PropertyKind
from mullerbox.spec.band import Band
from mullerbox.spec.sheet import SpecSheet
from mullerbox.units.percent import Percent
from mullerbox.units.pressure import Psi, WetTensile
from mullerbox.units.scales import Hardness, Permeability

PUBLISHED = {
    PropertyKind.COMPACTABILITY: Band.between(
        PropertyKind.COMPACTABILITY, Percent(38), Percent(44)
    ),
    PropertyKind.GREEN_COMPRESSION: Band.between(PropertyKind.GREEN_COMPRESSION, Psi(20), Psi(26)),
    PropertyKind.MOISTURE: Band.between(PropertyKind.MOISTURE, Percent("2.8"), Percent("3.6")),
    PropertyKind.MB_CLAY: Band.between(PropertyKind.MB_CLAY, Percent("7.0"), Percent("9.0")),
    PropertyKind.PERMEABILITY: Band.between(
        PropertyKind.PERMEABILITY, Permeability(90), Permeability(130)
    ),
    PropertyKind.LOI: Band.at_most(PropertyKind.LOI, Percent("3.5")),
    PropertyKind.VOLATILES: Band.at_most(PropertyKind.VOLATILES, Percent("2.2")),
    PropertyKind.FRIABILITY: Band.at_most(PropertyKind.FRIABILITY, Percent("12.0")),
    PropertyKind.WET_TENSILE: Band.at_least(PropertyKind.WET_TENSILE, WetTensile("0.20")),
    PropertyKind.MOLD_HARDNESS: Band.between(
        PropertyKind.MOLD_HARDNESS, Hardness(82), Hardness(90)
    ),
}


def sheet(name: str = "system sand 2025") -> SpecSheet:
    return SpecSheet(name=name, bands=dict(PUBLISHED))
