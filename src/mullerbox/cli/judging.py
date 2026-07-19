"""Resolving the sand a charge is judged against.

Three commands charge scrap and all three want the same option: name a sample
and permeability is judged against the band that sand should hold, leave it off
and the published anchor judges. The option text, the lookup and the two lines
printed underneath were written out three times before this module existed, and
they had already started to disagree about the wording.

Keeping it here also keeps the honest half honest. The caveat is printed by
whoever charged, not by whoever looked the sample up, so a command that takes
the option and forgets to say what it did is a command that quietly claims more
than it measured.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import click

from mullerbox.gfn.distribution import Distribution, grade
from mullerbox.gfn.fineness import fineness_of
from mullerbox.store import sieve_repo
from mullerbox.store.connection import Book

SAMPLE_HELP = "A sieve analysis to judge permeability against."


def sample_option(command: Callable[..., Any]) -> Callable[..., Any]:
    """The --sample option, so the three charging commands cannot drift apart."""
    decorator = click.option("--sample", "sample_id", default=None, help=SAMPLE_HELP)
    return decorator(command)


def distribution_for(book: Book, sample_id: str | None) -> Distribution | None:
    """Grade a sample's sieve analysis, or nothing when no sample was named."""
    if sample_id is None:
        return None
    return grade(fineness_of(sieve_repo.load_analysis(book, sample_id)))


def band_note(distribution: Distribution | None) -> str | None:
    """One line naming the sand the permeability band was shifted onto."""
    if distribution is None:
        return None
    return f"permeability judged against a {distribution} sand"


__all__ = ["SAMPLE_HELP", "band_note", "distribution_for", "sample_option"]
