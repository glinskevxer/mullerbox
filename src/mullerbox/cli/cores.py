"""Commands for the core room: binder systems, batches and tensiles.

``core blow`` refuses a draw past bench life and says how old the batch is when
it does. That refusal is the reason the command exists rather than the operator
keeping a clipboard: the sand looks fine past bench life, blows fine, and makes
cores with no strength in them, and the only thing that knows is the clock.

``core judge`` will not judge a batch on specimens broken away from full cure.
It says how many it had to leave out, because a batch judged on one specimen out
of six is a batch nobody has really judged.
"""

from __future__ import annotations

from datetime import datetime

import click

from mullerbox.cli.context import Context, handle, pass_context
from mullerbox.cli.main import main
from mullerbox.cli.parsing import read_member
from mullerbox.core.batch import CoreBatch
from mullerbox.core.binder import Binder, BinderSystem
from mullerbox.core.mix import cores_from, mix_for
from mullerbox.core.testing import TensileResult, batch_verdict
from mullerbox.errors import BadInputError
from mullerbox.report.layout import Column, Table
from mullerbox.store import core_repo
from mullerbox.units.bulk import Pounds
from mullerbox.units.duration import Seconds
from mullerbox.units.percent import Percent
from mullerbox.units.pressure import Psi


@main.group("core")
def cores() -> None:
    """Core sand: binder systems, batches and tensiles."""


@cores.command("add-system")
@click.argument("name")
@click.argument("binder_name")
@click.option("--resin", required=True, help="Resin addition, percent.")
@click.option("--catalyst", required=True, help="Catalyst addition, percent.")
@click.option("--bench-life", required=True, help="Bench life, seconds.")
@click.option("--strip", required=True, help="Strip time, seconds.")
@click.option("--cure", required=True, help="Full cure, seconds.")
@click.option("--floor", required=True, help="Tensile floor, psi.")
@pass_context
@handle
def add_system(
    context: Context,
    name: str,
    binder_name: str,
    resin: str,
    catalyst: str,
    bench_life: str,
    strip: str,
    cure: str,
    floor: str,
) -> None:
    """Put a binder system on the book."""
    system = BinderSystem(
        binder=read_member(binder_name, Binder, "a binder"),
        resin=Percent(resin),
        catalyst=Percent(catalyst),
        bench_life=Seconds(bench_life),
        strip_time=Seconds(strip),
        full_cure=Seconds(cure),
        tensile_floor=Psi(floor),
    )
    with context.book() as book:
        core_repo.save_system(book, name, system)
    context.say(f"added {name}: {system}")


@cores.command("systems")
@pass_context
@handle
def list_systems(context: Context) -> None:
    """List the binder systems and their three times."""
    with context.book() as book:
        names = core_repo.list_systems(book)
        table = Table(
            columns=(
                Column("name"),
                Column("binder"),
                Column.number("bench life"),
                Column.number("strip"),
                Column.number("cure"),
                Column.number("floor"),
            )
        )
        for name in names:
            system = core_repo.load_system(book, name)
            table.add(
                name,
                system.binder.label,
                str(system.bench_life),
                str(system.strip_time),
                str(system.full_cure),
                str(system.tensile_floor),
            )
    if not names:
        context.say("no binder systems on the book")
        return
    for line in table.render():
        context.say(line)


@cores.command("mix")
@click.argument("batch_id")
@click.option("--system", "system_name", required=True, help="Which binder system.")
@click.option("--at", "mixed_at", required=True, help="When it was mixed, ISO.")
@click.option("--charged", required=True, help="Sand charged, pounds.")
@pass_context
@handle
def mix(context: Context, batch_id: str, system_name: str, mixed_at: str, charged: str) -> None:
    """Record a core sand batch as mixed."""
    with context.book() as book:
        system = core_repo.load_system(book, system_name)
        built = CoreBatch(
            batch_id=batch_id,
            system=system,
            mixed_at=_moment(mixed_at),
            charged=Pounds(charged),
        )
        core_repo.save_batch(book, built, system_name)
    context.say(f"mixed {built}")


