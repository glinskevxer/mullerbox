"""New sand, which goes in for two completely different reasons.

**Make up** replaces what left. Sand goes out of the system on castings, in the
dust collector, and on the floor, and if it is not replaced the system shrinks
until the muller is running half batches. This is bookkeeping: measure what
left, put that much back.

**Dilution** replaces what is still there and should not be. Dead clay and fines
accumulate because nothing removes them: dehydroxylated bentonite stays in the
sand as inert powder, and it neither bonds nor screens out. The only way down is
to take some of the system away and put fresh sand in its place.

Those two are usually satisfied by one addition and they are not the same
number, which is where systems get into trouble. A shop that adds only make up
sand has a system whose dead clay climbs forever; the sand gets progressively
harder to compact, the operator answers with water, and the mold strength goes
with it. The dilution requirement is almost always the larger of the two, and it
is the one nobody measures.

Dilution arithmetic is worth stating plainly because the intuition is wrong.
Replacing a fraction of the system does not remove that fraction of the dead
clay, it removes exactly that fraction, and the remainder is diluted into the
same total mass. So the dead clay falls in proportion to the fraction replaced,
and getting from three percent to two percent takes a third of the system, not
a third of the difference.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from mullerbox.addition.material import Addition, Material
from mullerbox.errors import BadInputError
from mullerbox.units.bulk import Pounds
from mullerbox.units.percent import Percent

# Nobody replaces more than this in one shift. Past it the system is a new
# system, the properties move faster than the lab can follow, and the right
# answer is a planned changeout rather than an addition.
MAX_REPLACEMENT_SHARE = Decimal("0.15")

PLACES = Decimal("0.000001")


def dead_clay(total: Percent, live: Percent) -> Percent:
    """What the wash found that the titration did not: clay that no longer bonds."""
    if not isinstance(total, Percent):
        raise BadInputError("total clay is a percentage")
    if not isinstance(live, Percent):
        raise BadInputError("live clay is a percentage")
    if live > total:
        raise BadInputError(
            f"live clay of {live} is above total clay of {total}, "
            "which means one of the two tests is wrong"
        )
    return Percent(total.value - live.value)


@dataclass(frozen=True)
class SandCall:
    """The new sand decision, with both requirements kept separate."""

    make_up: Pounds
    dilution: Pounds
    replacement_share: Decimal
    capped: bool
    addition: Addition

    @property
    def dilution_governs(self) -> bool:
        """True when dilution is asking for more than make up is."""
        return self.dilution > self.make_up

    def __str__(self) -> str:
        driver = "dilution" if self.dilution_governs else "make up"
        return f"{self.addition} driven by {driver}"


def share_to_reach(current: Percent, target: Percent) -> Decimal:
    """The fraction of the system to replace to bring a contaminant to target.

    Uncapped and unrounded, because the caller has to be able to see that the
    honest answer was forty percent before it gets clipped to fifteen.
    """
    if not isinstance(current, Percent):
        raise BadInputError("the current level is a percentage")
    if not isinstance(target, Percent):
        raise BadInputError("the target level is a percentage")
    if current.value <= 0:
        return Decimal(0)
    if target >= current:
        return Decimal(0)
    return ((current.value - target.value) / current.value).quantize(PLACES, rounding=ROUND_HALF_UP)


def new_sand_for(
    losses: Pounds,
    current_dead_clay: Percent,
    target_dead_clay: Percent,
    system_mass: Pounds,
) -> SandCall:
    """Work out the new sand addition, taking the larger of the two requirements.

    The two are not added together. Sand replaced for dilution is sand that also
    replaces losses, so adding them double counts. The addition is whichever of
    the two is larger, which is dilution on nearly every shift a system has ever
    had.
    """
    if not isinstance(losses, Pounds):
        raise BadInputError("system losses are a bulk mass")
    if not isinstance(system_mass, Pounds):
        raise BadInputError("the system mass is a bulk mass")
    if system_mass.is_zero:
        raise BadInputError("a system with no sand in it cannot be diluted")
    wanted = share_to_reach(current_dead_clay, target_dead_clay)
    capped = wanted > MAX_REPLACEMENT_SHARE
    share = MAX_REPLACEMENT_SHARE if capped else wanted
    dilution = system_mass.scaled(share)
    charged = dilution if dilution > losses else losses
    driver = "dilution" if dilution > losses else "make up"
    reason = (
        f"{driver}: {losses} lost against a dilution requirement of "
        f"{dilution} to bring dead clay from {current_dead_clay} "
        f"to {target_dead_clay}"
    )
    if capped:
        reason += f", capped at {MAX_REPLACEMENT_SHARE * 100}% of the system"
    return SandCall(
        make_up=losses,
        dilution=dilution,
        replacement_share=share,
        capped=capped,
        addition=(
            Addition.nothing(Material.NEW_SAND, reason)
            if charged.is_zero
            else Addition(material=Material.NEW_SAND, mass=charged, reason=reason)
        ),
    )


def dead_clay_after(current: Percent, replaced: Pounds, system_mass: Pounds) -> Percent:
    """Where the dead clay lands once a replacement has been made.

    The inverse of ``share_to_reach``, and worth having so the two can be
    checked against each other rather than trusted separately.
    """
    if not isinstance(current, Percent):
        raise BadInputError("the current level is a percentage")
    if not isinstance(replaced, Pounds):
        raise BadInputError("the replaced mass is a bulk mass")
    if not isinstance(system_mass, Pounds):
        raise BadInputError("the system mass is a bulk mass")
    if system_mass.is_zero:
        raise BadInputError("a system with no sand in it has no dead clay")
    if replaced > system_mass:
        raise BadInputError("more sand cannot be replaced than the system holds")
    kept = Decimal(1) - replaced.fraction_of(system_mass)
    return Percent((current.value * kept).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


__all__ = [
    "MAX_REPLACEMENT_SHARE",
    "SandCall",
    "dead_clay",
    "dead_clay_after",
    "new_sand_for",
    "share_to_reach",
]
