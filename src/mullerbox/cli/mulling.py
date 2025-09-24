"""Commands the muller operator runs.

``muller plan`` is the one that matters. It reads the sand's current numbers off
the book, reads the pour record for the shift being answered, and prints the
four additions in charging order. It prints the projected bond as its own line,
because the operator needs to see that the water was sized against a bond level
the sand does not have yet.

Every number it needs is an option with no default. A batch plan built on a
guessed system mass is wrong by the same proportion as the guess, every batch,
and a default here would make that invisible.
"""

from __future__ import annotations

from datetime import date

import click

from mullerbox.burnout.loss import burnout_of
from mullerbox.burnout.pour import Pour
from mullerbox.cli.context import Context, handle, pass_context
from mullerbox.cli.main import main
from mullerbox.errors import BadInputError, NotFoundError
from mullerbox.muller.cycle import Cycle
from mullerbox.muller.plan import plan_batch
from mullerbox.spec.pattern import parse_pattern_class
from mullerbox.store import heat_repo
from mullerbox.units.bulk import Pounds
from mullerbox.units.duration import Seconds
from mullerbox.units.percent import Percent
from mullerbox.units.thermal import Temperature


@main.group("muller")
def mulling() -> None:
    """Batch planning and muller cycles."""


@mulling.command("plan")
@click.option("--on", "as_of", required=True, help="The shift being answered, yyyy-mm-dd.")
@click.option("--pattern", required=True, help="Which class was poured.")
@click.option("--system", "system_mass", required=True, help="System mass in pounds.")
@click.option("--batch", "batch_size", required=True, help="Batch mass in pounds.")
@click.option("--mb", "measured_clay", required=True, help="Methylene blue clay, percent.")
@click.option("--mb-target", required=True, help="Published bond target, percent.")
@click.option("--loi", "measured_loi", required=True, help="Loss on ignition, percent.")
@click.option("--loi-ceiling", required=True, help="LOI ceiling, percent.")
@click.option("--total-clay", required=True, help="Total clay by wash, percent.")
@click.option("--dead-target", required=True, help="Dead clay target, percent.")
@click.option("--losses", required=True, help="Sand that left the system, pounds.")
@click.option("--comp", "measured_comp", required=True, help="Compactability, percent.")
@click.option("--comp-target", required=True, help="Compactability target, percent.")
@click.option("--return-f", required=True, help="Return sand temperature, Fahrenheit.")
@pass_context
@handle
def plan(
    context: Context,
    as_of: str,
    pattern: str,
    system_mass: str,
    batch_size: str,
    measured_clay: str,
    mb_target: str,
    measured_loi: str,
    loi_ceiling: str,
    total_clay: str,
    dead_target: str,
    losses: str,
    measured_comp: str,
    comp_target: str,
    return_f: str,
) -> None:
    """Work out the four additions for the next batch."""
    when = _date_from(as_of)
    cls = parse_pattern_class(pattern)
    with context.book() as book:
        pours = [p for p in heat_repo.load_pours(book, when) if p.pattern is cls]
    if not pours:
        raise NotFoundError(f"{cls.label} pour record on", when.isoformat())
    poured = _combined(pours)
    burnout = burnout_of(poured, Percent(measured_clay), Percent(measured_loi))
    built = plan_batch(
        burnout=burnout,
        system_mass=Pounds(system_mass),
        batch_size=Pounds(batch_size),
        measured_clay=Percent(measured_clay),
        clay_target=Percent(mb_target),
        measured_loi=Percent(measured_loi),
        loi_ceiling=Percent(loi_ceiling),
        measured_total_clay=Percent(total_clay),
        dead_clay_target=Percent(dead_target),
        losses=Pounds(losses),
        measured_compactability=Percent(measured_comp),
        compactability_target=Percent(comp_target),
        return_temperature=Temperature.fahrenheit(return_f),
    )
    context.say(f"{cls.label} at {poured.sand_to_metal}:1, severity {poured.severity}")
    for line in built.render():
        context.say(line)


@mulling.command("check-cycle")
@click.option("--batch", "batch_id", required=True, help="The batch number.")
@click.option("--return-sand", required=True, help="Return sand in the batch, pounds.")
@click.option("--bentonite", default="0", help="Bentonite charged, pounds.")
@click.option("--water", default="0", help="Water charged, pounds.")
@click.option("--dry", "dry_mull", required=True, help="Dry mull seconds.")
@click.option("--wet", "wet_mull", required=True, help="Wet mull seconds.")
@pass_context
@handle
def check_cycle(
    context: Context,
    batch_id: str,
    return_sand: str,
    bentonite: str,
    water: str,
    dry_mull: str,
    wet_mull: str,
) -> None:
    """Check a mull schedule against the dry mull first rule before running it."""
    from mullerbox.addition.material import Addition, Material

    additions = []
    if Pounds(bentonite).value > 0:
        additions.append(
            Addition(
                material=Material.BENTONITE,
                mass=Pounds(bentonite),
                reason="charged on the batch sheet",
            )
        )
    if Pounds(water).value > 0:
        additions.append(
            Addition(
                material=Material.WATER,
                mass=Pounds(water),
                reason="charged on the batch sheet",
            )
        )
    cycle = Cycle.charge(batch_id, Pounds(return_sand), additions)
    mulled = cycle.mulled(Seconds(dry_mull), Seconds(wet_mull))
    context.say(
        f"batch {batch_id} passes: {mulled.total_mull} total mull, {mulled.batch_mass} discharged"
    )


def _combined(pours: list[Pour]) -> Pour:
    """Roll several pours of one class on one day into a single record."""
    metal = Pounds.zero()
    sand = Pounds.zero()
    for pour in pours:
        metal = metal + pour.metal
        sand = sand + pour.sand
    return Pour(
        poured_on=pours[0].poured_on,
        pattern=pours[0].pattern,
        metal=metal,
        sand=sand,
    )


def _date_from(text: str) -> date:
    try:
        return date.fromisoformat(text.strip())
    except ValueError:
        raise BadInputError(f"{text!r} is not a date in yyyy-mm-dd form") from None


__all__ = ["check_cycle", "mulling", "plan"]
