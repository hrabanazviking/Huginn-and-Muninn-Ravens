"""Muninn benchmark — now a repeatable gate (RM-005).

Run: python scripts/benchmark.py [--check | --update-baseline | --no-check]

What it does:
- Runs the headline operations below on a fresh temporary store,
  at the workload sizes in ``WORKLOAD`` (overridable by flags).
- Prints a text summary and a JSON record. Every record carries an
  environment block (machine, CPU count, load average, Python and
  SQLite versions) so a number is never quoted without the machine
  and load it was measured under (RM-005/RM-006 honesty rule).
- Gate mode (``--check``, the default when a baseline exists):
  compares each headline operation against ``baseline.json``
  beside this script and exits 1 if any operation regressed by
  more than the threshold (default 25%).
- ``--update-baseline`` re-records ``baseline.json`` from this run.
  Re-baselining is a deliberate act: do it only when a change is
  understood, never to silence a regression you have not read.

Class: BENCH. Numbers on a loaded machine are indicative, not
absolutes — the environment block in every record says so.
"""

import argparse
import json
import os
import platform
import sqlite3
import statistics
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

DEFAULT_THRESHOLD = 0.25
BASELINE_PATH = Path(__file__).resolve().parent / "baseline.json"

WORKLOAD = {
    "n_nodes": 5000,
    "n_activate": 20000,
    "n_batch": 2000,
    "read_repeat": 3,
}

# Headline operations, in run order. These keys are the gate's
# contract: a baseline missing one, or a run missing one, fails.
HEADLINE_OPS = (
    "remember",
    "activate",
    "activate_batch",
    "get_associations",
    "spread_activation",
    "decay",
    "consolidate",
    "stats",
)


def environment_block():
    """Machine + load labelling for every benchmark record."""
    try:
        load = list(os.getloadavg())
    except (AttributeError, OSError):
        load = None
    return {
        "recorded_at": datetime.now(UTC).isoformat(),
        "machine": platform.machine(),
        "system": platform.system(),
        "platform": platform.platform(),
        "node": platform.node(),
        "cpu_count": os.cpu_count(),
        "load_avg": load,
        "python_version": platform.python_version(),
        "sqlite_version": sqlite3.sqlite_version,
    }


def compare_to_baseline(current, baseline, threshold=DEFAULT_THRESHOLD):
    """Return a list of regression dicts; empty list means the gate passes.

    ``current`` and ``baseline`` map headline op -> median/total ms.
    A regression is a current value more than ``threshold`` (a
    fraction, default 0.25) above its baseline. A headline op
    missing from either side is reported as a regression with
    ``reason: "missing"`` — a silent gap must never pass the gate.
    """
    regressions = []
    for op in HEADLINE_OPS:
        if op not in baseline:
            regressions.append(
                {"operation": op, "reason": "missing_from_baseline"}
            )
            continue
        if op not in current:
            regressions.append(
                {"operation": op, "reason": "missing_from_current"}
            )
            continue
        base = float(baseline[op])
        cur = float(current[op])
        change = (cur - base) / base if base > 0 else (0.0 if cur == 0 else float("inf"))
        if change > threshold:
            regressions.append(
                {
                    "operation": op,
                    "baseline_ms": base,
                    "current_ms": cur,
                    "regression": change,
                    "threshold": threshold,
                }
            )
    return regressions


def _bench_ms(label, fn, repeat=1):
    times = []
    result = None
    for _ in range(repeat):
        start = time.perf_counter()
        result = fn()
        times.append((time.perf_counter() - start) * 1000)
    med = statistics.median(times)
    print(f"{label:<44} {med:10.1f} ms  (median of {repeat})")
    return med, result


