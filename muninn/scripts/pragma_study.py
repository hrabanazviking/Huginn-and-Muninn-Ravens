"""Muninn connection pragmas study at 100k edges -- RM-066 gate.

Run: python scripts/pragma_study.py [--output pragma_study.json]

What it measures (roadmap RM-066: ``cache_size``,
``mmap_size``, ``temp_store`` measured per package;
defaults changed only on evidence, recorded per
pragma): the twin of ``huginn/scripts/pragma_study.py``.

- Muninn's open road sets exactly four pragmas today
  (``busy_timeout``, ``journal_mode=WAL``, ``synchronous
  =FULL``, ``foreign_keys=ON``). The three studied
  pragmas are never set, so SQLite's compiled defaults
  apply; the gate reads them back from a freshly opened
  store and records them as found (``defaults_as_found``).
- The seed is the RM-058/RM-065 uniform store -- 5,000
  nodes, 100,000 directed edge rows -- built once
  through the public API, checkpointed, and copied
  byte-for-byte for every measurement.
- Variants: ``baseline`` (connection exactly as the
  package opens it), ``cache16`` (``PRAGMA cache_size=
  -16384`` -- a 16 MiB page cache), ``cache64``
  (``PRAGMA cache_size=-65536`` -- 64 MiB, several
  times the whole store), ``mmap`` (``PRAGMA mmap_size=
  268435456``), ``temp`` (``PRAGMA temp_store=MEMORY``),
  and ``all`` (cache64 + mmap + temp together). Each
  variant is
  applied to the live connection the package opened
  (the study's one reach inside, stated here: pragmas
  are per-connection, so the study must set them on the
  connection the package owns) and read back before any
  timing is quoted -- a variant whose readback is not
  what it set fails the run.
- Each measurement is a fresh byte copy + fresh open +
  TWO timed passes per workload: pass 1 with the SQLite
  page cache cold, pass 2 warm on the same connection
  (the OS/tmpfs cache cannot be dropped from here and
  the record says so). Median of three measurements
  per variant per workload per temperature.
- Workloads (public API only): ``read_pass`` -- 200
  ``get_node``, 50 ``spread_activation`` (depth 2), 5
  ``stats()``, 100 ``get_associations`` (limit 100),
  repeated 4x per pass; ``aggregate_pass`` -- 40
  ``stats()`` + 80 ``spread_activation`` (depth 2), the
  sort/aggregate-bearing road. Every pass accumulates a
  fingerprint of everything it read; every fingerprint
  in the run must be identical or the run fails -- a
  pragma may change speed, never results.
- Name discipline: this slice's ``cache_size`` is
  SQLite's ``PRAGMA cache_size`` (the connection's page
  cache). It is NOT RM-063's ``cache_size`` config field
  (the per-object ``get_node`` warm cache); the two
  share a name and nothing else.

Class: BENCH. No package code changes in this slice
unless the record's verdict demands one; the script
runs unchanged on the RM-065 tree and produces the
same record shape. Numbers on a loaded machine are
indicative, not absolutes -- the environment block
says so. Stores live on tmpfs; local store only.
"""

import argparse
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
READ_REPS = 4
CACHE16_SIZE_KIB = -16384  # PRAGMA cache_size, negative = KiB
CACHE64_SIZE_KIB = -65536
MMAP_SIZE_BYTES = 268435456  # 256 MiB
TEMP_STORE_MEMORY = 2

VARIANTS = ("baseline", "cache16", "cache64", "mmap", "temp", "all")
_VARIANT_SQL = {
    "baseline": (),
    "cache16": (f"PRAGMA cache_size={CACHE16_SIZE_KIB}",),
    "cache64": (f"PRAGMA cache_size={CACHE64_SIZE_KIB}",),
    "mmap": (f"PRAGMA mmap_size={MMAP_SIZE_BYTES}",),
    "temp": (f"PRAGMA temp_store={TEMP_STORE_MEMORY}",),
    "all": (
        f"PRAGMA cache_size={CACHE64_SIZE_KIB}",
        f"PRAGMA mmap_size={MMAP_SIZE_BYTES}",
        f"PRAGMA temp_store={TEMP_STORE_MEMORY}",
    ),
}


