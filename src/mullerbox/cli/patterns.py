"""Commands for the pattern register, and the pour record check it enables.

``pattern check-pours`` is why the register is worth keeping. It reads the pour
log against what each pattern's geometry says it should have been, and names the
days where the two disagree enough that the record is more likely wrong than the
shift unusual. Nothing else in the package can check a pour record, and every
addition is sized against one.
"""

from __future__ import annotations

from decimal import Decimal

import click

from mullerbox.cli.context import Context, handle, pass_context
from mullerbox.cli.main import main
from mullerbox.cli.parsing import read_date, read_decimal, read_member
from mullerbox.heat.pattern import Pattern
from mullerbox.report.layout import Column, Table
from mullerbox.spec.pattern import PatternClass
from mullerbox.store import heat_repo, pattern_repo
from mullerbox.units.bulk import Pounds


@main.group("pattern")
def patterns() -> None:
    """The pattern register and the pour records it can check."""


@patterns.command("register")
@click.argument("pattern_id")
@click.argument("name")
@click.argument("class_name")
@click.option("--flask", required=True, help="Flask volume in cubic feet.")
@click.option("--cavities", type=int, required=True, help="Castings per mold.")
@click.option("--weight", required=True, help="One casting's weight in pounds.")
@pass_context
@handle
def register(
    context: Context,
    pattern_id: str,
    name: str,
    class_name: str,
    flask: str,
    cavities: int,
    weight: str,
) -> None:
    """Put a pattern on the register."""
    built = Pattern(
        pattern_id=pattern_id,
        name=name,
        pattern_class=read_member(class_name, PatternClass, "a pattern class"),
        flask_cubic_feet=read_decimal(flask, "flask volume"),
        cavities=cavities,
        casting_weight=Pounds(weight),
    )
    with context.book() as book:
        pattern_repo.save_pattern(book, built)
    context.say(f"registered {built}")


@patterns.command("list")
@pass_context
@handle
def list_patterns(context: Context) -> None:
    """Every pattern on the register with its expected pour ratio."""
    with context.book() as book:
        found = pattern_repo.load_register(book)
    if not len(found):
        context.say("no patterns on the register")
        return
    table = Table(
        columns=(
            Column("pattern"),
            Column("name"),
            Column("class"),
            Column.number("cavities"),
            Column.number("metal"),
            Column.number("expected ratio"),
        )
    )
    for pattern in found.patterns:
        table.add(
            pattern.pattern_id,
            pattern.name,
            pattern.pattern_class.label,
            str(pattern.cavities),
            str(pattern.metal_per_mold),
            f"{pattern.expected_ratio}:1",
        )
    for line in table.render():
        context.say(line)


@patterns.command("retire")
@click.argument("pattern_id")
@pass_context
@handle
def retire(context: Context, pattern_id: str) -> None:
    """Take a pattern off the register."""
    with context.book() as book:
        pattern_repo.retire(book, pattern_id)
    context.say(f"retired {pattern_id}")


@patterns.command("check-pours")
@click.argument("pattern_id")
@click.option("--on", "as_of", required=True, help="Which day's pours, yyyy-mm-dd.")
@pass_context
@handle
def check_pours(context: Context, pattern_id: str, as_of: str) -> None:
    """Check a day's pour records against what the pattern's geometry says."""
    when = read_date(as_of)
    with context.book() as book:
        pattern = pattern_repo.load_pattern(book, pattern_id)
        pours = [p for p in heat_repo.load_pours(book, when) if p.pattern is pattern.pattern_class]
    if not pours:
        context.say(f"no {pattern.pattern_class.label} pour was recorded on {when}")
        return
    suspect = 0
    for pour in pours:
        recorded = Decimal(pour.sand_to_metal)
        context.say(pattern.check_ratio(recorded))
        if pattern.ratio_looks_wrong(recorded):
            suspect += 1
    context.say("")
    if suspect:
        context.say(
            f"{suspect} of {len(pours)} records look wrong; every addition sized "
            "against them carries the same error"
        )
    else:
        context.say(f"{len(pours)} records are consistent with the geometry")


__all__ = ["check_pours", "list_patterns", "patterns", "register", "retire"]
