"""Hebbian semantics, maintenance, self-healing and read purity."""

import sqlite3

import pytest

from muninn import HebbianMemory
from muninn.config import MuninnConfig
from muninn.errors import MuninnValidationError


@pytest.fixture
def mem(tmp_path):
    m = HebbianMemory(MuninnConfig(db_path=str(tmp_path / "m.db")))
    yield m
    m.close()


def _write_state(db_path):
    """Snapshot of every write-bearing table, via a separate connection."""
    conn = sqlite3.connect(str(db_path))
    try:
        acts = conn.execute("SELECT COUNT(*) FROM activation_log").fetchone()[0]
        conns = conn.execute(
            "SELECT memory_a_id, memory_b_id, strength, co_activation_count"
            " FROM hebbian_connections ORDER BY 1, 2"
        ).fetchall()
        nodes = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        counters = conn.execute(
            "SELECT memory_id, total_activations FROM node_activation ORDER BY 1"
        ).fetchall()
        return acts, [tuple(r) for r in conns], nodes, [tuple(r) for r in counters]
    finally:
        conn.close()


def test_hebbian_bounded_learning(mem):
    mem.activate_batch([1, 2])
    s1 = mem.get_associations(1)[0]["strength"]
    assert s1 == pytest.approx(0.1)  # first wiring = learning rate
    mem.activate_batch([1, 2])
    s2 = mem.get_associations(1)[0]["strength"]
    assert s2 == pytest.approx(1 - 0.9 * 0.9)
    for _ in range(50):
        mem.activate_batch([1, 2])
    s3 = mem.get_associations(1)[0]["strength"]
    assert 0.99 < s3 <= 1.0  # bounded, never exceeds 1
    assert mem.get_associations(1)[0]["co_activation_count"] == 52


def test_batch_dedupes_and_skips_self_pairs(mem):
    result = mem.activate_batch([5, 5, 6, 6])
    assert result["activated"] == 2
    assert result["pairs_wired"] == 1
    assert mem.activation_count(5) == 1
    assert mem.get_associations(5)[0]["memory_id"] == 6


def test_activation_restores_confidence(mem, tmp_path):
    mem.activate(7)
    mem.decay(days=90)  # confidence half-life 90d → ~0.5
    conn = sqlite3.connect(str(tmp_path / "m.db"))
    conf = conn.execute(
        "SELECT confidence FROM node_activation WHERE memory_id = 7"
    ).fetchone()[0]
    conn.close()
    assert conf == pytest.approx(0.5, abs=0.02)
    for _ in range(30):
        mem.activate(7)
    conn = sqlite3.connect(str(tmp_path / "m.db"))
    conf = conn.execute(
        "SELECT confidence FROM node_activation WHERE memory_id = 7"
    ).fetchone()[0]
    conn.close()
    assert conf > 0.95


def test_decay_prunes_and_reports(mem):
    mem.associate(1, 2, strength=0.02)
    mem.associate(1, 3, strength=0.9)
    out = mem.decay(days=30)  # edge half-life 30d → factor 0.5
    assert out["edges_decayed"] == 4  # both directions of both pairs
    assert mem.get_associations(1, min_strength=0.4)[0]["memory_id"] == 3
    # 0.02 * 0.5 = 0.01 — not below prune threshold 0.01; decay more
    out = mem.decay(days=30)
    assert out["edges_pruned"] >= 2  # the weak pair, both directions
    assert [a["memory_id"] for a in mem.get_associations(1)] == [3]


def test_consolidate_marks_strong_edges(mem):
    mem.associate(1, 2, strength=0.85)
    mem.associate(1, 3, strength=0.4)
    out = mem.consolidate()
    assert out["newly_consolidated"] == 2  # both directed rows of the pair
    assocs = {a["memory_id"]: a for a in mem.get_associations(1)}
    assert assocs[2]["consolidated"] is True
    assert assocs[3]["consolidated"] is False
    again = mem.consolidate()
    assert again["newly_consolidated"] == 0  # re-runnable


