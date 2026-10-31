"""Qdrant backend against a fake client; auto-mode fallback roads.

No real server is used: a stand-in ``qdrant_client`` module is placed
in sys.modules. The fake computes true cosine over stored vectors and
honours the filter shapes the backend builds, so the backend's
mapping code is genuinely exercised.
"""

import math
import sys
import types

import pytest

from huginn import HuginnConfig, HuginnMemory
from huginn.errors import HuginnBackendError, HuginnConfigurationError

# ─── Fake qdrant_client ───────────────────────────────────────────────

class _NS:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class FakeModels(types.SimpleNamespace):
    Distance = types.SimpleNamespace(COSINE="cosine")

    @staticmethod
    def VectorParams(size, distance):
        return _NS(size=size, distance=distance)

    @staticmethod
    def PointStruct(id, vector, payload):
        return _NS(id=id, vector=vector, payload=payload)

    @staticmethod
    def FieldCondition(key, match=None, range=None):
        return _NS(key=key, match=match, range=range)

    @staticmethod
    def MatchValue(value):
        return _NS(value=value)

    @staticmethod
    def Range(gte=None):
        return _NS(gte=gte)

    @staticmethod
    def Filter(must):
        return _NS(must=must)

    @staticmethod
    def PointIdsList(points):
        return _NS(points=points)


def _matches(payload, flt):
    if flt is None:
        return True
    for cond in flt.must:
        if cond.match is not None and payload.get(cond.key) != cond.match.value:
            return False
        if cond.range is not None and not (payload.get(cond.key, 0) >= (cond.range.gte or 0)):
            return False
    return True


def _cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class FakeQdrantClient:
    instances = []

    def __init__(self, url=None, api_key=None, timeout=None):
        self.url = url
        self.points = {}
        self.collections = set()
        FakeQdrantClient.instances.append(self)

    def get_collections(self):
        return _NS(collections=list(self.collections))

    def get_collection(self, name):
        if name not in self.collections:
            raise RuntimeError("no such collection")
        return _NS(name=name)

    def create_collection(self, collection_name, vectors_config):
        self.collections.add(collection_name)

    def upsert(self, collection_name, points):
        for p in points:
            self.points[p.id] = p

    def retrieve(self, collection_name, ids, with_payload=False):
        return [self.points[i] for i in ids if i in self.points]

    def delete(self, collection_name, points_selector):
        for pid in points_selector.points:
            self.points.pop(pid, None)

    def count(self, collection_name):
        return _NS(count=len(self.points))

    def query_points(self, collection_name, query, limit, query_filter=None, with_payload=True):
        scored = []
        for p in self.points.values():
            if not _matches(p.payload, query_filter):
                continue
            scored.append(_NS(id=p.id, payload=p.payload, score=_cosine(query, p.vector)))
        scored.sort(key=lambda r: r.score, reverse=True)
        return _NS(points=scored[:limit])

    def close(self):
        pass


@pytest.fixture
def fake_qdrant(monkeypatch):
    module = types.ModuleType("qdrant_client")
    module.QdrantClient = FakeQdrantClient
    module.models = FakeModels
    monkeypatch.setitem(sys.modules, "qdrant_client", module)
    FakeQdrantClient.instances.clear()
    return module


@pytest.fixture
def dead_qdrant(monkeypatch):
    """A qdrant_client whose client always fails to reach a server."""
    module = types.ModuleType("qdrant_client")

    class DeadClient:
        def __init__(self, **kw):
            pass

        def get_collections(self):
            raise ConnectionError("connection refused")

    module.QdrantClient = DeadClient
    module.models = FakeModels
    monkeypatch.setitem(sys.modules, "qdrant_client", module)
    return module


def _cfg(tmp_path, **kw):
    base = {
        "backend": "qdrant",
        "qdrant_url": "http://fake:6333",
        "local_db_path": str(tmp_path / "h.db"),
        "embedder": "hashing",
        "vector_dim": 64,
    }
    base.update(kw)
    return HuginnConfig(**base)


def test_explicit_qdrant_round_trip(fake_qdrant, tmp_path):
    h = HuginnMemory(config=_cfg(tmp_path))
    mid = h.upsert_memory(
        content="semantic vectors over a fake server",
        category="test",
        importance=8,
        tags=["fake"],
        memory_id=7,
    )
    assert mid == 7
    h.upsert_memory(content="entirely different topic about cooking", category="food")
    results = h.search(query_text="semantic vectors fake", limit=2)
    assert results and results[0]["id"] == 7
    assert results[0]["tags"] == ["fake"]
    assert h.get(7)["category"] == "test"
    filtered = h.search(query_text="cooking", category="food")
    assert [r["category"] for r in filtered] == ["food"]
    assert h.health()["status"] == "healthy"
    assert h.health()["documents"] == 2
    assert h.delete(7) is True
    assert h.get(7) is None
    h.close()


def test_derived_id_is_deterministic(fake_qdrant, tmp_path):
    h = HuginnMemory(config=_cfg(tmp_path))
    a = h.upsert_memory(content="same words", category="fact")
    b = h.upsert_memory(content="same words", category="fact")
    assert a == b
    assert h.health()["documents"] == 1
    h.close()


def test_explicit_qdrant_unreachable_is_loud(dead_qdrant, tmp_path):
    h = HuginnMemory(config=_cfg(tmp_path))
    with pytest.raises(HuginnBackendError):
        h.upsert_memory(content="nowhere to land", category="test")
    health = h.health()
    assert health["status"] == "unhealthy"
    h.close()


def test_auto_falls_back_to_local(dead_qdrant, tmp_path):
    cfg = HuginnConfig(
        backend="auto",
        qdrant_url="http://dead:6333",
        local_db_path=str(tmp_path / "h.db"),
    )
    h = HuginnMemory(config=cfg)
    mid = h.upsert_memory(content="fallback memories still land", category="fact")
    assert isinstance(mid, int)
    results = h.search(query_text="fallback memories")
    assert results and results[0]["id"] == mid
    health = h.health()
    assert health["status"] == "degraded"
    assert health["backend"] == "local"
    assert "fallback_reason" in health
    h.close()


def test_auto_falls_back_when_client_missing(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "qdrant_client", None)  # import raises
    cfg = HuginnConfig(
        backend="auto", local_db_path=str(tmp_path / "h.db")
    )
    h = HuginnMemory(config=cfg)
    h.upsert_memory(content="no client package, still fine", category="fact")
    assert h.health()["backend"] == "local"
    h.close()


def test_explicit_qdrant_missing_client_is_configuration_error(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "qdrant_client", None)
    h = HuginnMemory(config=_cfg(tmp_path))
    with pytest.raises(HuginnConfigurationError):
        h.upsert_memory(content="x", category="fact")
    h.close()
