"""One way to build a sand system off the command line.

Four commands take the same seven options and turn them into a `SandSystem`.
They were written one at a time and they had already drifted: two defaulted the
basis to measured and one to nameplate, the option that says when the mass was
counted was ``--inventoried`` in three of them and read out of a different
option in the fourth, and only one of them said in its help that the basis is
the difference between a figure somebody counted and a figure somebody
remembered.

That drift is not cosmetic here. `mullerbox.system.state` treats the basis as
load bearing, so a command that quietly defaults it to measured is a command
that lets a nameplate guess through the one check built to stop it. Defaulting
to nameplate is the safe direction: the worst it does is make somebody type the
option that says they counted the sand.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import click

from mullerbox.cli.parsing import read_date, read_member
from mullerbox.system.state import MassBasis, SandSystem
from mullerbox.units.bulk import Pounds
from mullerbox.units.percent import Percent
from mullerbox.units.thermal import Temperature

DEFAULT_NAME = "the sand system"


def system_options(command: Callable[..., Any]) -> Callable[..., Any]:
    """The seven options every command that names a sand system takes.

    Applied bottom up, so they read on ``--help`` in the order written here.
    """
    for decorator in reversed(
        (
            click.option("--name", default=DEFAULT_NAME, help="What to call the system."),
            click.option("--mass", required=True, help="System mass in pounds."),
            click.option(
                "--basis",
                default="nameplate",
                help="measured or nameplate. Nameplate means nobody counted it.",
            ),
            click.option("--inventoried", required=True, help="When the mass was set, yyyy-mm-dd."),
            click.option("--batch", required=True, help="Muller batch size, pounds."),
            click.option("--return-f", required=True, help="Return sand temperature, Fahrenheit."),
            click.option("--dust-rate", default="1.5", help="Collector loss rate, percent."),
        )
    ):
        command = decorator(command)
    return command


def build_system(
    name: str,
    mass: str,
    basis: str,
    inventoried: str,
    batch: str,
    return_f: str,
    dust_rate: str,
) -> SandSystem:
    """Turn the seven options into a system, refusing the same things everywhere."""
    return SandSystem(
        name=name,
        mass=Pounds(mass),
        basis=read_member(basis, MassBasis, "a mass basis"),
        established_on=read_date(inventoried),
        batch_size=Pounds(batch),
        return_temperature=Temperature.fahrenheit(return_f),
        dust_loss_rate=Percent(dust_rate),
    )


__all__ = ["DEFAULT_NAME", "build_system", "system_options"]
