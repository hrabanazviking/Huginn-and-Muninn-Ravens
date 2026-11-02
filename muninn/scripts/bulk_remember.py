"""Muninn bulk remember — RM-060 gate script.

Run: python scripts/bulk_remember.py [--output bulk_remember.json]

What it does:
- Ingests ``NODES`` distinct nodes (the RM-020 benchmark
  corpus, category ``bench``) into a fresh store two ways:
  the ``remember`` loop the roadmap names — one call, one
  transaction, one backpressure check per node — and the new
  ``remember_many`` batch API — one preparation pass, one
  transaction, backpressure applied once.
- Each road is measured on a fresh store per repeat; the
  record carries the median of ``REPEAT`` full runs per road
  and the RM-006 environment block, plus the RM-020 corpus
  block for the ingested texts.
- Both roads' stores are verified to hold exactly the same
  logical content (same ids in order, same node count, same
  per-node fields excluding timestamps) before the record is
  produced; a mismatch raises instead of recording timings
  for two different stores.

Class: BENCH. This script is the RM-060 acceptance gate:
run it on the post-slice tree (the pre-slice tree has no
``remember_many`` to measure — the loop road *is* the
before). Numbers on a loaded machine are indicative, not
absolutes — the environment block says so. Stores live on
tmpfs (the RM-005 storage class); local store only, nothing
external is touched.
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

NODES = 10000

OPS = ("remember_loop", "remember_many")


def _items(n_nodes):
    """The ingest workload: RM-020 corpus texts as batch items."""
    return [
        {"content": _bench.corpus_text(i), "category": "bench"}
        for i in range(n_nodes)
    ]


def _fresh_memory(tmp_root, name):
    from muninn import HebbianMemory
    from muninn.config import MuninnConfig

    return HebbianMemory(
        MuninnConfig(
            db_path=str(Path(tmp_root) / name),
            auto_backup=False,
        )
    )


def _ingest_loop(items):
    """The loop remember_many replaces: one call per node."""
    tmp = tempfile.mkdtemp(prefix="muninn-bulk-loop-")
    mem = _fresh_memory(tmp, "loop.db")
    start = time.perf_counter()
    ids = [mem.remember(**item) for item in items]
    elapsed_ms = (time.perf_counter() - start) * 1000
    return mem, ids, elapsed_ms


def _ingest_batch(items):
    tmp = tempfile.mkdtemp(prefix="muninn-bulk-batch-")
    mem = _fresh_memory(tmp, "batch.db")
    start = time.perf_counter()
    ids = mem.remember_many(items)
    elapsed_ms = (time.perf_counter() - start) * 1000
    return mem, ids, elapsed_ms


def _logical_dump(mem, ids):
    """The store's logical content for the ids, in id order —
    every stored field except the timestamps."""
    dump = []
    for node_id in ids:
        node = mem.get_node(node_id)
        assert node is not None
        entry = node.to_dict()
        entry.pop("created_at")
        entry.pop("updated_at")
        dump.append(entry)
    return dump


def run_bulk_remember(n_nodes=NODES, repeat=REPEAT):
    """Ingest ``n_nodes`` by both roads ``repeat`` times each;
    return the full record. Sizes are parameters so tests can
    run the same shape small."""
    items = _items(n_nodes)
    loop_times = []
    batch_times = []
    verified = False
    for run in range(repeat):
        mem_loop, ids_loop, ms_loop = _ingest_loop(items)
        mem_batch, ids_batch, ms_batch = _ingest_batch(items)
        loop_times.append(ms_loop)
        batch_times.append(ms_batch)
        if run == 0:
            # Like with like: the two roads must have built
            # the same store before any timing is quoted.
            assert ids_loop == ids_batch, "roads returned different ids"
            assert mem_loop.stats()["total_nodes"] == n_nodes
            assert mem_batch.stats()["total_nodes"] == n_nodes
            assert _logical_dump(mem_loop, ids_loop) == _logical_dump(
                mem_batch, ids_batch
            ), "roads built logically different stores"
            verified = True
        mem_loop.close()
        mem_batch.close()
    loop_ms = statistics.median(loop_times)
    batch_ms = statistics.median(batch_times)
    texts = [item["content"] for item in items]
    return {
        "package": "muninn",
        "schema": 1,
        "kind": "bulk_remember",
        "environment": _bench.environment_block(),
        "results_ms": {
            "remember_loop": loop_ms,
            "remember_many": batch_ms,
        },
        "details": {
            "nodes": n_nodes,
            "repeat": repeat,
            "speedup": round(loop_ms / batch_ms, 2) if batch_ms else None,
            "loop_ms_per_node": round(loop_ms / n_nodes, 4),
            "batch_ms_per_node": round(batch_ms / n_nodes, 4),
            "stores_verified_identical": verified,
            "corpus": _bench.corpus_block(texts),
            "unit": (
                f"median total ms to ingest {n_nodes} distinct nodes "
                f"into a fresh store (median of {repeat} runs per road)"
            ),
            "storage_class": "tmpfs (tempfile default on this machine)",
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None,
                        help="write the JSON record to this path")
    args = parser.parse_args(argv)
    record = run_bulk_remember()
    for op in OPS:
        print(f"{op:<28} {record['results_ms'][op]:10.1f} ms")
    print(f"speedup: {record['details']['speedup']}x "
          f"({record['details']['nodes']} nodes, "
          f"stores verified identical: "
          f"{record['details']['stores_verified_identical']})")
    env = record["environment"]
    print(f"recorded_at: {env['recorded_at']}  load_avg: {env['load_avg']}")
    if args.output is not None:
        args.output.write_text(json.dumps(record, indent=2) + "\n")
        print(f"bulk-remember record written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
