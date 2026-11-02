"""RM-013 — Idempotency matrix for muninn (one test per matrix row).

The matrix itself lives in ``docs/API_REFERENCE.md`` (Part 3).
Classes, per the matrix definitions:

- **I** — idempotent: an identical repeat leaves the logical store
  state unchanged (write timestamps excluded where a row says so)
  and returns an equal result (a state-changing row may return its
  "already done" signal on the repeat — e.g. ``forget`` True→False).
- **R** — safely re-runnable: a repeat is safe (no error, no
  duplication, no corruption) but applies its defined effect again.
- **N** — intentionally not idempotent: every call is a new event
  by design; a blind retry double-applies.

Every public ``HebbianMemory`` method has exactly one row here;
``Muninn`` (the facade) inherits them all unchanged (row M-01b).
"""

import pytest

from muninn import HebbianMemory, MemoryNode, Muninn
from muninn.config import MuninnConfig


def _mem(tmp_path, name="m.db", **overrides):
    return HebbianMemory(MuninnConfig(db_path=str(tmp_path / name), **overrides))


def _pair(m):
    a = m.remember("alpha raven memory", importance=7)
    b = m.remember("beta raven memory", importance=6)
    return a, b


# ─── lifecycle rows ───────────────────────────────────────────────


def test_row_m01_construction_and_reopen(tmp_path):
    db = str(tmp_path / "m.db")
    m = HebbianMemory(MuninnConfig(db_path=db))
    nid = m.remember("persistent raven memory")
    before = m.stats()
    m.close()
    for _ in range(2):  # reopening is safely re-runnable, state intact
        m2 = HebbianMemory(MuninnConfig(db_path=db))
        try:
            assert m2.get_node(nid).content == "persistent raven memory"
            assert m2.stats() == before
            assert m2.health()["recovered_from_backup"] is False
        finally:
            m2.close()


def test_row_m01b_facade_inherits_the_matrix(tmp_path):
    facade = Muninn(data_path=str(tmp_path))  # a directory, ancestor shape
    try:
        nid = facade.remember("facade raven memory")
        assert facade.remember("facade raven memory") == nid
        assert facade.activate(nid) == 1
        assert facade.activate(nid) == 2  # row M-04 holds through the facade
    finally:
        facade.close()


def test_row_m02_close_is_idempotent(tmp_path):
    m = _mem(tmp_path)
    m.remember("closable raven memory")
    m.close()
    m.close()  # second and third closes are no-ops, never errors
    m.close()


def test_row_m03_backup_is_safely_rerunnable(tmp_path):
    m = _mem(tmp_path)
    m.remember("backed up raven memory")
    try:
        first = m.backup()
        stats_after_first = m.stats()
        second = m.backup()
        assert first is not None and second == first  # newest generation path
        assert m.stats() == stats_after_first  # the store itself never changes
    finally:
        m.close()


# ─── intentionally-not rows: every call is a new event ────────────


def test_row_m04_activate_is_intentionally_not_idempotent(tmp_path):
    m = _mem(tmp_path)
    a, _ = _pair(m)
    try:
        assert m.activate(a) == 1
        assert m.activate(a) == 2  # a retry is a SECOND activation, by design
        assert m.activation_count(a) == 2
    finally:
        m.close()


def test_row_m05_activate_batch_is_intentionally_not_idempotent(tmp_path):
    m = _mem(tmp_path)
    a, b = _pair(m)
    try:
        first = m.activate_batch([a, b])
        assert first["connections_created"] == 1
        strength_after_first = m.get_associations(a)[0]["strength"]
        second = m.activate_batch([a, b])
        assert second["connections_created"] == 0
        assert second["connections_strengthened"] == 1
        # …but the wiring strengthened again and both ids logged again:
        assert m.get_associations(a)[0]["strength"] > strength_after_first
        assert m.activation_count(a) == 2
    finally:
        m.close()


