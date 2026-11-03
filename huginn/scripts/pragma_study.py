"""Huginn connection pragmas study, local backend -- RM-066 gate.

Run: python scripts/pragma_study.py [--output pragma_study.json]

What it measures (roadmap RM-066: ``cache_size``,
``mmap_size``, ``temp_store`` measured per package;
defaults changed only on evidence, recorded per
pragma): the twin of ``muninn/scripts/pragma_study.py``
for Huginn's local backend, whose ``_db`` machinery is
Muninn's twin.

- The local backend's open road sets exactly four
  pragmas today (``busy_timeout``, ``journal_mode=WAL``,
  ``synchronous=FULL``, ``foreign_keys=ON``). The three
  studied pragmas are never set, so SQLite's compiled
  defaults apply; the gate reads them back from a
  freshly opened store and records them as found
  (``defaults_as_found``). The Qdrant backend has no
  local connection and is out of scope, stated here.
- The seed is 5,000 distinct documents (the RM-061
  distinct-corpus formula: a pure function of the
  index, 20-79 tokens per document over a 1,024-term
  vocabulary) stored through the public ``upsert_memory``
  API, checkpointed, and copied byte-for-byte for every
  measurement.
- Variants: ``baseline`` (connection exactly as the
  backend opens it), ``cache16`` (``PRAGMA cache_size=
  -16384`` -- a 16 MiB page cache), ``cache64``
  (``PRAGMA cache_size=-65536`` -- 64 MiB, several
  times the whole store), ``mmap`` (``PRAGMA mmap_size=
  268435456``), ``temp`` (``PRAGMA temp_store=MEMORY``),
  and ``all`` (cache64 + mmap + temp together). Each
  variant is
  applied to the live connection the backend opened
  (the study's one reach inside, stated here: pragmas
  are per-connection, so the study must set them on the
  connection the backend owns) and read back before any
  timing is quoted -- a variant whose readback is not
  what it set fails the run.
- Each measurement is a fresh byte copy + fresh open +
  TWO timed passes per workload: pass 1 with the SQLite
  page cache cold, pass 2 warm on the same connection
  (the OS/tmpfs cache cannot be dropped from here and
  the record says so). Median of three measurements
  per variant per workload per temperature.
- Workloads (public facade API only): ``search_pass``
  -- the three RM-061 distinct-corpus queries, 2 rounds
  of ``search`` (limit 10); ``get_pass`` -- 500 document
  ``get`` calls on a fixed stride. Every pass
  accumulates a fingerprint of everything it read;
  every fingerprint in the run must be identical or
  the run fails -- a pragma may change speed, never
  results.
- Name discipline: this slice's ``cache_size`` is
  SQLite's ``PRAGMA cache_size`` (the connection's page
  cache). It is NOT RM-063's ``cache_size`` config field
  (the per-object document ``get`` warm cache); the two
  share a name and nothing else.

Class: BENCH. No package code changes in this slice
unless the record's verdict demands one; the script
runs unchanged on the RM-065 tree and produces the
same record shape. Numbers on a loaded machine are
indicative, not absolutes -- the environment block
says so. Stores live on tmpfs; local backend only,
nothing external -- a live Qdrant round-trip stays
NOT PROVEN.
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

DOCS = 5000
DISTINCT_VOCAB = 1024
QUERIES = (
    "term100 term200 term37",
    "term5 term999 term300",
    "term248 term17 term800",
)
SEARCH_ROUNDS = 2
GET_CALLS = 500
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


def distinct_text(i):
    """One distinct-corpus document (the RM-061 formula):
    a pure function of the index -- length 20-79 tokens,
    quadratic term formula -- so documents genuinely
    differ from each other."""
    length = 20 + (i * 13) % 60
    return " ".join(
        f"term{(i * 7919 + j * 104729 + j * j * 31 + i * j * 7) % DISTINCT_VOCAB}"
        for j in range(length)
    )


def _build_seed(seed_dir, n_docs):
    """Build the distinct-document store once via the
    public API; return (db_path, ids)."""
    from huginn import HuginnConfig, HuginnMemory

    db_path = Path(seed_dir) / "pragma.db"
    config = HuginnConfig(
        backend="local", local_db_path=str(db_path), auto_backup=False
    )
    mem = HuginnMemory(config)
    ids = [
        mem.upsert_memory(distinct_text(i), category=f"cat{i % 10}")
        for i in range(n_docs)
    ]
    mem.close()
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.commit()
    finally:
        conn.close()
    return db_path, ids


def _fresh_copy(seed_db):
    tmp = tempfile.mkdtemp(prefix="huginn-pragma-study-")
    db_path = Path(tmp) / "pragma.db"
    shutil.copy2(seed_db, db_path)
    return db_path


def _discard(db_path):
    """Remove one measurement directory."""
    shutil.rmtree(db_path.parent, ignore_errors=True)


def _open(db_path):
    from huginn import HuginnConfig, HuginnMemory

    config = HuginnConfig(
        backend="local", local_db_path=str(db_path), auto_backup=False
    )
    return HuginnMemory(config)


def _conn(mem):
    return mem._ensure_backend()._ensure_open()


def _read_pragmas(conn):
    return {
        name: conn.execute(f"PRAGMA {name}").fetchone()[0]
        for name in ("cache_size", "mmap_size", "temp_store")
    }


def _search_pass(mem, ids):
    fp = 0.0
    for _ in range(SEARCH_ROUNDS):
        for query in QUERIES:
            for doc in mem.search(query, limit=10):
                fp += doc["id"] + round(float(doc["score"]), 6)
    return round(fp, 3)


def _get_pass(mem, ids):
    fp = 0
    for i in range(GET_CALLS):
        doc = mem.get(ids[(i * 37) % len(ids)])
        fp += doc["id"] if doc else 0
    return fp


_WORKLOADS = {"search_pass": _search_pass, "get_pass": _get_pass}


def _measure(seed_db, ids, variant):
    """One timed pass per workload on a fresh copy + open."""
    db_path = _fresh_copy(seed_db)
    try:
        mem = _open(db_path)
        try:
            conn = _conn(mem)
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


def run_pragma_study(docs=DOCS):
    seed_dir = tempfile.mkdtemp(prefix="huginn-pragma-seed-")
    try:
        seed_db, ids = _build_seed(seed_dir, docs)
        store_bytes = seed_db.stat().st_size
        conn = sqlite3.connect(str(seed_db))
        try:
            stored_docs = conn.execute(
                "SELECT COUNT(*) FROM documents"
            ).fetchone()[0]
        finally:
            conn.close()

        # Defaults exactly as the backend's open leaves them.
        probe_path = _fresh_copy(seed_db)
        try:
            mem = _open(probe_path)
            try:
                defaults_found = _read_pragmas(_conn(mem))
            finally:
                mem.close()
        finally:
            _discard(probe_path)

        variants = {}
        fingerprints = set()
        for variant in VARIANTS:
            runs = [_measure(seed_db, ids, variant) for _ in range(3)]
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
                "documents": stored_docs,
                "store_bytes": store_bytes,
                "seed": f"{stored_docs} distinct documents (RM-061 "
                "distinct-corpus formula) stored via the public "
                "upsert API; every measurement starts from a byte "
                "copy of the closed, checkpointed seed file",
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
    parser.add_argument("--docs", type=int, default=DOCS)
    args = parser.parse_args(argv)
    record = run_pragma_study(docs=args.docs)
    args.output.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
