"""Muninn backup cost at 100k edges -- RM-065 gate script.

Run: python scripts/backup_cost.py [--output backup_cost.json]

What it measures (roadmap RM-065: backup-on-open and
pre-maintenance snapshots at 100k scale; incremental or
copy-on-write strategies only if the numbers demand it):

- The seed is the RM-058/RM-064 uniform store -- 5,000
  nodes, 100,000 directed edge rows, 50 activation
  confidences -- built once through the public API with
  ``auto_backup`` off, checkpointed, and then copied
  byte-for-byte into a fresh directory for every
  measurement, so every road starts from the identical
  store file.
- ``snapshot``: one ``take_backup`` (SQLite backup API
  full copy + quick_check + generation rotation) timed
  on fresh copies, median of three; the snapshot is
  verified (quick_check + edge count) before its time
  is quoted.
- ``open_unchanged`` / ``open_changed``: the
  backup-on-open road. Unchanged (newest backup already
  current) opens must take no backup -- proven by the
  backup file's hash standing still. Changed opens take
  one -- proven by the hash moving. Median of three
  opens each; the difference is the backup's share of
  an open that takes one.
- ``decay`` / ``consolidate``: the pre-maintenance
  snapshot's share, as the median difference between
  ``auto_backup=True`` and ``auto_backup=False`` runs
  on identical fresh copies, three runs each.
- ``double_pay``: an open that takes a backup followed
  immediately by a ``decay`` -- if the decay's
  pre-maintenance snapshot is row-for-row identical in
  content to the open's backup, the second snapshot
  re-bought bytes the first already held; the record
  names that cost (it is the ``snapshot`` median) and
  whether it happened.

Class: BENCH. No package code changes in this slice
unless the record's verdict demands one; the script
runs unchanged on the RM-064 tree and produces the
same record shape. Numbers on a loaded machine are
indicative, not absolutes -- the environment block
says so. Stores live on tmpfs; local store only.
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

NODES = 5000
FORWARD = 10  # pairs per node -> 100,000 directed rows
DECAY_DAYS = 10.0


def _strength(i):
    return 0.1 + 0.05 * (i % 17)


def _build_seed(seed_dir):
    """Build the uniform store once; return its db path."""
    import sqlite3

    from muninn import HebbianMemory
    from muninn.config import MuninnConfig

    db_path = Path(seed_dir) / "uniform.db"
    config = MuninnConfig(
        db_path=str(db_path), max_nodes=NODES + 10, auto_backup=False
    )
    mem = HebbianMemory(config)
    ids = [
        mem.remember(f"uniform node {i} unique text {i}", category="bench")
        for i in range(NODES)
    ]
    for i, mid in enumerate(ids):
        for k in range(1, FORWARD + 1):
            mem.associate(mid, ids[(i + k) % NODES], strength=_strength(i + k))
    for i in range(0, NODES, 100):
        mem.activate(ids[i])
    mem.close()
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.commit()
    finally:
        conn.close()
    return db_path


def _fresh_copy(seed_db):
    tmp = tempfile.mkdtemp(prefix="muninn-backup-cost-")
    db_path = Path(tmp) / "uniform.db"
    shutil.copy2(seed_db, db_path)
    return db_path


def _discard(db_path):
    """Remove one measurement directory (store + its backups).

    Measurement copies are ~40 MB a piece at this scale; a
    gate that keeps them all fills the tmpfs it measures on
    (this script's first full run did exactly that).
    """
    shutil.rmtree(db_path.parent, ignore_errors=True)


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _tables(db_path):
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    try:
        nodes = conn.execute("SELECT * FROM nodes ORDER BY id").fetchall()
        edges = conn.execute(
            "SELECT * FROM hebbian_connections ORDER BY memory_a_id, memory_b_id"
        ).fetchall()
        confs = conn.execute(
            "SELECT * FROM node_activation ORDER BY memory_id"
        ).fetchall()
    finally:
        conn.close()
    return nodes, edges, confs


def _open(db_path, *, auto_backup):
    from muninn import HebbianMemory
    from muninn.config import MuninnConfig

    config = MuninnConfig(
        db_path=str(db_path), max_nodes=NODES + 10, auto_backup=auto_backup
    )
    return HebbianMemory(config)


def _timeit(fn):
    start = time.perf_counter()
    result = fn()
    return result, (time.perf_counter() - start) * 1000


def run_backup_cost(nodes=NODES):
    global NODES
    NODES = nodes
    seed_dir = tempfile.mkdtemp(prefix="muninn-backup-seed-")
    seed_db = _build_seed(seed_dir)
    store_bytes = seed_db.stat().st_size
    seed_edges = len(_tables(seed_db)[1])

    from muninn._db import take_backup

    # -- snapshot: one full take_backup per fresh copy --
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
            edges = probe.execute(
                "SELECT COUNT(*) FROM hebbian_connections"
            ).fetchone()[0]
        finally:
            probe.close()
        snapshot_verified = snapshot_verified and ok and edges == seed_edges
        _discard(db_path)

    # -- backup-on-open: unchanged vs changed --
    def _open_case(changed):
        db_path = _fresh_copy(seed_db)
        take_backup(db_path, 3)
        bak1 = db_path.with_name(db_path.name + ".bak-1")
        if changed:
            mem = _open(db_path, auto_backup=False)
            mem.remember("one post-backup write", category="bench")
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

    # -- pre-maintenance: decay / consolidate, backup on vs off --
    def _maintenance(kind, auto_backup):
        db_path = _fresh_copy(seed_db)
        mem = _open(db_path, auto_backup=auto_backup)
        try:
            if kind == "decay":
                _, elapsed = _timeit(lambda: mem.decay(days=DECAY_DAYS))
            else:
                _, elapsed = _timeit(lambda: mem.consolidate())
            return elapsed
        finally:
            mem.close()
            _discard(db_path)

    medians = {}
    for kind in ("decay", "consolidate"):
        on = [_maintenance(kind, True) for _ in range(3)]
        off = [_maintenance(kind, False) for _ in range(3)]
        medians[kind] = {
            "auto_backup_true_median_ms": round(statistics.median(on), 1),
            "auto_backup_false_median_ms": round(statistics.median(off), 1),
            "backup_share_ms": round(
                statistics.median(on) - statistics.median(off), 1
            ),
            "times_true_ms": [round(t, 1) for t in on],
            "times_false_ms": [round(t, 1) for t in off],
        }

    # -- double pay: open-with-backup, then immediate decay --
    db_path = _fresh_copy(seed_db)
    take_backup(db_path, 3)
    mem = _open(db_path, auto_backup=False)
    mem.remember("one post-backup write", category="bench")
    mem.close()
    mem = _open(db_path, auto_backup=True)  # this open takes a backup
    bak1 = db_path.with_name(db_path.name + ".bak-1")
    open_backup_tables = _tables(bak1)
    mem.decay(days=DECAY_DAYS)  # takes its own pre-maintenance snapshot
    mem.close()
    double_pay_equal = _tables(bak1) == open_backup_tables
    _discard(db_path)
    shutil.rmtree(seed_dir, ignore_errors=True)

    snapshot_median = round(statistics.median(snapshot_times), 1)
    open_unchanged_median = round(statistics.median(open_unchanged_times), 1)
    open_changed_median = round(statistics.median(open_changed_times), 1)
    return {
        "slice": "RM-065",
        "generated_at": datetime.now(UTC).isoformat(),
        "environment": _bench.environment_block(),
        "store": {
            "nodes": NODES,
            "directed_edges": seed_edges,
            "store_bytes": store_bytes,
            "seed": "RM-058 uniform store built once via the public API; "
            "every measurement starts from a byte copy of the closed, "
            "checkpointed seed file",
        },
        "snapshot": {
            "times_ms": [round(t, 1) for t in snapshot_times],
            "median_ms": snapshot_median,
            "backup_bytes": snapshot_bytes,
            "verified_quick_check_and_edges": snapshot_verified,
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
        "maintenance": medians,
        "double_pay": {
            "open_backup_equals_pre_decay_snapshot_tables": double_pay_equal,
            "redundant_snapshot_cost_ms": snapshot_median if double_pay_equal else 0.0,
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_suffix(".json"),
    )
    parser.add_argument("--nodes", type=int, default=NODES)
    args = parser.parse_args(argv)
    record = run_backup_cost(nodes=args.nodes)
    args.output.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
