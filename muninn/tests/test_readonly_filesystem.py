"""RM-030 — Read-only filesystem behaviour for muninn.

Opening a store that cannot be written to must fail loudly and
immediately with a typed ``MuninnStorageError`` — never hang on
the busy timeout, never surface as a raw ``sqlite3.Error`` or
``OSError``, and never be mistaken for corruption (which would
send the open down the backup-restore road and either destroy
the caller's time or lie about the store's state).

The fault is marked the way a user or a mount marks it: the
store file or its directory loses every write permission bit.
Muninn's open pre-flight reads those bits deliberately, so the
refusal holds even for a process privileged enough to override
them; a genuinely read-only mount is caught by the same
pre-flight (the process cannot write there) and, behind it, by
the translation of SQLite's own read-only errors during open.
No read-only *mode* is offered by this slice: a Muninn store is
opened for writing or not at all.
"""

import hashlib
import os
import sqlite3
import time

import pytest

from muninn import HebbianMemory, MuninnStorageError
from muninn.config import MuninnConfig


def _mem(path, **overrides):
    return HebbianMemory(MuninnConfig(db_path=str(path), **overrides))


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_readonly_store_file_fails_loudly_and_immediately(tmp_path):
    db = tmp_path / "m.db"
    m = _mem(db)
    seed = m.remember("alpha seed")
    m.close()
    before = _digest(db)
    os.chmod(db, 0o444)
    try:
        started = time.monotonic()
        with pytest.raises(MuninnStorageError) as caught:
            # A 60 s busy timeout must play no part: the refusal
            # is a pre-flight, not a lock wait.
            _mem(db, busy_timeout_ms=60_000)
        elapsed = time.monotonic() - started
    finally:
        os.chmod(db, 0o644)
    assert str(caught.value) == (
        f"muninn store {db} is read-only and cannot be opened for writing"
    )
    assert not isinstance(caught.value, sqlite3.Error)
    assert not isinstance(caught.value, OSError)
    assert "corrupt" not in str(caught.value)
    assert elapsed < 5.0
    # The failed open touched nothing: no restore, no rewrite,
    # no new backup generation.
    assert _digest(db) == before
    assert not (tmp_path / "m.db.bak-1").exists()
    # Unmarked, the same store opens with its data intact and
    # performs zero recovery.
    m2 = _mem(db)
    try:
        assert m2.recovered_from_backup is False
        assert m2.health()["integrity"] == "ok"
        assert m2.get_node(seed).content == "alpha seed"
    finally:
        m2.close()


def test_store_in_readonly_directory_fails_loudly(tmp_path):
    db = tmp_path / "m.db"
    m = _mem(db)
    seed = m.remember("kept in a read-only directory")
    m.close()
    os.chmod(tmp_path, 0o555)
    try:
        with pytest.raises(MuninnStorageError) as caught:
            _mem(db)
    finally:
        os.chmod(tmp_path, 0o755)
    assert "is read-only" in str(caught.value)
    m2 = _mem(db)
    try:
        assert m2.get_node(seed).content == "kept in a read-only directory"
    finally:
        m2.close()


def test_new_store_in_readonly_directory_is_refused_and_not_created(tmp_path):
    ro_dir = tmp_path / "ro"
    ro_dir.mkdir()
    db = ro_dir / "new.db"
    os.chmod(ro_dir, 0o555)
    try:
        started = time.monotonic()
        with pytest.raises(MuninnStorageError) as caught:
            _mem(db, busy_timeout_ms=60_000)
        elapsed = time.monotonic() - started
    finally:
        os.chmod(ro_dir, 0o755)
    assert str(caught.value) == (
        f"muninn store {db} is read-only and cannot be opened for writing"
    )
    assert elapsed < 5.0
    assert not db.exists()
    assert list(ro_dir.iterdir()) == []


def test_new_store_below_readonly_ancestor_is_refused(tmp_path):
    ro_dir = tmp_path / "ro"
    ro_dir.mkdir()
    db = ro_dir / "sub" / "deep.db"
    os.chmod(ro_dir, 0o555)
    try:
        with pytest.raises(MuninnStorageError):
            _mem(db)
    finally:
        os.chmod(ro_dir, 0o755)
    # The missing intermediate directory was never created.
    assert not (ro_dir / "sub").exists()
