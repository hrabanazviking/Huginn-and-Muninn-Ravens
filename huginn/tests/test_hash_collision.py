"""RM-047 — Hash-collision honesty for huginn.

Threat TH-08 (docs/THREAT_MODEL.md): Huginn's idempotent
store keys identity on (content_hash, category) locally, and
on the derived point id — the content hash truncated to
64 bits — on Qdrant. The hash is SHA-256, so a natural
full-hash collision is implausible, but the pre-slice code
trusted the hash alone on both roads:

* local: a row found by (hash, category) was updated in
  place with the incoming content — two different memories
  under one hash would have silently become one, the first
  one's content overwritten;
* Qdrant: a derived-id upsert blindly overwrote whatever
  point already held the id, and the truncation widened the
  surface from 256 bits to 64. The derivation also used the
  full unsigned 64 bits, so roughly half of derived ids
  exceeded the facade's ``memory_id`` ceiling of 2⁶³−1 and
  could never be fetched back through ``HuginnMemory.get``
  (the RM-046 discovery this slice inherits).

The fix, both roads: a length+content double check wherever
a hash hit is about to be treated as the same memory. Local:
the found row's content length and exact content must equal
the incoming content before the update proceeds. Qdrant:
before a derived-id upsert, the existing point is retrieved
and hygiene-checked (RM-046); its category, content length
and exact content must match, or the upsert is refused with
a typed error naming only the id, and the held point is
left untouched. Derived ids are also masked to 63 bits, so
every derived id fits the facade ceiling. An explicit
``memory_id`` is the caller's own addressing and keeps its
replace semantics on both roads — it is not the idempotent
path and is not collision-checked.

Collisions are forced the way the roadmap's acceptance
names: an injected hash function — the backends' module
``_content_hash`` replaced with a constant — plus, for the
Qdrant truncation surface, a point planted at a target's
derived id carrying different content under its own correct
hash. All Qdrant proof is against fake clients; a live
Qdrant round-trip stays NOT PROVEN.
"""

import sys
import types

import pytest

import huginn.local_backend
import huginn.qdrant_backend
from huginn import HuginnConfig, HuginnMemory
from huginn.errors import HuginnBackendError, HuginnValidationError
from huginn.qdrant_backend import QdrantBackend, _content_hash, _derived_id
from huginn.text import HashingEmbedder

FORCED_HASH = "e" * 64
CEILING = 2**63 - 1


@pytest.fixture
def forced_local_hash(monkeypatch):
    monkeypatch.setattr(
        huginn.local_backend, "_content_hash", lambda content, category: FORCED_HASH
    )


@pytest.fixture
def forced_qdrant_hash(monkeypatch):
    monkeypatch.setattr(
        huginn.qdrant_backend,
        "_content_hash",
        lambda content, category: FORCED_HASH,
    )


def _local(tmp_path, **kw):
    return HuginnMemory(
        HuginnConfig(
            backend="local", local_db_path=str(tmp_path / "h.db"), **kw
        )
    )


# ─── local backend ────────────────────────────────────────────────────


def test_local_forced_collision_different_length_is_refused(
    forced_local_hash, tmp_path
):
    h = _local(tmp_path)
    try:
        first = h.upsert_memory("short", category="fact")
        with pytest.raises(HuginnValidationError) as caught:
            h.upsert_memory("a much longer different memory", category="fact")
        assert str(caught.value) == (
            "content hash collision: a different memory already "
            f"holds this content hash (id {first}); refusing to merge"
        )
        assert h.get(first)["content"] == "short"
        assert h.health()["documents"] == 1
    finally:
        h.close()


def test_local_forced_collision_same_length_is_refused(
    forced_local_hash, tmp_path
):
    h = _local(tmp_path)
    try:
        first = h.upsert_memory("alpha", category="fact")
        with pytest.raises(HuginnValidationError):
            h.upsert_memory("alphe", category="fact")
        assert h.get(first)["content"] == "alpha"
        assert h.health()["documents"] == 1
    finally:
        h.close()


def test_local_true_duplicate_under_forced_hash_still_merges(
    forced_local_hash, tmp_path
):
    h = _local(tmp_path)
    try:
        first = h.upsert_memory("same words", category="fact", importance=5)
        again = h.upsert_memory("same words", category="fact", importance=9)
        assert again == first
        assert h.get(first)["importance"] == 9
        assert h.health()["documents"] == 1
    finally:
        h.close()


def test_local_forced_hash_different_category_is_not_a_collision(
    forced_local_hash, tmp_path
):
    h = _local(tmp_path)
    try:
        a = h.upsert_memory("shared text", category="fact")
        b = h.upsert_memory("other text", category="note")
        assert a != b
        assert h.health()["documents"] == 2
    finally:
        h.close()


def test_local_free_explicit_id_on_a_collision_is_not_a_clash(
    forced_local_hash, tmp_path
):
    h = _local(tmp_path)
    try:
        first = h.upsert_memory("first memory", category="fact")
        # memory_id 99 is free and the forced hash matches the
        # first memory's row — but the content differs, so the
        # refusal is the collision error, not the id-clash one.
        with pytest.raises(HuginnValidationError) as caught:
            h.upsert_memory(
                "different memory", category="fact", memory_id=99
            )
        assert "content hash collision" in str(caught.value)
        assert first == 1
        assert h.health()["documents"] == 1
    finally:
        h.close()


