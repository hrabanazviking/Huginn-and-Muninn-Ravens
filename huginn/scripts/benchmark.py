"""Huginn benchmark — local backend, indicative numbers.

Run: python scripts/benchmark.py
"""

import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from huginn import HuginnConfig, HuginnMemory  # noqa: E402

WORDS = (
    "raven wolf river stone fire ice saga rune ship sea storm wolf "
    "memory thought wisdom eye well tree root branch leaf song sword"
).split()


def doc_text(i):
    words = [WORDS[(i * 7 + j * 3) % len(WORDS)] for j in range(24)]
    return " ".join(words)


def main():
    tmp = tempfile.mkdtemp(prefix="huginn-bench-")
    h = HuginnMemory(
        HuginnConfig(backend="local", local_db_path=str(Path(tmp) / "bench.db"))
    )
    n_docs = 5000
    start = time.perf_counter()
    for i in range(n_docs):
        h.upsert_memory(content=doc_text(i), category=f"cat{i % 10}", importance=5)
    elapsed = time.perf_counter() - start
    print(f"upsert_memory() x{n_docs} docs           {elapsed * 1000:10.1f} ms total"
          f"  ({elapsed / n_docs * 1000:.2f} ms/doc)")

    queries = ["raven wisdom tree", "sword fire storm", "ship sea song", "wolf eye memory"]
    times = []
    for i in range(200):
        q = queries[i % len(queries)]
        start = time.perf_counter()
        h.search(query_text=q, limit=10)
        times.append((time.perf_counter() - start) * 1000)
    times.sort()
    print(f"search(limit=10) over {n_docs} docs      median {statistics.median(times):8.2f} ms"
          f"  p95 {times[int(len(times) * 0.95)]:8.2f} ms")

    times = []
    for i in range(100):
        start = time.perf_counter()
        h.search(query_text=queries[i % len(queries)], limit=10, category="cat3")
        times.append((time.perf_counter() - start) * 1000)
    times.sort()
    print(f"search(category filter)                 median {statistics.median(times):8.2f} ms"
          f"  p95 {times[int(len(times) * 0.95)]:8.2f} ms")
    h.close()


if __name__ == "__main__":
    main()
