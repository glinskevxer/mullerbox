"""Commands about the sand system itself: its mass, its balance and its cooler.

``system balance`` is the command that tells a shop its system mass figure is
wrong. Nothing else does. Every addition in this package is a share of that
mass, so a figure that is thirty percent high produces additions that are thirty
percent light, every shift, and the only symptom is a bond level that will not
come up no matter what the muller does.

The command prints the residual and refuses to distribute it. That is worth
stating in the help text as well as in the code, because the first thing anyone
asks on seeing a balance that will not close is whether the dust figure can
absorb it, and the answer has to be the same every time.
"""

from __future__ import annotations

import click

from mullerbox.cli.context import Context, handle, pass_context
from mullerbox.cli.main import main
from mullerbox.cli.parsing import read_date, read_decimal
from mullerbox.cli.systemopts import build_system, system_options
from mullerbox.errors import BadInputError
from mullerbox.gfn.fineness import fineness_of
from mullerbox.report.inventory import expected_new_sand, inventory_report
from mullerbox.report.layout import Column, Table, heading
from mullerbox.report.system import system_report
from mullerbox.store import inventory_repo, sieve_repo
from mullerbox.system.balance import RESIDUAL_TOLERANCE, Balance
from mullerbox.system.cooler import cooling_water_for, reachable_temperature
from mullerbox.system.dust import collector_take, fineness_after
from mullerbox.system.inventory import Count, Vessel, apply_count, reconcile
from mullerbox.units.bulk import Pounds
from mullerbox.units.thermal import Temperature


@main.group("system")
def systems() -> None:
    """The circulating sand system, its balance and its cooler."""


@systems.command("balance")
@click.option("--on", "shift_on", required=True, help="yyyy-mm-dd")
@system_options
@click.option("--new-sand", required=True, help="New sand added, pounds.")
@click.option("--core-return", required=True, help="Core sand returned, pounds.")
@click.option("--shipped", required=True, help="Sand shipped on castings, pounds.")
@click.option("--dust", required=True, help="Dust collected, pounds.")
@click.option("--swept", required=True, help="Sand swept up, pounds.")
@click.option("--throughput", required=True, help="Sand handled, pounds.")
@pass_context
@handle
def balance(
    context: Context,
    shift_on: str,
    name: str,
    mass: str,
    basis: str,
    inventoried: str,
    batch: str,
    return_f: str,
    dust_rate: str,
    new_sand: str,
    core_return: str,
    shipped: str,
    dust: str,
    swept: str,
    throughput: str,
) -> None:
    """Strike a shift's sand balance. The residual is reported, never absorbed."""
    system = build_system(name, mass, basis, inventoried, batch, return_f, dust_rate)
    struck = Balance(
        system=system,
        shift_on=read_date(shift_on),
        new_sand=Pounds(new_sand),
        core_sand_returned=Pounds(core_return),
        shipped_on_castings=Pounds(shipped),
        dust_collected=Pounds(dust),
        swept_up=Pounds(swept),
        throughput=Pounds(throughput),
    )
    for line in heading(f"sand balance for {struck.shift_on}"):
        context.say(line)
    table = Table(columns=(Column("term"), Column.number("pounds")))
    table.add("new sand in", str(struck.new_sand))
    table.add("core sand returned", str(struck.core_sand_returned))
    table.add("shipped on castings", str(struck.shipped_on_castings))
    table.add("dust collected", str(struck.dust_collected))
    table.add("swept up", str(struck.swept_up))
    table.add("dust expected", str(struck.expected_dust))
    for line in table.render():
        context.say(line)
    context.say("")
    context.say(struck.finding())
    context.say(
        f"the residual is not distributed; the {RESIDUAL_TOLERANCE} tolerance is on throughput"
    )
    if not struck.expected_dust.is_zero:
        context.say(f"dust variance {struck.dust_variance:+.2%} against expected")
    if not system.is_measured:
        context.say(
            "the system mass is a nameplate figure, so every addition sized "
            "against it carries the same error"
        )
    elif system.is_stale_at(struck.shift_on):
        context.say("the system mass has not been inventoried recently enough to dose against")


