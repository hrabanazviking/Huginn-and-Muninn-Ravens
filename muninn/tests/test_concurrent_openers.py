"""RM-037 — Concurrent openers for muninn.

Two or more objects holding the same store at once — in one
process or across processes — is **supported**, with the
behaviour defined in ``docs/CONCURRENT_OPENERS.md``:

* each object owns its connection and its internal lock; no
  in-memory state is shared between objects;
* ordinary reads and writes are serialized by SQLite itself
  (WAL + each writer's busy timeout, RM-031): a write that
  commits through one object is visible to reads through any
  other object at once, and committed writes never lose each
  other — counts stay exact;
* the open-time duties (creation, integrity probe, restore,
  backup-on-open, heal) and every rolling backup are
  serialized per store file by the coordination lock in
  ``muninn._db`` (an in-process RLock plus an ``flock`` on the
  sibling ``.open-lock`` file), so a second opener never sees
  a half-created store, never races a restore, and never
  collides on the shared ``.bak-tmp`` snapshot path;
* closing one object leaves the others fully working.

What is *not* promised across objects: the RM-012 timestamp
guard is per object, so timestamps issued by different
objects may repeat or invert by microseconds (each object's
own issues stay strictly increasing).
"""

import os
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

import muninn
from muninn import HebbianMemory, MuninnStorageError
from muninn.config import MuninnConfig

WORKER_SCRIPT = """
import sys
import time
from pathlib import Path

from muninn import HebbianMemory
from muninn.config import MuninnConfig

db, index, shared, ready, go = (
    sys.argv[1],
    int(sys.argv[2]),
    int(sys.argv[3]),
    Path(sys.argv[4]),
    Path(sys.argv[5]),
)
ready.write_text("ready")
deadline = time.monotonic() + 60
while not go.exists() and time.monotonic() < deadline:
    time.sleep(0.01)
mem = HebbianMemory(MuninnConfig(db_path=db))
for j in range(10):
    mem.remember(f"worker {index} memory {j}")
for _ in range(10):
    mem.activate(shared)
mem.close()
"""


def _mem(path, **overrides):
    return HebbianMemory(MuninnConfig(db_path=str(path), **overrides))


def _quick_check(path):
    conn = sqlite3.connect(str(path))
    try:
        return str(conn.execute("PRAGMA quick_check").fetchone()[0])
    finally:
        conn.close()


