"""RM-023 — Shutdown cleanliness for huginn (local backend).

``close()`` must leave the store exactly as a healthy store
should be left: the WAL fully checkpointed (no half-written
tail for the next open to recover), no lingering threads, and
a reopen that performs **zero** recovery —
``recovered_from_backup`` stays False in health and a raw
``PRAGMA wal_checkpoint`` finds nothing to do.
"""

import sqlite3
import threading
from pathlib import Path

from huginn import HuginnMemory
from huginn.config import HuginnConfig


def _local(db):
    return HuginnMemory(HuginnConfig(backend="local", local_db_path=db))


def _wal_size(db):
    wal = Path(db + "-wal")
    return wal.stat().st_size if wal.exists() else 0


def _checkpoint(db):
    conn = sqlite3.connect(db)
    row = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
    conn.close()
    return row  # (busy, log_pages, checkpointed_pages)


def test_close_checkpoints_wal_and_reopen_recovers_nothing(tmp_path):
    db = str(tmp_path / "h.db")
    h = _local(db)
    h.upsert_memory("the ravens remember shutdown", importance=8)
    h.upsert_memory("a second document about clean closes", importance=6)
    h.close()
    # The WAL is gone (or empty): close checkpointed everything.
    assert _wal_size(db) == 0

    reopened = _local(db)
    try:
        health = reopened.health()
        assert health["recovered_from_backup"] is False
        assert health["integrity"] == "ok"
        results = reopened.search("ravens remember")
        assert results, "search lost the stored document across reopen"
    finally:
        reopened.close()
    assert _wal_size(db) == 0
    busy, log_pages, _checkpointed = _checkpoint(db)
    assert busy == 0
    assert log_pages == 0


def test_double_close_is_a_noop_and_reopen_is_clean(tmp_path):
    db = str(tmp_path / "h.db")
    h = _local(db)
    h.upsert_memory("a document that survives two closes", importance=5)
    h.close()
    h.close()  # idempotent: no error, no state change
    assert _wal_size(db) == 0
    reopened = _local(db)
    try:
        assert reopened.health()["recovered_from_backup"] is False
        assert reopened.search("survives two closes")
    finally:
        reopened.close()


def test_close_leaves_no_lingering_threads(tmp_path):
    baseline = {t.ident for t in threading.enumerate()}
    h = _local(str(tmp_path / "h.db"))
    h.upsert_memory("thread check document", importance=5)
    h.close()
    lingering = [
        t
        for t in threading.enumerate()
        if t.ident not in baseline and t.is_alive()
    ]
    assert lingering == []
