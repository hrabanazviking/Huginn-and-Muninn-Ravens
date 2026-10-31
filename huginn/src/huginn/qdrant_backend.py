"""Huginn's Qdrant backend (optional extra: ``huginn[qdrant]``).

The client is imported lazily and the server is only ever contacted
on first use — importing this module, or constructing the backend,
touches no network. All Qdrant/model types are resolved at call time
so tests can stand a fake client in ``sys.modules``.

Identity: a point's id is the caller's ``memory_id`` when given, else
derived deterministically from the content hash — re-upserting the
same memory naturally targets the same point, and identical content
in the same category is one point (idempotent, like the local store).
"""

from __future__ import annotations

import contextlib
import hashlib
import logging
import threading
from typing import Any

from .config import HuginnConfig
from .errors import HuginnBackendError, HuginnConfigurationError
from .text import Embedder

logger = logging.getLogger("huginn.qdrant")


def _content_hash(content: str, category: str) -> str:
    return hashlib.sha256(f"{category}\x00{content}".encode()).hexdigest()


def _derived_id(content_hash: str) -> int:
    return int.from_bytes(bytes.fromhex(content_hash[:16]), "big")


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
                f"Qdrant at {self.config.qdrant_url} unreachable: {exc}"
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
                    f"{self.config.collection_name!r}: {exc}"
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
                raise HuginnBackendError(f"Qdrant upsert failed: {exc}") from exc
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
                raise HuginnBackendError(f"Qdrant delete failed: {exc}") from exc

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
                raise HuginnBackendError(f"Qdrant retrieve failed: {exc}") from exc
            if not points:
                return None
            return self._point_to_doc(points[0])

    def _point_to_doc(self, point: Any, score: float | None = None) -> dict[str, Any]:
        payload = getattr(point, "payload", None) or {}
        doc = {
            "id": int(point.id),
            "content": payload.get("content", ""),
            "category": payload.get("category", ""),
            "importance": int(payload.get("importance", 5)),
            "tags": list(payload.get("tags", [])),
            "emotional_valence": float(payload.get("emotional_valence", 0.0)),
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
                raise HuginnBackendError(f"Qdrant search failed: {exc}") from exc
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
                raise HuginnBackendError(f"Qdrant count failed: {exc}") from exc

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
