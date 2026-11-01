"""RM-032 — Partial-file states for muninn.

A store is more than one file: the main database, its ``-wal``
and ``-shm`` sidecars, the rolling ``.bak-N`` generations and
the transient ``.bak-tmp`` a backup is written to first. A
crash, a killed backup, or a careless copy can leave any
combination of those behind. The defined behaviour
(``docs/PARTIAL_FILE_STATES.md``), mirrored in huginn:

* main present, WAL missing — the normal post-checkpoint
  state: opens, all checkpointed data intact, no recovery;
* main present, WAL garbage — SQLite discards an invalid WAL;
  the checkpointed data stands, no recovery;
* main truncated (partially, or to zero bytes) — the
  corruption road: restore the newest verified backup, or
  the typed refusal. A zero-length main file is *not* a fresh
  store — before this slice SQLite's empty-file convention
  opened it as a silently empty store, even with a verified
  backup sitting beside it (and the empty store then rotated
  into the backup chain on later opens);
* main missing, non-empty WAL present — the WAL is evidence
  of lost memory: restore a verified backup, or a typed
  refusal naming the partial state; never start empty and
  discard the WAL silently;
* ``.bak-tmp`` left behind by a killed backup — removed on
  open, never read as a store, never a restore candidate:
  the newest *completed* generation is what restores.
"""

import hashlib
import os
import sqlite3
from pathlib import Path

import pytest

from muninn import HebbianMemory, MuninnConfig, MuninnStorageError


def _mem(path, **overrides):
    return HebbianMemory(MuninnConfig(db_path=str(path), **overrides))


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _seed_with_backup(db):
    """Two opens, so ``.bak-1`` holds the alpha-only snapshot.

    The second open takes its backup before beta is written,
    so the generation provably contains alpha and not beta.
    Returns (alpha_id, beta_id).
    """
    m = _mem(db)
    alpha = m.remember("alpha seed memory")
    m.close()
    m = _mem(db)
    beta = m.remember("beta second memory")
    m.close()
    assert Path(f"{db}.bak-1").exists()
    return alpha, beta


def _make_wal(db):
    """Leave a real, non-empty WAL beside the (closed) store."""
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("INSERT INTO meta(key, value) VALUES ('rm032_probe', 'x')")
    conn.commit()
    wal = Path(f"{db}-wal")
    data = wal.read_bytes()
    conn.close()
    wal.write_bytes(data)
    assert wal.stat().st_size > 0
    return wal


def test_wal_missing_opens_with_all_data(tmp_path):
    db = tmp_path / "m.db"
    m = _mem(db)
    alpha = m.remember("alpha seed memory")
    m.close()
    # A clean close checkpoints and removes the WAL: this is
    # the normal state, not damage.
    assert not Path(f"{db}-wal").exists()
    m = _mem(db)
    assert m.recovered_from_backup is False
    assert m.stats()["total_nodes"] == 1
    assert m.get_node(alpha) is not None
    m.close()


def test_garbage_wal_beside_healthy_store_opens_with_data(tmp_path):
    db = tmp_path / "m.db"
    m = _mem(db)
    alpha = m.remember("alpha seed memory")
    m.close()
    Path(f"{db}-wal").write_bytes(b"rm032 garbage wal, not frames" * 16)
    m = _mem(db)
    assert m.recovered_from_backup is False
    assert m.stats()["total_nodes"] == 1
    assert m.get_node(alpha) is not None
    m.close()


def test_zero_length_store_restores_from_backup(tmp_path):
    db = tmp_path / "m.db"
    alpha, _beta = _seed_with_backup(db)
    db.write_bytes(b"")
    m = _mem(db)
    assert m.recovered_from_backup is True
    # The restored store is the backup's state: alpha, not beta.
    assert m.stats()["total_nodes"] == 1
    assert m.get_node(alpha) is not None
    m.close()


def test_zero_length_store_without_backup_refuses(tmp_path):
    db = tmp_path / "m.db"
    m = _mem(db)
    m.remember("alpha seed memory")
    m.close()
    # A single open never took a backup: no generations exist.
    assert not Path(f"{db}.bak-1").exists()
    db.write_bytes(b"")
    with pytest.raises(MuninnStorageError) as caught:
        _mem(db)
    assert str(caught.value) == (
        f"muninn store {db} is corrupt and no rolling backup "
        f"verified; refusing to start empty over lost memory"
    )
    # The refusal changes nothing: the truncated file stands
    # for inspection, and a second attempt refuses identically.
    assert db.stat().st_size == 0
    with pytest.raises(MuninnStorageError):
        _mem(db)