def test_local_explicit_id_replace_keeps_its_semantics(
    forced_local_hash, tmp_path
):
    h = _local(tmp_path)
    try:
        first = h.upsert_memory("original text", category="fact")
        replaced = h.upsert_memory(
            "replacement text", category="fact", memory_id=first
        )
        assert replaced == first
        assert h.get(first)["content"] == "replacement text"
    finally:
        h.close()


# ─── Qdrant backend (fake clients only) ──────────────────────────────


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

    def count(self, collection_name):
        return _NS(count=len(self.points))

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


def test_derived_ids_always_fit_the_facade_ceiling():
    # Find, deterministically, a content whose pre-RM-047
    # (unmasked) derivation exceeded the ceiling — half of all
    # contents qualify — and show the masked derivation fits.
    over = None
    for i in range(100):
        raw = int.from_bytes(
            bytes.fromhex(_content_hash(f"content {i}", "fact")[:16]), "big"
        )
        if raw > CEILING:
            over = (f"content {i}", raw)
            break
    assert over is not None, "no over-ceiling content in 100 tries"
    content, raw = over
    derived = _derived_id(_content_hash(content, "fact"))
    assert derived == raw & CEILING
    assert derived <= CEILING
    for i in range(50):
        assert _derived_id(_content_hash(f"other {i}", "fact")) <= CEILING


def test_derived_upsert_is_fetchable_through_the_facade(
    monkeypatch, tmp_path
):
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
    h = HuginnMemory(config=cfg)
    try:
        # A content whose unmasked derivation was over the
        # ceiling: stored pre-RM-047, it could never have been
        # fetched through this facade. Now it round-trips.
        content = None
        for i in range(100):
            candidate = f"fetchable content {i}"
            raw = int.from_bytes(
                bytes.fromhex(_content_hash(candidate, "fact")[:16]), "big"
            )
            if raw > CEILING:
                content = candidate
                break
        assert content is not None
        mid = h.upsert_memory(content, category="fact")
        assert mid <= CEILING
        doc = h.get(mid)
        assert doc is not None and doc["content"] == content
    finally:
        h.close()


def test_qdrant_forced_collision_is_refused_and_point_untouched(
    forced_qdrant_hash,
):
    backend = _backend()
    try:
        first_id = backend.upsert(
            "first memory", category="fact", importance=5, tags=[],
            emotional_valence=0.0,
        )
        with pytest.raises(HuginnBackendError) as caught:
            backend.upsert(
                "a different and longer memory", category="fact",
                importance=5, tags=[], emotional_valence=0.0,
            )
        assert str(caught.value) == (
            "content hash collision: a different memory already "
            f"holds this content hash (id {first_id}); refusing to merge"
        )
        (point,) = backend._client.points.values()
        assert point.payload["content"] == "first memory"
        assert backend.count() == 1
    finally:
        backend.close()


def test_qdrant_true_duplicate_under_forced_hash_still_merges(
    forced_qdrant_hash,
):
    backend = _backend()
    try:
        first = backend.upsert(
            "same words", category="fact", importance=5, tags=[],
            emotional_valence=0.0,
        )
        again = backend.upsert(
            "same words", category="fact", importance=9, tags=[],
            emotional_valence=0.0,
        )
        assert again == first
        assert backend.get(first)["importance"] == 9
        assert backend.count() == 1
    finally:
        backend.close()


def test_qdrant_truncation_collision_with_a_planted_point_is_refused():
    backend = _backend()
    try:
        target = "the incoming memory"
        point_id = _derived_id(_content_hash(target, "fact"))
        planted_content = "planted different content"
        backend._client.points[point_id] = _NS(
            id=point_id,
            vector=[0.0] * 64,
            payload={
                "content": planted_content,
                "category": "fact",
                "importance": 5,
                "tags": [],
                "emotional_valence": 0.0,
                "content_hash": _content_hash(planted_content, "fact"),
            },
        )
        with pytest.raises(HuginnBackendError) as caught:
            backend.upsert(
                target, category="fact", importance=5, tags=[],
                emotional_valence=0.0,
            )
        assert "content hash collision" in str(caught.value)
        assert planted_content not in str(caught.value)
        assert (
            backend._client.points[point_id].payload["content"]
            == planted_content
        )
    finally:
        backend.close()


def test_qdrant_explicit_id_replace_keeps_its_semantics():
    backend = _backend()
    try:
        backend.upsert(
            "original text", category="fact", importance=5, tags=[],
            emotional_valence=0.0, memory_id=31,
        )
        replaced = backend.upsert(
            "replacement text", category="fact", importance=5, tags=[],
            emotional_valence=0.0, memory_id=31,
        )
        assert replaced == 31
        assert backend.get(31)["content"] == "replacement text"
    finally:
        backend.close()
