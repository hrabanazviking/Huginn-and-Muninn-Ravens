"""Muninn read path at 100k edges — RM-058 gate script.

Run: python scripts/read_path.py [--output read_path.json]

What it does:
- Builds two deterministic graphs and profiles the two read
  operations the roadmap names — ``get_associations`` and
  ``spread_activation`` — on each:
  * **uniform**: 5,000 nodes, every node associated with the
    next 10 nodes on a ring (strengths by a fixed formula) —
    50,000 undirected pairs = **100,000 directed rows**,
    degree 20 per node. This is the 100k-edge store the
    roadmap asks for (the RM-057 atlas store carried only
    ~4,000 connection rows).
  * **hub**: one hub node associated with 10,000 spokes —
    20,000 directed rows, hub degree 10,000. Hubs are where
    read paths go to die: a limited ``get_associations``
    must not sort the whole neighbourhood, and a depth-2
    ``spread_activation`` from the hub faces a 10,000-node
    frontier.
- Every operation is measured on a fixed sample batch,
  median of ``REPEAT`` runs, exactly as the atlas harness
  does. The record carries the RM-006 environment block.
- Also records the ``EXPLAIN QUERY PLAN`` of the
  ``get_associations`` query shape, so the plan (index used,
  temp b-tree or not) is evidence, not assertion.

Class: BENCH. This script is the RM-058 before/after gate:
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

UNIFORM_NODES = 5000
UNIFORM_FORWARD = 10  # pairs per node -> degree 20, 100k directed rows
HUB_SPOKES = 10000

OPS = (
    "uniform_get_associations",
    "uniform_spread_depth2",
    "uniform_spread_depth3",
    "hub_get_associations_limit100",
    "hub_get_associations_limit10000",
    "hub_spread_depth1",
    "hub_spread_depth2",
)


def _strength(i):
    return 0.1 + 0.05 * (i % 17)


def _bench_ms(fn, repeat=REPEAT):
    times = []
    for _ in range(repeat):
        start = time.perf_counter()
        fn()
        times.append((time.perf_counter() - start) * 1000)
    return statistics.median(times)


def build_uniform(n_nodes=UNIFORM_NODES, forward=UNIFORM_FORWARD):
    """Ring-lattice graph: node i wired to the next ``forward``
    nodes; returns (memory, ids). Directed rows = 2 * n * forward."""
    from muninn import HebbianMemory
    from muninn.config import MuninnConfig

    tmp = tempfile.mkdtemp(prefix="muninn-readpath-uniform-")
    mem = HebbianMemory(
        MuninnConfig(
            db_path=str(Path(tmp) / "uniform.db"),
            max_nodes=n_nodes + 10,
            auto_backup=False,
        )
    )
    ids = [
        mem.remember(f"uniform node {i} unique text {i}", category="bench")
        for i in range(n_nodes)
    ]
    for i, mid in enumerate(ids):
        for k in range(1, forward + 1):
            mem.associate(mid, ids[(i + k) % n_nodes], strength=_strength(i + k))
    return mem, ids


def build_hub(n_spokes=HUB_SPOKES):
    """One hub wired to ``n_spokes`` spokes; returns
    (memory, hub_id, spoke_ids). Directed rows = 2 * n_spokes."""
    from muninn import HebbianMemory
    from muninn.config import MuninnConfig

    tmp = tempfile.mkdtemp(prefix="muninn-readpath-hub-")
    mem = HebbianMemory(
        MuninnConfig(
            db_path=str(Path(tmp) / "hub.db"),
            max_nodes=n_spokes + 10,
            auto_backup=False,
        )
    )
    hub = mem.remember("hub node unique", category="bench")
    spokes = [
        mem.remember(f"spoke node {i} unique text {i}", category="bench")
        for i in range(n_spokes)
    ]
    for i, spoke in enumerate(spokes):
        mem.associate(hub, spoke, strength=_strength(i))
    return mem, hub, spokes


def _get_associations_plan(mem):
    import sqlite3

    db_path = mem.config.db_path
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "EXPLAIN QUERY PLAN"
        " SELECT memory_b_id, strength, co_activation_count, consolidated,"
        " last_coactivated_at FROM hebbian_connections"
        " WHERE memory_a_id = ? AND strength >= ?"
        " ORDER BY strength DESC, co_activation_count DESC, memory_b_id ASC"
        " LIMIT ?",
        (1, 0.0, 100),
    ).fetchall()
    conn.close()
    return [r[3] for r in rows]


def run_read_path(uniform_nodes=UNIFORM_NODES, hub_spokes=HUB_SPOKES):
    """Build both graphs, measure every op in ``OPS``; return
    the full record. Sizes are parameters so tests can run the
    same shape small."""
    results = {}
    details = {}

    mem, ids = build_uniform(uniform_nodes, UNIFORM_FORWARD)
    n = uniform_nodes
    results["uniform_get_associations"] = _bench_ms(
        lambda: [mem.get_associations(ids[i % n]) for i in range(200)]
    )
    results["uniform_spread_depth2"] = _bench_ms(
        lambda: [mem.spread_activation([ids[i % n]], depth=2) for i in range(50)]
    )
    results["uniform_spread_depth3"] = _bench_ms(
        lambda: [mem.spread_activation([ids[i % n]], depth=3) for i in range(20)]
    )
    stats = mem.stats()
    details["uniform"] = {
        "n_nodes": stats["total_nodes"],
        "directed_rows": stats["total_connections"],
        "samples": {"get_associations": 200, "spread_depth2": 50, "spread_depth3": 20},
    }
    plan = _get_associations_plan(mem)
    mem.close()

    mem, hub, _spokes = build_hub(hub_spokes)
    results["hub_get_associations_limit100"] = _bench_ms(
        lambda: [mem.get_associations(hub) for _ in range(20)]
    )
    results["hub_get_associations_limit10000"] = _bench_ms(
        lambda: [mem.get_associations(hub, limit=10000) for _ in range(20)]
    )
    results["hub_spread_depth1"] = _bench_ms(
        lambda: mem.spread_activation([hub], depth=1)
    )
    results["hub_spread_depth2"] = _bench_ms(
        lambda: mem.spread_activation([hub], depth=2)
    )
    stats = mem.stats()
    details["hub"] = {
        "n_nodes": stats["total_nodes"],
        "directed_rows": stats["total_connections"],
        "samples": {
            "get_associations_limit100": 20,
            "get_associations_limit10000": 20,
            "spread_depth1": REPEAT,
            "spread_depth2": REPEAT,
        },
    }
    mem.close()

    details["get_associations_query_plan"] = plan
    details["unit"] = (
        "median total ms for the labelled fixed sample batch "
        f"(median of {REPEAT} runs)"
    )
    details["storage_class"] = "tmpfs (tempfile default on this machine)"
    return {
        "package": "muninn",
        "schema": 1,
        "kind": "read_path",
        "environment": _bench.environment_block(),
        "results_ms": results,
        "details": details,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None,
                        help="write the JSON record to this path")
    args = parser.parse_args(argv)
    record = run_read_path()
    for op in OPS:
        print(f"{op:<36} {record['results_ms'][op]:10.1f} ms")
    print(f"plan: {record['details']['get_associations_query_plan']}")
    env = record["environment"]
    print(f"recorded_at: {env['recorded_at']}  load_avg: {env['load_avg']}")
    if args.output is not None:
        args.output.write_text(json.dumps(record, indent=2) + "\n")
        print(f"read-path record written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
