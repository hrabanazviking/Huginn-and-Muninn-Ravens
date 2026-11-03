"""RM-067 — Query-plan proofs for muninn.

``EXPLAIN QUERY PLAN`` pins for the hot queries of the
package (record ``docs/QUERY_PLANS.md``): every query
that must ride an index names that index in its plan,
so a schema change that drops the index fails this
suite loudly instead of silently slowing the store.
The deliberate full scans (``retrieve``'s filtered scan
and ``get_by_path`` — bounded by ``max_nodes`` by
design) are pinned as scans: adding an index there is
equally a deliberate change to this file. Plans are
read on a fresh raw connection to a store built
through the public API, the RM-058 pattern. The
sensitivity tests prove the pins can fail: dropping an
index in a scratch copy changes the plan exactly where
the pin asserts it.
"""

import sqlite3
from pathlib import Path

import pytest

from muninn import HebbianMemory, MuninnConfig


def _mem(tmp_path, **overrides):
    overrides.setdefault("db_path", str(tmp_path / "m.db"))
    return HebbianMemory(MuninnConfig(**overrides))


def _seeded(tmp_path):
    mem = _mem(tmp_path)
    ids = [
        mem.remember(f"plan probe memory {i} about ravens", category="probe")
        for i in range(20)
    ]
    mem.activate_batch(ids[:6])
    mem.close()
    conn = sqlite3.connect(str(tmp_path / "m.db"))
    return conn, ids


def _plan(conn, sql, params=()):
    rows = conn.execute("EXPLAIN QUERY PLAN " + sql, params).fetchall()
    return " | ".join(str(r[3]) for r in rows)


def _repo_root():
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "RAVENS_ROADMAP_2026-10-31.md").is_file():
            return parent
    return None


def test_get_node_plan_is_a_primary_key_search(tmp_path):
    conn, ids = _seeded(tmp_path)
    try:
        plan = _plan(conn, "SELECT * FROM nodes WHERE id = ?", (ids[0],))
        assert "SEARCH nodes USING INTEGER PRIMARY KEY" in plan
    finally:
        conn.close()


def test_get_associations_plan_rides_the_covering_index(tmp_path):
    conn, ids = _seeded(tmp_path)
    try:
        plan = _plan(
            conn,
            "SELECT memory_b_id, strength, co_activation_count, consolidated,"
            " last_coactivated_at FROM hebbian_connections"
            " WHERE memory_a_id = ? AND strength >= ?"
            " ORDER BY strength DESC, co_activation_count DESC, memory_b_id ASC"
            " LIMIT ?",
            (ids[0], 0.0, 100),
        )
        assert "idx_conn_a_strength" in plan
        assert "TEMP B-TREE" not in plan
    finally:
        conn.close()


def test_spread_chunk_plan_rides_the_covering_index(tmp_path):
    conn, ids = _seeded(tmp_path)
    try:
        plan = _plan(
            conn,
            "SELECT memory_a_id, memory_b_id, strength FROM hebbian_connections"
            " WHERE memory_a_id IN (?,?,?) AND strength >= ?"
            " ORDER BY memory_a_id ASC, memory_b_id ASC",
            (ids[0], ids[1], ids[2], 0.0),
        )
        assert "idx_conn_a_strength" in plan
        assert "SCAN hebbian_connections" not in plan
    finally:
        conn.close()


def test_pair_lookup_plan_is_a_primary_key_search(tmp_path):
    conn, ids = _seeded(tmp_path)
    try:
        plan = _plan(
            conn,
            "SELECT 1 FROM hebbian_connections"
            " WHERE memory_a_id = ? AND memory_b_id = ?",
            (ids[0], ids[1]),
        )
        assert "SEARCH hebbian_connections" in plan
        assert "sqlite_autoindex_hebbian_connections_1" in plan
    finally:
        conn.close()


def test_activation_plans_ride_their_indexes(tmp_path):
    conn, ids = _seeded(tmp_path)
    try:
        count_plan = _plan(
            conn,
            "SELECT COUNT(*) FROM activation_log WHERE memory_id = ?",
            (ids[0],),
        )
        assert "idx_activation_memory" in count_plan
        counter_plan = _plan(
            conn,
            "SELECT total_activations FROM node_activation WHERE memory_id = ?",
            (ids[0],),
        )
        assert "SEARCH node_activation USING INTEGER PRIMARY KEY" in counter_plan
        group_plan = _plan(
            conn,
            "SELECT memory_id, COUNT(*) AS c, MAX(activated_at) AS max_at"
            " FROM activation_log GROUP BY memory_id",
        )
        assert "USING INDEX idx_activation_memory" in group_plan
        assert "TEMP B-TREE FOR GROUP BY" not in group_plan
    finally:
        conn.close()


def test_forget_edges_plan_searches_both_directions(tmp_path):
    conn, ids = _seeded(tmp_path)
    try:
        plan = _plan(
            conn,
            "DELETE FROM hebbian_connections"
            " WHERE memory_a_id = ? OR memory_b_id = ?",
            (ids[0], ids[0]),
        )
        assert "sqlite_autoindex_hebbian_connections_1" in plan
        assert "idx_conn_b" in plan
    finally:
        conn.close()


def test_deliberate_scans_are_pinned_as_scans(tmp_path):
    conn, ids = _seeded(tmp_path)
    try:
        # retrieve's filtered scan and get_by_path ride no
        # index today — bounded by max_nodes by design
        # (docs/QUERY_PLANS.md). Pinning the scan means an
        # index added later updates this pin deliberately.
        retrieve_plan = _plan(
            conn, "SELECT * FROM nodes WHERE 1=1 AND category = ?", ("probe",)
        )
        assert retrieve_plan.startswith("SCAN nodes")
        path_plan = _plan(conn, "SELECT * FROM nodes WHERE path = ?", ("",))
        assert path_plan.startswith("SCAN nodes")
    finally:
        conn.close()


def test_dropping_the_covering_index_changes_the_plan(tmp_path):
    # Sensitivity: the get_associations pin above must be
    # able to fail. In a scratch copy with the index
    # dropped, the same query's plan no longer names it.
    conn, ids = _seeded(tmp_path)
    try:
        conn.execute("DROP INDEX idx_conn_a_strength")
        plan = _plan(
            conn,
            "SELECT memory_b_id, strength, co_activation_count, consolidated,"
            " last_coactivated_at FROM hebbian_connections"
            " WHERE memory_a_id = ? AND strength >= ?"
            " ORDER BY strength DESC, co_activation_count DESC, memory_b_id ASC"
            " LIMIT ?",
            (ids[0], 0.0, 100),
        )
        assert "idx_conn_a_strength" not in plan
    finally:
        conn.close()


def test_dropping_the_activation_index_changes_the_plan(tmp_path):
    conn, ids = _seeded(tmp_path)
    try:
        conn.execute("DROP INDEX idx_activation_memory")
        plan = _plan(
            conn,
            "SELECT COUNT(*) FROM activation_log WHERE memory_id = ?",
            (ids[0],),
        )
        assert "idx_activation_memory" not in plan
    finally:
        conn.close()


def test_record_doc_states_the_contract():
    root = _repo_root()
    if root is None:
        pytest.skip("not running inside a repo checkout")
    record = (root / "docs" / "QUERY_PLANS.md").read_text()
    assert "RM-067" in record
    assert "idx_conn_a_strength" in record
    assert "idx_activation_memory" in record
    assert "SCAN" in record
