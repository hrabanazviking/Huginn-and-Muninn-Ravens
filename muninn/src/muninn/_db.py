"""Store machinery for Muninn: WAL SQLite open, integrity, rolling backups.

Kept separate from the memory semantics so the crash-proofing and
self-healing can be read — and tested — on their own.

Durability contract
-------------------
* WAL journal mode + ``synchronous=FULL``: a ``kill -9`` mid-write
  loses at most the uncommitted transaction; every committed write
  survives reopen.
* A backup is a file copy made through SQLite's own backup API from a
  *verified-healthy* store, so a backup is never a snapshot of
  corruption.
* On open, if the main store fails ``quick_check`` (or is not a
  database at all), the newest backup that itself passes
  ``quick_check`` is restored over it, its WAL sidecars are removed,
  and the recovery is reported loudly. If no backup verifies, opening
  raises :class:`MuninnStorageError` — Muninn never silently starts
  empty over a corrupt store.
"""

from __future__ import annotations

import logging
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .errors import MuninnStorageError

logger = logging.getLogger("muninn.store")

SCHEMA_VERSION = "1"


@dataclass
class OpenReport:
    """What happened while opening a store."""

    recovered_from_backup: bool = False
    restored_backup: str | None = None
    backup_taken: bool = False
    integrity: str = "ok"


def _connect(path: Path, busy_timeout_ms: int) -> sqlite3.Connection:
    # check_same_thread=False: the one shared connection is used from
    # many threads, serialized by the owner's lock — that serialization
    # is the safety, and this flag is what permits it.
    conn = sqlite3.connect(
        str(path), timeout=busy_timeout_ms / 1000.0, check_same_thread=False
    )
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _quick_check_ok(conn: sqlite3.Connection) -> bool:
    try:
        row = conn.execute("PRAGMA quick_check").fetchone()
        return bool(row) and str(row[0]) == "ok"
    except sqlite3.Error:
        return False


def _backup_path(db_path: Path, generation: int) -> Path:
    return db_path.with_name(f"{db_path.name}.bak-{generation}")


def _sidecars(db_path: Path) -> list[Path]:
    return [Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")]


def take_backup(db_path: Path, keep: int) -> Path | None:
    """Rolling backup: shift generations down, snapshot the live store.

    Returns the newest backup path, or None when ``keep`` is 0.
    A failed backup never destroys the previous generations: rotation
    happens only after the new snapshot verifies.
    """
    if keep <= 0:
        return None
    newest = _backup_path(db_path, 1)
    tmp = db_path.with_name(f"{db_path.name}.bak-tmp")
    try:
        src = sqlite3.connect(str(db_path))
        try:
            dst = sqlite3.connect(str(tmp))
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()
        probe = sqlite3.connect(str(tmp))
        try:
            if not _quick_check_ok(probe):
                tmp.unlink(missing_ok=True)
                logger.error("muninn: backup verification failed; keeping old generations")
                return None
        finally:
            probe.close()
        # Rotate only now that the new snapshot is proven healthy.
        for gen in range(keep - 1, 0, -1):
            older = _backup_path(db_path, gen)
            if older.exists():
                shutil.move(str(older), str(_backup_path(db_path, gen + 1)))
        extra = _backup_path(db_path, keep + 1)
        extra.unlink(missing_ok=True)
        shutil.move(str(tmp), str(newest))
        return newest
    except sqlite3.Error as exc:
        logger.error("muninn: backup failed: %s", exc)
        tmp.unlink(missing_ok=True)
        return None


def _restore_from_backup(db_path: Path, keep: int) -> Path | None:
    """Restore the newest backup that passes quick_check. Returns it or None."""
    for gen in range(1, keep + 1):
        candidate = _backup_path(db_path, gen)
        if not candidate.exists():
            continue
        probe = sqlite3.connect(str(candidate))
        try:
            ok = _quick_check_ok(probe)
        finally:
            probe.close()
        if not ok:
            logger.error("muninn: backup generation %d is itself corrupt; skipping", gen)
            continue
        for sidecar in _sidecars(db_path):
            sidecar.unlink(missing_ok=True)
        shutil.copyfile(str(candidate), str(db_path))
        for sidecar in _sidecars(db_path):
            sidecar.unlink(missing_ok=True)
        return candidate
    return None


def open_store(
    db_path: Path,
    *,
    busy_timeout_ms: int,
    backup_keep: int,
    auto_backup: bool,
    schema_sql: str,
) -> tuple[sqlite3.Connection, OpenReport]:
    """Open (creating if needed) a Muninn store, healing corruption first.

    Applies the schema idempotently and returns the connection plus an
    :class:`OpenReport` describing any recovery that happened.
    """
    report = OpenReport()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    existed = db_path.exists()
    mtime_before = db_path.stat().st_mtime if existed else 0.0

    if existed:
        try:
            probe = _connect(db_path, busy_timeout_ms)
            try:
                healthy = _quick_check_ok(probe)
            finally:
                probe.close()
        except sqlite3.Error:
            # Not a database at all, unreadable header, etc. — same
            # road as a failed quick_check: restore or raise loudly.
            healthy = False
        if not healthy:
            logger.error(
                "muninn: store %s failed integrity — attempting restore from backup",
                db_path,
            )
            restored = _restore_from_backup(db_path, backup_keep) if backup_keep > 0 else None
            if restored is None:
                raise MuninnStorageError(
                    f"muninn store {db_path} is corrupt and no rolling backup "
                    f"verified; refusing to start empty over lost memory"
                )
            report.recovered_from_backup = True
            report.restored_backup = str(restored)
            logger.error("muninn: RECOVERED store %s from backup %s", db_path, restored)

    conn = _connect(db_path, busy_timeout_ms)
    try:
        conn.executescript(schema_sql)
        conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', ?)",
            (SCHEMA_VERSION,),
        )
        conn.commit()
    except sqlite3.Error as exc:
        conn.close()
        raise MuninnStorageError(f"muninn store {db_path} could not be prepared: {exc}") from exc

    if auto_backup and existed and backup_keep > 0:
        # Refresh the rolling backup only when the store changed since
        # the newest backup was taken — otherwise every open would
        # snapshot an identical store and push out useful generations.
        newest = _backup_path(db_path, 1)
        stale = (not newest.exists()) or (mtime_before > newest.stat().st_mtime)
        if stale:
            taken = take_backup(db_path, backup_keep)
            report.backup_taken = taken is not None
    return conn, report