def test_row_m06_associate_is_intentionally_not_idempotent(tmp_path):
    m = _mem(tmp_path)
    a, b = _pair(m)
    try:
        # Explicit-strength form: the strength value is pinned, but the
        # co-activation count still advances — a retry double-counts.
        assert m.associate(a, b, strength=0.5) == 0.5
        assert m.associate(a, b, strength=0.5) == 0.5
        assoc = m.get_associations(a)[0]
        assert assoc["strength"] == 0.5
        assert assoc["co_activation_count"] == 2
        # Default (delta) form: strength itself climbs toward 1.0.
        e = m.remember("gamma raven memory")
        f = m.remember("delta raven memory")
        first = m.associate(e, f)
        second = m.associate(e, f)
        assert 0.0 < first < second < 1.0
    finally:
        m.close()


def test_row_m14_retrieve_touch_is_intentionally_not_idempotent(tmp_path):
    m = _mem(tmp_path)
    a, _ = _pair(m)
    try:
        before = m.activation_count(a)
        got = m.retrieve(query="alpha", touch=True)
        assert [n.id for n in got] == [a]
        assert m.activation_count(a) == before + 1
        m.retrieve(query="alpha", touch=True)  # each touch reinforces again
        assert m.activation_count(a) == before + 2
    finally:
        m.close()


# ─── pure-read rows: idempotent, and the store provably unmoved ───


def _assert_pure(m, call):
    """Call twice: equal results, and no store counter moved."""
    stats_before = m.stats()
    first = call()
    second = call()
    assert first == second
    assert m.stats() == stats_before
    return first


def test_row_m07_get_associations_is_a_pure_idempotent_read(tmp_path):
    m = _mem(tmp_path)
    a, b = _pair(m)
    m.associate(a, b, strength=0.5)
    try:
        rows = _assert_pure(m, lambda: m.get_associations(a))
        assert rows[0]["memory_id"] == b
    finally:
        m.close()


def test_row_m08_activation_count_is_a_pure_idempotent_read(tmp_path):
    m = _mem(tmp_path)
    a, _ = _pair(m)
    m.activate(a)
    try:
        assert _assert_pure(m, lambda: m.activation_count(a)) == 1
    finally:
        m.close()


def test_row_m09_spread_activation_is_a_pure_idempotent_read(tmp_path):
    m = _mem(tmp_path)
    a, b = _pair(m)
    m.associate(a, b, strength=0.5)
    try:
        spread = _assert_pure(m, lambda: m.spread_activation([a]))
        assert spread[a] == 1.0 and b in spread
    finally:
        m.close()


def test_row_m12_get_node_is_a_pure_idempotent_read(tmp_path):
    m = _mem(tmp_path)
    a, _ = _pair(m)
    try:
        node = _assert_pure(m, lambda: m.get_node(a))
        assert node.content == "alpha raven memory"
        assert m.get_node(999999) is None
    finally:
        m.close()


def test_row_m13_retrieve_without_touch_is_a_pure_idempotent_read(tmp_path):
    m = _mem(tmp_path)
    a, _ = _pair(m)
    try:
        got = _assert_pure(m, lambda: [n.id for n in m.retrieve(query="raven")])
        assert a in got
        assert m.activation_count(a) == 0  # the pure read reinforced nothing
    finally:
        m.close()


def test_row_m15_get_by_path_is_a_pure_idempotent_read(tmp_path):
    m = _mem(tmp_path)
    nid = m.remember("pathed raven memory", path="lore/ravens")
    try:
        got = _assert_pure(m, lambda: [n.id for n in m.get_by_path("lore/ravens")])
        assert got == [nid]
    finally:
        m.close()


def test_row_m16_get_children_is_a_pure_idempotent_read(tmp_path):
    m = _mem(tmp_path)
    nid = m.remember("child raven memory", path="lore/ravens")
    try:
        def children():
            return {k: [n.id for n in v] for k, v in m.get_children("lore").items()}

        got = _assert_pure(m, children)
        assert got == {"lore/ravens": [nid]}
    finally:
        m.close()


def test_row_m21_get_tree_structure_is_a_pure_idempotent_read(tmp_path):
    m = _mem(tmp_path)
    m.remember("tree raven memory", path="lore/ravens")
    try:
        tree = _assert_pure(m, m.get_tree_structure)
        assert tree["lore"]["ravens"]["_nodes"] == 1
    finally:
        m.close()


