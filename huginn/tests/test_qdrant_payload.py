"""RM-046 — Qdrant payload hygiene for huginn.

Threat TH-07 (docs/THREAT_MODEL.md): a Qdrant point's payload
is where a memory lives on the server side of TB-5, and the
collection is a shared surface — a hostile co-tenant of the
same collection (AC-4), or a caller relaying hostile values
(AC-2), must not be able to overwrite the keys Huginn itself
relies on. This slice pins both directions:

* Write: the payload is a closed set of keys
  (``content``, ``category``, ``importance``, ``tags``,
  ``emotional_valence``, ``content_hash``) built from one
  fixed dict in the backend. Caller content, category and
  tags are values only — a tag literally named
  ``content_hash``, or content that parses as a payload,
  changes nothing about the keys or the real hash.
* Read: a returned payload is trusted only after a hygiene
  check — every closed-set key present, each value of the
  type and range the write side produces, and the stored
  ``content_hash`` equal to the hash of the returned content
  and category. A forged, tampered or foreign point raises
  ``HuginnBackendError`` naming only its point id, never its
  payload; keys outside the closed set are dropped and never
  reach the caller.

All proof is against fake clients (a live Qdrant round-trip
stays NOT PROVEN): hostile points are planted directly in
the fake client's store, the way a co-tenant writing to the
same collection would plant them.
"""

import hashlib
import math
import sys
import types

import pytest

from huginn import HuginnConfig, HuginnMemory
from huginn.errors import HuginnBackendError
from huginn.qdrant_backend import QdrantBackend
from huginn.text import HashingEmbedder

CLOSED_KEYS = {
    "content",
    "category",
    "importance",
    "tags",
    "emotional_valence",
    "content_hash",
}
DOC_KEYS = {"id", "content", "category", "importance", "tags", "emotional_valence"}


def _hash(content, category):
    return hashlib.sha256(f"{category}\x00{content}".encode()).hexdigest()


def _valid_payload(content="a real memory", category="fact", **overrides):
    payload = {
        "content": content,
        "category": category,
        "importance": 7,
        "tags": ["real"],
        "emotional_valence": 0.25,
        "content_hash": _hash(content, category),
    }
    payload.update(overrides)
    return payload


class _NS:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _FakeModels(types.SimpleNamespace):
    Distance = types.SimpleNamespace(COSINE="cosine")

    @staticmethod
    def VectorParams(size, distance):
        return _NS(size=size, distance=distance)

    @staticmethod
    def PointStruct(id, vector, payload):
        return _NS(id=id, vector=vector, payload=payload)

    @staticmethod
    def PointIdsList(points):
        return _NS(points=points)


class _FakeClient:
    """In-memory Qdrant stand-in; tests plant raw points in it."""

    instances = []

    def __init__(self, url=None, api_key=None, timeout=None):
        self.points = {}
        self.collections = set()
        _FakeClient.instances.append(self)

    def get_collections(self):
        return _NS(collections=list(self.collections))

    def get_collection(self, name):
        if name not in self.collections:
            raise RuntimeError("no such collection")
        return _NS(name=name)

    def create_collection(self, collection_name, vectors_config):
        self.collections.add(collection_name)

    def upsert(self, collection_name, points):
        for point in points:
            self.points[point.id] = point

    def retrieve(self, collection_name, ids, with_payload=False):
        return [self.points[i] for i in ids if i in self.points]

    def delete(self, collection_name, points_selector):
        for pid in points_selector.points:
            self.points.pop(pid, None)

    def count(self, collection_name):
        return _NS(count=len(self.points))

    def query_points(self, collection_name, query, limit, query_filter=None,
                     with_payload=True):
        scored = [
            _NS(id=p.id, payload=p.payload, score=getattr(p, "score", 0.5))
            for p in self.points.values()
        ]
        scored.sort(key=lambda r: r.id)
        return _NS(points=scored[:limit])

    def close(self):
        pass