def test_partial_truncation_with_wal_restores_from_backup(tmp_path):
    db = tmp_path / "m.db"
    alpha, _beta = _seed_with_backup(db)
    db.write_bytes(db.read_bytes()[:100])
    Path(f"{db}-wal").write_bytes(b"rm032 garbage wal, not frames" * 16)
    m = _mem(db)
    assert m.recovered_from_backup is True
    assert m.stats()["total_nodes"] == 1
    assert m.get_node(alpha) is not None
    m.close()
    # The restore removed the dead sidecars: nothing of the
    # garbage WAL survives (a zero-length remnant may remain
    # after the closing checkpoint; its bytes may not).
    wal = Path(f"{db}-wal")
    assert not wal.exists() or b"rm032 garbage" not in wal.read_bytes()


def test_missing_main_with_wal_restores_from_backup(tmp_path):
    db = tmp_path / "m.db"
    alpha, _beta = _seed_with_backup(db)
    wal = _make_wal(db)
    orphan_bytes = wal.read_bytes()
    db.unlink()
    assert not db.exists() and wal.exists()
    m = _mem(db)
    assert m.recovered_from_backup is True
    assert m.stats()["total_nodes"] == 1
    assert m.get_node(alpha) is not None
    m.close()
    # The orphaned WAL was consumed by the restore, not kept:
    # after a clean close nothing of its bytes remains.
    assert not wal.exists() or wal.read_bytes() != orphan_bytes


def test_missing_main_with_wal_and_no_backup_refuses(tmp_path):
    db = tmp_path / "m.db"
    m = _mem(db)
    m.remember("alpha seed memory")
    m.close()
    assert not Path(f"{db}.bak-1").exists()
    wal = _make_wal(db)
    db.unlink()
    with pytest.raises(MuninnStorageError) as caught:
        _mem(db)
    assert str(caught.value) == (
        f"muninn store {db} has a write-ahead log but no main "
        f"file and no rolling backup verified; refusing to start "
        f"empty over lost memory"
    )
    # Nothing was created over the evidence: no fresh main
    # file, and the WAL stands for inspection.
    assert not db.exists()
    assert wal.exists()


def test_stale_bak_tmp_removed_on_quiet_open(tmp_path):
    db = tmp_path / "m.db"
    _seed_with_backup(db)
    bak1 = Path(f"{db}.bak-1")
    before = _digest(bak1)
    tmp = Path(f"{db}.bak-tmp")
    tmp.write_bytes(b"half a backup from a killed process")
    # Make this open a quiet one: the store is older than its
    # newest backup, so no new backup is taken — the temp's
    # removal must come from the RM-032 cleanup, not from a
    # backup overwriting it.
    bak_mtime = bak1.stat().st_mtime
    os.utime(db, (bak_mtime - 10, bak_mtime - 10))
    m = _mem(db)
    assert m.recovered_from_backup is False
    assert m.stats()["total_nodes"] == 2
    m.close()
    assert not tmp.exists()
    assert _digest(bak1) == before


def test_bak_tmp_is_never_a_restore_candidate(tmp_path):
    db = tmp_path / "m.db"
    m = _mem(db)
    m.remember("alpha seed memory")
    m.close()
    # The temp is a *complete, valid* copy of the store — and
    # still not a generation: no .bak-N exists, so a corrupt
    # main must refuse, not resurrect from the temp.
    tmp = Path(f"{db}.bak-tmp")
    tmp.write_bytes(db.read_bytes())
    db.write_bytes(b"corrupt main store garbage" * 10)
    with pytest.raises(MuninnStorageError) as caught:
        _mem(db)
    assert "is corrupt and no rolling backup verified" in str(caught.value)
    # The failed open still discarded the stale temp.
    assert not tmp.exists()


def test_backup_generation_wins_over_bak_tmp(tmp_path):
    db = tmp_path / "m.db"
    alpha, _beta = _seed_with_backup(db)
    # A valid temp holding *both* memories beside a generation
    # holding only alpha: the restore must come from the
    # generation (1 node), never from the temp (2 nodes).
    Path(f"{db}.bak-tmp").write_bytes(db.read_bytes())
    db.write_bytes(b"corrupt main store garbage" * 10)
    m = _mem(db)
    assert m.recovered_from_backup is True
    assert m.stats()["total_nodes"] == 1
    assert m.get_node(alpha) is not None
    m.close()