def test_row_m25_health_is_a_pure_idempotent_read(tmp_path):
    m = _mem(tmp_path)
    _pair(m)
    try:
        health = _assert_pure(m, m.health)
        assert health["status"] == "healthy" and health["nodes"] == 2
    finally:
        m.close()


def test_row_m26_stats_and_get_stats_are_pure_idempotent_reads(tmp_path):
    m = _mem(tmp_path)
    _pair(m)
    try:
        stats = _assert_pure(m, m.stats)
        assert stats["total_nodes"] == 2
        assert m.get_stats() == stats  # the ancestor alias agrees, purely
        assert m.stats() == stats
    finally:
        m.close()


def test_row_m27_dump_is_a_pure_idempotent_read(tmp_path):
    m = _mem(tmp_path)
    _pair(m)
    try:
        dump = _assert_pure(m, lambda: m.dump(limit=10))
        assert dump["stats"]["total_nodes"] == 2 and len(dump["nodes"]) == 2
    finally:
        m.close()


# ─── idempotent write rows ────────────────────────────────────────


def test_row_m10_remember_is_idempotent(tmp_path):
    m = _mem(tmp_path)
    try:
        first = m.remember("same raven memory", category="lore", path="p", importance=7)
        second = m.remember("same raven memory", category="lore", path="p", importance=7)
        assert second == first
        assert m.stats()["total_nodes"] == 1
        # A retry carrying different fields is still the same memory:
        # the first write wins (INSERT OR IGNORE on the content hash).
        third = m.remember("same raven memory", category="lore", path="p", importance=3)
        assert third == first
        assert m.get_node(first).importance == 7
    finally:
        m.close()


def test_row_m30_remember_many_is_idempotent(tmp_path):
    m = _mem(tmp_path)
    try:
        items = [
            {"content": "batch raven one", "category": "lore", "importance": 7},
            {"content": "batch raven two", "category": "lore", "importance": 6},
            {"content": "batch raven one", "category": "lore", "importance": 7},
        ]
        first = m.remember_many(items)
        stats_after_first = m.stats()
        second = m.remember_many(items)
        assert second == first  # same ids, in the same order
        assert first[0] == first[2]  # the in-batch duplicate shares its id
        assert m.stats() == stats_after_first  # no duplicate nodes
        assert m.stats()["total_nodes"] == 2
    finally:
        m.close()


def test_row_m11_store_alias_is_idempotent(tmp_path):
    m = _mem(tmp_path)
    try:
        first = m.store("aliased raven memory", path="p", memory_type="fact")
        second = m.store("aliased raven memory", path="p", memory_type="fact")
        assert second == first
        assert m.stats()["total_nodes"] == 1
    finally:
        m.close()


def test_row_m17_update_is_idempotent_apart_from_updated_at(tmp_path):
    m = _mem(tmp_path)
    a, _ = _pair(m)
    try:
        assert m.update(a, importance=9, tags=["Rune"]) is True
        node_first = m.get_node(a)
        assert m.update(a, importance=9, tags=["Rune"]) is True
        node_second = m.get_node(a)
        assert node_second.importance == node_first.importance == 9
        assert node_second.tags == node_first.tags == ["rune"]
        assert node_second.content == node_first.content
        # Only the write stamp may differ (RM-012's monotonic _tick).
        assert node_second.updated_at >= node_first.updated_at
        assert m.stats()["total_nodes"] == 2
        assert m.update(999999, importance=1) is False  # missing id, repeatably
        assert m.update(999999, importance=1) is False
    finally:
        m.close()


def test_row_m18_forget_is_state_idempotent(tmp_path):
    m = _mem(tmp_path)
    a, b = _pair(m)
    m.associate(a, b, strength=0.5)
    try:
        assert m.forget(a) is True
        stats_after_first = m.stats()
        assert m.forget(a) is False  # already gone: the "already done" signal
        assert m.stats() == stats_after_first  # …and the state did not move
        assert m.get_node(a) is None
    finally:
        m.close()


