"""RM-037 — Concurrent openers for huginn (local backend).

Two or more objects holding the same local store at once —
in one process or across processes — is **supported**, with
the behaviour defined in ``docs/CONCURRENT_OPENERS.md``:

* each facade builds its own backend, connection and lock;
  no in-memory store state is shared between objects (the
  facade's flight history is per-object bookkeeping, not
  store data);
* ordinary reads and writes are serialized by SQLite itself
  (WAL + each writer's busy timeout, RM-031): a write that
  commits through one object is visible to reads through any
  other object at once, and committed writes never lose each
  other — document counts stay exact;
* the open-time duties (creation, integrity probe, restore,
  backup-on-open, heal) and every rolling backup are
  serialized per store file by the coordination lock in
  ``huginn._db`` (an in-process RLock plus an ``flock`` on
  the sibling ``.open-lock`` file), so a second opener never
  sees a half-created store, never races a restore, and
  never collides on the shared ``.bak-tmp`` snapshot path;
* closing one object leaves the others fully working.

The Qdrant backend holds no local file: concurrent objects
there are concurrent clients of one server, and a live
server round-trip stays NOT PROVEN — this file pins the
local backend only. What is *not* promised across objects:
the RM-012 timestamp guard is per object, so ``updated_at``
values issued by different objects may repeat or invert by
microseconds (each object's own issues stay monotonic, and
a document's ``updated_at`` never precedes its own
``created_at`` as issued by one object).
"""

import os
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

import huginn
from huginn import HuginnBackendError, HuginnMemory
from huginn.config import HuginnConfig

WORKER_SCRIPT = """
import sys
import time
from pathlib import Path

from huginn import HuginnMemory
from huginn.config import HuginnConfig

db, index, ready, go = sys.argv[1], int(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
ready.write_text("ready")
deadline = time.monotonic() + 60
while not go.exists() and time.monotonic() < deadline:
    time.sleep(0.01)
mem = HuginnMemory(HuginnConfig(backend="local", local_db_path=db))
for j in range(10):
    mem.upsert_memory(
        f"worker {index} document {j} about ravens", memory_id=index * 100 + j + 1001
    )
assert len(mem.search("ravens", limit=50)) >= 1
mem.close()
"""


def _mem(path, **overrides):
    return HuginnMemory(
        HuginnConfig(backend="local", local_db_path=str(path), **overrides)
    )


def _quick_check(path):
    conn = sqlite3.connect(str(path))
    try:
        return str(conn.execute("PRAGMA quick_check").fetchone()[0])
    finally:
        conn.close()


