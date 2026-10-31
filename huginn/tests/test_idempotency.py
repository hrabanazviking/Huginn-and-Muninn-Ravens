"""RM-013 — Idempotency matrix for huginn (one test per matrix row).

The matrix itself lives in ``docs/API_REFERENCE.md`` (Part 3).
Classes, per the matrix definitions:

- **I** — idempotent: an identical repeat leaves the logical store
  state unchanged (write timestamps excluded where a row says so)
  and returns an equal result (a state-changing row may return its
  "already done" signal on the repeat — e.g. ``delete`` True→False).
- **R** — safely re-runnable: a repeat is safe (no error, no
  duplication, no corruption) but applies its defined effect again.
- **N** — intentionally not idempotent: every call is a new event
  by design; a blind retry double-applies.

Rows cover the local backend (the contractual default). The live
Qdrant backend mirrors the H-03/H-04 upsert identity and the pure
reads by construction, but a live Qdrant round-trip is still
NOT PROVEN, so no Qdrant row is claimed proven here.
"""

from huginn import HuginnMemory, analyze_query, semantic_search
from huginn.config import HuginnConfig
from huginn.local_backend import LocalBackend


def _hug(tmp_path, name="h.db"):
    return HuginnMemory(
        HuginnConfig(backend="local", local_db_path=str(tmp_path / name))
    )


def _seed(h):
    return h.upsert_memory(
        content="runes and ravens fly at dawn", category="lore",
        importance=7, tags=["rune"], emotional_valence=0.2,
    )


# ─── lifecycle rows ───────────────────────────────────────────────


def test_row_h01_construction_and_reopen(tmp_path):
    db = str(tmp_path / "h.db")
    h = HuginnMemory(HuginnConfig(backend="local", local_db_path=db))
    doc_id = _seed(h)
    h.close()
    for _ in range(2):  # reopening is safely re-runnable, state intact
        h2 = HuginnMemory(HuginnConfig(backend="local", local_db_path=db))
        try:
            assert h2.get(doc_id)["content"] == "runes and ravens fly at dawn"
            assert h2.health()["documents"] == 1
            assert h2.health()["recovered_from_backup"] is False
        finally:
            h2.close()


def test_row_h02_close_is_idempotent(tmp_path):
    h = _hug(tmp_path)
    _seed(h)
    h.close()
    h.close()  # second and third closes are no-ops, never errors
    h.close()
    never_used = _hug(tmp_path, name="unused.db")
    never_used.close()  # closing before the lazy backend exists is fine
    never_used.close()


# ─── idempotent write rows ────────────────────────────────────────


def test_row_h03_upsert_without_id_is_idempotent(tmp_path):
    h = _hug(tmp_path)
    try:
        first = _seed(h)
        second = _seed(h)
        assert second == first
        assert h.health()["documents"] == 1
        # Upsert means replace: a repeat carrying new fields updates
        # the SAME document in place instead of duplicating it.
        third = h.upsert_memory(
            content="runes and ravens fly at dawn", category="lore",
            importance=9, tags=["rune"], emotional_valence=0.2,
        )
        assert third == first
        assert h.get(first)["importance"] == 9
        assert h.health()["documents"] == 1
    finally:
        h.close()


def test_row_h04_upsert_with_explicit_id_is_idempotent(tmp_path):
    h = _hug(tmp_path)
    try:
        first = h.upsert_memory(content="aligned raven memory", memory_id=42)
        second = h.upsert_memory(content="aligned raven memory", memory_id=42)
        assert first == second == 42
        assert h.health()["documents"] == 1
        # Replacing the content under the explicit id, twice: the
        # second replace lands exactly where the first did.
        h.upsert_memory(content="aligned raven memory rewritten", memory_id=42)
        h.upsert_memory(content="aligned raven memory rewritten", memory_id=42)
        assert h.get(42)["content"] == "aligned raven memory rewritten"
        assert h.health()["documents"] == 1
        assert h.search(query_text="rewritten")[0]["id"] == 42
    finally:
        h.close()


def test_row_h07_delete_is_state_idempotent(tmp_path):
    h = _hug(tmp_path)
    try:
        doc_id = _seed(h)
        assert h.delete(doc_id) is True
        assert h.health()["documents"] == 0
        assert h.delete(doc_id) is False  # already gone, state unmoved
        assert h.health()["documents"] == 0
        assert h.get(doc_id) is None
    finally:
        h.close()