@cores.command("blow")
@click.argument("batch_id")
@click.option("--mass", required=True, help="Sand drawn, pounds.")
@click.option("--at", "when", required=True, help="When it was blown, ISO.")
@pass_context
@handle
def blow(context: Context, batch_id: str, mass: str, when: str) -> None:
    """Draw sand off a batch, refusing a draw past bench life."""
    moment = _moment(when)
    with context.book() as book:
        batch = core_repo.load_batch(book, batch_id)
        drawn = batch.blow(Pounds(mass), moment)
        core_repo.update_batch(book, drawn)
    context.say(f"blew {Pounds(mass)} at {batch.age_at(moment)} old, {drawn.remaining} left")


@cores.command("break")
@click.argument("batch_id")
@click.argument("specimen_id")
@click.argument("tensile")
@click.option("--at", "when", required=True, help="When it was broken, ISO.")
@pass_context
@handle
def break_specimen(
    context: Context, batch_id: str, specimen_id: str, tensile: str, when: str
) -> None:
    """Record a broken tensile specimen against a batch."""
    with context.book() as book:
        batch = core_repo.load_batch(book, batch_id)
        result = TensileResult(
            specimen_id=specimen_id,
            system=batch.system,
            mixed_at=batch.mixed_at,
            broken_at=_moment(when),
            tensile=Psi(tensile),
        )
        core_repo.save_tensile(book, batch_id, specimen_id, result)
    mark = "at full cure" if result.at_full_cure else "AWAY FROM FULL CURE"
    context.say(f"{result}, {mark}")


@cores.command("judge")
@click.argument("batch_id")
@pass_context
@handle
def judge(context: Context, batch_id: str) -> None:
    """Judge a batch on the specimens broken at full cure."""
    with context.book() as book:
        results = core_repo.load_tensiles(book, batch_id)
    if not results:
        context.say(f"batch {batch_id} has no specimens broken against it")
        return
    off_cure = [r for r in results if not r.at_full_cure]
    context.say(batch_verdict(results))
    if off_cure:
        named = ", ".join(r.specimen_id for r in off_cure)
        context.say(f"left out of the judgement, broken away from full cure: {named}")


def _moment(text: str) -> datetime:
    try:
        return datetime.fromisoformat(text.strip())
    except ValueError:
        raise BadInputError(f"{text!r} is not a moment in yyyy-mm-ddThh:mm:ss form") from None


@cores.command("size-mix")
@click.argument("system_name")
@click.argument("cores_wanted")
@pass_context
@handle
def size_mix(context: Context, system_name: str, cores_wanted: str) -> None:
    """Work out what to charge for a weight of cores.

    Allows for spillage and nothing else. A bit extra in case is a bit of scrap
    every mix, because core sand that is not blown inside bench life cannot go
    back in the hopper and cannot go into the green sand system either.
    """
    with context.book() as book:
        system = core_repo.load_system(book, system_name)
    mix = mix_for(system, Pounds(cores_wanted))
    table = Table(columns=(Column("charge"), Column.number("pounds")))
    table.add("sand", str(mix.sand))
    table.add("resin", str(mix.resin))
    table.add("catalyst", str(mix.catalyst))
    table.add("total", str(mix.total_charge))
    for line in table.render():
        context.say(line)
    context.say("")
    context.say(
        f"{mix.spillage} of that is the spillage allowance; the rest makes "
        f"{mix.cores_wanted} of cores"
    )
    context.say(
        f"if none of it is blown, {mix.waste_if_unused} is scrapped, because core "
        "sand does not go round again"
    )
    context.say(
        f"resin is {system.resin} of the sand and catalyst is {system.catalyst_ratio} of the resin"
    )


@cores.command("yield")
@click.argument("system_name")
@click.argument("sand_available")
@pass_context
@handle
def yield_from(context: Context, system_name: str, sand_available: str) -> None:
    """How many cores a fixed mixer load will make, after spillage."""
    with context.book() as book:
        system = core_repo.load_system(book, system_name)
    made = cores_from(system, Pounds(sand_available))
    context.say(f"{Pounds(sand_available)} of sand makes {made} of cores")
    if made.is_zero:
        return
    context.say(f"blown inside a {system.bench_life} bench life or scrapped")


__all__ = [
    "add_system",
    "blow",
    "break_specimen",
    "cores",
    "judge",
    "list_systems",
    "mix",
    "size_mix",
    "yield_from",
]
