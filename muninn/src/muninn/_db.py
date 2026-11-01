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
* A store on a read-only filesystem, in a read-only directory, or
  marked read-only itself is refused on open with a typed
  :class:`MuninnStorageError` — immediately, before any connection
  or backup-restore attempt (RM-030; see
  ``docs/READONLY_FILESYSTEM.md``). There is no read-only mode:
  Muninn stores are opened for writing or not at all.
* A store locked by another process is awaited up to the
  configured busy timeout; if the lock is still held when the
  timeout expires, opening raises :class:`MuninnStorageError`
  naming the contention (RM-031; see ``docs/LOCKED_STORE.md``).
  Contention is never mistaken for corruption and never takes
  the backup-restore road. Pure reads are unaffected by a held
  write lock: WAL readers proceed against a snapshot.
* Partial file states have defined open behaviour (RM-032; see
  ``docs/PARTIAL_FILE_STATES.md``): a leftover ``.bak-tmp`` from
  a killed backup is removed on open and is never read as a
  store or a restore candidate; a main store truncated to zero
  bytes takes the corruption road (restore from a verified
  backup, else the typed refusal) instead of opening as a
  silently empty store; and a non-empty write-ahead log left
  without its main file is evidence of lost memory — a verified
  backup is restored, else opening raises a typed
  :class:`MuninnStorageError` naming the partial state.