def _race_openers(db, count, barrier):
    """Open ``count`` objects on ``db`` from simultaneous threads."""
    opened = {}
    errors = {}

    def opener(i):
        try:
            barrier.wait(timeout=30)
            opened[i] = _mem(db)
        except Exception as exc:  # collected and asserted by the caller
            errors[i] = exc

    threads = [threading.Thread(target=opener, args=(i,)) for i in range(count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    return opened, errors


def test_two_objects_same_process_cross_visible_and_exact(tmp_path):
    db = tmp_path / "m.db"
    a = _mem(db)
    alpha = a.remember("alpha from the first object")
    b = _mem(db)
    try:
        # B sees A's committed write at once; A sees B's.
        assert b.get_node(alpha).content == "alpha from the first object"
        beta = b.remember("beta from the second object")
        assert a.get_node(beta).content == "beta from the second object"
        assert a.stats()["total_nodes"] == 2
        assert b.stats()["total_nodes"] == 2
        assert a.health()["integrity"] == "ok"
        assert b.health()["integrity"] == "ok"
    finally:
        a.close()
        b.close()


def test_two_objects_interleaved_activation_returns_exact_totals(tmp_path):
    db = tmp_path / "m.db"
    a = _mem(db)
    x = a.remember("shared node x")
    y = a.remember("shared node y")
    b = _mem(db)
    try:
        # Alternating objects: every activation returns the exact
        # running total, whichever object issued it — no lost
        # update across connections.
        assert a.activate(x) == 1
        assert b.activate(x) == 2
        assert a.activate(x) == 3
        assert b.activate(x) == 4
        report_a = a.activate_batch([x, y])
        report_b = b.activate_batch([x, y])
        assert report_a["activated"] == 2
        assert report_b["activated"] == 2
        assert a.stats()["total_activations"] == 8
        assert b.stats()["total_activations"] == 8
        # The pair wired by the two batches is one pair — two
        # directed rows — co-activated once per batch.
        assert a.stats()["total_connections"] == 2
        assoc = a.get_associations(x)
        assert len(assoc) == 1
        assert assoc[0]["co_activation_count"] == 2
    finally:
        a.close()
        b.close()


def test_threaded_openers_race_fresh_store_creation(tmp_path):
    db = tmp_path / "fresh.db"
    opened, errors = _race_openers(db, 6, threading.Barrier(6))
    try:
        assert errors == {}
        assert len(opened) == 6
        for i, mem in opened.items():
            mem.remember(f"created by opener {i}")
        for mem in opened.values():
            assert mem.stats()["total_nodes"] == 6
            assert mem.health()["integrity"] == "ok"
            assert mem.recovered_from_backup is False
    finally:
        for mem in opened.values():
            mem.close()
    again = _mem(db)
    try:
        assert again.stats()["total_nodes"] == 6
        assert again.recovered_from_backup is False
    finally:
        again.close()


def test_cross_process_openers_write_exact_counts(tmp_path):
    db = tmp_path / "m.db"
    seed = _mem(db)
    shared = seed.remember("shared seed node")
    seed.close()

    env = dict(os.environ)
    pkg_parent = str(Path(muninn.__file__).resolve().parent.parent)
    env["PYTHONPATH"] = pkg_parent + os.pathsep + env.get("PYTHONPATH", "")
    procs = []
    for i in range(2):
        ready = tmp_path / f"worker{i}.ready"
        procs.append(
            subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    WORKER_SCRIPT,
                    str(db),
                    str(i),
                    str(shared),
                    str(ready),
                    str(tmp_path / "go"),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
        )
    try:
        deadline = time.monotonic() + 60
        while not all((tmp_path / f"worker{i}.ready").exists() for i in range(2)):
            if time.monotonic() > deadline:
                raise AssertionError("cross-process workers never signalled ready")
            time.sleep(0.02)
        (tmp_path / "go").write_text("go")
        for proc in procs:
            _, stderr = proc.communicate(timeout=120)
            assert proc.returncode == 0, stderr
    finally:
        for proc in procs:
            if proc.poll() is None:
                proc.kill()

    mem = _mem(db)
    try:
        assert mem.stats()["total_nodes"] == 21
        assert mem.stats()["total_activations"] == 20
    finally:
        mem.close()
    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute(
            "SELECT total_activations FROM node_activation WHERE memory_id = ?",
            (shared,),
        ).fetchone()
    finally:
        conn.close()
    assert int(row[0]) == 20


def test_concurrent_backups_from_two_objects_stay_verified(tmp_path):
    db = tmp_path / "m.db"
    a = _mem(db)
    a.remember("backup race seed memory")
    b = _mem(db)
    errors = {}
    barrier = threading.Barrier(2)

    def backer(name, mem):
        try:
            barrier.wait(timeout=30)
            for _ in range(5):
                assert mem.backup() is not None
        except Exception as exc:  # collected and asserted below
            errors[name] = exc

    threads = [
        threading.Thread(target=backer, args=("a", a)),
        threading.Thread(target=backer, args=("b", b)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    try:
        assert errors == {}
        assert _quick_check(tmp_path / "m.db.bak-1") == "ok"
        # Both objects still write after the backup race.
        a.remember("written by a after backups")
        b.remember("written by b after backups")
        assert a.stats()["total_nodes"] == 3
    finally:
        a.close()
        b.close()


def test_concurrent_openers_on_stale_store_take_one_sound_backup(tmp_path):
    db = tmp_path / "m.db"
    seed = _mem(db)
    seed_id = seed.remember("seed before the race")
    seed.close()
    # A creation open takes no backup-on-open, so every racing
    # opener below finds the backup stale (here: missing).
    assert not (tmp_path / "m.db.bak-1").exists()
    opened, errors = _race_openers(db, 4, threading.Barrier(4))
    try:
        assert errors == {}
        assert len(opened) == 4
        for mem in opened.values():
            assert mem.get_node(seed_id).content == "seed before the race"
    finally:
        for mem in opened.values():
            mem.close()
    assert _quick_check(tmp_path / "m.db.bak-1") == "ok"


def test_close_of_one_object_leaves_the_other_fully_working(tmp_path):
    db = tmp_path / "m.db"
    a = _mem(db)
    alpha = a.remember("alpha before the close")
    b = _mem(db)
    a.close()
    try:
        beta = b.remember("beta written after a closed")
        assert b.get_node(alpha).content == "alpha before the close"
        assert b.get_node(beta).content == "beta written after a closed"
        # The closed object itself refuses use, typed (existing law).
        with pytest.raises(MuninnStorageError):
            a.remember("must not land")
        assert b.stats()["total_nodes"] == 2
    finally:
        b.close()
    again = _mem(db)
    try:
        assert again.stats()["total_nodes"] == 2
    finally:
        again.close()


def test_threaded_openers_race_restore_of_corrupt_store(tmp_path):
    db = tmp_path / "m.db"
    first = _mem(db)
    alpha = first.remember("alpha seed memory")
    first.close()
    second = _mem(db)
    second.remember("beta written after the backup")
    second.close()
    # .bak-1 now holds the alpha-only snapshot (taken by the
    # second open, before beta was written).
    db.write_bytes(b"corrupt main store garbage" * 10)
    opened, errors = _race_openers(db, 4, threading.Barrier(4))
    try:
        assert errors == {}
        assert len(opened) == 4
        # The restore happened exactly along the serialized
        # road: at least one opener reports the recovery, and
        # every opener reads the restored alpha snapshot.
        assert any(mem.recovered_from_backup for mem in opened.values())
        for mem in opened.values():
            assert mem.get_node(alpha).content == "alpha seed memory"
            assert mem.health()["integrity"] == "ok"
    finally:
        for mem in opened.values():
            mem.close()
    again = _mem(db)
    try:
        assert again.get_node(alpha).content == "alpha seed memory"
        assert again.recovered_from_backup is False
    finally:
        again.close()
