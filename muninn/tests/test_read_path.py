"""RM-058 — Muninn read path pins.

The slice, proven by ``scripts/read_path.py`` at 100k edges:

- ``get_associations`` gained the covering index
  ``idx_conn_a_strength`` (memory_a_id, strength DESC,
  co_activation_count DESC, memory_b_id ASC, + the two
  remaining selected columns as trailing keys), so a limited
  read of a high-degree node is served in index order with
  no temp b-tree sort of its whole neighbourhood. Tables and
  columns are unchanged; the index is created by the schema
  script on every open, so pre-RM-058 stores gain it on
  their next open.
- ``spread_activation`` now reads each depth level with
  batched queries (chunks of 500 frontier ids) instead of
  one query per frontier node, examining candidates in
  exactly the per-node walk's order, so results — capped
  results included — are bit-for-bit the old walk's.

These tests pin the semantics against an independent
reference walk built on ``get_associations``, the index and
its query plan, the on-open upgrade, and the committed
gate record. No test depends on wall-clock timings.
"""

import importlib.util
import json
import sqlite3
from pathlib import Path

from muninn import HebbianMemory
from muninn.config import MuninnConfig

PKG = Path(__file__).parent.parent
SCRIPT = PKG / "scripts" / "read_path.py"
COMMITTED = PKG / "scripts" / "read_path.json"
ENV_KEYS = (
    "recorded_at",
    "machine",
    "system",
    "platform",
    "node",
    "cpu_count",
    "load_avg",
    "python_version",
    "sqlite_version",
)


def _load_script():
    spec = importlib.util.spec_from_file_location("muninn_read_path", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _strength(i):
    return 0.1 + 0.05 * (i % 17)


def _make(tmp_path, name="m.db", n_nodes=100000, **config_kw):
    return HebbianMemory(
        MuninnConfig(
            db_path=str(tmp_path / name),
            max_nodes=n_nodes,
            auto_backup=False,
            **config_kw,
        )
    )


def _ring(mem, n, forward):
    ids = [
        mem.remember(f"ring node {i} unique {i}", category="bench")
        for i in range(n)
    ]
    for i, mid in enumerate(ids):
        for k in range(1, forward + 1):
            mem.associate(mid, ids[(i + k) % n], strength=_strength(i + k))
    return ids


def _hub(mem, n_spokes):
    hub = mem.remember("hub node unique", category="bench")
    spokes = [
        mem.remember(f"spoke node {i} unique {i}", category="bench")
        for i in range(n_spokes)
    ]
    for i, spoke in enumerate(spokes):
        mem.associate(hub, spoke, strength=_strength(i))
    return hub, spokes


def _reference_spread(mem, seeds, *, depth, attenuation, min_strength, limit, cap):
    """The pre-RM-058 per-node walk, rebuilt on the public
    read API: frontier in id order, neighbours in id order,
    the cap counting candidates in that same order."""
    levels = dict.fromkeys(seeds, 1.0)
    frontier = dict(levels)
    examined = 0
    capped = False
    for _ in range(depth):
        nxt = {}
        for mid in sorted(frontier):
            if capped:
                break
            rows = mem.get_associations(mid, min_strength=min_strength, limit=10000)
            for row in sorted(rows, key=lambda r: r["memory_id"]):
                if examined >= cap:
                    capped = True
                    break
                examined += 1
                value = frontier[mid] * row["strength"] * attenuation
                if value > nxt.get(row["memory_id"], 0.0):
                    nxt[row["memory_id"]] = value
        for mid, value in nxt.items():
            if value > levels.get(mid, 0.0):
                levels[mid] = value
        frontier = nxt
        if capped or not frontier:
            break
    ranked = sorted(levels.items(), key=lambda kv: (-kv[1], kv[0]))
    return dict(ranked[:limit]), examined, capped


def _assert_spread_parity(mem, seeds, *, depth=2, attenuation=0.5,
                          min_strength=0.0, limit=1000):
    expected, examined, capped = _reference_spread(
        mem, seeds, depth=depth, attenuation=attenuation,
        min_strength=min_strength, limit=limit,
        cap=mem.config.max_spread_candidates,
    )
    result = mem.spread_activation(
        seeds, depth=depth, attenuation=attenuation,
        min_strength=min_strength, limit=limit,
    )
    assert result == expected
    stats = mem.last_spread_activation_stats
    assert stats["candidates_examined"] == examined
    assert stats["capped"] == capped
    assert stats["nodes_returned"] == len(expected)


# ─── the gate script and its committed record ───────────────────


def test_script_graphs_reach_100k_directed_rows():
    script = _load_script()
    assert 2 * script.UNIFORM_NODES * script.UNIFORM_FORWARD == 100000
    assert script.HUB_SPOKES == 10000
    assert script.OPS == (
        "uniform_get_associations",
        "uniform_spread_depth2",
        "uniform_spread_depth3",
        "hub_get_associations_limit100",
        "hub_get_associations_limit10000",
        "hub_spread_depth1",
        "hub_spread_depth2",
    )


def test_tiny_run_covers_every_op_with_exact_row_counts(tmp_path, monkeypatch):
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    script = _load_script()
    record = script.run_read_path(uniform_nodes=60, hub_spokes=40)
    assert record["package"] == "muninn"
    assert record["kind"] == "read_path"
    for key in ENV_KEYS:
        assert key in record["environment"], f"environment block missing {key}"
    for op in script.OPS:
        assert record["results_ms"][op] >= 0, f"missing op {op}"
    assert record["details"]["uniform"]["directed_rows"] == 2 * 60 * 10
    assert record["details"]["hub"]["directed_rows"] == 2 * 40
    plan = " ".join(record["details"]["get_associations_query_plan"])
    assert "idx_conn_a_strength" in plan
    assert "TEMP B-TREE" not in plan


def test_committed_record_is_the_100k_edge_run():
    record = json.loads(COMMITTED.read_text())
    assert record["package"] == "muninn"
    assert record["kind"] == "read_path"
    for key in ENV_KEYS:
        assert key in record["environment"], f"environment block missing {key}"
    assert record["details"]["uniform"]["n_nodes"] == 5000
    assert record["details"]["uniform"]["directed_rows"] == 100000
    assert record["details"]["hub"]["directed_rows"] == 20000
    script = _load_script()
    for op in script.OPS:
        assert isinstance(record["results_ms"][op], (int, float))
        assert record["results_ms"][op] >= 0
    plan = " ".join(record["details"]["get_associations_query_plan"])
    assert "idx_conn_a_strength" in plan
    assert "TEMP B-TREE" not in plan


# ─── the index ──────────────────────────────────────────────────


def test_fresh_store_carries_the_read_path_index(tmp_path):
    mem = _make(tmp_path)
    mem.close()
    conn = sqlite3.connect(str(tmp_path / "m.db"))
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index'"
        " AND name='idx_conn_a_strength'"
    ).fetchall()
    conn.close()
    assert rows == [("idx_conn_a_strength",)]


