"""Reading and writing core sand: binder systems, batches and their tensiles.

A tensile result is stored against its batch rather than carrying its own copy
of the mix time and the binder. Two reasons.

The mix time is a fact about the batch and duplicating it onto every specimen
gives it several places to be wrong. A specimen's age is derived: broken at,
minus the batch's mixed at.

And the binder system is what decides whether an age counts as full cure, so a
specimen that carried its own copy could disagree with its batch about which
system it came off. It cannot here, because it does not have one.

The cost is that a specimen cannot be loaded without its batch, which is the
right shape: a tensile with no batch behind it has no age and no floor to be
judged against, so it is not a result yet.
"""

from __future__ import annotations

from datetime import datetime

from mullerbox.core.batch import CoreBatch
from mullerbox.core.binder import Binder, BinderSystem
from mullerbox.core.testing import TensileResult
from mullerbox.errors import BadInputError, DuplicateError, NotFoundError
from mullerbox.store.connection import Book
from mullerbox.units.bulk import Pounds
from mullerbox.units.duration import Seconds
from mullerbox.units.percent import Percent
from mullerbox.units.pressure import Psi


def save_system(book: Book, name: str, system: BinderSystem) -> None:
    """Put a binder system on the book under a name the shop uses for it."""
    if not isinstance(system, BinderSystem):
        raise BadInputError("a binder system is expected")
    if not name.strip():
        raise BadInputError("a binder system needs a name")
    if system_exists(book, name):
        raise DuplicateError("binder system", name)
    with book.write():
        book.execute(
            "INSERT INTO binder_system (name, binder, resin_pct, catalyst_pct,"
            " bench_life_s, strip_time_s, full_cure_s, tensile_floor)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                name,
                system.binder.name,
                str(system.resin.value),
                str(system.catalyst.value),
                system.bench_life.value,
                system.strip_time.value,
                system.full_cure.value,
                str(system.tensile_floor.value),
            ),
        )


def system_exists(book: Book, name: str) -> bool:
    return book.one("SELECT name FROM binder_system WHERE name = ?", (name,)) is not None


def load_system(book: Book, name: str) -> BinderSystem:
    """Rebuild a binder system, through the type's own ordering checks."""
    row = book.one(
        "SELECT binder, resin_pct, catalyst_pct, bench_life_s, strip_time_s,"
        " full_cure_s, tensile_floor FROM binder_system WHERE name = ?",
        (name,),
    )
    if row is None:
        raise NotFoundError("binder system", name)
    binder_name = str(row["binder"])
    try:
        binder = Binder[binder_name]
    except KeyError:
        raise BadInputError(f"the book carries binder {binder_name!r}, which is not one") from None
    return BinderSystem(
        binder=binder,
        resin=Percent(str(row["resin_pct"])),
        catalyst=Percent(str(row["catalyst_pct"])),
        bench_life=Seconds(int(row["bench_life_s"])),
        strip_time=Seconds(int(row["strip_time_s"])),
        full_cure=Seconds(int(row["full_cure_s"])),
        tensile_floor=Psi(str(row["tensile_floor"])),
    )


def list_systems(book: Book) -> list[str]:
    rows = book.all("SELECT name FROM binder_system ORDER BY name")
    return [str(r["name"]) for r in rows]


def save_batch(book: Book, batch: CoreBatch, system_name: str) -> None:
    """Write a core batch against a binder system already on the book."""
    if not isinstance(batch, CoreBatch):
        raise BadInputError("a core batch is expected")
    if not system_exists(book, system_name):
        raise NotFoundError("binder system", system_name)
    if batch_exists(book, batch.batch_id):
        raise DuplicateError("core batch", batch.batch_id)
    with book.write():
        book.execute(
            "INSERT INTO core_batch (batch_id, system_name, mixed_at, charged_lb,"
            " blown_lb) VALUES (?, ?, ?, ?, ?)",
            (
                batch.batch_id,
                system_name,
                batch.mixed_at.isoformat(),
                str(batch.charged.value),
                str(batch.blown.value),
            ),
        )


def batch_exists(book: Book, batch_id: str) -> bool:
    return book.one("SELECT batch_id FROM core_batch WHERE batch_id = ?", (batch_id,)) is not None


def load_batch(book: Book, batch_id: str) -> CoreBatch:
    """Rebuild a core batch and the binder system behind it."""
    row = book.one(
        "SELECT system_name, mixed_at, charged_lb, blown_lb FROM core_batch WHERE batch_id = ?",
        (batch_id,),
    )
    if row is None:
        raise NotFoundError("core batch", batch_id)
    return CoreBatch(
        batch_id=batch_id,
        system=load_system(book, str(row["system_name"])),
        mixed_at=datetime.fromisoformat(str(row["mixed_at"])),
        charged=Pounds(str(row["charged_lb"])),
        blown=Pounds(str(row["blown_lb"])),
    )


def update_batch(book: Book, batch: CoreBatch) -> None:
    """Write back how much has been blown off a batch."""
    if not isinstance(batch, CoreBatch):
        raise BadInputError("a core batch is expected")
    if not batch_exists(book, batch.batch_id):
        raise NotFoundError("core batch", batch.batch_id)
    with book.write():
        book.execute(
            "UPDATE core_batch SET blown_lb = ? WHERE batch_id = ?",
            (str(batch.blown.value), batch.batch_id),
        )


def save_tensile(book: Book, batch_id: str, specimen_id: str, result: TensileResult) -> None:
    """Record a broken specimen against its batch."""
    if not isinstance(result, TensileResult):
        raise BadInputError("a tensile result is expected")
    if not batch_exists(book, batch_id):
        raise NotFoundError("core batch", batch_id)
    existing = book.one(
        "SELECT specimen_id FROM core_tensile WHERE specimen_id = ?", (specimen_id,)
    )
    if existing is not None:
        raise DuplicateError("specimen", specimen_id)
    with book.write():
        book.execute(
            "INSERT INTO core_tensile (specimen_id, batch_id, broken_at, tensile_psi)"
            " VALUES (?, ?, ?, ?)",
            (
                specimen_id,
                batch_id,
                result.broken_at.isoformat(),
                str(result.tensile.value),
            ),
        )


def load_tensiles(book: Book, batch_id: str) -> list[TensileResult]:
    """Every specimen broken off one batch, with its age derived from the batch."""
    batch = load_batch(book, batch_id)
    rows = book.all(
        "SELECT specimen_id, broken_at, tensile_psi FROM core_tensile"
        " WHERE batch_id = ? ORDER BY broken_at, specimen_id",
        (batch_id,),
    )
    return [
        TensileResult(
            specimen_id=str(r["specimen_id"]),
            system=batch.system,
            mixed_at=batch.mixed_at,
            broken_at=datetime.fromisoformat(str(r["broken_at"])),
            tensile=Psi(str(r["tensile_psi"])),
        )
        for r in rows
    ]


__all__ = [
    "batch_exists",
    "list_systems",
    "load_batch",
    "load_system",
    "load_tensiles",
    "save_batch",
    "save_system",
    "save_tensile",
    "system_exists",
    "update_batch",
]
