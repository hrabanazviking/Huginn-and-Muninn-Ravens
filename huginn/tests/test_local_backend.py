"""Local backend: ranking, identity, filters, healing, read purity."""

import sqlite3

import pytest

from huginn import HuginnConfig, HuginnMemory
from huginn.errors import HuginnValidationError


@pytest.fixture
def huginn(tmp_path):
    h = HuginnMemory(
        HuginnConfig(backend="local", local_db_path=str(tmp_path / "h.db"))
    )
    yield h
    h.close()


def _write_state(db_path):
    conn = sqlite3.connect(str(db_path))
    try:
        docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        terms = conn.execute(
            "SELECT doc_id, term, tf FROM doc_terms ORDER BY 1, 2"
        ).fetchall()
        stats = conn.execute(
            "SELECT term, doc_freq FROM corpus_stats ORDER BY 1"
        ).fetchall()
        return docs, [tuple(r) for r in terms], [tuple(r) for r in stats]
    finally:
        conn.close()


def test_ranking_prefers_relevant(huginn):
    huginn.upsert_memory(content="the quick brown fox jumps over the lazy dog", category="animals")
    huginn.upsert_memory(content="quantum entanglement and photon pairs", category="physics")
    huginn.upsert_memory(content="fox hunting dogs in autumn fields", category="animals")
    results = huginn.search(query_text="fox dog", limit=3)
    assert results, "expected results"
    assert "fox" in results[0]["content"]
    assert all("photon" not in r["content"] for r in results)


def test_upsert_idempotent_and_explicit_id(huginn):
    a = huginn.upsert_memory(content="stable memory", category="fact")
    b = huginn.upsert_memory(content="stable memory", category="fact")
    assert a == b
    assert huginn.health()["documents"] == 1
    # explicit id (the Bifröst id-alignment road)
    c = huginn.upsert_memory(content="aligned memory", category="fact", memory_id=42)
    assert c == 42
    assert huginn.get(42)["content"] == "aligned memory"
    # re-upsert under the explicit id replaces content and re-indexes
    huginn.upsert_memory(content="aligned memory rewritten", category="fact", memory_id=42)
    assert huginn.get(42)["content"] == "aligned memory rewritten"
    assert huginn.search(query_text="rewritten")[0]["id"] == 42
    assert huginn.search(query_text="aligned memory")  # overlap still finds it


def test_delete(huginn):
    mid = huginn.upsert_memory(content="ephemeral thought", category="fact")
    assert huginn.delete(mid) is True
    assert huginn.get(mid) is None
    assert huginn.search(query_text="ephemeral") == []
    assert huginn.delete(mid) is False


def test_search_is_pure_read(huginn, tmp_path):
    huginn.upsert_memory(content="purity of the read path matters", category="law")
    huginn.upsert_memory(content="second memory about paths", category="law")
    before = _write_state(tmp_path / "h.db")
    huginn.search(query_text="read path")
    huginn.get(1)
    huginn.fly("purity")
    huginn.health()
    after = _write_state(tmp_path / "h.db")
    assert before == after


def test_heal_repairs_index_drift(huginn, tmp_path):
    mid = huginn.upsert_memory(content="drift repair test memory", category="fact")
    db = str(tmp_path / "h.db")
    conn = sqlite3.connect(db)
    conn.execute("UPDATE corpus_stats SET doc_freq = 999 WHERE term = 'drift'")
    conn.execute(
        "INSERT INTO doc_terms (doc_id, term, tf) VALUES (99999, 'ghost', 1)"
    )
    conn.commit()
    conn.close()
    report = huginn._backend.heal()
    assert report["doc_freq_fixed"] >= 1
    assert report["orphan_terms_pruned"] == 1
    conn = sqlite3.connect(db)
    fixed = conn.execute(
        "SELECT doc_freq FROM corpus_stats WHERE term = 'drift'"
    ).fetchone()[0]
    conn.close()
    assert fixed == 1
    assert huginn.get(mid)["content"].startswith("drift")


def test_validation(huginn):
    with pytest.raises(HuginnValidationError):
        huginn.upsert_memory(content="")
    with pytest.raises(HuginnValidationError):
        huginn.upsert_memory(content="x", importance=0)
    with pytest.raises(HuginnValidationError):
        huginn.upsert_memory(content="x", emotional_valence=-2.0)
    with pytest.raises(HuginnValidationError):
        huginn.search(query_text=None)
    assert huginn.search(query_text="   ") == []  # blank = honest empty
    assert huginn.health()["documents"] == 0  # nothing was written


def test_hashing_embedder_local_mode(tmp_path):
    h = HuginnMemory(
        HuginnConfig(
            backend="local",
            local_db_path=str(tmp_path / "h.db"),
            embedder="hashing",
            vector_dim=128,
        )
    )
    h.upsert_memory(content="viking longships sail the northern seas", category="saga")
    h.upsert_memory(content="python decorators and context managers", category="skill")
    results = h.search(query_text="longships northern seas")
    assert results and "longships" in results[0]["content"]
    assert h.health()["embedder"] == "hashing"
    h.close()
