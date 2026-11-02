"""Muninn activation write path — RM-059 gate script.

Run: python scripts/write_path.py [--output write_path.json]

What it does:
- Builds one deterministic store (``NODES`` remembered nodes)
  and profiles the activation write operations the roadmap
  names — ``activate`` (same id, distinct ids),
  ``activate_batch`` on a small co-active set (the per-id loop
  road), and ``retrieve(..., touch=True)`` (the one explicitly
  named reinforcing read, which shares the activation helper).
- Every operation is measured on a fixed sample batch, median
  of ``REPEAT`` runs, exactly as the atlas harness does. The
  record carries the RM-006 environment block.
- Also counts the SQL statements one ``activate()`` call
  executes (via the connection's trace callback, counting
  INSERT/UPDATE/DELETE/SELECT executions on the store's own
  connection — the Bifröst ``_get_conn`` seam), and records
  their shapes. Statement count is the slice's primary gate:
  timings on a loaded machine move, executed statements do
  not.

Class: BENCH. This script is the RM-059 before/after gate:
run it on the pre-slice tree and on the post-slice tree and
the two records compare like with like. Numbers on a loaded
machine are indicative, not absolutes — the environment
block says so. Stores live on tmpfs (the RM-005 storage
class); local store only, nothing external is touched.
"""

import argparse
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import benchmark as _bench  # noqa: E402  (sibling script, path set above)

REPEAT = 3

NODES = 2000

OPS = (
    "activate_same_id",
    "activate_distinct_ids",
    "activate_batch5",
    "retrieve_touch",
)

_COUNTED = ("INSERT", "UPDATE", "DELETE", "SELECT")


def _bench_ms(fn, repeat=REPEAT):
    times = []
    for _ in range(repeat):
        start = time.perf_counter()
        fn()
        times.append((time.perf_counter() - start) * 1000)
    return statistics.median(times)


def build_store(n_nodes=NODES):
    """A deterministic store of ``n_nodes`` plain nodes;
    returns (memory, ids)."""
    from muninn import HebbianMemory
    from muninn.config import MuninnConfig

    tmp = tempfile.mkdtemp(prefix="muninn-writepath-")
    mem = HebbianMemory(
        MuninnConfig(
            db_path=str(Path(tmp) / "write.db"),
            max_nodes=n_nodes + 10,
            auto_backup=False,
        )
    )
    ids = [
        mem.remember(f"write node {i} unique text {i}", category="bench")
        for i in range(n_nodes)
    ]
    return mem, ids


def count_activate_statements(mem, memory_id):
    """SQL executions one ``activate()`` call performs.

    Returns (total, [first-word kinds in execution order]).
    The trace callback sees every statement the connection
    executes; only the four data-statement kinds are counted
    (BEGIN/COMMIT are connection bookkeeping, not per-call
    work in the helper).
    """
    seen = []

    def _trace(sql):
        head = sql.lstrip().split(None, 1)[0].upper() if sql.strip() else ""
        if head in _COUNTED:
            seen.append(head)

    conn = mem._get_conn()
    conn.set_trace_callback(_trace)
    try:
        mem.activate(memory_id)
    finally:
        conn.set_trace_callback(None)
    return len(seen), seen


def run_write_path(n_nodes=NODES):
    """Build the store, measure every op in ``OPS`` plus the
    per-activate statement count; return the full record.
    Sizes are parameters so tests can run the same shape
    small."""
    results = {}
    details = {}

    mem, ids = build_store(n_nodes)
    n = n_nodes
    results["activate_same_id"] = _bench_ms(
        lambda: [mem.activate(ids[0]) for _ in range(2000)]
    )
    results["activate_distinct_ids"] = _bench_ms(
        lambda: [mem.activate(ids[i % n]) for i in range(2000)]
    )
    batch = ids[:5]
    results["activate_batch5"] = _bench_ms(
        lambda: [mem.activate_batch(batch) for _ in range(400)]
    )
    results["retrieve_touch"] = _bench_ms(
        lambda: [mem.retrieve(touch=True, top_k=5) for _ in range(200)]
    )
    count, kinds = count_activate_statements(mem, ids[1])
    details["statements_per_activate"] = count
    details["statement_kinds_per_activate"] = kinds
    details["samples"] = {
        "activate_same_id": 2000,
        "activate_distinct_ids": 2000,
        "activate_batch5": 400,
        "retrieve_touch": 200,
    }
    details["unit"] = (
        "median total ms for the labelled fixed sample batch "
        f"(median of {REPEAT} runs)"
    )
    details["storage_class"] = "tmpfs (tempfile default on this machine)"
    mem.close()
    return {
        "package": "muninn",
        "schema": 1,
        "kind": "write_path",
        "environment": _bench.environment_block(),
        "results_ms": results,
        "details": details,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None,
                        help="write the JSON record to this path")
    args = parser.parse_args(argv)
    record = run_write_path()
    for op in OPS:
        print(f"{op:<28} {record['results_ms'][op]:10.1f} ms")
    print(f"statements_per_activate: {record['details']['statements_per_activate']}"
          f" {record['details']['statement_kinds_per_activate']}")
    env = record["environment"]
    print(f"recorded_at: {env['recorded_at']}  load_avg: {env['load_avg']}")
    if args.output is not None:
        args.output.write_text(json.dumps(record, indent=2) + "\n")
        print(f"write-path record written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
