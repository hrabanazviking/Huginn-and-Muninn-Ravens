"""RM-063 — Warm-cache pins for huginn.

The optional bounded in-memory cache for ``get``
(record ``docs/WARM_CACHES.md``): off by default
(``cache_size=0``, every call reads the backend — the
pre-RM-063 behaviour), LRU-bounded when on, held in
the facade so it covers both backends, counted in the
dedicated ``cache_stats`` property (never in the
pinned-pure ``health()`` snapshot), and invalidated by
every write through the same object (``upsert_memory``,
``delete``, ``secure_forget``), so a hit is never stale
for this object's own writes. The cache is per-object
only — the staleness test below pins that documented
window: a write through another object is not seen
until eviction or an own write to that id.
"""

from pathlib import Path
from typing import Any

import pytest

from huginn import HuginnConfig, HuginnMemory
from huginn.errors import HuginnConfigurationError


def _huginn(tmp_path, **overrides):
    overrides.setdefault("backend", "local")
    overrides.setdefault("local_db_path", str(tmp_path / "h.db"))
    return HuginnMemory(HuginnConfig(**overrides))


def _repo_root():
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "RAVENS_ROADMAP_2026-10-31.md").is_file():
            return parent
    return None


def test_cache_is_disabled_by_default(tmp_path):
    hug = _huginn(tmp_path)
    try:
        assert hug.config.cache_size == 0
        doc_id = hug.upsert_memory("uncached thought")
        assert hug.get(doc_id)["content"] == "uncached thought"
        assert hug.get(doc_id)["content"] == "uncached thought"
        assert hug.cache_stats == {
            "enabled": False,
            "size": 0,
            "cap": 0,
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "hit_rate": 0.0,
        }
        other = _huginn(tmp_path)
        try:
            other.upsert_memory("seen immediately", memory_id=doc_id)
        finally:
            other.close()
        assert hug.get(doc_id)["content"] == "seen immediately"
    finally:
        hug.close()


def test_cache_size_validation_is_typed(tmp_path):
    with pytest.raises(HuginnConfigurationError) as exc:
        HuginnConfig(local_db_path=str(tmp_path / "x.db"), cache_size=-1)
    assert str(exc.value) == "cache_size must be >= 0"
    with pytest.raises(HuginnConfigurationError):
        HuginnConfig(local_db_path=str(tmp_path / "x.db"), cache_size="ten")


def test_cache_stats_never_constructs_the_backend(tmp_path):
    hug = _huginn(tmp_path, cache_size=3)
    try:
        # Lazy construction is contractual: reading the
        # accounting must not open a store or probe a server.
        assert hug._backend is None
        stats = hug.cache_stats
        assert stats["cap"] == 3
        assert stats["size"] == 0
        assert hug._backend is None
    finally:
        hug.close()


def test_hit_miss_accounting_is_exact(tmp_path):
    hug = _huginn(tmp_path, cache_size=4)
    try:
        a = hug.upsert_memory("first thought")
        b = hug.upsert_memory("second thought")
        assert hug.get(a)["content"] == "first thought"  # miss
        assert hug.get(a)["content"] == "first thought"  # hit
        assert hug.get(b)["content"] == "second thought"  # miss
        assert hug.get(a)["content"] == "first thought"  # hit
        stats = hug.cache_stats
        assert stats["enabled"] is True
        assert stats["cap"] == 4
        assert stats["size"] == 2
        assert stats["hits"] == 2
        assert stats["misses"] == 2
        assert stats["evictions"] == 0
        assert stats["hit_rate"] == 0.5
    finally:
        hug.close()


def test_a_miss_is_never_cached(tmp_path):
    hug = _huginn(tmp_path, cache_size=4)
    try:
        assert hug.get(424242) is None
        assert hug.get(424242) is None
        stats = hug.cache_stats
        assert stats["misses"] == 2
        assert stats["hits"] == 0
        assert stats["size"] == 0
    finally:
        hug.close()


def test_cache_is_bounded_with_lru_eviction(tmp_path):
    hug = _huginn(tmp_path, cache_size=2)
    try:
        a = hug.upsert_memory("lru one")
        b = hug.upsert_memory("lru two")
        c = hug.upsert_memory("lru three")
        hug.get(a)  # miss, cache [a]
        hug.get(b)  # miss, cache [a, b]
        hug.get(a)  # hit,  cache [b, a]
        hug.get(c)  # miss, evicts b (the LRU entry)
        stats = hug.cache_stats
        assert stats["size"] == 2
        assert stats["evictions"] == 1
        assert hug.get(a) is not None  # hit — still warm
        assert hug.cache_stats["hits"] == 2
        hug.get(b)  # miss — b was evicted
        assert hug.cache_stats["misses"] == 4
    finally:
        hug.close()


