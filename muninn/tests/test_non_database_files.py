"""RM-033 — Non-database files at the muninn store path.

The path a caller names can hold things that are not a
database at all. The defined behaviour
(``docs/NON_DATABASE_FILES.md``), mirrored in huginn:

* a text file (long or short) is a corrupt store: the
  corruption road — restore a verified backup, else the
  typed corrupt refusal; the file's bytes are never touched
  by a refused open;
* an empty file is the RM-032 truncated store: the same
  corruption road, never a silently fresh store;
* a directory is refused *as a directory*, by a pre-flight
  shape check that runs before any connection or restore
  attempt, with or without a backup beside it. Before this
  slice a directory with a verified backup leaked a raw
  ``IsADirectoryError`` out of the restore copy (measured by
  probe against the RM-032 packages), and one without was
  misreported as a corrupt store. A directory is never
  deleted or replaced to make room for a restore;
* any other non-regular file (a FIFO here) is refused with
  the typed not-a-regular-file message, before any open is
  attempted on it.

Every answer is a typed ``MuninnStorageError`` — never a
traceback, never a raw ``OSError`` or ``sqlite3.Error``.
"""

import hashlib
import os
from pathlib import Path

import pytest

from muninn import HebbianMemory, MuninnConfig, MuninnStorageError

TEXT = "this is a plain text file, not a database at all. " * 4


def _mem(path, **overrides):
    return HebbianMemory(MuninnConfig(db_path=str(path), **overrides))


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _seed_with_backup(db):
    """Two opens, so ``.bak-1`` holds the alpha-only snapshot."""
    m = _mem(db)
    alpha = m.remember("alpha seed memory")
    m.close()
    m = _mem(db)
    m.remember("beta second memory")
    m.close()
    assert Path(f"{db}.bak-1").exists()
    return alpha


def _directory_message(db):
    return (
        f"muninn store {db} is a directory, not a database "
        f"file; refusing to open"
    )


def _corrupt_message(db):
    return (
        f"muninn store {db} is corrupt and no rolling backup "
        f"verified; refusing to start empty over lost memory"
    )


def test_text_file_without_backup_refuses_typed(tmp_path):
    db = tmp_path / "m.db"
    db.write_text(TEXT)
    before = _digest(db)
    with pytest.raises(MuninnStorageError) as caught:
        _mem(db)
    assert str(caught.value) == _corrupt_message(db)
    # The refusal is the typed error itself (not a wrapped
    # sqlite3 error), and the file stands byte-identical.
    assert type(caught.value) is MuninnStorageError
    assert _digest(db) == before
    # No sidecars or backups were created by the refused open.
    # RM-037 amendment: the one new neighbour is the zero-byte
    # `.open-lock` coordination file — the corrupt-store road
    # runs under the per-store coordination lock, and the lock
    # file is left in place by design (docs/FORMAT_STABILITY.md).
    # The RM-033 pre-flight refusals (directory, non-regular
    # file, read-only) still create nothing at all.
    assert sorted(p.name for p in tmp_path.iterdir()) == ["m.db", "m.db.open-lock"]


def test_short_text_file_without_backup_refuses_typed(tmp_path):
    db = tmp_path / "m.db"
    db.write_text("hello")
    with pytest.raises(MuninnStorageError) as caught:
        _mem(db)
    assert str(caught.value) == _corrupt_message(db)
    assert db.read_text() == "hello"


def test_text_file_with_backup_restores(tmp_path):
    db = tmp_path / "m.db"
    alpha = _seed_with_backup(db)
    db.write_text(TEXT)
    m = _mem(db)
    assert m.recovered_from_backup is True
    # The restored store is the backup's state: alpha, not beta.
    assert m.stats()["total_nodes"] == 1
    assert m.get_node(alpha) is not None
    m.close()


def test_empty_file_without_backup_refuses_typed(tmp_path):
    db = tmp_path / "m.db"
    db.write_bytes(b"")
    with pytest.raises(MuninnStorageError) as caught:
        _mem(db)
    assert str(caught.value) == _corrupt_message(db)
    # Still empty, still a file: nothing was created over it.
    assert db.is_file() and db.stat().st_size == 0


def test_empty_file_with_backup_restores(tmp_path):
    db = tmp_path / "m.db"
    alpha = _seed_with_backup(db)
    db.write_bytes(b"")
    m = _mem(db)
    assert m.recovered_from_backup is True
    assert m.stats()["total_nodes"] == 1
    assert m.get_node(alpha) is not None
    m.close()


def test_directory_without_backup_refuses_as_directory(tmp_path):
    db = tmp_path / "m.db"
    db.mkdir()
    (db / "keep.txt").write_text("someone's files")
    with pytest.raises(MuninnStorageError) as caught:
        _mem(db)
    assert str(caught.value) == _directory_message(db)
    assert type(caught.value) is MuninnStorageError
    # The directory and its contents stand untouched, and a
    # second attempt refuses identically.
    assert db.is_dir()
    assert (db / "keep.txt").read_text() == "someone's files"
    with pytest.raises(MuninnStorageError) as caught2:
        _mem(db)
    assert str(caught2.value) == _directory_message(db)


def test_directory_with_backup_refuses_as_directory(tmp_path):
    # The pre-fix leak: a verified backup beside a directory
    # sent the open down the restore road, whose file copy
    # raised a raw IsADirectoryError out of open_store.
    db = tmp_path / "m.db"
    _seed_with_backup(db)
    bak = Path(f"{db}.bak-1")
    bak_digest = _digest(bak)
    db.unlink()
    db.mkdir()
    with pytest.raises(MuninnStorageError) as caught:
        _mem(db)
    assert str(caught.value) == _directory_message(db)
    assert type(caught.value) is MuninnStorageError
    # The directory was not replaced by the restore, and the
    # backup generation was not consumed or rotated.
    assert db.is_dir()
    assert _digest(bak) == bak_digest


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="no mkfifo on this platform")
def test_fifo_refuses_as_not_a_regular_file(tmp_path):
    db = tmp_path / "m.db"
    os.mkfifo(db)
    with pytest.raises(MuninnStorageError) as caught:
        _mem(db)
    assert str(caught.value) == (
        f"muninn store {db} is not a regular file; refusing to open"
    )
    assert type(caught.value) is MuninnStorageError
    assert db.exists() and not db.is_file()