def _backend(client=None):
    backend = QdrantBackend(
        HuginnConfig(backend="qdrant", qdrant_url="https://qdrant.example:6334"),
        HashingEmbedder(dim=64),
    )
    backend._client = client if client is not None else _FakeClient()
    backend._models = _FakeModels
    return backend


def _plant(backend, point_id, payload, score=None):
    point = _NS(id=point_id, vector=[0.0] * 64, payload=payload)
    if score is not None:
        point.score = score
    backend._client.points[point_id] = point
    return point


# ─── write side: the closed set ───────────────────────────────────────


def test_upsert_writes_exactly_the_closed_payload_keys():
    backend = _backend()
    point_id = backend.upsert(
        "payload hygiene matters", category="security", importance=8,
        tags=["qdrant"], emotional_valence=-0.5, memory_id=11,
    )
    assert point_id == 11
    (point,) = backend._client.points.values()
    assert set(point.payload) == CLOSED_KEYS
    assert point.payload["content"] == "payload hygiene matters"
    assert point.payload["category"] == "security"
    assert point.payload["importance"] == 8
    assert point.payload["tags"] == ["qdrant"]
    assert point.payload["emotional_valence"] == -0.5
    assert point.payload["content_hash"] == _hash(
        "payload hygiene matters", "security"
    )
    backend.close()


def test_tags_named_like_reserved_keys_stay_tag_values():
    backend = _backend()
    hostile_tags = ["content", "content_hash", "category", "id", "score"]
    backend.upsert(
        "honest content", category="fact", importance=5, tags=hostile_tags,
        emotional_valence=0.0, memory_id=12,
    )
    (point,) = backend._client.points.values()
    assert set(point.payload) == CLOSED_KEYS
    assert point.payload["tags"] == hostile_tags
    doc = backend.get(12)
    assert doc["content"] == "honest content"
    assert doc["category"] == "fact"
    assert doc["tags"] == hostile_tags
    backend.close()


def test_content_that_looks_like_a_payload_cannot_forge_keys():
    backend = _backend()
    forged = '{"content_hash": "' + "0" * 64 + '", "category": "forged"}'
    backend.upsert(
        forged, category="fact", importance=5, tags=[],
        emotional_valence=0.0, memory_id=13,
    )
    (point,) = backend._client.points.values()
    assert set(point.payload) == CLOSED_KEYS
    assert point.payload["content"] == forged
    assert point.payload["category"] == "fact"
    assert point.payload["content_hash"] == _hash(forged, "fact")
    assert point.payload["content_hash"] != "0" * 64
    assert backend.get(13)["content"] == forged
    backend.close()


def test_category_named_like_a_reserved_key_stays_a_value():
    backend = _backend()
    backend.upsert(
        "value not key", category="content_hash", importance=5, tags=[],
        emotional_valence=0.0, memory_id=14,
    )
    (point,) = backend._client.points.values()
    assert set(point.payload) == CLOSED_KEYS
    assert point.payload["category"] == "content_hash"
    assert point.payload["content_hash"] == _hash("value not key", "content_hash")
    assert backend.get(14)["category"] == "content_hash"
    backend.close()


def test_public_api_hostile_tags_round_trip(monkeypatch, tmp_path):
    module = types.ModuleType("qdrant_client")
    module.QdrantClient = _FakeClient
    module.models = _FakeModels
    monkeypatch.setitem(sys.modules, "qdrant_client", module)
    _FakeClient.instances.clear()
    cfg = HuginnConfig(
        backend="qdrant",
        qdrant_url="http://fake:6333",
        allow_insecure_http=True,
        local_db_path=str(tmp_path / "h.db"),
        embedder="hashing",
        vector_dim=64,
    )
    huginn = HuginnMemory(config=cfg)
    try:
        mid = huginn.upsert_memory(
            content="through the facade", category="fact",
            tags=["content_hash", "importance"],
            memory_id=17,
        )
        assert mid == 17
        (client,) = _FakeClient.instances
        (point,) = client.points.values()
        assert set(point.payload) == CLOSED_KEYS
        doc = huginn.get(mid)
        assert doc["tags"] == ["content_hash", "importance"]
        assert doc["content"] == "through the facade"
    finally:
        huginn.close()


