"""Commands the technician runs at the bench itself.

``bench needs`` answers the question a new technician asks constantly and an
experienced one asks whenever the method book has gone missing: what do I need
before I can run this. It also totals the sand for a set of tests, which is the
number that decides whether one sample pull is enough.

``bench specimen`` is the gate. A rammed cylinder outside the height tolerance
was made wrong, and every number taken off it is a number about the ramming
rather than about the sand. The command says so before the readings are entered,
which is the only point at which saying so is cheap.
"""

from __future__ import annotations

import click

from mullerbox.bench.procedure import (
    one_specimen_only,
    procedure_for,
    sand_needed,
)
from mullerbox.bench.specimen import NOMINAL_HEIGHT, ram
from mullerbox.cli.context import Context, handle, pass_context
from mullerbox.cli.main import main
from mullerbox.props.kind import PropertyKind, parse_property
from mullerbox.report.layout import Column, Table


@main.group("bench")
def bench() -> None:
    """Specimens and the methods run on them."""


@bench.command("needs")
@click.argument("properties", nargs=-1, required=True)
@pass_context
@handle
def needs(context: Context, properties: tuple[str, ...]) -> None:
    """Say what a set of tests needs before any of them can be run."""
    kinds: list[PropertyKind] = [parse_property(name) for name in properties]
    one_specimen_only(kinds)
    for kind in kinds:
        procedure = procedure_for(kind)
        context.say(f"{kind.label}:")
        for line in procedure.requirements():
            context.say(f"  {line}")
    context.say("")
    context.say(f"{sand_needed(kinds)} of sand between them")
    sharing = [k for k in kinds if procedure_for(k).needs_specimen]
    if len(sharing) > 1:
        named = ", ".join(k.label for k in sharing)
        context.say(f"{named} share one rammed specimen")


@bench.command("methods")
@pass_context
@handle
def methods(context: Context) -> None:
    """Every published method, with what it takes."""
    table = Table(
        columns=(
            Column("property"),
            Column("preparation"),
            Column.number("sand"),
            Column("instrument"),
            Column("destroys it"),
        )
    )
    for kind in PropertyKind:
        procedure = procedure_for(kind)
        table.add(
            kind.label,
            procedure.preparation.label,
            str(procedure.sample_mass),
            kind.measured_by.label,
            "yes" if procedure.destructive else "no",
        )
    for line in table.render():
        context.say(line)


@bench.command("specimen")
@click.argument("specimen_id")
@click.argument("loose_height", type=int)
@click.argument("rammed_height", type=int)
@click.option("--rams", type=int, default=3, help="How many times it was rammed.")
@pass_context
@handle
def specimen(
    context: Context,
    specimen_id: str,
    loose_height: int,
    rammed_height: int,
    rams: int,
) -> None:
    """Check a rammed specimen before any reading is hung off it.

    Heights are in thousandths of an inch, which is what the gauge reads.
    """
    made = ram(specimen_id, loose_height, rammed_height, rams)
    context.say(str(made))
    context.say(f"compactability {made.compactability}")
    context.say(
        f"height error {made.height_error:+} thousandths against a nominal {NOMINAL_HEIGHT}"
    )
    if made.is_acceptable:
        context.say("readings may be taken off this specimen")
        return
    made.require_acceptable()


__all__ = ["bench", "methods", "needs", "specimen"]
