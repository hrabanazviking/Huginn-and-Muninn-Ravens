"""Huginn backup cost at 100k documents -- RM-065 gate script.

Run: python scripts/backup_cost.py [--output backup_cost.json]

What it measures (roadmap RM-065: backup cost at 100k
scale): the twin of ``muninn/scripts/backup_cost.py``
for Huginn's local backend, whose ``_db`` machinery is
Muninn's twin. Huginn has no maintenance passes, so the
roads here are the snapshot itself and backup-on-open:

- The seed is a 100,000-document local store built by
  direct construction (a real open creates the file,
  then ``documents`` rows are inserted in one
  transaction -- the RM-062 scale-corpus road; the
  term index and ``doc_vectors`` are intentionally
  empty, stated here and in the record: backup cost is
  proportional to store bytes, and the per-megabyte
  rate is reported so the number carries to the
  vector-carrying store RM-062 measured).
- ``snapshot``: one ``take_backup`` per fresh byte
  copy of the seed, median of three, verified
  (quick_check + document count) before quoting.
- ``open_unchanged`` / ``open_changed``: as in the
  Muninn gate -- the unchanged open must leave the
  newest backup's hash standing still, the changed
  open must move it; the medians' difference is the
  backup's share of an open that takes one.

Class: BENCH. Runs unchanged on the RM-064 tree.
Numbers on a loaded machine are indicative, not
absolutes -- the environment block says so. Stores
live on tmpfs; local backend only, nothing external.
"""

import argparse
import hashlib
import json
import shutil
import sqlite3
import statistics
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import benchmark as _bench  # noqa: E402  (sibling script, path set above)

DOCS = 100_000
SEED_TS = "2026-01-01T00:00:00+00:00"
_SEED_BATCH = 5000


def _text(i):
    return f"backup cost document {i} " + " ".join(
        f"term{(i * 31 + j * 7) % 512}" for j in range(24)
    )


def _build_seed(seed_dir, n_docs):
    from huginn import HuginnConfig, HuginnMemory
    from huginn.local_backend import _content_hash

    db_path = Path(seed_dir) / "backup.db"
    config = HuginnConfig(
        backend="local", local_db_path=str(db_path), auto_backup=False
    )
    mem = HuginnMemory(config)
    mem.health()  # a real open creates the store
    mem.close()
    conn = sqlite3.connect(str(db_path))
    try:
        for start in range(0, n_docs, _SEED_BATCH):
            rows = []
            for i in range(start, min(start + _SEED_BATCH, n_docs)):
                text = _text(i)
                category = f"cat{i % 10}"
                rows.append((
                    i + 1, text, _content_hash(text, category), category,
                    (i % 10) + 1, "[]", 0.0, SEED_TS, SEED_TS,
                ))
            conn.executemany(
                "INSERT INTO documents"
                " (id, content, content_hash, category, importance, tags,"
                "  emotional_valence, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.commit()
    finally:
        conn.close()
    return db_path


def _fresh_copy(seed_db):
    tmp = tempfile.mkdtemp(prefix="huginn-backup-cost-")
    db_path = Path(tmp) / "backup.db"
    shutil.copy2(seed_db, db_path)
    return db_path


def _discard(db_path):
    """Remove one measurement directory (see the Muninn twin)."""
    shutil.rmtree(db_path.parent, ignore_errors=True)


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _open(db_path, *, auto_backup):
    from huginn import HuginnConfig, HuginnMemory

    config = HuginnConfig(
        backend="local", local_db_path=str(db_path), auto_backup=auto_backup
    )
    mem = HuginnMemory(config)
    mem.health()  # force the lazy open inside the timing when asked
    return mem


def _timeit(fn):
    start = time.perf_counter()
    result = fn()
    return result, (time.perf_counter() - start) * 1000


def run_backup_cost(docs=DOCS):
    seed_dir = tempfile.mkdtemp(prefix="huginn-backup-seed-")
    seed_db = _build_seed(seed_dir, docs)
    store_bytes = seed_db.stat().st_size
    probe = sqlite3.connect(str(seed_db))
    try:
        seed_docs = probe.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    finally:
        probe.close()

    from huginn._db import take_backup

    snapshot_times = []
    snapshot_bytes = None
    snapshot_verified = True
    for _ in range(3):
        db_path = _fresh_copy(seed_db)
        taken, elapsed = _timeit(lambda p=db_path: take_backup(p, 3))
        snapshot_times.append(elapsed)
        assert taken is not None
        snapshot_bytes = taken.stat().st_size
        probe = sqlite3.connect(str(taken))
        try:
            ok = probe.execute("PRAGMA quick_check").fetchone()[0] == "ok"
            count = probe.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        finally:
            probe.close()
        snapshot_verified = snapshot_verified and ok and count == seed_docs
        _discard(db_path)

    def _open_case(changed):
        db_path = _fresh_copy(seed_db)
        take_backup(db_path, 3)
        bak1 = db_path.with_name(db_path.name + ".bak-1")
        if changed:
            mem = _open(db_path, auto_backup=False)
            mem.upsert_memory("one post-backup write")
            mem.close()
        before = _sha256(bak1)
        mem, elapsed = _timeit(lambda: _open(db_path, auto_backup=True))
        mem.close()
        took = before != _sha256(bak1)
        _discard(db_path)
        return elapsed, took

    open_unchanged_times, open_changed_times = [], []
    unchanged_took, changed_took = [], []
    for _ in range(3):
        elapsed, took = _open_case(changed=False)
        open_unchanged_times.append(elapsed)
        unchanged_took.append(took)
        elapsed, took = _open_case(changed=True)
        open_changed_times.append(elapsed)
        changed_took.append(took)

    shutil.rmtree(seed_dir, ignore_errors=True)
    snapshot_median = round(statistics.median(snapshot_times), 1)
    open_unchanged_median = round(statistics.median(open_unchanged_times), 1)
    open_changed_median = round(statistics.median(open_changed_times), 1)
    return {
        "slice": "RM-065",
        "generated_at": datetime.now(UTC).isoformat(),
        "environment": _bench.environment_block(),
        "store": {
            "documents": seed_docs,
            "store_bytes": store_bytes,
            "seed": "direct construction: documents rows in one "
            "transaction into a store created by a real open; term "
            "index and doc_vectors intentionally empty (backup cost "
            "is byte-proportional; ms_per_mb carries the number)",
        },
        "snapshot": {
            "times_ms": [round(t, 1) for t in snapshot_times],
            "median_ms": snapshot_median,
            "backup_bytes": snapshot_bytes,
            "verified_quick_check_and_documents": snapshot_verified,
            "ms_per_mb": round(snapshot_median / (store_bytes / 1e6), 2),
        },
        "open": {
            "unchanged_median_ms": open_unchanged_median,
            "unchanged_times_ms": [round(t, 1) for t in open_unchanged_times],
            "unchanged_took_backup": unchanged_took,
            "changed_median_ms": open_changed_median,
            "changed_times_ms": [round(t, 1) for t in open_changed_times],
            "changed_took_backup": changed_took,
            "backup_share_ms": round(open_changed_median - open_unchanged_median, 1),
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_suffix(".json"),
    )
    parser.add_argument("--docs", type=int, default=DOCS)
    args = parser.parse_args(argv)
    record = run_backup_cost(docs=args.docs)
    args.output.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
