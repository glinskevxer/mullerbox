"""Schema migrations, applied in order and recorded as they go.

Forward only, and deliberately. A rollback needs a down step that is tested,
and a down step is only ever tested by running it, which nobody does on a
foundry's book at two in the morning. What gets used instead is a restore from
last night's file, so the down steps rot quietly until the one time they are
needed. Not having them is more honest.

Two properties are checked before anything is applied, not asserted in a
comment. Versions have to run from one with no gaps and no repeats, because a
gap means a migration was deleted rather than superseded and a repeat means two
branches both took the next number. Either way applying them in the order they
happen to be listed produces a schema that matches nobody's expectation, and the
check is four lines.

Each migration runs inside one transaction with its bookkeeping row, so a
migration that fails halfway leaves the book on the previous version rather than
on a version that is recorded but only partly there.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from mullerbox.errors import ConfigError
from mullerbox.store.connection import Book

_BOOKKEEPING = """
CREATE TABLE IF NOT EXISTS schema_migration (
    version    INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    applied_at TEXT NOT NULL
)
"""


@dataclass(frozen=True)
class Migration:
    """One numbered step, and the statements that make it."""

    version: int
    name: str
    statements: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ConfigError("migrations are numbered from one")
        if not self.name.strip():
            raise ConfigError(f"migration {self.version} has no name")
        if not self.statements:
            raise ConfigError(f"migration {self.version} does nothing")


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version=1,
        name="screen series and instruments",
        statements=(
            """
            CREATE TABLE screen_series (
                name TEXT PRIMARY KEY
            )
            """,
            """
            CREATE TABLE screen_step (
                series_name TEXT NOT NULL REFERENCES screen_series (name),
                position    INTEGER NOT NULL,
                mesh_number INTEGER NOT NULL,
                micrometres INTEGER NOT NULL,
                multiplier  INTEGER NOT NULL,
                PRIMARY KEY (series_name, position)
            )
            """,
            """
            CREATE UNIQUE INDEX screen_step_mesh
                ON screen_step (series_name, mesh_number)
            """,
            """
            CREATE TABLE instrument (
                tag  TEXT PRIMARY KEY,
                kind TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE calibration (
                certificate    TEXT PRIMARY KEY,
                instrument_tag TEXT NOT NULL REFERENCES instrument (tag),
                calibrated_on  TEXT NOT NULL,
                due_on         TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX calibration_by_instrument
                ON calibration (instrument_tag, calibrated_on)
            """,
        ),
    ),
    Migration(
        version=2,
        name="samples and property results",
        statements=(
            """
            CREATE TABLE sample (
                sample_id  TEXT PRIMARY KEY,
                taken_on   TEXT NOT NULL,
                point      TEXT NOT NULL,
                system_name TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE result (
                sample_id      TEXT NOT NULL REFERENCES sample (sample_id),
                property       TEXT NOT NULL,
                reading        TEXT NOT NULL,
                scale          TEXT NOT NULL,
                instrument_tag TEXT NOT NULL REFERENCES instrument (tag),
                tested_on      TEXT NOT NULL,
                PRIMARY KEY (sample_id, property)
            )
            """,
            """
            CREATE INDEX result_by_property
                ON result (property, tested_on)
            """,
            """
            CREATE TABLE sieve_reading (
                sample_id   TEXT NOT NULL REFERENCES sample (sample_id),
                series_name TEXT NOT NULL REFERENCES screen_series (name),
                charged_cg  INTEGER NOT NULL,
                mesh_number INTEGER NOT NULL,
                retained_cg INTEGER NOT NULL,
                PRIMARY KEY (sample_id, mesh_number)
            )
            """,
        ),
    ),
    Migration(
        version=3,
        name="production: heats, molds, castings and pours",
        statements=(
            """
            CREATE TABLE heat (
                heat_number TEXT PRIMARY KEY,
                poured_on   TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE mold (
                mold_id     TEXT PRIMARY KEY,
                heat_number TEXT NOT NULL REFERENCES heat (heat_number),
                pattern     TEXT NOT NULL,
                sand_lb     TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE casting (
                casting_id  TEXT PRIMARY KEY,
                mold_id     TEXT NOT NULL REFERENCES mold (mold_id),
                weight_lb   TEXT NOT NULL,
                disposition TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX casting_by_mold ON casting (mold_id)
            """,
            """
            CREATE INDEX mold_by_heat ON mold (heat_number)
            """,
            """
            CREATE TABLE pour (
                poured_on TEXT NOT NULL,
                pattern   TEXT NOT NULL,
                metal_lb  TEXT NOT NULL,
                sand_lb   TEXT NOT NULL,
                PRIMARY KEY (poured_on, pattern)
            )
            """,
            """
            CREATE TABLE casting_defect (
                casting_id TEXT NOT NULL REFERENCES casting (casting_id),
                defect     TEXT NOT NULL,
                PRIMARY KEY (casting_id, defect)
            )
            """,
        ),
    ),
    Migration(
        version=4,
        name="published spec sheets",
        statements=(
            """
            CREATE TABLE spec_sheet (
                name       TEXT PRIMARY KEY,
                published_on TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE spec_band (
                sheet_name TEXT NOT NULL REFERENCES spec_sheet (name),
                property   TEXT NOT NULL,
                low        TEXT,
                high       TEXT,
                scale      TEXT NOT NULL,
                PRIMARY KEY (sheet_name, property)
            )
            """,
            """
            CREATE INDEX spec_band_by_sheet ON spec_band (sheet_name)
            """,
        ),
    ),
    Migration(
        version=5,
        name="incoming material lots",
        statements=(
            """
            CREATE TABLE material_lot (
                lot_id       TEXT PRIMARY KEY,
                material     TEXT NOT NULL,
                mass_lb      TEXT NOT NULL,
                delivered_on TEXT NOT NULL,
                certificate  TEXT NOT NULL,
                state        TEXT NOT NULL,
                released_by  TEXT NOT NULL DEFAULT '',
                note         TEXT NOT NULL DEFAULT ''
            )
            """,
            """
            CREATE TABLE lot_claim (
                lot_id TEXT NOT NULL REFERENCES material_lot (lot_id),
                field  TEXT NOT NULL,
                value  TEXT NOT NULL,
                PRIMARY KEY (lot_id, field)
            )
            """,
            """
            CREATE INDEX lot_by_material ON material_lot (material, delivered_on)
            """,
        ),
    ),
    Migration(
        version=6,
        name="material prices",
        statements=(
            """
            CREATE TABLE material_price (
                material  TEXT NOT NULL,
                effective TEXT NOT NULL,
                per_ton   TEXT NOT NULL,
                PRIMARY KEY (material, effective)
            )
            """,
            """
            CREATE INDEX price_by_date ON material_price (effective)
            """,
        ),
    ),
    Migration(
        version=7,
        name="the testing programme",
        statements=(
            """
            CREATE TABLE test_interval (
                property  TEXT PRIMARY KEY,
                frequency TEXT NOT NULL,
                set_on    TEXT NOT NULL,
                because   TEXT NOT NULL DEFAULT ''
            )
            """,
            """
            CREATE TABLE interval_change (
                property  TEXT NOT NULL,
                changed_on TEXT NOT NULL,
                was       TEXT NOT NULL,
                became    TEXT NOT NULL,
                because   TEXT NOT NULL,
                PRIMARY KEY (property, changed_on)
            )
            """,
        ),
    ),
    Migration(
        version=8,
        name="core sand",
        statements=(
            """
            CREATE TABLE binder_system (
                name          TEXT PRIMARY KEY,
                binder        TEXT NOT NULL,
                resin_pct     TEXT NOT NULL,
                catalyst_pct  TEXT NOT NULL,
                bench_life_s  INTEGER NOT NULL,
                strip_time_s  INTEGER NOT NULL,
                full_cure_s   INTEGER NOT NULL,
                tensile_floor TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE core_batch (
                batch_id   TEXT PRIMARY KEY,
                system_name TEXT NOT NULL REFERENCES binder_system (name),
                mixed_at   TEXT NOT NULL,
                charged_lb TEXT NOT NULL,
                blown_lb   TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE core_tensile (
                specimen_id TEXT PRIMARY KEY,
                batch_id    TEXT NOT NULL REFERENCES core_batch (batch_id),
                broken_at   TEXT NOT NULL,
                tensile_psi TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX tensile_by_batch ON core_tensile (batch_id)
            """,
        ),
    ),
    Migration(
        version=9,
        name="sieve wear checks",
        statements=(
            """
            CREATE TABLE wear_check (
                series_name TEXT NOT NULL REFERENCES screen_series (name),
                mesh_number INTEGER NOT NULL,
                checked_on  TEXT NOT NULL,
                measured_um INTEGER NOT NULL,
                PRIMARY KEY (series_name, mesh_number, checked_on)
            )
            """,
            """
            CREATE INDEX wear_by_date ON wear_check (series_name, checked_on)
            """,
        ),
    ),
)


def _check_the_list(migrations: tuple[Migration, ...]) -> None:
    versions = [m.version for m in migrations]
    if versions != sorted(versions):
        raise ConfigError("the migrations are not in version order")
    if len(set(versions)) != len(versions):
        raise ConfigError("two migrations share a version number")
    expected = list(range(1, len(versions) + 1))
    if versions != expected:
        raise ConfigError(f"the migrations run {versions}, which is not a run from one")


def current_version(book: Book) -> int:
    """The highest migration applied, or zero on an untouched book."""
    book.execute(_BOOKKEEPING)
    highest = book.scalar("SELECT max(version) FROM schema_migration")
    return 0 if highest is None else int(str(highest))


def applied(book: Book) -> list[tuple[int, str]]:
    """Every migration on the book, in the order it was applied."""
    book.execute(_BOOKKEEPING)
    rows = book.all("SELECT version, name FROM schema_migration ORDER BY version")
    return [(int(r["version"]), str(r["name"])) for r in rows]


def pending(book: Book, migrations: tuple[Migration, ...] = MIGRATIONS) -> list[Migration]:
    """The migrations this book has not had yet, in order."""
    _check_the_list(migrations)
    at = current_version(book)
    return [m for m in migrations if m.version > at]


def migrate(book: Book, migrations: tuple[Migration, ...] = MIGRATIONS) -> list[int]:
    """Apply everything outstanding. Returns the versions applied, in order."""
    if not isinstance(book, Book):
        raise ConfigError("migrations run against an open book")
    _check_the_list(migrations)
    at = current_version(book)
    done: list[int] = []
    for migration in migrations:
        if migration.version <= at:
            continue
        with book.write():
            for statement in migration.statements:
                book.execute(statement)
            book.execute(
                "INSERT INTO schema_migration (version, name, applied_at) VALUES (?, ?, ?)",
                (
                    migration.version,
                    migration.name,
                    datetime.now(UTC).isoformat(timespec="seconds"),
                ),
            )
        done.append(migration.version)
    return done


def require_current(book: Book, migrations: tuple[Migration, ...] = MIGRATIONS) -> None:
    """Refuse to work against a book that is behind the code."""
    outstanding = pending(book, migrations)
    if outstanding:
        names = ", ".join(str(m.version) for m in outstanding)
        raise ConfigError(f"the book is behind: migrations {names} have not been applied")


__all__ = [
    "MIGRATIONS",
    "Migration",
    "applied",
    "current_version",
    "migrate",
    "pending",
    "require_current",
]
