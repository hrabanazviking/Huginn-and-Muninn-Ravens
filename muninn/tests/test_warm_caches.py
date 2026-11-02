"""RM-063 — Warm-cache pins for muninn.

The optional bounded in-memory cache for ``get_node``
(record ``docs/WARM_CACHES.md``): off by default
(``cache_size=0``, every call reads the store — the
pre-RM-063 behaviour), LRU-bounded when on, counted in
the dedicated ``cache_stats`` property (never in the
pinned-pure ``health()``/``stats()`` snapshots), and
invalidated by every write through the same object, so
a hit is never stale for this object's own writes. The
cache is per-object only — the staleness test below
pins that documented window instead of pretending it
away: a write through another object is not seen until
eviction or an own write to that id.
"""

import sqlite3
from pathlib import Path

import pytest

from muninn import HebbianMemory, MuninnConfig
from muninn.errors import MuninnConfigurationError


def _mem(tmp_path, **overrides):
    overrides.setdefault("db_path", str(tmp_path / "m.db"))
    return HebbianMemory(MuninnConfig(**overrides))


def _repo_root():
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "RAVENS_ROADMAP_2026-10-31.md").is_file():
            return parent
    return None


def test_cache_is_disabled_by_default(tmp_path):
    mem = _mem(tmp_path)
    try:
        assert mem.config.cache_size == 0
        node_id = mem.remember("uncached raven")
        assert mem.get_node(node_id).content == "uncached raven"
        assert mem.get_node(node_id).content == "uncached raven"
        stats = mem.cache_stats
        assert stats == {
            "enabled": False,
            "size": 0,
            "cap": 0,
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "hit_rate": 0.0,
        }
        # Disabled means a second opener's write is seen at once.
        other = _mem(tmp_path)
        try:
            other.update(node_id, content="seen immediately")
        finally:
            other.close()
        assert mem.get_node(node_id).content == "seen immediately"
    finally:
        mem.close()


def test_cache_size_validation_is_typed(tmp_path):
    with pytest.raises(MuninnConfigurationError) as exc:
        MuninnConfig(db_path=str(tmp_path / "x.db"), cache_size=-1)
    assert str(exc.value) == "cache_size must be >= 0"
    with pytest.raises(MuninnConfigurationError):
        MuninnConfig(db_path=str(tmp_path / "x.db"), cache_size="ten")


def test_hit_miss_accounting_is_exact(tmp_path):
    mem = _mem(tmp_path, cache_size=4)
    try:
        a = mem.remember("first raven")
        b = mem.remember("second raven")
        assert mem.get_node(a).content == "first raven"  # miss
        assert mem.get_node(a).content == "first raven"  # hit
        assert mem.get_node(b).content == "second raven"  # miss
        assert mem.get_node(a).content == "first raven"  # hit
        stats = mem.cache_stats
        assert stats["enabled"] is True
        assert stats["cap"] == 4
        assert stats["size"] == 2
        assert stats["hits"] == 2
        assert stats["misses"] == 2
        assert stats["evictions"] == 0
        assert stats["hit_rate"] == 0.5
    finally:
        mem.close()


def test_a_miss_is_never_cached(tmp_path):
    mem = _mem(tmp_path, cache_size=4)
    try:
        assert mem.get_node(424242) is None
        assert mem.get_node(424242) is None
        stats = mem.cache_stats
        assert stats["misses"] == 2
        assert stats["hits"] == 0
        assert stats["size"] == 0
    finally:
        mem.close()


def test_cache_is_bounded_with_lru_eviction(tmp_path):
    mem = _mem(tmp_path, cache_size=2)
    try:
        a = mem.remember("lru one")
        b = mem.remember("lru two")
        c = mem.remember("lru three")
        mem.get_node(a)  # miss, cache [a]
        mem.get_node(b)  # miss, cache [a, b]
        mem.get_node(a)  # hit,  cache [b, a]
        mem.get_node(c)  # miss, evicts b (the LRU entry)
        stats = mem.cache_stats
        assert stats["size"] == 2
        assert stats["evictions"] == 1
        assert mem.get_node(a) is not None  # hit — still warm
        assert mem.cache_stats["hits"] == 2
        mem.get_node(b)  # miss — b was evicted
        assert mem.cache_stats["misses"] == 4
    finally:
        mem.close()


def test_update_and_move_invalidate(tmp_path):
    mem = _mem(tmp_path, cache_size=4)
    try:
        node_id = mem.remember("before update", path="old")
        assert mem.get_node(node_id).content == "before update"
        assert mem.get_node(node_id).content == "before update"  # hit
        mem.update(node_id, content="after update")
        node = mem.get_node(node_id)  # miss — invalidated
        assert node.content == "after update"
        assert mem.cache_stats["misses"] == 2
        mem.move(node_id, "new/path")
        assert mem.get_node(node_id).path == "new/path"
    finally:
        mem.close()


def test_activate_and_activate_batch_invalidate(tmp_path):
    mem = _mem(tmp_path, cache_size=4)
    try:
        a = mem.remember("activated one")
        b = mem.remember("activated two")
        assert mem.get_node(a).access_count == 0
        assert mem.get_node(a).access_count == 0  # hit, still 0
        mem.activate(a)
        assert mem.get_node(a).access_count == 1  # miss — fresh count
        assert mem.get_node(b).access_count == 0
        mem.activate_batch([a, b])
        assert mem.get_node(a).access_count == 2
        assert mem.get_node(b).access_count == 1
    finally:
        mem.close()


