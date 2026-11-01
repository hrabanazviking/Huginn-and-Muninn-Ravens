"""RM-030 — Read-only filesystem behaviour for huginn.

Opening a local store that cannot be written to must fail loudly
and immediately with a typed ``HuginnStorageError`` — never hang
on the busy timeout, never surface as a raw ``sqlite3.Error`` or
``OSError``, and never be mistaken for corruption (which would
send the open down the backup-restore road). The facade's
``health()`` keeps its never-raises contract: it reports the
same refusal as an ``unhealthy`` dict carrying the typed error.

The fault is marked the way a user or a mount marks it: the
store file or its directory loses every write permission bit.
Huginn's open pre-flight reads those bits deliberately, so the
refusal holds even for a process privileged enough to override
them; a genuinely read-only mount is caught by the same
pre-flight (the process cannot write there) and, behind it, by
the translation of SQLite's own read-only errors during open.
No read-only *mode* is offered by this slice, and the Qdrant
backend has no local file to refuse — this slice is the local
backend only.
"""

import hashlib
import os
import sqlite3
import time

import pytest

from huginn import HuginnConfig, HuginnMemory
from huginn.errors import HuginnStorageError
from huginn.local_backend import LocalBackend


def _cfg(path, **overrides):
    return HuginnConfig(backend="local", local_db_path=str(path), **overrides)


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_readonly_store_file_fails_loudly_and_immediately(tmp_path):
    db = tmp_path / "h.db"
    h = HuginnMemory(_cfg(db))
    seed = h.upsert_memory("alpha seed document about ravens")
    h.close()
    before = _digest(db)
    os.chmod(db, 0o444)
    try:
        started = time.monotonic()
        with pytest.raises(HuginnStorageError) as caught:
            # Direct backend construction is the opening act (the
            # facade builds it lazily); a 60 s busy timeout must
            # play no part in the refusal.
            LocalBackend(_cfg(db, busy_timeout_ms=60_000))
        elapsed = time.monotonic() - started
    finally:
        os.chmod(db, 0o644)
    assert str(caught.value) == (
        f"huginn store {db} is read-only and cannot be opened for writing"
    )
    assert not isinstance(caught.value, sqlite3.Error)
    assert not isinstance(caught.value, OSError)
    assert "corrupt" not in str(caught.value)
    assert elapsed < 5.0
    assert _digest(db) == before
    assert not (tmp_path / "h.db.bak-1").exists()
    h2 = HuginnMemory(_cfg(db))
    try:
        assert h2.health()["integrity"] == "ok"
        assert h2.get(seed)["content"] == "alpha seed document about ravens"
    finally:
        h2.close()


def test_facade_reports_readonly_open_as_unhealthy_health(tmp_path):
    db = tmp_path / "h.db"
    h = HuginnMemory(_cfg(db))
    h.upsert_memory("a document that must survive")
    h.close()
    os.chmod(db, 0o444)
    try:
        h2 = HuginnMemory(_cfg(db))
        # health() never raises for backend trouble: the refusal
        # arrives as the unhealthy report, naming the typed error.
        info = h2.health()
        assert info["status"] == "unhealthy"
        assert info["error_type"] == "HuginnStorageError"
        assert info["error"] == (
            f"huginn store {db} is read-only and cannot be opened for writing"
        )
        # A real operation raises the typed error itself.
        with pytest.raises(HuginnStorageError):
            h2.upsert_memory("doomed write")
        h2.close()
    finally:
        os.chmod(db, 0o644)


def test_new_store_in_readonly_directory_is_refused_and_not_created(tmp_path):
    ro_dir = tmp_path / "ro"
    ro_dir.mkdir()
    db = ro_dir / "new.db"
    os.chmod(ro_dir, 0o555)
    try:
        started = time.monotonic()
        with pytest.raises(HuginnStorageError) as caught:
            LocalBackend(_cfg(db, busy_timeout_ms=60_000))
        elapsed = time.monotonic() - started
    finally:
        os.chmod(ro_dir, 0o755)
    assert str(caught.value) == (
        f"huginn store {db} is read-only and cannot be opened for writing"
    )
    assert elapsed < 5.0
    assert not db.exists()
    assert list(ro_dir.iterdir()) == []
