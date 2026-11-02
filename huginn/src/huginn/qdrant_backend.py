"""Huginn's Qdrant backend (optional extra: ``huginn[qdrant]``).

The client is imported lazily and the server is only ever contacted
on first use — importing this module, or constructing the backend,
touches no network. All Qdrant/model types are resolved at call time
so tests can stand a fake client in ``sys.modules``.

Identity: a point's id is the caller's ``memory_id`` when given, else
derived deterministically from the content hash — re-upserting the
same memory naturally targets the same point, and identical content
in the same category is one point (idempotent, like the local store).

Hash-collision honesty (RM-047, threat TH-08): the derived id is
the content hash truncated and masked to 63 bits, so it always
fits the facade's ``memory_id`` ceiling. Before a derived-id
upsert overwrites anything, the point already at that id must
pass the length+content double check (same category, same
content length, the exact content); a different memory there is
a typed refusal, never a silent overwrite. See
``docs/HASH_COLLISION.md``.

Transport safety (RM-045, threat TH-06): the URL's scheme rule is
enforced at config construction (https for remote hosts, plain http
only for loopback or with an explicit opt-in). The API key is handed
only to the client constructor; every client exception this backend
wraps has the configured key scrubbed out of its text first
(:func:`scrub_api_key`), because the client's wording is not ours to
control and a server or proxy error can quote the credential back.

Payload hygiene (RM-046, threat TH-07): a point's payload keys are
a closed set (:data:`_PAYLOAD_KEYS`) written from a fixed dict in
:meth:`QdrantBackend.upsert` — caller content, category and tags are
values inside that dict, never keys, so no caller input can add or
overwrite a reserved key. On the way back, a returned payload is
trusted only after a hygiene check in
:meth:`QdrantBackend._point_to_doc`: every closed-set key present,
each value of its recorded type and range, and the stored
``content_hash`` equal to the hash of the returned content and
category. A point that fails — a hostile co-tenant's forgery, a
tampered point, a foreign point in the collection — raises a typed
error naming only the point id, never its payload; keys outside
the closed set are dropped and never reach the caller.
"""

from __future__ import annotations

import contextlib
import hashlib
import logging
import math
import threading
from typing import Any

from .config import HuginnConfig
from .errors import HuginnBackendError, HuginnConfigurationError
from .text import Embedder

logger = logging.getLogger("huginn.qdrant")


def scrub_api_key(text: str, api_key: str | None) -> str:
    """RM-045: ``text`` with every occurrence of the key removed.

    The replacement is a fixed placeholder, so a scrubbed error
    string still shows where the credential stood without
    carrying it. An unset or empty key scrubs nothing (an empty
    string would otherwise match everywhere).
    """
    if api_key:
        return text.replace(api_key, "***")
    return text


def _content_hash(content: str, category: str) -> str:
    """RM-047: the content hash — SHA-256 of category + content.

    The one hash function the idempotent-store path uses;
    tests inject a constant replacement for it to force the
    collisions SHA-256 makes implausible in nature (see
    docs/HASH_COLLISION.md).
    """
    return hashlib.sha256(f"{category}\x00{content}".encode()).hexdigest()


#: RM-047: derived point ids are masked to 63 bits, so a derived
#: id always fits the facade's ``memory_id`` ceiling
#: (2⁶³−1, the signed-integer id space Bifröst merges by). The
#: pre-RM-047 derivation used the full unsigned 64 bits, so
#: roughly half of derived ids could be stored but never
#: fetched through ``HuginnMemory.get`` (discovery recorded in
#: RM-046's slice entry). Masking makes the derived space
#: 63 bits wide; the collision surface that leaves is guarded
#: by the length+content double check in ``upsert`` below.
_DERIVED_ID_MASK = (1 << 63) - 1


def _derived_id(content_hash: str) -> int:
    return int.from_bytes(bytes.fromhex(content_hash[:16]), "big") & _DERIVED_ID_MASK


#: RM-046 (TH-07): the closed set of Qdrant payload keys, in the
#: order :meth:`QdrantBackend.upsert` writes them. Every payload
#: Huginn writes carries exactly these keys; every payload Huginn
#: reads must carry them all, correctly typed, with a matching
#: ``content_hash`` — see :meth:`QdrantBackend._point_to_doc`.
_PAYLOAD_KEYS = (
    "content",
    "category",
    "importance",
    "tags",
    "emotional_valence",
    "content_hash",
)