def _strength(i):
    return 0.1 + 0.05 * (i % 17)


def _build_seed(seed_dir, n_nodes):
    """Build the uniform store once; return its db path."""
    from muninn import HebbianMemory
    from muninn.config import MuninnConfig

    db_path = Path(seed_dir) / "uniform.db"
    config = MuninnConfig(
        db_path=str(db_path), max_nodes=n_nodes + 10, auto_backup=False
    )
    mem = HebbianMemory(config)
    ids = [
        mem.remember(f"uniform node {i} unique text {i}", category="bench")
        for i in range(n_nodes)
    ]
    for i, mid in enumerate(ids):
        for k in range(1, FORWARD + 1):
            mem.associate(mid, ids[(i + k) % n_nodes], strength=_strength(i + k))
    for i in range(0, n_nodes, 100):
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
    tmp = tempfile.mkdtemp(prefix="muninn-pragma-study-")
    db_path = Path(tmp) / "uniform.db"
    shutil.copy2(seed_db, db_path)
    return db_path


def _discard(db_path):
    """Remove one measurement directory (~20 MB a copy)."""
    shutil.rmtree(db_path.parent, ignore_errors=True)


def _open(db_path, n_nodes):
    from muninn import HebbianMemory
    from muninn.config import MuninnConfig

    config = MuninnConfig(
        db_path=str(db_path), max_nodes=n_nodes + 10, auto_backup=False
    )
    return HebbianMemory(config)


def _read_pragmas(conn):
    return {
        name: conn.execute(f"PRAGMA {name}").fetchone()[0]
        for name in ("cache_size", "mmap_size", "temp_store")
    }


def _read_pass(mem, ids):
    fp = 0
    for _ in range(READ_REPS):
        for mid in ids[::25]:  # 200 get_node at full scale
            node = mem.get_node(mid)
            fp += node.id if node else 0
        for mid in ids[::100]:  # 50 spreads, depth 2
            fp += len(mem.spread_activation([mid], depth=2))
        for _ in range(5):
            fp += mem.stats()["total_nodes"]
        for mid in ids[::50]:  # 100 association reads
            fp += len(mem.get_associations(mid, limit=100))
    return fp


def _aggregate_pass(mem, ids):
    fp = 0.0
    for _ in range(40):
        stats = mem.stats()
        fp += stats["total_nodes"] + stats["total_connections"]
    for mid in ids[::62][:80]:  # 80 spreads, depth 2
        for node_id, score in mem.spread_activation([mid], depth=2).items():
            fp += node_id + round(float(score), 6)
    return round(fp, 3)


_WORKLOADS = {"read_pass": _read_pass, "aggregate_pass": _aggregate_pass}


def _measure(seed_db, n_nodes, ids, variant):
    """One timed pass per workload on a fresh copy + open."""
    db_path = _fresh_copy(seed_db)
    try:
        mem = _open(db_path, n_nodes)
        try:
            conn = mem._get_conn()
            for sql in _VARIANT_SQL[variant]:
                conn.execute(sql)
            readback = _read_pragmas(conn)
            out = {"pragmas": readback}
            for name, fn in _WORKLOADS.items():
                passes = []
                for _ in range(2):  # pass 1 cold, pass 2 warm
                    start = time.perf_counter()
                    fp = fn(mem, ids)
                    passes.append(
                        {
                            "ms": round(
                                (time.perf_counter() - start) * 1000, 1
                            ),
                            "fingerprint": fp,
                        }
                    )
                out[name] = {"passes": passes}
            return out
        finally:
            mem.close()
    finally:
        _discard(db_path)


def _expected_readback(variant, baseline_found):
    expected = dict(baseline_found)
    if variant == "cache16":
        expected["cache_size"] = CACHE16_SIZE_KIB
    if variant in ("cache64", "all"):
        expected["cache_size"] = CACHE64_SIZE_KIB
    if variant in ("mmap", "all"):
        expected["mmap_size"] = MMAP_SIZE_BYTES
    if variant in ("temp", "all"):
        expected["temp_store"] = TEMP_STORE_MEMORY
    return expected


