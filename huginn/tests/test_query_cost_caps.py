"""RM-053 — Query cost ceilings for huginn (threat TH-13).

A local search scores candidate documents: every document
the term index offers for the query (TF-IDF road) or every
document in the vector table (vector road). Before this
slice that set was bounded only by the corpus itself. The
slice adds the explicit ceiling
``HuginnConfig.max_search_candidates``:

* one local search scores at most that many candidates;
* when more candidates exist, the lowest-id candidates
  are scored — deterministically — and the rest are not
  considered by that call (the cap applies *before* the
  category / importance filter, exactly as the unbounded
  candidate fetch did);
* the bite is visible in ``HuginnMemory.last_search_stats``:
  ``candidates_total`` (offered), ``candidates_scored``,
  ``cap`` and ``capped`` — a dedicated property, NOT a
  ``health()`` field, because health snapshots are pinned
  pure (a read must not change them);
* below the ceiling, results are exactly the unbounded
  search's;
* on the vector road, only surviving candidates' vectors
  are decoded at all.

The Qdrant backend is out of scope: the server owns its
query cost. Record: ``docs/QUERY_COST_CAPS.md``.
"""

import pytest

from huginn import HuginnMemory
from huginn.config import HuginnConfig
from huginn.errors import HuginnConfigurationError


def _huginn(tmp_path, **overrides):
    config = HuginnConfig(
        backend="local",
        local_db_path=str(tmp_path / "h.db"),
        **overrides,
    )
    return HuginnMemory(config)


def _corpus(mem, count=12):
    ids = []
    for i in range(count):
        ids.append(
            mem.upsert_memory(
                f"raven common tale number {i}", category="lore"
            )
        )
    return ids


def test_default_ceiling_and_initial_stats(tmp_path):
    mem = _huginn(tmp_path)
    try:
        assert mem.config.max_search_candidates == 10000
        assert mem.last_search_stats == {
            "candidates_total": 0,
            "candidates_scored": 0,
            "candidates_pruned": 0,
            "cap": 10000,
            "capped": False,
        }
    finally:
        mem.close()


def test_ceiling_is_validated_at_construction(tmp_path):
    with pytest.raises(HuginnConfigurationError):
        HuginnConfig(
            local_db_path=str(tmp_path / "x.db"), max_search_candidates=0
        )
    with pytest.raises(HuginnConfigurationError):
        HuginnConfig(
            local_db_path=str(tmp_path / "x.db"), max_search_candidates=-2
        )


def test_below_the_ceiling_the_search_is_unchanged(tmp_path):
    mem = _huginn(tmp_path)
    try:
        ids = _corpus(mem, count=6)
        results = mem.search("raven", limit=10)
        assert {r["id"] for r in results} == set(ids)
        stats = mem.last_search_stats
        assert stats["candidates_total"] == 6
        assert stats["candidates_scored"] == 6
        assert stats["capped"] is False
    finally:
        mem.close()


def test_tfidf_cap_bites_deterministically(tmp_path):
    mem = _huginn(tmp_path, max_search_candidates=5)
    try:
        ids = _corpus(mem, count=12)
        first = mem.search("raven", limit=10)
        stats = mem.last_search_stats
        assert stats["candidates_total"] == 12
        assert stats["candidates_scored"] == 5
        assert stats["cap"] == 5
        assert stats["capped"] is True
        # The lowest-id candidates are the ones scored.
        assert {r["id"] for r in first} <= set(ids[:5])
        assert first, "the scored candidates do match the query"
        second = mem.search("raven", limit=10)
        assert [r["id"] for r in second] == [r["id"] for r in first]
    finally:
        mem.close()


def test_cap_applies_before_the_category_filter(tmp_path):
    mem = _huginn(tmp_path, max_search_candidates=5)
    try:
        for i in range(5):
            mem.upsert_memory(f"raven alpha tale {i}", category="alpha")
        for i in range(7):
            mem.upsert_memory(f"raven beta tale {i}", category="beta")
        results = mem.search("raven", limit=10, category="beta")
        stats = mem.last_search_stats
        # All five scored candidates were alpha; the beta
        # documents were beyond the bite and never scored.
        assert results == []
        assert stats["candidates_total"] == 12
        assert stats["candidates_scored"] == 0
        assert stats["capped"] is True
    finally:
        mem.close()


def test_vector_road_cap_bites(tmp_path):
    mem = _huginn(tmp_path, embedder="hashing", max_search_candidates=4)
    try:
        _corpus(mem, count=9)
        mem.search("raven", limit=10)
        stats = mem.last_search_stats
        assert stats["candidates_total"] == 9
        assert stats["candidates_scored"] == 4
        assert stats["cap"] == 4
        assert stats["capped"] is True
    finally:
        mem.close()


def test_no_candidates_records_an_honest_zero(tmp_path):
    mem = _huginn(tmp_path, max_search_candidates=3)
    try:
        _corpus(mem, count=4)
        assert mem.search("nonexistentterm", limit=10) == []
        stats = mem.last_search_stats
        assert stats["candidates_total"] == 0
        assert stats["candidates_scored"] == 0
        assert stats["capped"] is False
    finally:
        mem.close()


def test_property_is_lazy_and_returns_a_copy(tmp_path):
    mem = _huginn(tmp_path, max_search_candidates=2)
    try:
        # Before the first search the property reports the
        # zero record — and reading it must not construct
        # the backend (lazy construction is contractual).
        assert mem.last_search_stats == {
            "candidates_total": 0,
            "candidates_scored": 0,
            "candidates_pruned": 0,
            "cap": 2,
            "capped": False,
        }
        assert mem._backend is None
        _corpus(mem, count=3)
        mem.search("raven", limit=10)
        record = mem.last_search_stats
        assert record["capped"] is True
        record["capped"] = "tampered"
        assert mem.last_search_stats["capped"] is True
        # And the health snapshot stays pure through a search.
        health_before = mem.health()
        mem.search("raven", limit=10)
        assert mem.health() == health_before
    finally:
        mem.close()
