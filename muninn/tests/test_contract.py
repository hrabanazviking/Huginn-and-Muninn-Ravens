"""The Bifröst contract, exercised exactly as Bifröst exercises it.

Mirrors, call for call, what hrabanazviking/bifrost @ b66e98cc does with
the muninn package in src/bifrost/core.py and tests/test_hebbian_guard.py.
"""

import sqlite3

import pytest

from muninn import HebbianMemory
from muninn.config import MuninnConfig


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "muninn_hebbian.db")


def test_bifrost_construction_shape(db_path):
    # from muninn import HebbianMemory; from muninn.config import MuninnConfig
    config = MuninnConfig(db_path=db_path)
    muninn = HebbianMemory(config)
    muninn.close()
    muninn.close()  # double close must not error (bridge test does this)


def test_activate_and_stats_keys(db_path):
    muninn = HebbianMemory(MuninnConfig(db_path=db_path))
    muninn.activate(1)
    muninn.activate(1, emotional_valence=0.5)
    stats = muninn.stats()
    assert stats["total_activations"] == 2
    assert stats["total_connections"] == 0
    muninn.close()


def test_get_conn_raw_sql_activation_count(db_path):
    """Bifröst's _get_activation_count: raw SQL over _get_conn()."""
    muninn = HebbianMemory(MuninnConfig(db_path=db_path))
    for _ in range(3):
        muninn.activate(42)
    conn = muninn._get_conn()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM activation_log WHERE memory_id = ?",
        (42,),
    ).fetchone()
    assert row["cnt"] == 3
    muninn.close()


def test_guard_scenario_below_and_above_threshold(db_path):
    """The bridge's Hebbian guard: individual activate() never wires;
    activate_batch() wires. This is the semantic the guard relies on."""
    muninn = HebbianMemory(MuninnConfig(db_path=db_path))
    for _ in range(3):
        muninn.activate(1)
    assert muninn.stats()["total_connections"] == 0
    muninn.activate_batch([1, 2, 3], emotional_valence=0.0)
    stats = muninn.stats()
    assert stats["total_connections"] > 0
    assert stats["total_activations"] >= 3
    muninn.close()


def test_get_associations_shape_and_order(db_path):
    """Bifröst: muninn.get_associations(id, min_strength=weight) and
    associations[0]['strength'] is the boost — strongest first."""
    muninn = HebbianMemory(MuninnConfig(db_path=db_path))
    muninn.associate(1, 2, strength=0.3)
    muninn.associate(1, 3, strength=0.9)
    muninn.associate(1, 4, strength=0.6)
    assocs = muninn.get_associations(1, min_strength=0.2)
    assert [a["memory_id"] for a in assocs] == [3, 4, 2]
    assert assocs[0]["strength"] == pytest.approx(0.9)
    assert all("strength" in a for a in assocs)
    # min_strength filters
    assert [a["memory_id"] for a in muninn.get_associations(1, min_strength=0.5)] == [3, 4]
    muninn.close()


def test_decay_and_consolidate_return_dicts(db_path):
    muninn = HebbianMemory(MuninnConfig(db_path=db_path))
    muninn.activate_batch([1, 2])
    assert isinstance(muninn.decay(days=1), dict)
    assert isinstance(muninn.consolidate(), dict)
    muninn.close()


def test_health_shape(db_path):
    muninn = HebbianMemory(MuninnConfig(db_path=db_path))
    health = muninn.health()
    assert health["status"] == "healthy"
    muninn.close()


def test_schema_tables_exist(db_path):
    """The two contractual tables (bridge + Hermes Slice 87 probe)."""
    muninn = HebbianMemory(MuninnConfig(db_path=db_path))
    muninn.close()
    conn = sqlite3.connect(db_path)
    tables = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    conn.close()
    assert "activation_log" in tables
    assert "hebbian_connections" in tables


def test_wal_mode(db_path):
    muninn = HebbianMemory(MuninnConfig(db_path=db_path))
    mode = muninn._get_conn().execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"
    muninn.close()