class QdrantBackend:
    """Qdrant vector store behind the shared backend shape."""

    kind = "qdrant"

    def __init__(self, config: HuginnConfig, embedder: Embedder):
        self.config = config
        self._embedder = embedder
        self._lock = threading.RLock()
        self._client: Any = None
        self._models: Any = None
        self._collection_ready = False
        self._closed = False

    def _scrub(self, exc: BaseException) -> str:
        """RM-045: a client exception's text, key-scrubbed."""
        return scrub_api_key(str(exc), self.config.qdrant_api_key)

    # ─── lazy client ──────────────────────────────────────────────────

    def _ensure_client(self) -> Any:
        if self._closed:
            raise HuginnBackendError("Huginn Qdrant backend is closed")
        if self._client is not None:
            return self._client
        try:
            import qdrant_client
            from qdrant_client import QdrantClient
        except ImportError as exc:
            raise HuginnConfigurationError(
                "backend='qdrant' needs the 'qdrant' extra: "
                "pip install 'huginn[qdrant]'"
            ) from exc
        self._models = qdrant_client.models
        self._client = QdrantClient(
            url=self.config.qdrant_url,
            api_key=self.config.qdrant_api_key,
            timeout=self.config.qdrant_timeout,
        )
        return self._client

    def ping(self) -> None:
        """Raise HuginnBackendError unless the server answers.

        A missing qdrant-client stays a HuginnConfigurationError —
        that is a packaging fact, not a server failure.
        """
        try:
            client = self._ensure_client()
            client.get_collections()
        except HuginnConfigurationError:
            raise
        except Exception as exc:
            raise HuginnBackendError(
                f"Qdrant at {self.config.qdrant_url} unreachable: {self._scrub(exc)}"
            ) from exc

    def _ensure_collection(self) -> None:
        if self._collection_ready:
            return
        client = self._ensure_client()
        models = self._models
        try:
            client.get_collection(self.config.collection_name)
        except Exception:
            try:
                client.create_collection(
                    collection_name=self.config.collection_name,
                    vectors_config=models.VectorParams(
                        size=self._embedder.dim,
                        distance=models.Distance.COSINE,
                    ),
                )
            except Exception as exc:
                raise HuginnBackendError(
                    f"could not create Qdrant collection "
                    f"{self.config.collection_name!r}: {self._scrub(exc)}"
                ) from exc
        self._collection_ready = True

    # ─── writes ───────────────────────────────────────────────────────

    def upsert(
        self,
        content: str,
        *,
        category: str,
        importance: int,
        tags: list[str],
        emotional_valence: float,
        memory_id: int | None = None,
    ) -> int:
        content_hash = _content_hash(content, category)
        point_id = int(memory_id) if memory_id is not None else _derived_id(content_hash)
        with self._lock:
            self.ping()
            self._ensure_collection()
            client = self._ensure_client()
            models = self._models
            if memory_id is None:
                # RM-047 (TH-08): the derived id is a truncated
                # hash, so an existing point at this id is the
                # same memory only after the length+content
                # double check — its payload (hygiene-checked
                # first, RM-046) must carry the same category,
                # a content of the same length, and that exact
                # content. A different memory at the derived id
                # — a full-hash collision, a truncation
                # collision, or a co-tenant's point — is refused
                # loudly instead of being silently overwritten.
                # An explicit memory_id is the caller's own
                # addressing and keeps its replace semantics.
                try:
                    existing = client.retrieve(
                        collection_name=self.config.collection_name,
                        ids=[point_id],
                        with_payload=True,
                    )
                except Exception as exc:
                    raise HuginnBackendError(
                        f"Qdrant upsert failed: {self._scrub(exc)}"
                    ) from exc
                if existing:
                    held = self._point_to_doc(existing[0])
                    if (
                        held["category"] != category
                        or len(held["content"]) != len(content)
                        or held["content"] != content
                    ):
                        raise HuginnBackendError(
                            "content hash collision: a different memory already "
                            f"holds this content hash (id {point_id}); "
                            "refusing to merge"
                        )
            # RM-046 (TH-07): the payload is this fixed dict —
            # exactly _PAYLOAD_KEYS, in that order. Caller values
            # (content, category, tags) are stored as values
            # only; nothing a caller supplies is ever used as a
            # payload key, so a reserved key cannot be added to
            # or overwritten through this road.
            payload = {
                "content": content,
                "category": category,
                "importance": importance,
                "tags": list(tags),
                "emotional_valence": emotional_valence,
                "content_hash": content_hash,
            }
            point = models.PointStruct(
                id=point_id,
                vector=self._embedder.embed(content),
                payload=payload,
            )
            try:
                client.upsert(
                    collection_name=self.config.collection_name,
                    points=[point],
                )
            except Exception as exc:
                raise HuginnBackendError(
                    f"Qdrant upsert failed: {self._scrub(exc)}"
                ) from exc
            return point_id

    def delete(self, memory_id: int) -> bool:
        with self._lock:
            self.ping()
            self._ensure_collection()
            client = self._ensure_client()
            models = self._models
            try:
                existing = client.retrieve(
                    collection_name=self.config.collection_name,
                    ids=[int(memory_id)],
                )
                if not existing:
                    return False
                client.delete(
                    collection_name=self.config.collection_name,
                    points_selector=models.PointIdsList(points=[int(memory_id)]),
                )
                return True
            except Exception as exc:
                raise HuginnBackendError(
                    f"Qdrant delete failed: {self._scrub(exc)}"
                ) from exc

    # ─── reads ────────────────────────────────────────────────────────

    def get(self, memory_id: int) -> dict[str, Any] | None:
        with self._lock:
            self.ping()
            self._ensure_collection()
            client = self._ensure_client()
            try:
                points = client.retrieve(
                    collection_name=self.config.collection_name,
                    ids=[int(memory_id)],
                    with_payload=True,
                )
            except Exception as exc:
                raise HuginnBackendError(
                    f"Qdrant retrieve failed: {self._scrub(exc)}"
                ) from exc
            if not points:
                return None
            return self._point_to_doc(points[0])

    def _point_to_doc(self, point: Any, score: float | None = None) -> dict[str, Any]:
        # RM-046 (TH-07): a returned point is not trusted by
        # shape alone. The collection is a shared surface — a
        # hostile co-tenant (AC-4) or a tampered server can hand
        # back a point whose payload overwrites a reserved key
        # with a wrong-typed or forged value, and the pre-slice
        # code coerced whatever it found (int("999") importance,
        # a string's characters as tags, foreign content under a
        # real memory's hash). Now the payload must pass the
        # hygiene check: a dict carrying every closed-set key,
        # each value of the type and range upsert writes, and a
        # content_hash matching the returned content+category.
        # Anything else is a typed refusal naming only the point
        # id — never payload content. Extra keys outside the
        # closed set are dropped: the doc below is built from
        # the closed set only, as it always was.
        try:
            point_id = int(point.id)
        except (AttributeError, TypeError, ValueError, OverflowError):
            raise HuginnBackendError(
                "Qdrant point has a malformed payload"
            ) from None
        raw_payload = getattr(point, "payload", None)
        payload: dict[str, Any] = raw_payload if isinstance(raw_payload, dict) else {}
        content = payload.get("content")
        category = payload.get("category")
        importance = payload.get("importance")
        tags = payload.get("tags")
        valence = payload.get("emotional_valence")
        stored_hash = payload.get("content_hash")
        valid = (
            isinstance(raw_payload, dict)
            and all(key in payload for key in _PAYLOAD_KEYS)
            and isinstance(content, str)
            and isinstance(category, str)
            and isinstance(importance, int)
            and not isinstance(importance, bool)
            and 1 <= importance <= 10
            and isinstance(tags, list)
            and all(isinstance(tag, str) for tag in tags)
            and isinstance(valence, (int, float))
            and not isinstance(valence, bool)
            and math.isfinite(float(valence))
            and -1.0 <= float(valence) <= 1.0
            and isinstance(stored_hash, str)
            and stored_hash == _content_hash(content, category)
            and (
                score is None
                or (
                    isinstance(score, (int, float))
                    and not isinstance(score, bool)
                    and math.isfinite(float(score))
                )
            )
        )
        if not valid:
            raise HuginnBackendError(
                f"Qdrant point {point_id} has a malformed payload"
            )
        doc = {
            "id": point_id,
            "content": payload["content"],
            "category": payload["category"],
            "importance": int(payload["importance"]),
            "tags": list(payload["tags"]),
            "emotional_valence": float(payload["emotional_valence"]),
        }
        if score is not None:
            doc["score"] = float(score)
        return doc

    def _build_filter(self, category: str | None, min_importance: int) -> Any:
        conditions = []
        models = self._models
        if category:
            conditions.append(
                models.FieldCondition(
                    key="category",
                    match=models.MatchValue(value=category),
                )
            )
        if min_importance > 1:
            conditions.append(
                models.FieldCondition(
                    key="importance",
                    range=models.Range(gte=min_importance),
                )
            )
        if not conditions:
            return None
        return models.Filter(must=conditions)

    def search(
        self,
        query_text: str,
        *,
        limit: int,
        category: str | None,
        min_importance: int,
    ) -> list[dict[str, Any]]:
        with self._lock:
            self.ping()
            self._ensure_collection()
            client = self._ensure_client()
            query_filter = self._build_filter(category, min_importance)
            vector = self._embedder.embed(query_text)
            try:
                if hasattr(client, "query_points"):
                    response = client.query_points(
                        collection_name=self.config.collection_name,
                        query=vector,
                        limit=limit,
                        query_filter=query_filter,
                        with_payload=True,
                    )
                    points = response.points
                else:
                    points = client.search(
                        collection_name=self.config.collection_name,
                        query_vector=vector,
                        limit=limit,
                        query_filter=query_filter,
                        with_payload=True,
                    )
            except Exception as exc:
                raise HuginnBackendError(
                    f"Qdrant search failed: {self._scrub(exc)}"
                ) from exc
            return [
                self._point_to_doc(p, score=getattr(p, "score", 0.0)) for p in points
            ]

    def count(self) -> int:
        with self._lock:
            self.ping()
            self._ensure_collection()
            client = self._ensure_client()
            try:
                result = client.count(collection_name=self.config.collection_name)
                return int(result.count)
            except Exception as exc:
                raise HuginnBackendError(
                    f"Qdrant count failed: {self._scrub(exc)}"
                ) from exc

    def health(self) -> dict[str, Any]:
        with self._lock:
            self.ping()
            documents = self.count()
            return {
                "status": "healthy",
                "backend": "qdrant",
                "qdrant_url": self.config.qdrant_url,
                "collection": self.config.collection_name,
                "documents": documents,
            }

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            if self._client is not None:
                with contextlib.suppress(Exception):
                    self._client.close()
                self._client = None
