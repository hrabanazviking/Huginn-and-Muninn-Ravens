"""RM-031 — Locked-store contention for huginn's local backend.

A second process holding the local store's write lock is a
normal event for a memory store that several processes share.
The defined behaviour (``docs/LOCKED_STORE.md``) mirrors
Muninn's:

* the contender waits — the configured ``busy_timeout_ms`` is
  honoured, neither skipped nor exceeded by an unbounded hang;
* if the lock is released inside the timeout, the open or write
  simply succeeds;
* if the timeout expires first, the failure is the typed
  ``HuginnStorageError`` naming the contention — one stable
  message shape for opens, one for writes — never a raw
  ``sqlite3.Error``, and never the corruption road (contention
  must not trigger a backup restore or a "corrupt" verdict);
  the facade's ``health()`` keeps its never-raises contract and
  reports the same refusal as an ``unhealthy`` dict;
* pure reads are not contention at all: WAL readers proceed
  against a snapshot while another process holds the write lock;
* once the lock is released, the store (and an already-open
  object whose write was refused) works normally again.

The lock holder is a real second process (a subprocess running
a raw ``sqlite3`` connection in an exclusive transaction) for
the open and write acceptance tests, as the roadmap requires;
a second in-process connection drives the remaining cases,
which exercise the same SQLite lock. The Qdrant backend has no
local file and no SQLite lock; it is untouched by this slice.
"""

import hashlib
import sqlite3
import subprocess
import sys
import time
from contextlib import contextmanager

import pytest

from huginn import HuginnConfig, HuginnMemory
from huginn.errors import HuginnStorageError
from huginn.local_backend import LocalBackend

HOLDER_SCRIPT = """
import sqlite3
import sys
import time
from pathlib import Path

db, ready, release = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
hold = float(sys.argv[4])
conn = sqlite3.connect(db)
conn.execute("BEGIN EXCLUSIVE")
conn.execute("CREATE TABLE IF NOT EXISTS rm031_hold (x INTEGER)")
conn.execute("INSERT INTO rm031_hold VALUES (1)")
ready.write_text("held")
if hold > 0:
    time.sleep(hold)
else:
    deadline = time.monotonic() + 60
    while not release.exists() and time.monotonic() < deadline:
        time.sleep(0.02)
conn.rollback()
conn.close()
"""