@systems.command("cooler")
@click.option("--sand", required=True, help="Sand through the cooler, pounds.")
@click.option("--entering-f", required=True, help="Shakeout temperature, Fahrenheit.")
@click.option("--wet-bulb-f", required=True, help="Wet bulb temperature, Fahrenheit.")
@click.option("--wanted-f", default=None, help="Target temperature, Fahrenheit.")
@click.option("--water", default=None, help="Water the cooler can spray, pounds.")
@pass_context
@handle
def cooler(
    context: Context,
    sand: str,
    entering_f: str,
    wet_bulb_f: str,
    wanted_f: str | None,
    water: str | None,
) -> None:
    """Size the cooler for a target, or say where a given spray rate lands."""
    stream = Pounds(sand)
    entering = Temperature.fahrenheit(entering_f)
    wet_bulb = Temperature.fahrenheit(wet_bulb_f)
    if wanted_f is not None:
        call = cooling_water_for(stream, entering, Temperature.fahrenheit(wanted_f), wet_bulb)
        context.say(str(call))
        if not call.reachable:
            context.say(
                f"the floor is {call.floor.fahrenheit_value} F on a "
                f"{wet_bulb.fahrenheit_value} F wet bulb"
            )
        return
    if water is None:
        context.say("give either a target with --wanted-f or a spray rate with --water")
        return
    landed = reachable_temperature(stream, entering, Pounds(water), wet_bulb)
    context.say(
        f"{Pounds(water)} takes {stream} from {entering.fahrenheit_value} F "
        f"to {landed.fahrenheit_value} F"
    )


@systems.command("report")
@click.option("--on", "as_of", required=True, help="yyyy-mm-dd")
@system_options
@pass_context
@handle
def report(
    context: Context,
    as_of: str,
    name: str,
    mass: str,
    basis: str,
    inventoried: str,
    batch: str,
    return_f: str,
    dust_rate: str,
) -> None:
    """The system's own sheet, leading with how the mass figure was arrived at."""
    built = build_system(name, mass, basis, inventoried, batch, return_f, dust_rate)
    for line in system_report(built, read_date(as_of)).render():
        context.say(line)


@systems.command("collector")
@click.argument("sample_id")
@click.option("--throughput", required=True, help="Sand handled, pounds.")
@pass_context
@handle
def collector(context: Context, sample_id: str, throughput: str) -> None:
    """What the dust collector takes from a throughput of this sand.

    Takes a sample rather than a bare tonnage, because the collector is a screen
    and not a percentage: the answer depends on how many fines the sand has, and
    two systems running the same tonnage lose different amounts.
    """
    with context.book() as book:
        analysis = sieve_repo.load_analysis(book, sample_id)
    spread = fineness_of(analysis)
    take = collector_take(spread, Pounds(throughput))
    context.say(str(take))
    context.say(f"which is {take.share_removed} of the throughput")
    coarsest = take.coarsest_touched
    if coarsest is None:
        context.say("nothing on this sand is fine enough for the collector to take")
        return
    context.say(f"the coarsest screen it touched was {coarsest.label}")
    if take.removed == take.throughput:
        # Every grain was fine enough to be caught, so there is no sand left to
        # take a fineness of. Real on a pure fines sample and worth saying
        # plainly rather than raising out of the arithmetic.
        context.say(
            "the collector would take all of this sand, so there is no drift to "
            "report; nothing of it survives the pass"
        )
        return
    after = fineness_after(spread, take)
    context.say(
        f"the sand through the collector drifts from GFN {spread.value} to {after}, "
        "which no daily reading shows"
    )


def _vessels(entries: tuple[str, ...]) -> tuple[Vessel, ...]:
    """Parse the repeated --vessel option.

    The shape is name:capacity:fill:density, and the density may be left off
    entirely, which is how the operator says nobody measured it. An empty
    trailing field means the same thing, because that is what a spreadsheet
    export produces and refusing it would only teach people to type a zero.
    """
    built: list[Vessel] = []
    for entry in entries:
        parts = entry.split(":")
        if len(parts) not in (3, 4):
            raise BadInputError(
                f"{entry!r} is not name:capacity:fill or name:capacity:fill:density"
            )
        name, capacity, fill = parts[0], parts[1], parts[2]
        density = parts[3].strip() if len(parts) == 4 else ""
        built.append(
            Vessel(
                name=name.strip(),
                capacity_cubic_feet=read_decimal(capacity, "a vessel capacity"),
                filled_fraction=read_decimal(fill, "a fill fraction"),
                density_pounds_per_cubic_foot=(
                    read_decimal(density, "a bulk density") if density else None
                ),
            )
        )
    return tuple(built)


