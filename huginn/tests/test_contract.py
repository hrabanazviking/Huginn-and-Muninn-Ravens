"""The Bifröst contract, exercised exactly as Bifröst exercises it.

Bifröst (hrabanazviking/bifrost @ b66e98cc, src/bifrost/core.py) does:
    from huginn import HuginnMemory
    huginn = HuginnMemory(config=None)
    huginn.upsert_memory(content=, category=, importance=, tags=, emotional_valence=)
    huginn.search(query_text=, limit=, category=, min_importance=)
    huginn.health()          # dict with "status"
    huginn.close()           # via hasattr check
"""

import pytest

from huginn import HuginnConfig, HuginnMemory


@pytest.fixture
def local_cfg(tmp_path):
    return HuginnConfig(
        backend="local", local_db_path=str(tmp_path / "huginn_local.db")
    )


def test_bifrost_call_shapes(local_cfg):
    huginn = HuginnMemory(config=local_cfg)
    vector_id = huginn.upsert_memory(
        content="Freyja is the Vanir goddess of love and seiðr",
        category="spiritual",
        importance=9,
        tags=["freyja", "seiðr"],
        emotional_valence=0.7,
    )
    assert isinstance(vector_id, int)
    results = huginn.search(
        query_text="goddess of love",
        limit=5,
        category=None,
        min_importance=1,
    )
    assert len(results) == 1
    r = results[0]
    assert r["id"] == vector_id
    assert r["content"].startswith("Freyja")
    assert r["category"] == "spiritual"
    assert r["importance"] == 9
    assert r["tags"] == ["freyja", "seiðr"]
    assert r["emotional_valence"] == pytest.approx(0.7)
    assert 0.0 < r["score"] <= 1.0
    huginn.close()
    huginn.close()  # idempotent


def test_health_shape(local_cfg):
    huginn = HuginnMemory(config=local_cfg)
    health = huginn.health()
    assert health["status"] == "healthy"
    assert health["backend"] == "local"
    huginn.close()


def test_config_none_constructs_lazily(tmp_path, monkeypatch):
    """HuginnMemory(config=None) — Bifröst's exact call — must build
    nothing and open nothing at construction time."""
    monkeypatch.setenv("HOME", str(tmp_path))
    huginn = HuginnMemory(config=None)
    assert huginn._backend is None
    assert list(tmp_path.iterdir()) == []
    huginn.close()


def test_search_filters(local_cfg):
    huginn = HuginnMemory(config=local_cfg)
    huginn.upsert_memory(content="runes and norse mythology", category="spiritual", importance=9)
    huginn.upsert_memory(content="runes in python code", category="skill", importance=3)
    by_cat = huginn.search(query_text="runes", category="skill")
    assert [r["category"] for r in by_cat] == ["skill"]
    by_imp = huginn.search(query_text="runes", min_importance=5)
    assert [r["importance"] for r in by_imp] == [9]
    huginn.close()