def test_get_associations_plan_uses_index_without_temp_btree(tmp_path):
    mem = _make(tmp_path)
    mem.close()
    conn = sqlite3.connect(str(tmp_path / "m.db"))
    plan = [
        r[3]
        for r in conn.execute(
            "EXPLAIN QUERY PLAN"
            " SELECT memory_b_id, strength, co_activation_count, consolidated,"
            " last_coactivated_at FROM hebbian_connections"
            " WHERE memory_a_id = ? AND strength >= ?"
            " ORDER BY strength DESC, co_activation_count DESC, memory_b_id ASC"
            " LIMIT ?",
            (1, 0.0, 100),
        )
    ]
    conn.close()
    joined = " ".join(plan)
    assert "idx_conn_a_strength" in joined
    assert "TEMP B-TREE" not in joined


def test_pre_slice_store_gains_the_index_on_open(tmp_path):
    mem = _make(tmp_path)
    a = mem.remember("first unique memory", category="bench")
    b = mem.remember("second unique memory", category="bench")
    mem.associate(a, b, strength=0.5)
    mem.close()
    # Simulate a pre-RM-058 store: the index does not exist.
    conn = sqlite3.connect(str(tmp_path / "m.db"))
    conn.execute("DROP INDEX idx_conn_a_strength")
    conn.commit()
    conn.close()
    mem = _make(tmp_path)
    rows = mem.get_associations(a)
    assert [r["memory_id"] for r in rows] == [b]
    mem.close()
    conn = sqlite3.connect(str(tmp_path / "m.db"))
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index'"
        " AND name='idx_conn_a_strength'"
    ).fetchall()
    conn.close()
    assert rows == [("idx_conn_a_strength",)]


def test_get_associations_limit_is_the_exact_top_of_the_full_list(tmp_path):
    mem = _make(tmp_path)
    hub, _spokes = _hub(mem, 300)
    full = mem.get_associations(hub, limit=10000)
    assert len(full) == 300
    assert mem.get_associations(hub, limit=100) == full[:100]
    assert mem.get_associations(hub) == full[:100]  # default limit
    keys = [
        (-r["strength"], -r["co_activation_count"], r["memory_id"]) for r in full
    ]
    assert keys == sorted(keys)
    mem.close()


# ─── spread parity with the per-node walk ───────────────────────


def test_spread_parity_on_ring_graph(tmp_path):
    mem = _make(tmp_path)
    ids = _ring(mem, 40, 4)
    for depth in (1, 2, 3):
        _assert_spread_parity(mem, [ids[7]], depth=depth)
    _assert_spread_parity(mem, [ids[7]], depth=3, min_strength=0.55)
    _assert_spread_parity(mem, [ids[7], ids[20]], depth=2, attenuation=0.25)
    _assert_spread_parity(mem, [ids[7]], depth=2, limit=5)
    mem.close()


def test_spread_parity_from_hub_across_chunk_boundary(tmp_path):
    mem = _make(tmp_path)
    hub, spokes = _hub(mem, 600)
    # Depth 2 from the hub: the second level's frontier is all
    # 600 spokes — wider than one 500-id query chunk.
    _assert_spread_parity(mem, [hub], depth=2)
    _assert_spread_parity(mem, [hub], depth=1)
    _assert_spread_parity(mem, spokes[:10], depth=2)
    mem.close()


def test_spread_cap_bites_identically_inside_the_second_chunk(tmp_path):
    # 600 seed spokes, depth 1: chunk one examines the first
    # 500 seeds' edges, the cap (550) bites inside chunk two.
    mem = _make(tmp_path, max_spread_candidates=550)
    hub, spokes = _hub(mem, 600)
    assert [r["memory_id"] for r in mem.get_associations(hub, limit=10000)]
    _assert_spread_parity(mem, spokes, depth=1)
    assert mem.last_spread_activation_stats["capped"] is True
    assert mem.last_spread_activation_stats["candidates_examined"] == 550
    mem.close()
