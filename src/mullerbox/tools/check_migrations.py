"""Check that no migration has been edited after it shipped.

A migration is applied once per book and never again. So editing one that has
already shipped changes what a *new* book gets and changes nothing about the
books already out there, and the two silently diverge. The divergence is not
visible anywhere: both books say they are at version 4, both pass their tests,
and one of them has a column the other does not.

This gate makes that impossible to do by accident. Every migration's statements
are hashed and the hashes are written down in this file. Change a migration and
the gate fails; the only way past it is to update the hash here, which is a
line in a diff that a reviewer will ask about. Adding a *new* migration needs a
new hash, which is the same deliberate act and the correct one.

The gate also applies the whole set to a scratch book, which catches a statement
that is valid SQL to read and invalid to run.

Run as ``python -m mullerbox.tools.check_migrations``.
"""

from __future__ import annotations

import hashlib
import sys

from mullerbox.store.connection import open_book
from mullerbox.store.migrations import MIGRATIONS, Migration, current_version, migrate

# The hash of each shipped migration. Update deliberately, never to make the
# gate pass.
SHIPPED: dict[int, str] = {
    1: "05691c64c8a36fed",
    2: "35666da3d5104afd",
    3: "9ce00e25cc2e86b0",
    4: "04eea1d6859c37b8",
    5: "c103890b376a709b",
    6: "943e89d516f93c9e",
    7: "841c15b2821a0aa5",
    8: "1225bb32a3ed42e0",
    9: "7240e4a655401a1e",
}


def digest(migration: Migration) -> str:
    """A stable short hash of what a migration actually does.

    Over the statements only. The name is documentation and renaming it should
    not trip the gate; the version is the key and cannot change without being a
    different migration.

    Runs of whitespace collapse to one space, so reindenting a statement is
    free. Whitespace that was not there before is not free: ``t (a INTEGER)``
    and ``t ( a INTEGER )`` hash differently. That is stricter than SQL needs
    and it is the right side to err on, because a false alarm costs one line in
    ``SHIPPED`` and a miss costs a schema divergence nobody can see.
    """
    joined = "\n".join(" ".join(s.split()) for s in migration.statements)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


def problems() -> list[str]:
    """Every migration fault, as readable lines."""
    found: list[str] = []
    for migration in MIGRATIONS:
        actual = digest(migration)
        expected = SHIPPED.get(migration.version)
        if expected is None:
            found.append(
                f"migration {migration.version} ({migration.name}) has no hash "
                f"recorded; add {actual!r} to SHIPPED if it is new"
            )
        elif expected != actual:
            found.append(
                f"migration {migration.version} ({migration.name}) has changed "
                f"since it shipped: recorded {expected}, now {actual}"
            )
    recorded = set(SHIPPED)
    present = {m.version for m in MIGRATIONS}
    for version in sorted(recorded - present):
        found.append(f"migration {version} has a hash but is not in the list")
    return found


def applies_cleanly() -> list[str]:
    """Run the whole set against a scratch book and report anything that fails."""
    try:
        with open_book() as book:
            done = migrate(book)
            if done != [m.version for m in MIGRATIONS]:
                return [f"applying to an empty book ran {done}, not every migration"]
            if current_version(book) != len(MIGRATIONS):
                return ["the book did not reach the last migration"]
            tables = set(book.tables)
    except Exception as exc:  # noqa: BLE001 - the gate reports rather than raises
        return [f"the migrations do not apply: {exc}"]
    expected = {
        "schema_migration",
        "screen_series",
        "screen_step",
        "instrument",
        "calibration",
        "sample",
        "result",
        "sieve_reading",
        "heat",
        "mold",
        "casting",
        "pour",
        "casting_defect",
        "spec_sheet",
        "spec_band",
        "material_lot",
        "lot_claim",
        "material_price",
        "test_interval",
        "interval_change",
        "binder_system",
        "core_batch",
        "core_tensile",
        "wear_check",
    }
    missing = sorted(expected - tables)
    return [f"the schema has no {name!r} table" for name in missing]


def main() -> int:
    """Print every migration problem and exit non-zero if there are any."""
    found = problems() + applies_cleanly()
    for line in found:
        print(line)
    if found:
        print(f"\n{len(found)} migration problems")
        return 1
    print(f"{len(MIGRATIONS)} migrations are unchanged and apply cleanly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