def test_upsert_invalidates(tmp_path):
    hug = _huginn(tmp_path, cache_size=4)
    try:
        doc_id = hug.upsert_memory("before upsert")
        assert hug.get(doc_id)["content"] == "before upsert"
        assert hug.get(doc_id)["content"] == "before upsert"  # hit
        hug.upsert_memory("after upsert", memory_id=doc_id)
        doc = hug.get(doc_id)  # miss — invalidated
        assert doc["content"] == "after upsert"
        assert hug.cache_stats["misses"] == 2
        # An idempotent re-upsert of new content under a
        # fresh explicit id is a write to that id too.
        hug.upsert_memory("brand new", memory_id=77)
        assert hug.get(77)["content"] == "brand new"
    finally:
        hug.close()


def test_delete_and_secure_forget_invalidate(tmp_path):
    hug = _huginn(tmp_path, cache_size=4)
    try:
        a = hug.upsert_memory("plain deleted")
        b = hug.upsert_memory("securely forgotten")
        assert hug.get(a) is not None
        assert hug.get(b) is not None
        assert hug.cache_stats["size"] == 2
        assert hug.delete(a) is True
        assert hug.get(a) is None
        assert hug.secure_forget(b) is True
        assert hug.get(b) is None
        assert hug.cache_stats["size"] == 0
    finally:
        hug.close()


def test_caller_mutation_never_poisons_the_cache(tmp_path):
    hug = _huginn(tmp_path, cache_size=4)
    try:
        doc_id = hug.upsert_memory("clean thought", tags=["one"])
        doc = hug.get(doc_id)
        doc["tags"].append("evil")
        doc["content"] = "hacked"
        fresh = hug.get(doc_id)  # a hit — and clean
        assert hug.cache_stats["hits"] >= 1
        assert fresh["tags"] == ["one"]
        assert fresh["content"] == "clean thought"
    finally:
        hug.close()


def test_per_object_staleness_is_the_documented_window(tmp_path):
    hug = _huginn(tmp_path, cache_size=4)
    other = _huginn(tmp_path, cache_size=4)
    try:
        doc_id = hug.upsert_memory("version one")
        assert hug.get(doc_id)["content"] == "version one"  # miss
        assert hug.get(doc_id)["content"] == "version one"  # hit
        other.upsert_memory("version two", memory_id=doc_id)
        assert other.get(doc_id)["content"] == "version two"
        # Per-object only, as documented: this object's
        # cache still serves its own last-seen version.
        assert hug.get(doc_id)["content"] == "version one"  # stale hit
        hug.upsert_memory("version three", memory_id=doc_id)
        assert hug.get(doc_id)["content"] == "version three"
    finally:
        hug.close()
        other.close()


def test_cached_get_is_pure_for_health(tmp_path):
    hug = _huginn(tmp_path, cache_size=4)
    try:
        doc_id = hug.upsert_memory("pure thought")
        hug.get(doc_id)
        health_before = hug.health()
        hug.get(doc_id)
        hug.get(doc_id)
        assert hug.health() == health_before
        assert hug.cache_stats["hits"] == 2
    finally:
        hug.close()


class _CountingBackend:
    """A toy backend proving the facade cache is
    backend-agnostic (the Qdrant road rides the same
    facade): every ``get`` that reaches it is counted."""

    kind = "toy"

    def __init__(self):
        self.docs: dict[int, dict[str, Any]] = {}
        self.get_calls = 0

    def get(self, memory_id):
        self.get_calls += 1
        doc = self.docs.get(int(memory_id))
        return dict(doc) if doc is not None else None

    def upsert(self, content, *, category, importance, tags,
               emotional_valence, memory_id=None):
        doc_id = int(memory_id) if memory_id is not None else (
            max(self.docs, default=0) + 1
        )
        self.docs[doc_id] = {
            "id": doc_id,
            "content": content,
            "category": category,
            "importance": importance,
            "tags": list(tags),
            "emotional_valence": emotional_valence,
        }
        return doc_id

    def delete(self, memory_id):
        return self.docs.pop(int(memory_id), None) is not None

    def secure_forget(self, memory_id):
        return self.delete(memory_id)


def test_facade_cache_covers_any_backend(tmp_path):
    hug = _huginn(tmp_path, cache_size=2)
    try:
        backend = _CountingBackend()
        hug._backend = backend  # the facade's own seam
        doc_id = hug.upsert_memory("toy thought")
        assert hug.get(doc_id)["content"] == "toy thought"  # miss
        assert hug.get(doc_id)["content"] == "toy thought"  # hit
        assert backend.get_calls == 1
        hug.upsert_memory("toy thought v2", memory_id=doc_id)
        assert hug.get(doc_id)["content"] == "toy thought v2"
        assert backend.get_calls == 2
    finally:
        hug.close()


def test_record_doc_states_the_contract():
    root = _repo_root()
    if root is None:
        pytest.skip("not running inside a repo checkout")
    record = (root / "docs" / "WARM_CACHES.md").read_text()
    assert "RM-063" in record
    assert "`cache_size`" in record
    assert "`cache_stats`" in record
    assert "per-object" in record