def run_pragma_study(nodes=NODES):
    seed_dir = tempfile.mkdtemp(prefix="muninn-pragma-seed-")
    try:
        seed_db = _build_seed(seed_dir, nodes)
        store_bytes = seed_db.stat().st_size
        conn = sqlite3.connect(str(seed_db))
        try:
            seed_edges = conn.execute(
                "SELECT COUNT(*) FROM hebbian_connections"
            ).fetchone()[0]
        finally:
            conn.close()

        # Defaults exactly as the package's open leaves them.
        probe_path = _fresh_copy(seed_db)
        try:
            mem = _open(probe_path, nodes)
            try:
                defaults_found = _read_pragmas(mem._get_conn())
            finally:
                mem.close()
        finally:
            _discard(probe_path)

        ids = list(range(1, nodes + 1))
        variants = {}
        fingerprints = set()
        for variant in VARIANTS:
            runs = [_measure(seed_db, nodes, ids, variant) for _ in range(3)]
            readbacks = [r["pragmas"] for r in runs]
            assert all(rb == readbacks[0] for rb in readbacks), variant
            assert readbacks[0] == _expected_readback(
                variant, defaults_found
            ), (variant, readbacks[0])
            entry = {"pragmas": readbacks[0]}
            for name in _WORKLOADS:
                fps = {
                    p["fingerprint"] for r in runs for p in r[name]["passes"]
                }
                assert len(fps) == 1, (variant, name, fps)
                fingerprints.add((name, fps.pop()))
                entry[name] = {}
                for idx, label in enumerate(("cold", "warm")):
                    times = [r[name]["passes"][idx]["ms"] for r in runs]
                    entry[name][label] = {
                        "times_ms": times,
                        "median_ms": round(statistics.median(times), 1),
                    }
            variants[variant] = entry

        fp_by_workload = {}
        for name, fp in fingerprints:
            fp_by_workload.setdefault(name, set()).add(fp)
        fingerprints_equal = all(
            len(fps) == 1 for fps in fp_by_workload.values()
        )

        base = variants["baseline"]
        deltas = {}
        for variant in VARIANTS[1:]:
            deltas[variant] = {}
            for name in _WORKLOADS:
                deltas[variant][name] = {}
                for label in ("cold", "warm"):
                    med = variants[variant][name][label]["median_ms"]
                    ref = base[name][label]["median_ms"]
                    deltas[variant][name][label] = {
                        "median_ms": med,
                        "vs_baseline_pct": round((med - ref) / ref * 100, 1)
                        if ref
                        else 0.0,
                    }

        return {
            "slice": "RM-066",
            "generated_at": datetime.now(UTC).isoformat(),
            "environment": _bench.environment_block(),
            "store": {
                "nodes": nodes,
                "directed_edges": seed_edges,
                "store_bytes": store_bytes,
                "seed": "RM-058 uniform store built once via the public "
                "API; every measurement starts from a byte copy of the "
                "closed, checkpointed seed file",
            },
            "defaults_as_found": defaults_found,
            "variant_settings": {
                "cache16_size_kib": CACHE16_SIZE_KIB,
                "cache64_size_kib": CACHE64_SIZE_KIB,
                "mmap_size_bytes": MMAP_SIZE_BYTES,
                "temp_store_memory": TEMP_STORE_MEMORY,
            },
            "variants": variants,
            "vs_baseline": deltas,
            "fingerprints_equal_across_variants": fingerprints_equal,
            "fingerprint_note": "every pass accumulates a fingerprint "
            "of everything it read; a pragma may change speed, never "
            "results -- the run asserts all fingerprints identical",
        }
    finally:
        shutil.rmtree(seed_dir, ignore_errors=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_suffix(".json"),
    )
    parser.add_argument("--nodes", type=int, default=NODES)
    args = parser.parse_args(argv)
    record = run_pragma_study(nodes=args.nodes)
    args.output.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
