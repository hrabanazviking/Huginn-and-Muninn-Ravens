"""Muninn benchmark — indicative numbers on the machine at hand.

Run: python scripts/benchmark.py
Prints one line per measurement; BUILD_NOTES.md records a run.
"""

import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from muninn import HebbianMemory  # noqa: E402
from muninn.config import MuninnConfig  # noqa: E402


def bench(label, fn, repeat=1):
    times = []
    for _ in range(repeat):
        start = time.perf_counter()
        result = fn()
        times.append(time.perf_counter() - start)
    med = statistics.median(times)
    print(f"{label:<44} {med * 1000:10.1f} ms  (median of {repeat})")
    return result


def main():
    tmp = tempfile.mkdtemp(prefix="muninn-bench-")
    mem = HebbianMemory(MuninnConfig(db_path=str(Path(tmp) / "bench.db")))

    n_nodes = 5000
    bench(f"remember() x{n_nodes} nodes", lambda: [
        mem.remember(f"benchmark memory {i} about topic {i % 50}", category="bench")
        for i in range(n_nodes)
    ])

    n_act = 20000
    bench(f"activate() x{n_act} single activations", lambda: [
        mem.activate(1000 + (i % 500)) for i in range(n_act)
    ])

    n_batch = 2000
    bench(f"activate_batch(5 ids) x{n_batch}", lambda: [
        mem.activate_batch([2000 + (i % 100) + j for j in range(5)])
        for i in range(n_batch)
    ])

    stats = mem.stats()
    print(f"  store now: {stats['total_nodes']} nodes, "
          f"{stats['total_connections']} connection rows, "
          f"{stats['total_activations']} activations")

    bench("get_associations() x5000 reads", lambda: [
        mem.get_associations(2000 + (i % 100)) for i in range(5000)
    ], repeat=3)
    bench("spread_activation(depth=2) x1000", lambda: [
        mem.spread_activation([2000 + (i % 100)], depth=2) for i in range(1000)
    ], repeat=3)
    bench("decay(days=1) over full store", lambda: mem.decay(days=1), repeat=3)
    bench("consolidate() over full store", lambda: mem.consolidate(), repeat=3)
    bench("stats()", lambda: mem.stats(), repeat=3)
    mem.close()


if __name__ == "__main__":
    main()