"""

from __future__ import annotations

import errno
import logging
import os
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


def _is_readonly_error(exc: BaseException) -> bool:
    """Does this failure mean the store location is read-only?

    Matches the filesystem errnos (EROFS / EACCES / EPERM) and
    SQLite's own wordings (``attempt to write a readonly
    database``, ``unable to open database file`` on a read-only
    filesystem) — the RM-030 classification.
    """
    if isinstance(exc, OSError) and exc.errno in (
        errno.EROFS,
        errno.EACCES,
        errno.EPERM,
    ):
        return True
    text = str(exc).lower()
    return (
        "readonly" in text
        or "read-only" in text
        or "unable to open database file" in text
    )


def _check_not_readonly(db_path: Path) -> None:
    """RM-030 pre-flight: refuse a read-only store location loudly.

    Runs before any connection is attempted, so a read-only open
    fails immediately — it never waits out the busy timeout, never
    probes the store, and never mistakes read-only for corruption
    and attempts a backup restore over a location it cannot write
    to. A location is read-only when the store file or the
    directory that must hold it (the parent, or the nearest
    existing ancestor when the parent does not exist yet) carries
    no write permission bit at all, or when this process cannot
    write there (a read-only mount, an ACL denial). The bit check
    is deliberate: a file or directory marked read-only is
    read-only by its owner's declaration, even for a process
    privileged enough to override the bits.
    """
    if db_path.exists() and (
        db_path.stat().st_mode & 0o222 == 0 or not os.access(db_path, os.W_OK)
    ):
        raise MuninnStorageError(
            f"muninn store {db_path} is read-only and cannot be opened for writing"
        )
    ancestor = db_path.parent
    while not ancestor.exists():
        if ancestor.parent == ancestor:
            return
        ancestor = ancestor.parent
    if ancestor.is_dir() and (
        ancestor.stat().st_mode & 0o222 == 0 or not os.access(ancestor, os.W_OK)
    ):
        raise MuninnStorageError(
            f"muninn store {db_path} is read-only and cannot be opened for writing"
        )


def _is_locked_error(exc: BaseException) -> bool:
    """Does this failure mean another connection holds the lock?

    Matches SQLite's busy/locked wordings (``database is locked``,
    ``database table is locked``, ``database is busy``) and, where
    the interpreter exposes it, the SQLITE_BUSY / SQLITE_LOCKED
    result codes (5 / 6, extended-code high bits ignored) — the
    RM-031 classification.
    """
    code = getattr(exc, "sqlite_errorcode", None)
    if isinstance(code, int) and code & 0xFF in (5, 6):
        return True
    text = str(exc).lower()
    return "locked" in text or "is busy" in text


def _quick_check_ok(conn: sqlite3.Connection) -> bool:
    try:
        row = conn.execute("PRAGMA quick_check").fetchone()
        return bool(row) and str(row[0]) == "ok"
    except sqlite3.Error:
        return False


def _backup_path(db_path: Path, generation: int) -> Path:
    return db_path.with_name(f"{db_path.name}.bak-{generation}")


def _backup_tmp_path(db_path: Path) -> Path:
    return db_path.with_name(f"{db_path.name}.bak-tmp")


def _discard_stale_backup_tmp(db_path: Path) -> None:
    """RM-032: remove a ``.bak-tmp`` left behind by a killed backup.

    The temp snapshot is transient by contract (see
    ``docs/FORMAT_STABILITY.md``): it is never read as a store
    and never a restore candidate, so a leftover carries no
    information — the last *completed* backup is the newest
    ``.bak-N`` generation. Removing it on open keeps the store
    directory honest and stops a later reader mistaking it for
    a generation.
    """
    tmp = _backup_tmp_path(db_path)
    if tmp.exists():
        logger.warning("muninn: removing stale backup temp file %s", tmp)
        tmp.unlink(missing_ok=True)


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
    tmp = _backup_tmp_path(db_path)
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
    _check_not_readonly(db_path)
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        if _is_readonly_error(exc):
            raise MuninnStorageError(
                f"muninn store {db_path} is read-only and cannot be opened for writing"
            ) from exc
        raise
    _discard_stale_backup_tmp(db_path)
    existed = db_path.exists()
    mtime_before = db_path.stat().st_mtime if existed else 0.0

    if not existed:
        # RM-032: a non-empty write-ahead log without its main
        # file is a partial state — frames of committed memory
        # whose store file is gone. Never start empty over it:
        # restore a verified backup (which removes the orphaned
        # sidecars) or refuse loudly. An empty or absent WAL
        # carries no frames and is not evidence of a lost store.
        wal_path = Path(str(db_path) + "-wal")
        if wal_path.exists() and wal_path.stat().st_size > 0:
            logger.error(
                "muninn: store %s is missing its main file but a "
                "write-ahead log remains — attempting restore from backup",
                db_path,
            )
            restored = _restore_from_backup(db_path, backup_keep) if backup_keep > 0 else None
            if restored is None:
                raise MuninnStorageError(
                    f"muninn store {db_path} has a write-ahead log but no main "
                    f"file and no rolling backup verified; refusing to start "
                    f"empty over lost memory"
                )
            report.recovered_from_backup = True
            report.restored_backup = str(restored)
            logger.error("muninn: RECOVERED store %s from backup %s", db_path, restored)
            existed = True
            mtime_before = db_path.stat().st_mtime

    if existed:
        if db_path.stat().st_size == 0:
            # RM-032: a zero-length main file is a truncated
            # store, not a fresh one — SQLite alone would call
            # it an empty database and open it silently. Take
            # the corruption road instead: restore or refuse.
            healthy = False
        else:
            try:
                probe = _connect(db_path, busy_timeout_ms)
                try:
                    try:
                        row = probe.execute("PRAGMA quick_check").fetchone()
                        healthy = bool(row) and str(row[0]) == "ok"
                    except sqlite3.Error as exc:
                        if _is_readonly_error(exc):
                            raise MuninnStorageError(
                                f"muninn store {db_path} is read-only and cannot be "
                                f"opened for writing"
                            ) from exc
                        if _is_locked_error(exc):
                            # RM-031: contention is not corruption —
                            # never take the restore road for it.
                            raise MuninnStorageError(
                                f"muninn store {db_path} is locked by another process "
                                f"(busy timeout {busy_timeout_ms} ms expired)"
                            ) from exc
                        healthy = False
                finally:
                    probe.close()
            except sqlite3.Error as exc:
                if _is_readonly_error(exc):
                    # RM-030: read-only is not corruption — never take
                    # the restore road for it; fail loudly at once.
                    raise MuninnStorageError(
                        f"muninn store {db_path} is read-only and cannot be opened for writing"
                    ) from exc
                if _is_locked_error(exc):
                    # RM-031: contention is not corruption either.
                    raise MuninnStorageError(
                        f"muninn store {db_path} is locked by another process "
                        f"(busy timeout {busy_timeout_ms} ms expired)"
                    ) from exc
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

    try:
        conn = _connect(db_path, busy_timeout_ms)
    except sqlite3.Error as exc:
        if _is_readonly_error(exc):
            raise MuninnStorageError(
                f"muninn store {db_path} is read-only and cannot be opened for writing"
            ) from exc
        if _is_locked_error(exc):
            raise MuninnStorageError(
                f"muninn store {db_path} is locked by another process "
                f"(busy timeout {busy_timeout_ms} ms expired)"
            ) from exc
        raise MuninnStorageError(
            f"muninn store {db_path} could not be prepared: {exc}"
        ) from exc
    try:
        conn.executescript(schema_sql)
        conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', ?)",
            (SCHEMA_VERSION,),
        )
        conn.commit()
    except sqlite3.Error as exc:
        conn.close()
        if _is_readonly_error(exc):
            raise MuninnStorageError(
                f"muninn store {db_path} is read-only and cannot be opened for writing"
            ) from exc
        if _is_locked_error(exc):
            raise MuninnStorageError(
                f"muninn store {db_path} is locked by another process "
                f"(busy timeout {busy_timeout_ms} ms expired)"
            ) from exc
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
