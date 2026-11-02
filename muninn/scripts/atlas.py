"""Muninn baseline atlas — headline operations at 1k / 10k / 100k
nodes (RM-057, Part V — Speed opens).

Run: python scripts/atlas.py [--scales 1000,10000,100000]
                             [--output atlas.json]

What it does:
- For each scale, seeds a fresh temporary store with that many
  nodes from the RM-020 benchmark corpus (the same formula
  generator as ``scripts/benchmark.py`` — BENCH numbers only ever
  compare like with like), then measures every headline
  operation from RM-005's gate contract (``HEADLINE_OPS``).
- ``remember`` is the seeding itself: total ms for the whole
  scale. The other operations are measured on fixed sample
  batches (``SAMPLE`` below — the same counts at every scale), so
  the atlas shows how each operation's cost grows with store
  size instead of mixing store size with batch size. Read and
  maintenance operations take the median of ``READ_REPEAT`` runs,
  exactly as the gate harness does.
- The record is a JSON atlas: one entry per scale with its
  results, its workload and its corpus block, under a single
  environment block (machine, CPU count, load average, Python
  and SQLite versions, UTC timestamp — RM-006 honesty rule: a
  number is never quoted without the machine and load it was
  measured under).

Class: BENCH. The atlas is a record, not a gate — nothing here
fails on a slow number; RM-071 wires the atlas operations into
the regression gate. Numbers on a loaded machine are
indicative, not absolutes — the environment block says so.
Local store only; nothing external is touched.
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

HEADLINE_OPS = _bench.HEADLINE_OPS
SCALES = (1000, 10000, 100000)

# Fixed sample batches, identical at every scale (see docstring).
SAMPLE = {
    "n_activate": 2000,
    "n_batch": 500,
    "n_get_associations": 1000,
    "n_spread": 200,
    "n_stats": 200,
}
READ_REPEAT = 3


def _bench_ms(label, fn, repeat=1):
    times = []
    result = None
    for _ in range(repeat):
        start = time.perf_counter()
        result = fn()
        times.append((time.perf_counter() - start) * 1000)
    med = statistics.median(times)
    print(f"{label:<48} {med:10.1f} ms  (median of {repeat})")
    return med, result


def run_at_scale(n_nodes):
    """Seed one fresh store of ``n_nodes`` and measure every
    headline operation; return (results_ms, details)."""
    from muninn import HebbianMemory
    from muninn.config import MuninnConfig

    tmp = tempfile.mkdtemp(prefix=f"muninn-atlas-{n_nodes}-")
    # The atlas claims a store of exactly n_nodes nodes, so the
    # backpressure ceiling (MuninnConfig.max_nodes, default
    # 20,000) is raised to an exact fit for the seed; with the
    # default, remember() would prune the seed back to 20,000
    # and the 100k row would not be a 100k-node store. The
    # override is recorded in the details of every scale.
    mem = HebbianMemory(
        MuninnConfig(db_path=str(Path(tmp) / "atlas.db"), max_nodes=n_nodes)
    )
    results = {}

    texts = _bench.corpus_texts(n_nodes)
    results["remember"], _ = _bench_ms(
        f"remember() x{n_nodes} nodes (seed)",
        lambda: [mem.remember(text, category="bench") for text in texts],
    )
    # Sample ids live inside the seeded range at every scale.
    offset = max(1, n_nodes // 5)
    window = max(1, min(500, n_nodes - offset))
    results["activate"], _ = _bench_ms(
        f"activate() x{SAMPLE['n_activate']} single activations",
        lambda: [
            mem.activate(offset + (i % window))
            for i in range(SAMPLE["n_activate"])
        ],
    )
    results["activate_batch"], _ = _bench_ms(
        f"activate_batch(5 ids) x{SAMPLE['n_batch']}",
        lambda: [
            mem.activate_batch([offset + ((i + j) % window) for j in range(5)])
            for i in range(SAMPLE["n_batch"])
        ],
    )
    seeded = mem.stats()
    print(
        f"  store now: {seeded['total_nodes']} nodes, "
        f"{seeded['total_connections']} connection rows, "
        f"{seeded['total_activations']} activations"
    )
    results["get_associations"], _ = _bench_ms(
        f"get_associations() x{SAMPLE['n_get_associations']} reads",
        lambda: [
            mem.get_associations(offset + (i % window))
            for i in range(SAMPLE["n_get_associations"])
        ],
        repeat=READ_REPEAT,
    )
    results["spread_activation"], _ = _bench_ms(
        f"spread_activation(depth=2) x{SAMPLE['n_spread']}",
        lambda: [
            mem.spread_activation([offset + (i % min(100, window))], depth=2)
            for i in range(SAMPLE["n_spread"])
        ],
        repeat=READ_REPEAT,
    )
    results["decay"], _ = _bench_ms(
        "decay(days=1) over full store",
        lambda: mem.decay(days=1),
        repeat=READ_REPEAT,
    )
    results["consolidate"], _ = _bench_ms(
        "consolidate() over full store",
        lambda: mem.consolidate(),
        repeat=READ_REPEAT,
    )
    results["stats"], _ = _bench_ms(
        f"stats() x{SAMPLE['n_stats']}",
        lambda: [mem.stats() for _ in range(SAMPLE["n_stats"])],
        repeat=READ_REPEAT,
    )
    mem.close()
    details = {
        "workload": {"n_nodes": n_nodes, **SAMPLE, "read_repeat": READ_REPEAT},
        "unit": (
            "remember: total ms for the seed batch; other ops: median "
            "total ms for the labelled fixed sample batch"
        ),
        "config_overrides": {"max_nodes": n_nodes},
        "store_after_seed": {
            "total_nodes": seeded["total_nodes"],
            "total_connections": seeded["total_connections"],
            "total_activations": seeded["total_activations"],
        },
        "corpus": _bench.corpus_block(texts),
    }
    return results, details


def run_atlas(scales=SCALES):
    """Run every scale; return the full atlas record."""
    entries = []
    for n in scales:
        print(f"--- scale: {n} nodes ---")
        results, details = run_at_scale(n)
        entries.append({"scale": n, "results_ms": results, "details": details})
    return {
        "package": "muninn",
        "schema": 1,
        "kind": "atlas",
        "environment": _bench.environment_block(),
        "scales": entries,
    }


def print_environment(record):
    env = record["environment"]
    print("environment:")
    for key in (
        "recorded_at", "machine", "system", "platform", "node",
        "cpu_count", "load_avg", "python_version", "sqlite_version",
    ):
        print(f"  {key}: {env[key]}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None,
                        help="write the JSON atlas record to this path")
    parser.add_argument(
        "--scales", type=str,
        default=",".join(str(s) for s in SCALES),
        help="comma-separated store sizes (default: 1000,10000,100000)",
    )
    args = parser.parse_args(argv)
    scales = tuple(int(s) for s in args.scales.split(",") if s.strip())
    record = run_atlas(scales)
    print_environment(record)
    for entry in record["scales"]:
        corpus = entry["details"]["corpus"]
        print(
            f"scale {entry['scale']}: corpus v{corpus['version']} "
            f"n={corpus['count']} sha256={corpus['sha256']}"
        )
    if args.output is not None:
        args.output.write_text(json.dumps(record, indent=2) + "\n")
        print(f"atlas record written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
