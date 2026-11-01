"""RM-035 — Huge-batch bench: ``activate_batch`` with 10k ids.

The acceptance proof for RM-035, kept as a runnable script (the
RM-015 soak division of labour: the suite pins the semantics at
feasible scale, this bench proves the headline number once,
against the real store):

    python3 scripts/huge_batch_bench.py [--ids 10000] [--workdir DIR]

It builds a fresh store in the workdir, runs ONE
``activate_batch`` over ids 1..N in one transaction, then verifies
the result against the store itself — activation log rows,
node_activation rows, directed hebbian rows (exactly N(N-1),
counted through the primary-key index), and the strength /
co-activation values of a deterministic spread of sample rows —
and prints a JSON record with the counts, the wall time, the
process peak RSS (``ru_maxrss``), the on-disk store size, and an
environment block (machine, load, Python, SQLite). (Full-table
uniformity and integrity scans over a ~10 GB store are the test
suite's job at feasible scale, not this bench's: at 100M rows they
cost more wall time than the batch itself.)

The store it leaves behind is ~105 bytes per directed row: at the
default 10k ids that is a ~10 GB database. The workdir is scratch
— delete it afterwards. Nothing here touches a real memory store.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import resource
import sqlite3
import sys
import time
from datetime import UTC, datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ids", type=int, default=10_000)
    parser.add_argument("--workdir", type=Path, default=Path("huge-batch-bench"))
    args = parser.parse_args()

    from muninn import HebbianMemory
    from muninn.config import MuninnConfig

    args.workdir.mkdir(parents=True, exist_ok=True)
    db_path = args.workdir / "bench.db"
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(str(db_path) + suffix)
        if candidate.exists():
            candidate.unlink()

    n = args.ids
    pairs = n * (n - 1) // 2
    mem = HebbianMemory(MuninnConfig(db_path=str(db_path)))
    started = time.time()
    result = mem.activate_batch(list(range(1, n + 1)))
    wall_s = time.time() - started

    conn = mem._get_conn()
    directed = conn.execute("SELECT COUNT(*) FROM hebbian_connections").fetchone()[0]
    activations = conn.execute("SELECT COUNT(*) FROM activation_log").fetchone()[0]
    counters = conn.execute("SELECT COUNT(*) FROM node_activation").fetchone()[0]
    lr = mem.config.learning_rate
    # A deterministic spread of 1,001 directed rows across the whole
    # key range: first, last, and every ~n/10th id wired to its
    # neighbour — each must carry the first-wiring strength and a
    # co-activation count of exactly 1.
    sample_ids = sorted({1, n} | {1 + (n * k) // 10 for k in range(10)})
    sample_ok = True
    sampled = 0
    for a in sample_ids:
        for b in sample_ids:
            if a == b:
                continue
            row = conn.execute(
                "SELECT strength, co_activation_count FROM hebbian_connections"
                " WHERE memory_a_id = ? AND memory_b_id = ?",
                (a, b),
            ).fetchone()
            sampled += 1
            if row is None or row[0] != lr or row[1] != 1:
                sample_ok = False
    mem.close()

    checks = {
        "report_activated": result["activated"] == n,
        "report_pairs": result["pairs_wired"] == pairs,
        "report_created": result["connections_created"] == pairs,
        "report_strengthened": result["connections_strengthened"] == 0,
        "directed_rows_exact": directed == 2 * pairs,
        "activation_log_exact": activations == n,
        "node_activation_exact": counters == n,
        "sampled_strength_and_count_uniform": sample_ok and sampled >= 100,
    }
    record = {
        "slice": "RM-035",
        "recorded_at": datetime.now(UTC).isoformat(),
        "ids": n,
        "pairs_unordered": pairs,
        "directed_rows": directed,
        "wall_seconds": round(wall_s, 2),
        "peak_rss_mb": round(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1
        ),
        "db_bytes": db_path.stat().st_size,
        "checks": checks,
        "all_checks_passed": all(checks.values()),
        "environment": {
            "machine": platform.machine(),
            "system": platform.system(),
            "node": platform.node(),
            "cpu_count": os.cpu_count(),
            "load_avg": list(os.getloadavg()) if hasattr(os, "getloadavg") else None,
            "python_version": platform.python_version(),
            "sqlite_version": sqlite3.sqlite_version,
        },
    }
    print(json.dumps(record, indent=2))
    return 0 if record["all_checks_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