def run_benchmark(workload):
    """Run the headline operations; return (results_ms, details)."""
    # Imported here, after the sys.path bootstrap above, so the script
    # also runs from a bare checkout with nothing installed.
    from muninn import HebbianMemory
    from muninn.config import MuninnConfig

    tmp = tempfile.mkdtemp(prefix="muninn-bench-")
    mem = HebbianMemory(MuninnConfig(db_path=str(Path(tmp) / "bench.db")))
    n_nodes = workload["n_nodes"]
    n_act = workload["n_activate"]
    n_batch = workload["n_batch"]
    repeat = workload["read_repeat"]
    results = {}

    results["remember"], _ = _bench_ms(
        f"remember() x{n_nodes} nodes",
        lambda: [
            mem.remember(
                f"benchmark memory {i} about topic {i % 50}", category="bench"
            )
            for i in range(n_nodes)
        ],
    )
    results["activate"], _ = _bench_ms(
        f"activate() x{n_act} single activations",
        lambda: [mem.activate(1000 + (i % 500)) for i in range(n_act)],
    )
    results["activate_batch"], _ = _bench_ms(
        f"activate_batch(5 ids) x{n_batch}",
        lambda: [
            mem.activate_batch([2000 + (i % 100) + j for j in range(5)])
            for i in range(n_batch)
        ],
    )
    stats = mem.stats()
    print(
        f"  store now: {stats['total_nodes']} nodes, "
        f"{stats['total_connections']} connection rows, "
        f"{stats['total_activations']} activations"
    )
    results["get_associations"], _ = _bench_ms(
        "get_associations() x5000 reads",
        lambda: [mem.get_associations(2000 + (i % 100)) for i in range(5000)],
        repeat=repeat,
    )
    results["spread_activation"], _ = _bench_ms(
        "spread_activation(depth=2) x1000",
        lambda: [
            mem.spread_activation([2000 + (i % 100)], depth=2)
            for i in range(1000)
        ],
        repeat=repeat,
    )
    results["decay"], _ = _bench_ms(
        "decay(days=1) over full store", lambda: mem.decay(days=1), repeat=repeat
    )
    results["consolidate"], _ = _bench_ms(
        "consolidate() over full store", lambda: mem.consolidate(), repeat=repeat
    )
    results["stats"], _ = _bench_ms(
        "stats() x1000",
        lambda: [mem.stats() for _ in range(1000)],
        repeat=repeat,
    )
    mem.close()
    details = {
        "workload": dict(workload),
        "unit": "median total ms for the labelled batch (seed ops run once)",
    }
    return results, details


def build_record(results, details, threshold):
    return {
        "package": "muninn",
        "schema": 1,
        "threshold": threshold,
        "environment": environment_block(),
        "results_ms": results,
        "details": details,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None,
                        help="write the JSON record to this path")
    parser.add_argument("--baseline", type=Path, default=BASELINE_PATH)
    parser.add_argument("--threshold", type=float, default=None,
                        help="regression fraction (default: baseline's, else 0.25)")
    parser.add_argument("--update-baseline", action="store_true")
    parser.add_argument("--no-check", action="store_true",
                        help="measure only; do not compare against the baseline")
    parser.add_argument("--nodes", type=int, default=WORKLOAD["n_nodes"])
    parser.add_argument("--activations", type=int, default=WORKLOAD["n_activate"])
    parser.add_argument("--batches", type=int, default=WORKLOAD["n_batch"])
    args = parser.parse_args(argv)

    workload = {
        "n_nodes": args.nodes,
        "n_activate": args.activations,
        "n_batch": args.batches,
        "read_repeat": WORKLOAD["read_repeat"],
    }
    results, details = run_benchmark(workload)

    baseline_record = None
    if args.baseline.exists():
        baseline_record = json.loads(args.baseline.read_text())
    if args.threshold is not None:
        threshold = args.threshold
    elif baseline_record is not None:
        threshold = float(baseline_record.get("threshold", DEFAULT_THRESHOLD))
    else:
        threshold = DEFAULT_THRESHOLD

    record = build_record(results, details, threshold)
    env = record["environment"]
    print("environment:")
    for key in (
        "recorded_at", "machine", "system", "platform", "node",
        "cpu_count", "load_avg", "python_version", "sqlite_version",
    ):
        print(f"  {key}: {env[key]}")
    if args.output is not None:
        args.output.write_text(json.dumps(record, indent=2) + "\n")
        print(f"record written: {args.output}")

    if args.update_baseline:
        args.baseline.write_text(json.dumps(record, indent=2) + "\n")
        print(f"baseline updated: {args.baseline}")
        return 0
    if args.no_check:
        return 0
    if baseline_record is None:
        print(f"GATE: no baseline at {args.baseline}; nothing to check against")
        return 0
    regressions = compare_to_baseline(
        results, baseline_record.get("results_ms", {}), threshold
    )
    if regressions:
        for r in regressions:
            if r.get("reason"):
                print(f"GATE FAIL: {r['operation']}: {r['reason']}")
            else:
                print(
                    f"GATE FAIL: {r['operation']}: {r['baseline_ms']:.1f} ms -> "
                    f"{r['current_ms']:.1f} ms "
                    f"(+{r['regression'] * 100:.1f}% > {threshold * 100:.0f}%)"
                )
        return 1
    print(f"GATE PASS: no headline operation regressed > {threshold * 100:.0f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
