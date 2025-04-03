from __future__ import annotations

from mullerbox.props.kind import PropertyKind, Reading
from mullerbox.spec.pattern import PatternClass
from mullerbox.spec.sheet import ResolvedSpec, resolve
from mullerbox.units.percent import Percent
from mullerbox.units.pressure import Psi, WetTensile
from mullerbox.units.scales import Hardness, Permeability
from tests.spec.helpers import sheet

# A sand comfortably in the middle of every published band.
GOOD: dict[PropertyKind, Reading] = {
    PropertyKind.COMPACTABILITY: Percent("41"),
    PropertyKind.GREEN_COMPRESSION: Psi("23"),
    PropertyKind.MOISTURE: Percent("3.2"),
    PropertyKind.MB_CLAY: Percent("8.0"),
    PropertyKind.PERMEABILITY: Permeability(110),
    PropertyKind.LOI: Percent("2.5"),
    PropertyKind.VOLATILES: Percent("1.5"),
    PropertyKind.FRIABILITY: Percent("8.0"),
    PropertyKind.WET_TENSILE: WetTensile("0.28"),
    PropertyKind.MOLD_HARDNESS: Hardness(86),
}


def readings(**overrides: Reading) -> dict[PropertyKind, Reading]:
    out = dict(GOOD)
    for name, value in overrides.items():
        out[PropertyKind[name]] = value
    return out


def spec_for(pattern: PatternClass) -> ResolvedSpec:
    return resolve(sheet(), pattern)