def test_row_m19_delete_alias_is_state_idempotent(tmp_path):
    m = _mem(tmp_path)
    a, _ = _pair(m)
    try:
        assert m.delete(a) is True
        assert m.delete(a) is False
        assert m.stats()["total_nodes"] == 1
    finally:
        m.close()


def test_row_m20_move_is_idempotent_apart_from_updated_at(tmp_path):
    m = _mem(tmp_path)
    a, _ = _pair(m)
    try:
        assert m.move(a, "lore/moved") is True
        assert m.move(a, "lore/moved") is True
        node = m.get_node(a)
        assert node.path == "lore/moved"
        assert [n.id for n in m.get_by_path("lore/moved")] == [a]
    finally:
        m.close()


def test_row_m22_heal_structure_is_idempotent(tmp_path):
    m = _mem(tmp_path)
    a, b = _pair(m)
    m.associate(a, b, strength=0.5)
    try:
        first = m.heal_structure()
        second = m.heal_structure()
        assert first["fixes"] == 0  # a healthy store needs nothing
        assert second == first  # …and a repeat finds the same nothing
        assert m.stats()["total_connections"] == 2
    finally:
        m.close()


def test_row_m24_consolidate_is_idempotent(tmp_path):
    m = _mem(tmp_path)
    a, b = _pair(m)
    m.associate(a, b, strength=0.9)
    try:
        first = m.consolidate()
        assert first["newly_consolidated"] == 2  # both directed rows
        second = m.consolidate()
        assert second["newly_consolidated"] == 0
        assert second["unmarked"] == 0
        assert second["total_consolidated"] == first["total_consolidated"] == 2
    finally:
        m.close()


def test_row_m28_memory_node_dict_round_trip_is_pure(tmp_path):
    m = _mem(tmp_path)
    a, _ = _pair(m)
    try:
        node = m.get_node(a)
        clone = MemoryNode.from_dict(node.to_dict())
        assert clone == node
        assert MemoryNode.from_dict(clone.to_dict()) == node  # and again
    finally:
        m.close()


# ─── safely-re-runnable rows ──────────────────────────────────────


def test_row_m23_decay_is_safely_rerunnable_and_cumulative(tmp_path):
    m = _mem(tmp_path)
    a, b = _pair(m)
    m.associate(a, b, strength=0.9)
    try:
        first = m.decay(days=1.0)
        strength_after_first = m.get_associations(a)[0]["strength"]
        second = m.decay(days=1.0)  # safe to run again — it decays AGAIN
        strength_after_second = m.get_associations(a)[0]["strength"]
        assert first["edges_decayed"] == second["edges_decayed"] == 2
        assert 0.9 > strength_after_first > strength_after_second > 0.0
        # The composition is the defined one: two decay(1) ≈ one decay(2).
        other = _mem(tmp_path, name="other.db")
        try:
            x = other.remember("alpha raven memory", importance=7)
            y = other.remember("beta raven memory", importance=6)
            other.associate(x, y, strength=0.9)
            other.decay(days=2.0)
            assert other.get_associations(x)[0]["strength"] == pytest.approx(
                strength_after_second, rel=1e-12
            )
        finally:
            other.close()
    finally:
        m.close()


def test_row_m29_decay_wall_clock_is_safely_rerunnable(tmp_path, monkeypatch):
    import muninn.core

    monkeypatch.setattr(
        muninn.core, "_now", lambda: "2026-01-01T00:00:00+00:00"
    )
    m = _mem(tmp_path)
    a, b = _pair(m)
    m.associate(a, b, strength=0.9)
    try:
        first = m.decay_wall_clock()  # arms the marker, decays 0 days
        strength_after_first = m.get_associations(a)[0]["strength"]
        second = m.decay_wall_clock()  # same clock reading: 0 more days
        strength_after_second = m.get_associations(a)[0]["strength"]
        assert first["elapsed_days"] == second["elapsed_days"] == 0.0
        assert strength_after_first == strength_after_second == 0.9
    finally:
        m.close()