def test_spread_activation(mem):
    mem.associate(1, 2, strength=1.0)
    mem.associate(2, 3, strength=1.0)
    mem.associate(1, 4, strength=0.1)
    spread = mem.spread_activation([1], depth=2, attenuation=0.5)
    assert spread[1] == 1.0
    assert spread[2] == pytest.approx(0.5)
    assert spread[3] == pytest.approx(0.25)
    assert spread[4] < spread[3]


def test_reads_are_pure(mem, tmp_path):
    """Slice 86 ground 2: no hidden writes on any read path."""
    db = tmp_path / "m.db"
    mem.remember("Freyja is the Vanir goddess of love", category="spiritual")
    mem.activate_batch([1, 2, 3])
    before = _write_state(db)
    mem.get_associations(1)
    mem.get_associations(1, min_strength=0.05)
    mem.activation_count(1)
    mem.spread_activation([1, 2])
    mem.get_node(1)
    mem.retrieve("Freyja")
    mem.retrieve(path="nowhere")
    mem.get_by_path("")
    mem.get_children("")
    mem.get_tree_structure()
    mem.health()
    mem.stats()
    mem.dump()
    after = _write_state(db)
    assert before == after


def test_retrieve_touch_is_the_named_reinforcing_read(mem, tmp_path):
    db = tmp_path / "m.db"
    nid = mem.remember("runes are symbols of power", category="spiritual")
    before = _write_state(db)
    mem.retrieve("runes")  # pure
    assert _write_state(db) == before
    mem.retrieve("runes", touch=True)  # explicitly reinforcing
    after = _write_state(db)
    assert after[0] == before[0] + 1  # exactly one activation logged
    assert mem.activation_count(nid) == 1


def test_heal_repairs_damage(mem, tmp_path):
    db = str(tmp_path / "m.db")
    mem.activate_batch([1, 2])
    mem.forget(9)  # tombstone an id with no edges yet
    conn = sqlite3.connect(db)
    # self-edge, dangling edge to the tombstoned id, asymmetric edge,
    # and a drifted counter — all written behind Muninn's back.
    conn.execute(
        "INSERT INTO hebbian_connections VALUES (5, 5, 0.5, 1, 0, 't', 't')"
    )
    conn.execute(
        "INSERT INTO hebbian_connections VALUES (1, 9, 0.5, 1, 0, 't', 't')"
    )
    conn.execute(
        "INSERT INTO hebbian_connections VALUES (3, 4, 0.7, 2, 0, 't', 't')"
    )
    conn.execute("UPDATE node_activation SET total_activations = 999 WHERE memory_id = 1")
    conn.commit()
    conn.close()
    report = mem.heal_structure()
    assert report["self_edges_pruned"] == 1
    assert report["dangling_edges_pruned"] >= 1
    assert report["pairs_repaired"] >= 1
    assert report["counters_fixed"] >= 1
    assert mem.activation_count(1) == 1
    # asymmetry repaired: 4 now associates back to 3
    assert mem.get_associations(4)[0]["memory_id"] == 3


def test_validation_errors(mem):
    with pytest.raises(MuninnValidationError):
        mem.activate("not-an-int")
    with pytest.raises(MuninnValidationError):
        mem.activate(-1)
    with pytest.raises(MuninnValidationError):
        mem.activate(1, emotional_valence=2.0)
    with pytest.raises(MuninnValidationError):
        mem.associate(1, 1)
    with pytest.raises(MuninnValidationError):
        mem.decay(days=-1)
    with pytest.raises(MuninnValidationError):
        mem.remember(None)
    with pytest.raises(MuninnValidationError):
        mem.remember("x", importance=11)
    # and none of the failures wrote anything
    assert mem.stats()["total_activations"] == 0
    assert mem.stats()["total_nodes"] == 0
