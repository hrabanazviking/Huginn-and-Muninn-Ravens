"""Threaded, crash-proof, self-healing, lazy — huginn edition."""

import os
import subprocess
import sys
import threading
import time

import pytest

from huginn import HuginnConfig, HuginnMemory
from huginn.errors import HuginnStorageError


def _local(tmp_path, **kw):
    return HuginnConfig(
        backend="local", local_db_path=str(tmp_path / "h.db"), **kw
    )


def test_concurrent_upserts_and_searches(tmp_path):
    h = HuginnMemory(config=_local(tmp_path))
    errors = []

    def worker(n):
        try:
            for i in range(25):
                h.upsert_memory(
                    content=f"thread {n} memory {i} about topic {n}",
                    category=f"cat{n}",
                )
                h.search(query_text=f"topic {n}")
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert h.health()["documents"] == 6 * 25
    h.close()


CHILD_SCRIPT = """
import sys
from huginn import HuginnConfig, HuginnMemory

db, progress = sys.argv[1], sys.argv[2]
h = HuginnMemory(HuginnConfig(backend="local", local_db_path=db))
done = 0
while True:
    h.upsert_memory(content=f"crash batch memory {done} zephyr quill", category="fact")
    done += 1
    with open(progress, "w") as fh:
        fh.write(str(done))
"""


def test_kill9_mid_write(tmp_path):
    db = tmp_path / "crash.db"
    progress = tmp_path / "progress.txt"
    progress.write_text("0")
    proc = subprocess.Popen(
        [sys.executable, "-c", CHILD_SCRIPT, str(db), str(progress)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.time() + 60
        committed = 0
        while time.time() < deadline:
            try:
                committed = int(progress.read_text().strip() or 0)
            except ValueError:
                committed = 0
            if committed >= 25:
                break
            time.sleep(0.05)
        assert committed >= 25
        proc.kill()
        proc.wait()
    finally:
        if proc.poll() is None:
            proc.kill()
    h = HuginnMemory(HuginnConfig(backend="local", local_db_path=str(db)))
    health = h.health()
    assert health["integrity"] == "ok"
    # every committed upsert is a distinct document (unique content)
    assert health["documents"] >= committed
    results = h.search(query_text="zephyr quill")
    assert results
    h.close()


def test_corruption_recovers_from_backup(tmp_path):
    db = tmp_path / "h.db"
    h = HuginnMemory(config=_local(tmp_path))
    mid = h.upsert_memory(content="the thought that must survive", category="fact")
    h.close()
    h = HuginnMemory(config=_local(tmp_path))
    h.health()  # huginn is lazy: first use builds the backend,
    h.close()   # whose open refreshes the rolling backup
    assert (tmp_path / "h.db.bak-1").exists()
    with open(db, "r+b") as fh:
        fh.write(b"GARBAGE-NOT-A-DATABASE" * 16)
    h = HuginnMemory(config=_local(tmp_path))
    assert h.health()["status"] == "healthy"  # first use builds + heals
    assert h._backend.recovered_from_backup is True
    assert h.health()["recovered_from_backup"] is True
    assert h.get(mid)["content"] == "the thought that must survive"
    h.close()


def test_corruption_without_backup_is_loud(tmp_path):
    db = tmp_path / "h.db"
    db.write_bytes(b"junk" * 512)
    h = HuginnMemory(
        HuginnConfig(backend="local", local_db_path=str(db), backup_keep=0)
    )
    with pytest.raises(HuginnStorageError):
        h.upsert_memory(content="doomed", category="fact")


def test_import_and_construction_are_lazy(tmp_path):
    env = dict(os.environ)
    env["HOME"] = str(tmp_path)
    code = (
        "import huginn, pathlib;"
        "h = huginn.HuginnMemory();"
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
