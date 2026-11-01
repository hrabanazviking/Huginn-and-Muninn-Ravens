"""RM-023 — Shutdown cleanliness for muninn.

``close()`` must leave the store exactly as a healthy store
should be left: the WAL fully checkpointed (no half-written
tail for the next open to recover), no lingering threads, and
a reopen that performs **zero** recovery —
``recovered_from_backup`` stays False and a raw
``PRAGMA wal_checkpoint`` finds nothing to do.
"""

import sqlite3
import threading
from pathlib import Path

from muninn import HebbianMemory
from muninn.config import MuninnConfig


def _mem(db):
    return HebbianMemory(MuninnConfig(db_path=db))


def _wal_size(db):
    wal = Path(db + "-wal")
    return wal.stat().st_size if wal.exists() else 0


def _checkpoint(db):
    conn = sqlite3.connect(db)
    row = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
    conn.close()
    return row  # (busy, log_pages, checkpointed_pages)


def test_close_checkpoints_wal_and_reopen_recovers_nothing(tmp_path):
    db = str(tmp_path / "m.db")
    m = _mem(db)
    a = m.remember("first raven memory", importance=7)
    b = m.remember("second raven memory", importance=6)
    m.associate(a, b, strength=0.8)
    m.activate(a)
    m.close()
    # The WAL is gone (or empty): close checkpointed everything.
    assert _wal_size(db) == 0

    reopened = _mem(db)
    try:
        assert reopened.recovered_from_backup is False
        assert reopened.health()["integrity"] == "ok"
        assert reopened.stats()["total_nodes"] == 2
        assert reopened.get_associations(a)[0]["strength"] > 0.0
    finally:
        reopened.close()
    assert _wal_size(db) == 0
    busy, log_pages, _checkpointed = _checkpoint(db)
    assert busy == 0
    assert log_pages == 0


def test_double_close_is_a_noop_and_reopen_is_clean(tmp_path):
    db = str(tmp_path / "m.db")
    m = _mem(db)
    m.remember("a memory that survives two closes", importance=5)
    m.close()
    m.close()  # idempotent: no error, no state change
    assert _wal_size(db) == 0
    reopened = _mem(db)
    try:
        assert reopened.recovered_from_backup is False
        assert reopened.stats()["total_nodes"] == 1
    finally:
        reopened.close()


def test_close_leaves_no_lingering_threads(tmp_path):
    baseline = {t.ident for t in threading.enumerate()}
    m = _mem(str(tmp_path / "m.db"))
    m.remember("thread check memory", importance=5)
    m.close()
    lingering = [
        t
        for t in threading.enumerate()
        if t.ident not in baseline and t.is_alive()
    ]
    assert lingering == []
