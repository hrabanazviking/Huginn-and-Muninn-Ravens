"""Store machinery for Huginn's local backend: WAL SQLite open,
integrity, rolling backups — the same discipline as Muninn's store,
implemented per package so huginn installs and runs independently.

Durability contract: WAL + ``synchronous=FULL`` (a kill -9 loses at
most the uncommitted transaction); backups are made through SQLite's
backup API from a verified-healthy store; on open, a corrupt main
store is restored from the newest backup that itself verifies —
loudly — and if none verifies, opening raises
:class:`HuginnStorageError` rather than starting empty over lost data.
"""

from __future__ import annotations

import logging
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .errors import HuginnStorageError

logger = logging.getLogger("huginn.store")

SCHEMA_VERSION = "1"


@dataclass
class OpenReport:
    recovered_from_backup: bool = False
    restored_backup: str | None = None
    backup_taken: bool = False
    integrity: str = "ok"


def _connect(path: Path, busy_timeout_ms: int) -> sqlite3.Connection:
    # check_same_thread=False: one shared connection, many threads,
    # serialized by the owner's lock.
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
    """Rolling backup; rotation happens only after the new snapshot
    verifies, so a failed backup never destroys older generations."""
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
                logger.error("huginn: backup verification failed; keeping old generations")
                return None
        finally:
            probe.close()
        for gen in range(keep - 1, 0, -1):
            older = _backup_path(db_path, gen)
            if older.exists():
                shutil.move(str(older), str(_backup_path(db_path, gen + 1)))
        _backup_path(db_path, keep + 1).unlink(missing_ok=True)
        shutil.move(str(tmp), str(newest))
        return newest
    except sqlite3.Error as exc:
        logger.error("huginn: backup failed: %s", exc)
        tmp.unlink(missing_ok=True)
        return None


def _restore_from_backup(db_path: Path, keep: int) -> Path | None:
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
            logger.error("huginn: backup generation %d is itself corrupt; skipping", gen)
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
    """Open (creating if needed) a Huginn local store, healing first."""
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
            healthy = False
        if not healthy:
            logger.error(
                "huginn: store %s failed integrity — attempting restore from backup",
                db_path,
            )
            restored = _restore_from_backup(db_path, backup_keep) if backup_keep > 0 else None
            if restored is None:
                raise HuginnStorageError(
                    f"huginn store {db_path} is corrupt and no rolling backup "
                    f"verified; refusing to start empty over lost memory"
                )
            report.recovered_from_backup = True
            report.restored_backup = str(restored)
            logger.error("huginn: RECOVERED store %s from backup %s", db_path, restored)

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
        raise HuginnStorageError(f"huginn store {db_path} could not be prepared: {exc}") from exc

    if auto_backup and existed and backup_keep > 0:
        newest = _backup_path(db_path, 1)
        stale = (not newest.exists()) or (mtime_before > newest.stat().st_mtime)
        if stale:
            taken = take_backup(db_path, backup_keep)
            report.backup_taken = taken is not None
    return conn, report
