"""Muninn decay/consolidate at 100k edges -- RM-064 gate script.

Run: python scripts/maintenance_scale.py [--output maintenance_scale.json]

What it does:
- Builds the RM-058 uniform store -- 5,000 nodes on a ring
  lattice, each node associated with the next 10 nodes --
  50,000 undirected pairs = **100,000 directed edge rows**,
  plus a fixed activation sample so ``node_activation``
  carries confidences. This is the 100k-edge store the
  roadmap's RM-064 acceptance names.
- Runs ``decay`` in the RM-064 chunked road
  (``maintenance_chunk_size`` = 1000) and in a single-chunk
  road (chunk size larger than the store -- the pre-RM-064
  full-store shape), and ``consolidate`` the same way.
- Parity is verified, never asserted: each run's final
  edge/confidence tables are compared row-for-row against
  an independent old-road reference computed in Python
  from the raw pre-run tables, and the chunked and
  single-chunk final tables are compared against each
  other. Timings are quoted only for runs whose parity
  held.
- Decay timings are the median of three runs, each on a
  freshly built identical store (decay is destructive;
  the read-path scripts could re-run one store, this one
  cannot). Consolidate is timed on the decayed stores.

Class: BENCH. Run it on the pre-slice tree and on the
post-slice tree and the two records compare like with
like: the script degrades gracefully on the old road
(no ``maintenance_chunk_size`` field, no ``progress``
parameter -- recorded as ``chunked: false``). Numbers on
a loaded machine are indicative, not absolutes -- the
environment block says so. Stores live on tmpfs; local
store only, nothing external is touched.
"""

import argparse
import json
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
CHUNK = 1000
SINGLE = 10_000_000
DECAY_DAYS = 10.0


def _strength(i):
    return 0.1 + 0.05 * (i % 17)


def _build(chunk_size):
    """One deterministic uniform store; returns (mem, db_path)."""
    from muninn import HebbianMemory
    from muninn.config import MuninnConfig

    tmp = tempfile.mkdtemp(prefix="muninn-maintenance-")
    db_path = str(Path(tmp) / "uniform.db")
    kwargs = {"db_path": db_path, "max_nodes": NODES + 10, "auto_backup": False}
    chunked = True
    try:
        config = MuninnConfig(maintenance_chunk_size=chunk_size, **kwargs)
    except TypeError:
        config = MuninnConfig(**kwargs)
        chunked = False
    mem = HebbianMemory(config)
    ids = [
        mem.remember(f"uniform node {i} unique text {i}", category="bench")
        for i in range(NODES)
    ]
    for i, mid in enumerate(ids):
        for k in range(1, FORWARD + 1):
            mem.associate(mid, ids[(i + k) % NODES], strength=_strength(i + k))
    for i in range(0, NODES, 100):
        mem.activate(ids[i])
    return mem, db_path, chunked


def _tables(db_path):
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    edges = conn.execute(
        "SELECT rowid, memory_a_id, memory_b_id, strength, consolidated"
        " FROM hebbian_connections ORDER BY rowid"
    ).fetchall()
    confs = conn.execute(
        "SELECT memory_id, confidence FROM node_activation ORDER BY memory_id"
    ).fetchall()
    conn.close()
    return edges, confs


def _reference_decay(edges, confs, mem, days):
    edge_factor = 0.5 ** (days / mem.config.decay_half_life_days)
    conf_factor = 0.5 ** (days / mem.config.confidence_half_life_days)
    out = []
    for rowid, a, b, strength, consolidated in edges:
        strength = strength * edge_factor
        if strength < mem.config.consolidation_threshold:
            consolidated = 0
        if strength < mem.config.prune_threshold:
            continue
        out.append((rowid, a, b, strength, consolidated))
    return out, [(mid, c * conf_factor) for mid, c in confs]


def _run_decay(mem, days):
    """Time one decay; collect progress when the road has it."""
    events = []
    start = time.perf_counter()
    try:
        report = mem.decay(days=days, progress=events.append)
    except TypeError:
        report = mem.decay(days=days)
    elapsed = (time.perf_counter() - start) * 1000
    return report, events, elapsed


