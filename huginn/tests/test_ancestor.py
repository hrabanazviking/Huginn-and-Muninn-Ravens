"""Ancestor Huginn semantics: analysis, flights, hops, TF-IDF search."""

import pytest

from huginn import HuginnConfig, HuginnMemory, analyze_query, semantic_search


def test_analyze_query_shapes():
    a = analyze_query("why do runes hold power")
    assert a["query_type"] == "explanatory"
    assert "runes" in a["key_terms"] and "why" not in a["key_terms"]
    b = analyze_query("compare the two ravens")
    assert b["query_type"] == "comparison"
    assert b["strategy"] == "multi_hop" and b["recommended_hops"] == 2
    c = analyze_query("list all memories")
    assert c["query_type"] == "enumeration" and c["strategy"] == "broad"


def test_semantic_search_function():
    docs = [
        "the raven flies over the battlefield at dawn",
        "python functions and list comprehensions",
        "ravens and crows are clever birds",
    ]
    hits = semantic_search("raven birds", docs, top_k=2)
    assert hits
    assert hits[0][0] in (0, 2)
    assert all(score > 0 for _, score in hits)
    assert semantic_search("anything", []) == []


@pytest.fixture
def huginn(tmp_path):
    h = HuginnMemory(
        HuginnConfig(backend="local", local_db_path=str(tmp_path / "h.db"))
    )
    yield h
    h.close()


def test_fly_returns_retrieval_result(huginn):
    huginn.upsert_memory(
        content="Freyja rides a chariot pulled by two cats, gift of the Vanir",
        category="myth",
    )
    flight = huginn.fly("Freyja chariot cats")
    assert flight.error is None
    assert flight.source_realm == "huginn:local"
    assert len(flight.results) == 1
    assert flight.relevance_scores == [flight.results[0]["score"]]
    assert flight.retrieval_time >= 0
    stats = huginn.get_flight_stats()
    assert stats["total_flights"] == 1
    assert stats["total_results_retrieved"] == 1


def test_fly_compression(huginn):
    long_content = "word " * 100 + "unique-marker"
    huginn.upsert_memory(content=long_content, category="bulk")
    flight = huginn.fly("unique-marker", compress=True)
    assert flight.results[0]["content"].endswith("...")
    raw = huginn.fly("unique-marker", compress=False)
    assert raw.results[0]["content"] == long_content


def test_multi_hop(huginn):
    huginn.upsert_memory(content="Odin gave his eye for wisdom at the well", category="myth")
    huginn.upsert_memory(content="wisdom of the well guides the wanderer home", category="myth")
    flights = huginn.multi_hop_retrieve("Odin eye", hop_count=2, max_results_per_hop=2)
    assert 1 <= len(flights) <= 2
    assert flights[0].results
