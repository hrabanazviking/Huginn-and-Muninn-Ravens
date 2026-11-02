"""Huginn baseline atlas — headline operations at 1k / 10k / 100k
documents (RM-057, Part V — Speed opens).

Run: python scripts/atlas.py [--scales 1000,10000,100000]
                             [--output atlas.json]

What it does:
- For each scale, seeds a fresh temporary local store with that
  many documents from the RM-020 benchmark corpus (the same
  formula generator and fixed search queries as
  ``scripts/benchmark.py`` — BENCH numbers only ever compare
  like with like), then measures every headline operation from
  RM-005's gate contract (``HEADLINE_OPS``).
- ``upsert`` is the seeding itself: total ms for the whole
  scale. The search operations are measured over fixed sample
  counts (``SAMPLE`` below — the same counts at every scale) and
  reported as median ms per search with the p95 beside them in
  the details, so the atlas shows how search cost grows with
  store size instead of mixing store size with sample size.
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
Local backend only; a live Qdrant round-trip stays NOT PROVEN
until actually run against a server.
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

# Fixed sample counts, identical at every scale (see docstring).
SAMPLE = {
    "n_search": 50,
    "n_search_filtered": 25,
}

QUERIES = ["raven wisdom tree", "sword fire storm", "ship sea song", "wolf eye memory"]


def run_at_scale(n_docs):
    """Seed one fresh store of ``n_docs`` and measure every
    headline operation; return (results_ms, details)."""
    from huginn import HuginnConfig, HuginnMemory

    tmp = tempfile.mkdtemp(prefix=f"huginn-atlas-{n_docs}-")
    h = HuginnMemory(
        HuginnConfig(backend="local", local_db_path=str(Path(tmp) / "atlas.db"))
    )
    results = {}

    texts = _bench.corpus_texts(n_docs)
    start = time.perf_counter()
    for i, text in enumerate(texts):
        h.upsert_memory(content=text, category=f"cat{i % 10}", importance=5)
    elapsed_ms = (time.perf_counter() - start) * 1000
    results["upsert"] = elapsed_ms
    print(f"upsert_memory() x{n_docs} docs (seed)      {elapsed_ms:10.1f} ms total"
          f"  ({elapsed_ms / n_docs:.2f} ms/doc)")

    def _search_median(n, **kwargs):
        times = []
        for i in range(n):
            q = QUERIES[i % len(QUERIES)]
            start = time.perf_counter()
            h.search(query_text=q, limit=10, **kwargs)
            times.append((time.perf_counter() - start) * 1000)
        times.sort()
        return statistics.median(times), times[int(len(times) * 0.95)]

    median, p95 = _search_median(SAMPLE["n_search"])
    results["search"] = median
    print(f"search(limit=10) over {n_docs} docs      median {median:8.2f} ms"
          f"  p95 {p95:8.2f} ms")
    search_stats_unfiltered = h.last_search_stats

    median_f, p95_f = _search_median(SAMPLE["n_search_filtered"], category="cat3")
    results["search_filtered"] = median_f
    print(f"search(category filter)                 median {median_f:8.2f} ms"
          f"  p95 {p95_f:8.2f} ms")
    # RM-053's candidate cap (max_search_candidates, default
    # 10,000) bites at the 100k scale by design; the atlas
    # measures the shipped defaults, so the cap's own record of
    # the last search is filed in the details, not hidden.
    search_stats = h.last_search_stats
    h.close()
    details = {
        "workload": {"n_docs": n_docs, **SAMPLE},
        "unit": "upsert: total ms for the seed batch; search ops: median ms per search",
        "search_p95_ms": {"search": p95, "search_filtered": p95_f},
        "last_search_stats_after_search": search_stats_unfiltered,
        "last_search_stats_after_filtered": search_stats,
        "backend": "local",
        "corpus": _bench.corpus_block(texts),
    }
    return results, details


def run_atlas(scales=SCALES):
    """Run every scale; return the full atlas record."""
    entries = []
    for n in scales:
        print(f"--- scale: {n} docs ---")
        results, details = run_at_scale(n)
        entries.append({"scale": n, "results_ms": results, "details": details})
    return {
        "package": "huginn",
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
