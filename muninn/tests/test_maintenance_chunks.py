"""RM-064 -- Chunked maintenance pins for muninn.

Decay and consolidate no longer run as one full-store
transaction (record ``docs/MAINTENANCE_SCALE.md``): each
walks its tables in committed chunks of
``maintenance_chunk_size`` rows, so the atomicity is per
chunk -- every chunk fully applied or fully rolled back,
never half a chunk -- stated in the reports
(``atomicity`` / ``chunks`` / ``chunk_size``) and reported
live through the optional ``progress`` callback, which
fires after each committed chunk. The per-row maths is
the old road's, so the final store state is exactly the
full-store result at any chunk size: these tests prove
that parity against a raw-table reference, pin the exact
progress sequences, and pin the chunk boundary itself
(a callback failure and a mid-chunk statement failure
each leave the store at a boundary -- committed chunks
applied, the failed chunk rolled back whole, later
chunks untouched). No test depends on wall-clock timings.
"""

import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

from muninn import HebbianMemory, MuninnConfig
from muninn.errors import MuninnConfigurationError, MuninnStorageError


def _mem(tmp_path, **overrides):
    overrides.setdefault("db_path", str(tmp_path / "m.db"))
    overrides.setdefault("auto_backup", False)
    return HebbianMemory(MuninnConfig(**overrides))


def _repo_root():
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "RAVENS_ROADMAP_2026-10-31.md").is_file():
            return parent
    return None


def _seed(mem, n_nodes=6):
    """A deterministic small store: a ring of directed edges
    with varied strengths (some below the prune threshold
    after a halving, some above the consolidation
    threshold), plus activations so confidences exist."""
    ids = [mem.remember(f"chunk node {i}", category="bench") for i in range(n_nodes)]
    strengths = [0.95, 0.5, 0.015, 0.85, 0.3, 0.012, 0.7, 0.02, 0.6, 0.4, 0.9, 0.25]
    pairs = []
    for i in range(n_nodes):
        a, b = ids[i], ids[(i + 1) % n_nodes]
        mem.associate(a, b, strength=strengths[2 * i])
        pairs.append((a, b))
    for mid in ids[:3]:
        mem.activate(mid)
    return ids


def _edges(db_path):
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "SELECT rowid, memory_a_id, memory_b_id, strength, consolidated"
        " FROM hebbian_connections ORDER BY rowid"
    ).fetchall()
    conn.close()
    return rows


def _confidences(db_path):
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "SELECT memory_id, confidence FROM node_activation ORDER BY memory_id"
    ).fetchall()
    conn.close()
    return rows


def _expected_decay(edges, confidences, edge_factor, conf_factor, cons, prune):
    out = []
    for rowid, a, b, strength, consolidated in edges:
        strength = strength * edge_factor
        if strength < cons:
            consolidated = 0
        if strength < prune:
            continue
        out.append((rowid, a, b, strength, consolidated))
    confs = [(mid, c * conf_factor) for mid, c in confidences]
    return out, confs


def test_chunk_size_default_and_validation(tmp_path):
    mem = _mem(tmp_path)
    try:
        assert mem.config.maintenance_chunk_size == 1000
    finally:
        mem.close()
    for bad in (0, -1, "big", None):
        with pytest.raises(MuninnConfigurationError) as excinfo:
            MuninnConfig(db_path=str(tmp_path / "x.db"), maintenance_chunk_size=bad)
        assert "maintenance_chunk_size must be >= 1" in str(excinfo.value)


def test_decay_report_states_chunking(tmp_path):
    mem = _mem(tmp_path, maintenance_chunk_size=4)
    try:
        _seed(mem)
        report = mem.decay(days=30.0)
        assert report["atomicity"] == "per_chunk"
        assert report["chunk_size"] == 4
        assert report["chunks"] >= 2  # edges and confidences both chunk
        assert report["edges_decayed"] == 12
        assert report["confidences_decayed"] == len(_confidences(tmp_path / "m.db"))
    finally:
        mem.close()