def _race_openers(db, count, barrier):
    """Open ``count`` facades on ``db`` from simultaneous threads.

    Huginn construction is lazy, so each opener forces its
    backend open (a ``stats()`` read) inside the race.
    """
    opened = {}
    errors = {}

    def opener(i):
        try:
            barrier.wait(timeout=30)
            mem = _mem(db)
            mem.stats()
            opened[i] = mem
        except Exception as exc:  # collected and asserted by the caller
            errors[i] = exc

    threads = [threading.Thread(target=opener, args=(i,)) for i in range(count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    return opened, errors


def test_two_objects_same_process_cross_visible_and_exact(tmp_path):
    db = tmp_path / "h.db"
    a = _mem(db)
    a.upsert_memory("alpha document about ravens", memory_id=101)
    b = _mem(db)
    try:
        assert b.get(101)["content"] == "alpha document about ravens"
        b.upsert_memory("beta document about wolves", memory_id=102)
        assert a.get(102)["content"] == "beta document about wolves"
        assert a.stats()["documents"] == 2
        assert b.stats()["documents"] == 2
        assert [r["id"] for r in a.search("wolves")] == [102]
        assert [r["id"] for r in b.search("ravens")] == [101]
        assert a.health()["integrity"] == "ok"
        assert b.health()["integrity"] == "ok"
    finally:
        a.close()
        b.close()


def test_two_objects_same_id_last_writer_wins_in_order(tmp_path):
    db = tmp_path / "h.db"
    a = _mem(db)
    b = _mem(db)
    try:
        a.upsert_memory("first version of the shared document", memory_id=7)
        b.upsert_memory("second version of the shared document", memory_id=7)
        # Sequential writes through two objects: the later
        # commit is what both objects read — no stale copy.
        assert a.get(7)["content"] == "second version of the shared document"
        assert b.get(7)["content"] == "second version of the shared document"
        assert a.stats()["documents"] == 1
        assert a.delete(7) is True
        assert b.get(7) is None
        assert b.stats()["documents"] == 0
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
            mem.upsert_memory(f"document created by opener {i}", memory_id=200 + i)
        for mem in opened.values():
            assert mem.stats()["documents"] == 6
            assert mem.health()["integrity"] == "ok"
            assert mem.health()["recovered_from_backup"] is False
    finally:
        for mem in opened.values():
            mem.close()
    again = _mem(db)
    try:
        assert again.stats()["documents"] == 6
        assert again.health()["recovered_from_backup"] is False
    finally:
        again.close()


def test_cross_process_openers_write_exact_counts(tmp_path):
    db = tmp_path / "h.db"
    seed = _mem(db)
    seed.upsert_memory("seed document about ravens", memory_id=1)
    seed.close()

    env = dict(os.environ)
    pkg_parent = str(Path(huginn.__file__).resolve().parent.parent)
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
        # 1 seed + 2 workers x 10 documents, no loss, no merge.
        assert mem.stats()["documents"] == 21
        for i in range(2):
            for j in range(10):
                doc = mem.get(i * 100 + j + 1001)
                assert doc is not None
                assert doc["content"] == f"worker {i} document {j} about ravens"
    finally:
        mem.close()


def test_concurrent_openers_on_stale_store_take_one_sound_backup(tmp_path):
    db = tmp_path / "h.db"
    seed = _mem(db)
    seed.upsert_memory("seed before the race", memory_id=1)
    seed.close()
    # A creation open takes no backup-on-open, so every racing
    # opener below finds the backup stale (here: missing).
    assert not (tmp_path / "h.db.bak-1").exists()
    opened, errors = _race_openers(db, 4, threading.Barrier(4))
    try:
        assert errors == {}
        assert len(opened) == 4
        for mem in opened.values():
            assert mem.get(1)["content"] == "seed before the race"
    finally:
        for mem in opened.values():
            mem.close()
    assert _quick_check(tmp_path / "h.db.bak-1") == "ok"


def test_close_of_one_object_leaves_the_other_fully_working(tmp_path):
    db = tmp_path / "h.db"
    a = _mem(db)
    a.upsert_memory("alpha before the close", memory_id=1)
    b = _mem(db)
    assert b.get(1) is not None
    a.close()
    try:
        b.upsert_memory("beta written after a closed", memory_id=2)
        assert b.get(1)["content"] == "alpha before the close"
        assert b.get(2)["content"] == "beta written after a closed"
        assert b.stats()["documents"] == 2
    finally:
        b.close()
    again = _mem(db)
    try:
        assert again.stats()["documents"] == 2
    finally:
        again.close()


def test_threaded_openers_race_restore_of_corrupt_store(tmp_path):
    db = tmp_path / "h.db"
    first = _mem(db)
    first.upsert_memory("alpha seed document", memory_id=1)
    first.close()
    second = _mem(db)
    second.upsert_memory("beta written after the backup", memory_id=2)
    second.close()
    # .bak-1 now holds the alpha-only snapshot (taken by the
    # second open, before beta was written).
    db.write_bytes(b"corrupt main store garbage" * 10)
    opened, errors = _race_openers(db, 4, threading.Barrier(4))
    try:
        assert errors == {}
        assert len(opened) == 4
        assert any(
            mem.health()["recovered_from_backup"] for mem in opened.values()
        )
        for mem in opened.values():
            assert mem.get(1)["content"] == "alpha seed document"
            assert mem.get(2) is None
            assert mem.health()["integrity"] == "ok"
    finally:
        for mem in opened.values():
            mem.close()
    again = _mem(db)
    try:
        assert again.get(1)["content"] == "alpha seed document"
        assert again.health()["recovered_from_backup"] is False
    finally:
        again.close()


def test_closed_facade_raises_typed_and_sibling_is_unaffected(tmp_path):
    db = tmp_path / "h.db"
    a = _mem(db)
    a.upsert_memory("alpha document", memory_id=1)
    b = _mem(db)
    assert b.get(1) is not None
    a.close()
    a.close()  # double close stays a no-op (RM-023)
    try:
        with pytest.raises(HuginnBackendError):
            a.upsert_memory("must not land", memory_id=2)
        assert b.get(2) is None
        assert b.stats()["documents"] == 1
    finally:
        b.close()