def test_retrieve_touch_invalidates(tmp_path):
    mem = _mem(tmp_path, cache_size=4)
    try:
        node_id = mem.remember("touched raven")
        assert mem.get_node(node_id).access_count == 0
        mem.retrieve(query="touched", touch=True)
        assert mem.get_node(node_id).access_count == 1
    finally:
        mem.close()


def test_forget_and_secure_forget_invalidate(tmp_path):
    mem = _mem(tmp_path, cache_size=4)
    try:
        a = mem.remember("plain forgotten")
        b = mem.remember("securely forgotten")
        assert mem.get_node(a) is not None
        assert mem.get_node(b) is not None
        assert mem.cache_stats["size"] == 2
        mem.forget(a)
        assert mem.get_node(a) is None
        mem.secure_forget(b)
        assert mem.get_node(b) is None
        assert mem.cache_stats["size"] == 0
    finally:
        mem.close()


def test_remember_many_and_backpressure_invalidate(tmp_path):
    mem = _mem(tmp_path, cache_size=8, max_nodes=2)
    try:
        low = mem.remember("low value", importance=1)
        high = mem.remember("high value", importance=9)
        assert mem.get_node(low) is not None  # cached
        assert mem.get_node(high) is not None  # cached
        ids = mem.remember_many(
            [{"content": "batch arrival", "importance": 10}]
        )
        # Backpressure pruned the lowest-value node (low);
        # its cached copy must not survive the prune.
        assert mem.get_node(low) is None
        assert mem.get_node(ids[0]).content == "batch arrival"
        assert mem.get_node(high) is not None
    finally:
        mem.close()


def test_caller_mutation_never_poisons_the_cache(tmp_path):
    mem = _mem(tmp_path, cache_size=4)
    try:
        node_id = mem.remember(
            {"nested": ["original"]},
            tags=["one"],
            metadata={"k": "v"},
        )
        node = mem.get_node(node_id)
        node.tags.append("evil")
        node.metadata["k"] = "changed"
        node.content["nested"].append("evil")
        fresh = mem.get_node(node_id)  # a hit — and clean
        assert mem.cache_stats["hits"] >= 1
        assert fresh.tags == ["one"]
        assert fresh.metadata == {"k": "v"}
        assert fresh.content == {"nested": ["original"]}
    finally:
        mem.close()


def test_per_object_staleness_is_the_documented_window(tmp_path):
    mem = _mem(tmp_path, cache_size=4)
    other = _mem(tmp_path, cache_size=4)
    try:
        node_id = mem.remember("version one")
        assert mem.get_node(node_id).content == "version one"  # miss
        assert mem.get_node(node_id).content == "version one"  # hit
        # A write through ANOTHER object is not seen by this
        # object's cache — per-object only, as documented.
        other.update(node_id, content="version two")
        assert other.get_node(node_id).content == "version two"
        assert mem.get_node(node_id).content == "version one"  # stale hit
        # This object's own write to the id ends the window.
        mem.update(node_id, content="version three")
        assert mem.get_node(node_id).content == "version three"
    finally:
        mem.close()
        other.close()


def test_cached_get_is_pure_for_health_and_stats(tmp_path):
    mem = _mem(tmp_path, cache_size=4)
    try:
        node_id = mem.remember("pure raven")
        mem.get_node(node_id)
        health_before = mem.health()
        stats_before = mem.stats()
        mem.get_node(node_id)
        mem.get_node(node_id)
        assert mem.health() == health_before
        assert mem.stats() == stats_before
        # The accounting exists — in its own accessor only.
        assert not any("cache" in key for key in mem.health())
        assert not any("cache" in key for key in mem.stats())
        assert mem.cache_stats["hits"] == 2
    finally:
        mem.close()


def test_a_hit_does_not_read_the_store(tmp_path):
    # Proven by changing the row behind the object's back
    # with a raw connection: the hit serves the cached copy
    # (no store read), the next miss — after this object's
    # own invalidation — serves the raw truth.
    mem = _mem(tmp_path, cache_size=4)
    try:
        node_id = mem.remember("cached truth")
        assert mem.get_node(node_id).content == "cached truth"
        raw = sqlite3.connect(str(tmp_path / "m.db"))
        try:
            raw.execute(
                "UPDATE nodes SET content = 'raw truth' WHERE id = ?",
                (node_id,),
            )
            raw.commit()
        finally:
            raw.close()
        assert mem.get_node(node_id).content == "cached truth"  # hit
        mem.activate(node_id)  # own write invalidates
        assert mem.get_node(node_id).content == "raw truth"  # miss
    finally:
        mem.close()


def test_record_doc_states_the_contract():
    root = _repo_root()
    if root is None:
        pytest.skip("not running inside a repo checkout")
    record = (root / "docs" / "WARM_CACHES.md").read_text()
    assert "RM-063" in record
    assert "`cache_size`" in record
    assert "`cache_stats`" in record
    assert "per-object" in record