@pytest.mark.parametrize("chunk_size", [1, 2, 7, 1000])
def test_decay_parity_across_chunk_sizes(tmp_path, chunk_size):
    mem = _mem(tmp_path, maintenance_chunk_size=chunk_size)
    try:
        _seed(mem)
        before_edges = _edges(tmp_path / "m.db")
        before_confs = _confidences(tmp_path / "m.db")
        report = mem.decay(days=30.0)
        expected_edges, expected_confs = _expected_decay(
            before_edges,
            before_confs,
            report["edge_factor"],
            report["confidence_factor"],
            mem.config.consolidation_threshold,
            mem.config.prune_threshold,
        )
        assert _edges(tmp_path / "m.db") == expected_edges
        assert _confidences(tmp_path / "m.db") == expected_confs
        assert report["edges_pruned"] == len(before_edges) - len(expected_edges)
    finally:
        mem.close()


def test_decay_progress_events_exact(tmp_path):
    mem = _mem(tmp_path, maintenance_chunk_size=5)
    try:
        _seed(mem)
        events = []
        mem.decay(days=1.0, progress=events.append)
        confs = _confidences(tmp_path / "m.db")
        edge_events = [e for e in events if e["phase"] == "edges"]
        conf_events = [e for e in events if e["phase"] == "confidences"]
        assert all(e["operation"] == "decay" for e in events)
        assert [e["chunk"] for e in edge_events] == list(
            range(1, len(edge_events) + 1)
        )
        assert edge_events[-1]["processed"] == edge_events[-1]["total"] == 12
        assert conf_events[-1]["processed"] == conf_events[-1]["total"] == len(confs)
        assert all(
            set(e) == {"operation", "phase", "chunk", "processed", "total"}
            for e in events
        )
        # Chunk sizes: full chunks first, the remainder last.
        processed = [e["processed"] for e in edge_events]
        deltas = [processed[0]] + [
            b - a for a, b in zip(processed, processed[1:], strict=False)
        ]
        assert deltas == [5, 5, 2]
    finally:
        mem.close()


def test_decay_callback_failure_leaves_chunk_boundary(tmp_path):
    mem = _mem(tmp_path, maintenance_chunk_size=2)
    try:
        _seed(mem)
        before = _edges(tmp_path / "m.db")
        calls = []

        def failing(event):
            calls.append(event)
            if event["phase"] == "edges" and event["chunk"] == 2:
                raise RuntimeError("reporter died")

        with pytest.raises(RuntimeError, match="reporter died"):
            mem.decay(days=30.0, progress=failing)
        after = _edges(tmp_path / "m.db")
        # Chunks 1-2 (rowids in order, 4 rows) applied; the
        # rest of the store is byte-for-byte the old state.
        factor = 0.5 ** (30.0 / mem.config.decay_half_life_days)
        # Prune/unmark inside committed chunks mirrors the
        # full reference for those rows.
        exp_edges, _ = _expected_decay(
            before[:4],
            [],
            factor,
            1.0,
            mem.config.consolidation_threshold,
            mem.config.prune_threshold,
        )
        assert [r for r in after if r[0] in {x[0] for x in exp_edges}] == exp_edges
        untouched = [r for r in after if r[0] > before[3][0]]
        assert untouched == before[4:]
        assert len(calls) == 2
        # The store is consistent and a fresh run completes.
        report = mem.decay(days=0.0)
        assert report["edges_decayed"] == len(_edges(tmp_path / "m.db"))
    finally:
        mem.close()


def test_decay_failed_chunk_rolls_back_whole(tmp_path):
    mem = _mem(tmp_path, maintenance_chunk_size=2)
    db = tmp_path / "m.db"
    try:
        _seed(mem)
        before = _edges(db)
        target_rowid = before[2][0]  # first row of chunk 2
        conn = sqlite3.connect(str(db))
        conn.execute(
            "CREATE TRIGGER rm064_boom BEFORE UPDATE ON hebbian_connections"
            f" WHEN NEW.rowid = {int(target_rowid)}"
            " BEGIN SELECT RAISE(ABORT, 'rm064 boom'); END"
        )
        conn.commit()
        conn.close()
        with pytest.raises(MuninnStorageError):
            mem.decay(days=30.0)
        after = _edges(db)
        factor = 0.5 ** (30.0 / mem.config.decay_half_life_days)
        exp_first, _ = _expected_decay(
            before[:2],
            [],
            factor,
            1.0,
            mem.config.consolidation_threshold,
            mem.config.prune_threshold,
        )
        # Chunk 1 committed; chunk 2 (incl. its first row,
        # updated in the same statement batch) rolled back
        # whole; later chunks never ran.
        assert [r for r in after if r[0] in {x[0] for x in exp_first}] == exp_first
        assert [r for r in after if r[0] >= target_rowid] == before[2:]
    finally:
        mem.close()