def test_row_h15_local_backend_heal_is_idempotent(tmp_path):
    backend = LocalBackend(
        HuginnConfig(backend="local", local_db_path=str(tmp_path / "h.db"))
    )
    try:
        backend.upsert(
            content="healable raven document", category="lore",
            importance=5, tags=[], emotional_valence=0.0,
        )
        first = backend.heal()
        second = backend.heal()
        assert first == {
            "orphan_terms_pruned": 0,
            "orphan_vectors_pruned": 0,
            "doc_freq_fixed": 0,
        }
        assert second == first
        assert backend.count() == 1
    finally:
        backend.close()


# ─── pure-read rows: idempotent, and the store provably unmoved ───


def _assert_pure(h, call):
    docs_before = h.health()["documents"]
    first = call()
    second = call()
    assert first == second
    assert h.health()["documents"] == docs_before
    return first


def test_row_h05_search_is_a_pure_idempotent_read(tmp_path):
    h = _hug(tmp_path)
    try:
        _seed(h)
        results = _assert_pure(h, lambda: h.search(query_text="runes ravens"))
        assert results and results[0]["content"] == "runes and ravens fly at dawn"
        assert h.search(query_text="   ") == []  # blank query, repeatably
        assert h.search(query_text="   ") == []
    finally:
        h.close()


def test_row_h06_get_is_a_pure_idempotent_read(tmp_path):
    h = _hug(tmp_path)
    try:
        doc_id = _seed(h)
        doc = _assert_pure(h, lambda: h.get(doc_id))
        assert doc["id"] == doc_id
        assert h.get(999999) is None
    finally:
        h.close()


def test_row_h08_health_is_a_pure_idempotent_read(tmp_path):
    h = _hug(tmp_path)
    try:
        _seed(h)
        health = _assert_pure(h, h.health)
        assert health["status"] == "healthy" and health["documents"] == 1
    finally:
        h.close()


def test_row_h09_stats_is_a_pure_idempotent_alias(tmp_path):
    h = _hug(tmp_path)
    try:
        _seed(h)
        stats = _assert_pure(h, h.stats)
        assert stats == h.health()  # the alias agrees with its target
    finally:
        h.close()


def test_row_h10_analyze_query_is_pure(tmp_path):
    h = _hug(tmp_path)
    try:
        first = h.analyze_query("where do ravens fly at dawn?")
        second = h.analyze_query("where do ravens fly at dawn?")
        assert first == second
        assert analyze_query("where do ravens fly at dawn?") == first
        assert h.health()["documents"] == 0  # it never touched the store
    finally:
        h.close()


def test_row_h11_semantic_search_module_function_is_pure():
    docs = ["ravens fly at dawn", "quantum photon pairs", "ravens and runes"]
    first = semantic_search("ravens", docs, top_k=2)
    second = semantic_search("ravens", docs, top_k=2)
    assert first == second
    assert first[0][0] in (0, 2)  # a raven document ranks first


def test_row_h14_get_flight_stats_is_a_pure_idempotent_read(tmp_path):
    h = _hug(tmp_path)
    try:
        _seed(h)
        assert h.get_flight_stats() == {"total_flights": 0}
        assert h.get_flight_stats() == {"total_flights": 0}  # reading adds none
    finally:
        h.close()


# ─── intentionally-not rows: flights are events, by design ────────


def test_row_h12_fly_is_store_pure_but_appends_flight_history(tmp_path):
    h = _hug(tmp_path)
    try:
        _seed(h)
        first = h.fly("runes ravens", max_results=3)
        assert h.get_flight_stats()["total_flights"] == 1
        second = h.fly("runes ravens", max_results=3)
        # The flight itself comes home the same (time excluded)…
        assert second.results == first.results
        assert second.relevance_scores == first.relevance_scores
        # …but each flight is a new recorded event — NOT idempotent.
        assert h.get_flight_stats()["total_flights"] == 2
        assert h.health()["documents"] == 1  # the store never moved
    finally:
        h.close()


def test_row_h13_multi_hop_retrieve_appends_one_flight_per_hop(tmp_path):
    h = _hug(tmp_path)
    try:
        _seed(h)
        h.upsert_memory(content="ravens carry runes over the sea", category="lore")
        first = h.multi_hop_retrieve("ravens runes", hop_count=2, max_results_per_hop=2)
        flights_after_first = h.get_flight_stats()["total_flights"]
        assert flights_after_first == len(first) >= 1
        second = h.multi_hop_retrieve("ravens runes", hop_count=2, max_results_per_hop=2)
        assert len(second) == len(first)
        assert [f.results for f in second] == [f.results for f in first]
        assert h.get_flight_stats()["total_flights"] == 2 * flights_after_first
        assert h.health()["documents"] == 2  # the store never moved
    finally:
        h.close()