def _cfg(path, **overrides):
    return HuginnConfig(backend="local", local_db_path=str(path), **overrides)


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@contextmanager
def _process_lock(tmp_path, db, hold=0.0):
    """A second process holding the store's write lock.

    Yields once the holder signals the lock is held. With
    ``hold=0`` the holder keeps the lock until this context
    exits; with ``hold>0`` it releases after that many seconds.
    """
    ready = tmp_path / "holder.ready"
    release = tmp_path / "holder.release"
    proc = subprocess.Popen(
        [sys.executable, "-c", HOLDER_SCRIPT, str(db), str(ready), str(release), str(hold)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 30
        while not ready.exists():
            if proc.poll() is not None:
                raise AssertionError("lock holder exited before holding the lock")
            if time.monotonic() > deadline:
                raise AssertionError("lock holder never signalled the lock")
            time.sleep(0.02)
        yield proc
    finally:
        release.write_text("release")
        proc.wait(timeout=30)


def _local_lock(db):
    """A second connection (same process) holding the write lock."""
    conn = sqlite3.connect(str(db))
    conn.execute("BEGIN EXCLUSIVE")
    conn.execute("CREATE TABLE IF NOT EXISTS rm031_hold (x INTEGER)")
    conn.execute("INSERT INTO rm031_hold VALUES (1)")
    return conn


def test_open_under_second_process_lock_times_out_with_typed_contention_error(tmp_path):
    db = tmp_path / "h.db"
    h = HuginnMemory(_cfg(db))
    seed = h.upsert_memory("alpha seed document about ravens")
    h.close()
    before = _digest(db)
    with _process_lock(tmp_path, db):
        started = time.monotonic()
        with pytest.raises(HuginnStorageError) as caught:
            LocalBackend(_cfg(db, busy_timeout_ms=1500))
        elapsed = time.monotonic() - started
    # The busy timeout was honoured: the open waited for the
    # lock instead of failing at once, and did not hang.
    assert elapsed >= 1.2
    assert elapsed < 20.0
    assert str(caught.value) == (
        f"huginn store {db} is locked by another process "
        f"(busy timeout 1500 ms expired)"
    )
    assert not isinstance(caught.value, sqlite3.Error)
    # Contention is not corruption: no restore was attempted,
    # the word never appears, and the store file is untouched.
    assert "corrupt" not in str(caught.value)
    assert _digest(db) == before
    assert not (tmp_path / "h.db.bak-1").exists()
    # Released, the same store opens clean with its data intact.
    h2 = HuginnMemory(_cfg(db))
    try:
        assert h2.health()["integrity"] == "ok"
        assert h2.get(seed)["content"] == "alpha seed document about ravens"
    finally:
        h2.close()


def test_open_succeeds_when_lock_is_released_within_the_timeout(tmp_path):
    db = tmp_path / "h.db"
    h = HuginnMemory(_cfg(db))
    seed = h.upsert_memory("released in time document")
    h.close()
    with _process_lock(tmp_path, db, hold=0.8):
        started = time.monotonic()
        backend = LocalBackend(_cfg(db, busy_timeout_ms=8000))
        elapsed = time.monotonic() - started
    try:
        # The open genuinely waited for the holder's release.
        assert elapsed >= 0.5
        assert backend.get(seed)["content"] == "released in time document"
    finally:
        backend.close()


def test_facade_reports_locked_open_as_unhealthy_health(tmp_path):
    db = tmp_path / "h.db"
    h = HuginnMemory(_cfg(db))
    h.upsert_memory("a document that must survive")
    h.close()
    holder = _local_lock(db)
    try:
        h2 = HuginnMemory(_cfg(db, busy_timeout_ms=1500))
        # health() never raises for backend trouble: the refusal
        # arrives as the unhealthy report, naming the typed error.
        info = h2.health()
        assert info["status"] == "unhealthy"
        assert info["error_type"] == "HuginnStorageError"
        assert info["error"] == (
            f"huginn store {db} is locked by another process "
            f"(busy timeout 1500 ms expired)"
        )
        # A real operation raises the typed error itself.
        with pytest.raises(HuginnStorageError):
            h2.upsert_memory("doomed write")
        h2.close()
    finally:
        holder.rollback()
        holder.close()


def test_upsert_under_second_process_lock_is_typed_contention(tmp_path):
    db = tmp_path / "h.db"
    h = HuginnMemory(_cfg(db, busy_timeout_ms=1500))
    seed = h.upsert_memory("alpha seed document about ravens")
    with _process_lock(tmp_path, db):
        started = time.monotonic()
        with pytest.raises(HuginnStorageError) as caught:
            h.upsert_memory("blocked thought about locks")
        elapsed = time.monotonic() - started
        assert elapsed >= 1.2
        assert elapsed < 20.0
        assert str(caught.value) == (
            "huginn write failed during upsert: store is locked "
            "by another process (busy timeout expired)"
        )
        assert not isinstance(caught.value, sqlite3.Error)
        # The refused write stored nothing.
        assert h.get(seed)["content"] == "alpha seed document about ravens"
        assert h.search("blocked") == []
    # The same object writes normally once the lock is gone.
    beta = h.upsert_memory("after the lock released document")
    assert h.get(beta)["content"] == "after the lock released document"
    h.close()


def test_reads_proceed_while_second_process_holds_the_write_lock(tmp_path):
    db = tmp_path / "h.db"
    h = HuginnMemory(_cfg(db))
    seed = h.upsert_memory("readable during contention document")
    with _process_lock(tmp_path, db):
        started = time.monotonic()
        assert h.get(seed)["content"] == "readable during contention document"
        assert [r["id"] for r in h.search("readable contention")] == [seed]
        # WAL snapshot reads do not wait out any busy timeout.
        assert time.monotonic() - started < 5.0
    h.close()


def test_zero_busy_timeout_open_fails_fast_with_typed_contention_error(tmp_path):
    db = tmp_path / "h.db"
    h = HuginnMemory(_cfg(db))
    h.upsert_memory("alpha seed document")
    h.close()
    holder = _local_lock(db)
    try:
        started = time.monotonic()
        with pytest.raises(HuginnStorageError) as caught:
            LocalBackend(_cfg(db, busy_timeout_ms=0))
        elapsed = time.monotonic() - started
    finally:
        holder.rollback()
        holder.close()
    assert str(caught.value) == (
        f"huginn store {db} is locked by another process (busy timeout 0 ms expired)"
    )
    assert elapsed < 5.0