def test_consolidate_parity_progress_and_report(tmp_path):
    mem = _mem(tmp_path, maintenance_chunk_size=5)
    try:
        _seed(mem)
        # Mixed starting flags: mark two weak edges, unmark
        # is exercised against the strong ones' old flags.
        conn = sqlite3.connect(str(tmp_path / "m.db"))
        conn.execute("UPDATE hebbian_connections SET consolidated = 1 WHERE strength < 0.5")
        conn.commit()
        conn.close()
        events = []
        report = mem.consolidate(progress=events.append)
        assert report["atomicity"] == "per_chunk"
        assert report["chunk_size"] == 5
        assert report["chunks"] == 3  # 12 edges in chunks of 5
        assert "heal" in report
        rows = _edges(tmp_path / "m.db")
        threshold = mem.config.consolidation_threshold
        assert all(
            consolidated == (1 if strength >= threshold else 0)
            for _, _, _, strength, consolidated in rows
        )
        assert report["total_consolidated"] == sum(r[4] for r in rows)
        assert [e["processed"] for e in events] == [5, 10, 12]
        assert all(e["operation"] == "consolidate" for e in events)
    finally:
        mem.close()


def test_consolidate_callback_failure_leaves_boundary(tmp_path):
    mem = _mem(tmp_path, maintenance_chunk_size=4)
    try:
        _seed(mem)
        before = _edges(tmp_path / "m.db")

        def failing(event):
            if event["chunk"] == 1:
                raise RuntimeError("stop after one")

        with pytest.raises(RuntimeError, match="stop after one"):
            mem.consolidate(progress=failing)
        after = {r[0]: r for r in _edges(tmp_path / "m.db")}
        threshold = mem.config.consolidation_threshold
        for row in before[:4]:
            want = 1 if row[3] >= threshold else 0
            assert after[row[0]][4] == want
        for row in before[4:]:
            assert after[row[0]] == row
    finally:
        mem.close()


def test_decay_wall_clock_report_carries_chunk_fields(tmp_path):
    mem = _mem(tmp_path, maintenance_chunk_size=3)
    try:
        _seed(mem)
        report = mem.decay_wall_clock()
        assert report["first_run"] is True
        assert report["chunk_size"] == 3
        assert report["atomicity"] == "per_chunk"
        assert report["chunks"] >= 1
    finally:
        mem.close()


def test_empty_store_maintenance(tmp_path):
    mem = _mem(tmp_path, maintenance_chunk_size=2)
    try:
        events = []
        report = mem.decay(days=5.0, progress=events.append)
        assert report["edges_decayed"] == 0
        assert report["chunks"] == 0
        assert events == []
        report = mem.consolidate(progress=events.append)
        assert report["chunks"] == 0
        assert report["total_consolidated"] == 0
    finally:
        mem.close()


def test_record_doc_states_per_chunk_atomicity():
    root = _repo_root()
    assert root is not None
    text = (root / "docs" / "MAINTENANCE_SCALE.md").read_text()
    assert "RM-064" in text
    assert "per chunk" in text.lower() or "per-chunk" in text.lower()


def test_gate_script_and_committed_record():
    root = _repo_root()
    assert root is not None
    script = root / "muninn" / "scripts" / "maintenance_scale.py"
    spec = importlib.util.spec_from_file_location("maintenance_scale", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert hasattr(module, "run_maintenance_scale")
    record = json.loads(
        (root / "muninn" / "scripts" / "maintenance_scale.json").read_text()
    )
    assert record["slice"] == "RM-064"
    assert record["store"]["directed_edges"] == 100000
    assert record["decay"]["parity"] is True
    assert record["consolidate"]["parity"] is True
    assert record["decay"]["chunks"] > 1