@systems.command("inventory")
@click.option("--name", required=True, help="Which sand system.")
@click.option("--on", "counted_on", required=True, help="yyyy-mm-dd")
@click.option(
    "--vessel",
    "vessels",
    multiple=True,
    required=True,
    help="name:capacity:fill:density, repeated. Leave the density off if nobody measured it.",
)
@click.option("--moulds", default=0, type=int, help="Moulds standing on the floor.")
@click.option("--sand-per-mould", default="0", help="Sand one mould takes, pounds.")
@click.option("--save/--no-save", default=True, help="Keep the count on the book.")
@pass_context
@handle
def inventory(
    context: Context,
    name: str,
    counted_on: str,
    vessels: tuple[str, ...],
    moulds: int,
    sand_per_mould: str,
    save: bool,
) -> None:
    """Take a system inventory and say what it found."""
    count = Count(
        system_name=name,
        counted_on=read_date(counted_on),
        vessels=_vessels(vessels),
        moulds_standing=moulds,
        sand_per_mould=Pounds(sand_per_mould),
    )
    table = Table(
        columns=(
            Column("vessel"),
            Column.number("cu ft"),
            Column.number("standing"),
            Column.number("lb/cu ft"),
            Column.number("pounds"),
        )
    )
    for vessel in count.vessels:
        density = vessel.density_pounds_per_cubic_foot
        table.add(
            vessel.name,
            str(vessel.capacity_cubic_feet),
            str(vessel.standing_cubic_feet),
            "" if density is None else str(density),
            "not counted" if density is None else str(vessel.mass),
        )
    for line in table.render():
        context.say(line)
    context.say("")
    context.say(f"in vessels {count.in_vessels}, on the floor {count.on_the_floor}")
    context.say(f"total {count.total}")
    if not count.on_the_floor.is_zero:
        context.say(f"{count.floor_share:.1%} of that is the floor estimate, which nobody weighed")
    if not count.is_complete:
        missed = ", ".join(v.name for v in count.uncounted_vessels)
        context.warn(f"this count did not reach {missed}, so it is partial")
    if save:
        with context.book() as book:
            inventory_repo.save_count(book, count)
        context.say(f"kept the count of {name} on {count.counted_on}")


@systems.command("reconcile")
@click.option("--on", "counted_on", required=True, help="Which count, yyyy-mm-dd.")
@system_options
@click.option("--adopt", is_flag=True, help="Write the count in as the system mass.")
@pass_context
@handle
def reconcile_count(
    context: Context,
    name: str,
    counted_on: str,
    mass: str,
    basis: str,
    inventoried: str,
    batch: str,
    return_f: str,
    dust_rate: str,
    adopt: bool,
) -> None:
    """Set a saved count against the figure the system was carrying.

    ``--adopt`` refuses a partial count. A count that did not reach every vessel
    comes back wearing the measured basis if it is adopted, and everything
    downstream stops asking whether the mass is a guess.
    """
    system = build_system(name, mass, basis, inventoried, batch, return_f, dust_rate)
    with context.book() as book:
        count = inventory_repo.load_count(book, name, read_date(counted_on))
    context.say(reconcile(system, count).verdict())
    if not adopt:
        return
    after = apply_count(system, count)
    context.say(
        f"adopt {after.mass} measured on {after.established_on}; pass "
        f"--mass {after.mass.value} --basis measured --inventoried "
        f"{after.established_on} from here on"
    )


@systems.command("counts")
@click.option("--name", required=True, help="Which sand system.")
@pass_context
@handle
def counts(context: Context, name: str) -> None:
    """Every inventory taken of a system, read as a run.

    The latest figure is already on the system record. What this adds is the
    line through the counts, which is the only thing that says whether the new
    sand going in matches the sand going out.
    """
    with context.book() as book:
        dates = inventory_repo.count_dates(book, name)
        rows = [inventory_repo.load_count(book, name, when) for when in dates]
    report = inventory_report(name, rows)
    for line in report.render():
        context.say(line)
    wanted = expected_new_sand(report)
    if wanted is not None:
        context.say("")
        context.say(f"holding it level takes about {wanted} of new sand a year")


__all__ = [
    "balance",
    "collector",
    "cooler",
    "counts",
    "inventory",
    "reconcile_count",
    "report",
    "systems",
]
