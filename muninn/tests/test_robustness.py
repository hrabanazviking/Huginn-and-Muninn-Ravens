"""Threaded, crash-proof, self-healing, lazy — proven, not promised."""

import os
import sqlite3
import subprocess
import sys
import threading

import pytest

from muninn import HebbianMemory
from muninn.config import MuninnConfig
from muninn.errors import MuninnStorageError


def test_concurrent_threads_no_lost_writes(tmp_path):
    """8 threads hammering activations + wiring: exact counts survive."""
    mem = HebbianMemory(MuninnConfig(db_path=str(tmp_path / "m.db")))
    errors = []

    def worker(n):
        try:
            for _ in range(50):
                mem.activate(100 + n)
                mem.activate_batch([100 + n, 200])
        except Exception as exc:  # pragma: no cover - failure surface
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    # per id: 50 solo activations + 50 batch activations
    for i in range(8):
        assert mem.activation_count(100 + i) == 100
    assert mem.activation_count(200) == 8 * 50
    pair = mem.get_associations(200)
    assert len(pair) == 8
    # co-activation counts are exact under concurrency
    assert all(a["co_activation_count"] == 50 for a in pair)
    mem.close()


def test_concurrent_remember_dedupes(tmp_path):
    mem = HebbianMemory(MuninnConfig(db_path=str(tmp_path / "m.db")))
    ids = []

    def worker():
        ids.append(mem.remember("one shared memory", category="fact"))

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(set(ids)) == 1
    assert mem.stats()["total_nodes"] == 1
    mem.close()


CHILD_SCRIPT = """
import sys
from muninn import HebbianMemory
from muninn.config import MuninnConfig

db, progress = sys.argv[1], sys.argv[2]
mem = HebbianMemory(MuninnConfig(db_path=db))
done = 0
while True:
    mem.activate_batch([1, 2, 3])
    done += 1
    with open(progress, "w") as fh:
        fh.write(str(done))
"""


def test_kill9_mid_write_no_corruption_no_lost_commits(tmp_path):
    db = tmp_path / "crash.db"
    progress = tmp_path / "progress.txt"
    progress.write_text("0")
    proc = subprocess.Popen(
        [sys.executable, "-c", CHILD_SCRIPT, str(db), str(progress)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        # wait until at least 30 batches have committed
        import time

        deadline = time.time() + 60
        committed = 0
        while time.time() < deadline:
            try:
                committed = int(progress.read_text().strip() or 0)
            except ValueError:
                committed = 0
            if committed >= 30:
                break
            time.sleep(0.05)
        assert committed >= 30
        proc.kill()  # SIGKILL, no cleanup, mid-flight
        proc.wait()
    finally:
        if proc.poll() is None:
            proc.kill()
    mem = HebbianMemory(MuninnConfig(db_path=str(db)))
    health = mem.health()
    assert health["integrity"] == "ok"
    # each batch logs exactly one activation per id, atomically: the
    # three ids must agree exactly — a torn batch would break the tie —
    # and no committed batch may be missing
    counts = [mem.activation_count(i) for i in (1, 2, 3)]
    assert counts[0] == counts[1] == counts[2]
    assert counts[0] >= committed
    assert mem.stats()["total_connections"] > 0
    mem.close()


def test_corruption_recovers_from_rolling_backup(tmp_path, caplog):
    db = tmp_path / "m.db"
    mem = HebbianMemory(MuninnConfig(db_path=str(db)))
    keep_id = mem.remember("the memory that must survive", category="fact")
    mem.activate_batch([keep_id, 77])
    mem.close()
    # second open refreshes the rolling backup with that state inside
    mem = HebbianMemory(MuninnConfig(db_path=str(db)))
    mem.close()
    assert (tmp_path / "m.db.bak-1").exists()
    # destroy the main store's header
    with open(db, "r+b") as fh:
        fh.write(b"GARBAGE-NOT-A-DATABASE" * 16)
    with caplog.at_level("ERROR", logger="muninn.store"):
        mem = HebbianMemory(MuninnConfig(db_path=str(db)))
    assert mem.recovered_from_backup is True
    assert mem.health()["status"] == "healthy"
    node = mem.get_node(keep_id)
    assert node is not None and "must survive" in node.content
    mem.close()


def test_corruption_without_backup_is_loud(tmp_path):
    db = tmp_path / "m.db"
    db.write_bytes(b"junk" * 512)
    with pytest.raises(MuninnStorageError):
        HebbianMemory(MuninnConfig(db_path=str(db), backup_keep=0))


def test_import_constructs_nothing(tmp_path):
    """Importing the package opens no files and builds no stores."""
    env = dict(os.environ)
    env["HOME"] = str(tmp_path)
    code = (
        "import muninn, muninn.config, pathlib;"
        "leftovers = [str(p) for p in pathlib.Path.home().rglob('*')];"
        "print(len(leftovers))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    assert out.stdout.strip() == "0"


def test_closed_object_raises_typed(tmp_path):
    mem = HebbianMemory(MuninnConfig(db_path=str(tmp_path / "m.db")))
    mem.close()
    with pytest.raises(MuninnStorageError):
        mem.activate(1)
    mem.close()  # still idempotent


def test_backup_generations_roll(tmp_path):
    db = tmp_path / "m.db"
    mem = HebbianMemory(MuninnConfig(db_path=str(db), backup_keep=2))
    mem.remember("one", category="fact")
    assert mem.backup() is not None
    mem.remember("two", category="fact")
    assert mem.backup() is not None
    mem.remember("three", category="fact")
    assert mem.backup() is not None
    assert (tmp_path / "m.db.bak-1").exists()
    assert (tmp_path / "m.db.bak-2").exists()
    assert not (tmp_path / "m.db.bak-3").exists()
    mem.close()