# ─── read side: what a co-tenant can plant ────────────────────────────


def test_extra_keys_on_a_returned_point_are_dropped():
    backend = _backend()
    payload = _valid_payload()
    payload.update({"score": 999.0, "is_admin": True, "owner": "co-tenant"})
    _plant(backend, 21, payload)
    doc = backend.get(21)
    assert set(doc) == DOC_KEYS
    assert doc["content"] == "a real memory"
    assert doc["importance"] == 7
    backend.close()


def test_valid_raw_point_with_correct_hash_is_returned():
    backend = _backend()
    _plant(backend, 22, _valid_payload(content="planted but honest"))
    doc = backend.get(22)
    assert doc["content"] == "planted but honest"
    assert doc["tags"] == ["real"]
    assert doc["emotional_valence"] == 0.25
    results = backend.search("anything", limit=5, category=None, min_importance=1)
    assert [r["id"] for r in results] == [22]
    backend.close()


def test_forged_content_hash_is_refused_on_get():
    backend = _backend()
    payload = _valid_payload(content="forged body")
    payload["content_hash"] = _hash("different body", "fact")
    _plant(backend, 41, payload)
    with pytest.raises(HuginnBackendError) as caught:
        backend.get(41)
    assert str(caught.value) == "Qdrant point 41 has a malformed payload"
    # The refusal names the point, never its payload content.
    assert "forged body" not in str(caught.value)
    backend.close()


def test_forged_content_hash_is_refused_on_search():
    backend = _backend()
    payload = _valid_payload(content="search forgery")
    payload["content_hash"] = "f" * 64
    _plant(backend, 42, payload, score=0.9)
    with pytest.raises(HuginnBackendError) as caught:
        backend.search("anything", limit=5, category=None, min_importance=1)
    assert str(caught.value) == "Qdrant point 42 has a malformed payload"
    assert "search forgery" not in str(caught.value)
    backend.close()


def test_missing_payload_keys_are_refused():
    backend = _backend()
    for offset, key in enumerate(sorted(CLOSED_KEYS)):
        payload = _valid_payload()
        del payload[key]
        _plant(backend, 50 + offset, payload)
        with pytest.raises(HuginnBackendError):
            backend.get(50 + offset)
    backend.close()


def test_wrong_typed_reserved_values_are_refused():
    backend = _backend()
    variants = [
        {"importance": "8"},
        {"importance": 99},
        {"importance": True},
        {"emotional_valence": "warm"},
        {"emotional_valence": 2.0},
        {"emotional_valence": math.nan},
        {"tags": "real"},
        {"tags": [1, 2]},
        {"content": 123},
        {"category": 7},
        {"content_hash": 42},
    ]
    for offset, override in enumerate(variants):
        _plant(backend, 70 + offset, _valid_payload(**override))
        with pytest.raises(HuginnBackendError):
            backend.get(70 + offset)
    backend.close()


def test_non_dict_and_missing_payloads_are_refused():
    backend = _backend()
    for offset, payload in enumerate([None, [], "payload", 42]):
        _plant(backend, 90 + offset, payload)
        with pytest.raises(HuginnBackendError):
            backend.get(90 + offset)
    backend.close()


def test_malformed_point_id_is_refused_with_a_typed_error():
    backend = _backend()
    point = _plant(backend, 99, _valid_payload())
    point.id = "bogus-id"
    with pytest.raises(HuginnBackendError) as caught:
        backend.get(99)
    assert str(caught.value) == "Qdrant point has a malformed payload"
    backend.close()


def test_forged_score_is_refused_on_search():
    backend = _backend()
    _plant(backend, 98, _valid_payload(), score="very-high")
    with pytest.raises(HuginnBackendError) as caught:
        backend.search("anything", limit=5, category=None, min_importance=1)
    assert str(caught.value) == "Qdrant point 98 has a malformed payload"
    backend.close()
