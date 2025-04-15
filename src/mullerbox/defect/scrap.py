"""Rolling a heat's scrap up into the report the shift meeting argues over.

The number everyone wants is "how much of this scrap is the sand's". Getting to
it needs one thing the individual attribution does not have: the weight. A
defect charged to sand on a two pound casting and the same defect on an eight
hundred pound casting are the same attribution and very different problems.

Two rules about the roll up are decisions rather than arithmetic.

**A casting is charged once.** A scrapped casting usually comes back with more
than one defect written on it, and the naive sum double counts its weight into
every bucket. The rule here is that the casting's weight lands in one bucket,
chosen by taking sand over anything else when any of its defects is a sand call.
That biases the sand's share upward, deliberately: the sand department would
rather answer for a casting that was arguably the pattern's than have a real
sand problem hidden inside the pattern column.

**Pending castings are counted separately and never as good.** A casting nobody
has judged is not scrap and is not a good casting, and folding it into either
makes the report improve when inspection falls behind.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from mullerbox.defect.attribution import Attribution, attribute
from mullerbox.defect.kind import Culprit, DefectKind
from mullerbox.errors import BadInputError, RuleError
from mullerbox.heat.heat import Casting, Heat, Mold
from mullerbox.props.kind import PropertyKind, Reading
from mullerbox.spec.pattern import PatternClass
from mullerbox.spec.sheet import ResolvedSpec
from mullerbox.units.bulk import Pounds


@dataclass(frozen=True)
class Charge:
    """One scrapped casting, charged to one place."""

    casting: Casting
    mold_id: str
    pattern: PatternClass
    culprit: Culprit
    attributions: tuple[Attribution, ...]

    @property
    def weight(self) -> Pounds:
        return self.casting.weight

    @property
    def sand_properties(self) -> tuple[PropertyKind, ...]:
        found: list[PropertyKind] = []
        for attribution in self.attributions:
            if attribution.is_sand:
                for kind in attribution.properties:
                    if kind not in found:
                        found.append(kind)
        return tuple(found)


@dataclass(frozen=True)
class ScrapReport:
    """A heat's scrap, split by who answers for it."""

    heat_number: str
    poured: Pounds
    charges: tuple[Charge, ...]
    pending: Pounds

    def weight_charged_to(self, culprit: Culprit) -> Pounds:
        if not isinstance(culprit, Culprit):
            raise BadInputError("a culprit is expected")
        running = Pounds.zero()
        for charge in self.charges:
            if charge.culprit is culprit:
                running = running + charge.weight
        return running

    @property
    def scrapped(self) -> Pounds:
        running = Pounds.zero()
        for charge in self.charges:
            running = running + charge.weight
        return running

    def share_charged_to(self, culprit: Culprit) -> Decimal:
        """That culprit's share of the poured weight, to four places."""
        if self.poured.is_zero:
            raise RuleError(f"heat {self.heat_number} poured no metal")
        return self.weight_charged_to(culprit).fraction_of(self.poured).quantize(Decimal("0.0001"))

    @property
    def sand_share(self) -> Decimal:
        return self.share_charged_to(Culprit.SAND)

    @property
    def properties_implicated(self) -> tuple[PropertyKind, ...]:
        """Every sand property named across the whole heat, most cited first."""
        counts: dict[PropertyKind, int] = {}
        for charge in self.charges:
            for kind in charge.sand_properties:
                counts[kind] = counts.get(kind, 0) + 1
        return tuple(sorted(counts, key=lambda k: (-counts[k], k.name)))

    def __str__(self) -> str:
        return (
            f"heat {self.heat_number}: {self.scrapped} scrapped of {self.poured}, "
            f"{self.weight_charged_to(Culprit.SAND)} to sand"
        )


def _charge_for(
    casting: Casting,
    mold: Mold,
    defects: tuple[DefectKind, ...],
    resolved: ResolvedSpec,
    readings: Mapping[PropertyKind, Reading],
) -> Charge:
    attributions = tuple(attribute(d, resolved, readings) for d in defects)
    if any(a.is_sand for a in attributions):
        culprit = Culprit.SAND
    elif attributions:
        culprit = attributions[0].culprit
    else:
        culprit = Culprit.PATTERN
    return Charge(
        casting=casting,
        mold_id=mold.mold_id,
        pattern=mold.pattern,
        culprit=culprit,
        attributions=attributions,
    )


def report_on(
    heat: Heat,
    defects: Mapping[str, tuple[DefectKind, ...]],
    specs: Mapping[PatternClass, ResolvedSpec],
    readings: Mapping[PropertyKind, Reading],
) -> ScrapReport:
    """Roll one heat's scrap up, resolving each mold against its own class.

    ``specs`` is keyed by pattern class rather than being a single resolution,
    because a heat can run several classes and each mold has to be judged
    against the bands that were in force for it. A mold whose class is not in
    the mapping is a gap in the setup rather than a mold to skip, so it raises.
    """
    if not isinstance(heat, Heat):
        raise BadInputError("a scrap report is built from a heat")
    charges: list[Charge] = []
    pending = Pounds.zero()
    for mold in heat.molds:
        resolved = specs.get(mold.pattern)
        if resolved is None:
            raise RuleError(
                f"mold {mold.mold_id} ran {mold.pattern.label} and no spec was resolved for it"
            )
        for casting in mold.castings:
            if not casting.disposition.is_decided:
                pending = pending + casting.weight
                continue
            if not casting.is_scrap:
                continue
            charges.append(
                _charge_for(
                    casting,
                    mold,
                    defects.get(casting.casting_id, ()),
                    resolved,
                    readings,
                )
            )
    return ScrapReport(
        heat_number=heat.heat_number,
        poured=heat.metal,
        charges=tuple(charges),
        pending=pending,
    )


__all__ = ["Charge", "ScrapReport", "report_on"]