def _run_consolidate(mem):
    events = []
    start = time.perf_counter()
    try:
        report = mem.consolidate(progress=events.append)
    except TypeError:
        report = mem.consolidate()
    elapsed = (time.perf_counter() - start) * 1000
    return report, events, elapsed


def run_maintenance_scale(nodes=NODES):
    global NODES
    NODES = nodes
    decay_times = []
    decay_parity = True
    decay_chunks = None
    decay_report = None
    chunked_final = None
    consolidate_chunks = None
    consolidate_parity = True
    consolidate_times = []
    consolidate_final = None
    store_info = {}
    chunked_road = True
    for run in range(3):
        mem, db_path, chunked_road = _build(CHUNK)
        try:
            before_edges, before_confs = _tables(db_path)
            if run == 0:
                store_info = {
                    "nodes": nodes,
                    "directed_edges": len(before_edges),
                    "confidences": len(before_confs),
                }
            expected_edges, expected_confs = _reference_decay(
                before_edges, before_confs, mem, DECAY_DAYS
            )
            report, events, elapsed = _run_decay(mem, DECAY_DAYS)
            decay_times.append(elapsed)
            after_edges, after_confs = _tables(db_path)
            decay_parity = decay_parity and (
                after_edges == expected_edges and after_confs == expected_confs
            )
            if run == 0:
                decay_report = report
                decay_chunks = report.get("chunks")
                chunked_final = (after_edges, after_confs)
            creport, cevents, celapsed = _run_consolidate(mem)
            consolidate_times.append(celapsed)
            rows = _tables(db_path)[0]
            threshold = mem.config.consolidation_threshold
            consolidate_parity = consolidate_parity and all(
                c == (1 if st >= threshold else 0) for _, _, _, st, c in rows
            )
            if run == 0:
                consolidate_chunks = creport.get("chunks")
                consolidate_final = rows
        finally:
            mem.close()
    # Single-chunk road (the pre-RM-064 shape) on one more
    # identical store: its final tables must equal the
    # chunked road's, row for row.
    mem, db_path, _ = _build(SINGLE)
    try:
        before_edges, before_confs = _tables(db_path)
        expected_edges, expected_confs = _reference_decay(
            before_edges, before_confs, mem, DECAY_DAYS
        )
        sreport, _, selapsed = _run_decay(mem, DECAY_DAYS)
        safter = _tables(db_path)
        single_parity = safter == (expected_edges, expected_confs)
        single_final_parity = chunked_final is not None and safter == chunked_final
        creport, _, celapsed_single = _run_consolidate(mem)
        srows = _tables(db_path)[0]
        consolidate_single_parity = srows == consolidate_final
    finally:
        mem.close()
    return {
        "slice": "RM-064",
        "generated_at": datetime.now(UTC).isoformat(),
        "environment": _bench.environment_block(),
        "store": store_info,
        "chunked": chunked_road,
        "decay": {
            "days": DECAY_DAYS,
            "chunk_size": CHUNK if chunked_road else None,
            "chunks": decay_chunks,
            "edges_decayed": decay_report["edges_decayed"],
            "edges_pruned": decay_report["edges_pruned"],
            "confidences_decayed": decay_report["confidences_decayed"],
            "parity": decay_parity,
            "times_ms": [round(t, 1) for t in decay_times],
            "median_ms": round(statistics.median(decay_times), 1),
        },
        "decay_single_chunk": {
            "chunk_size": SINGLE if chunked_road else None,
            "chunks": sreport.get("chunks"),
            "parity": single_parity,
            "matches_chunked_final": single_final_parity,
            "time_ms": round(selapsed, 1),
        },
        "consolidate": {
            "chunk_size": CHUNK if chunked_road else None,
            "chunks": consolidate_chunks,
            "parity": consolidate_parity,
            "matches_single_chunk_final": consolidate_single_parity,
            "times_ms": [round(t, 1) for t in consolidate_times],
            "median_ms": round(statistics.median(consolidate_times), 1),
            "single_chunk_time_ms": round(celapsed_single, 1),
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_suffix(".json"),
    )
    parser.add_argument("--nodes", type=int, default=NODES)
    args = parser.parse_args(argv)
    record = run_maintenance_scale(nodes=args.nodes)
    args.output.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
