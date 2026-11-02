"""Huginn — the Thought Raven: retrieval that flies out and returns
with what is relevant.

Modern, auditable form of the ancestors' design (NorseSagaEngine
``yggdrasil/ravens/huginn.py``): query analysis, flights
(:meth:`HuginnMemory.fly`), multi-hop retrieval, and TF-IDF semantic
search — over a real memory store this time: Qdrant when it is
genuinely available, otherwise Huginn's own local store, which is
fully capable with zero infrastructure.

Backend honesty:
* ``backend="auto"`` (the default, and what Bifröst gets with
  ``HuginnMemory(config=None)``): Qdrant is probed lazily on first
  use with a short timeout. Any failure — no server, no client
  package — falls back to the local backend *permanently for this
  object*, and ``health()`` reports ``status="degraded"`` with the
  reason. A missing Qdrant never crashes the caller.
* ``backend="qdrant"`` is explicit: failures raise
  :class:`HuginnBackendError`, loudly.
* ``backend="local"`` never touches the network.

Read honesty: ``search``, ``get`` and ``fly`` are pure reads. Huginn
has no reinforcing read at all — reinforcement is Muninn's job.

Scoring honesty: the local backend's default score is TF-IDF cosine —
*lexical* semantics (weighted word overlap). The Qdrant backend's
default embedder is deterministic feature hashing (lexical overlap in
vector form); true neural embeddings need
``embedder="sentence-transformers"`` (the ``embeddings`` extra).
``health()`` always names the effective embedder.
"""

from __future__ import annotations

import contextlib
import json
import logging
import math
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .config import HuginnConfig
from .errors import (
    HuginnBackendError,
    HuginnConfigurationError,
    HuginnError,
    HuginnValidationError,
)
from .local_backend import LocalBackend
from .qdrant_backend import QdrantBackend, scrub_api_key
from .text import (
    STOPWORDS,
    Embedder,
    HashingEmbedder,
    SentenceTransformerEmbedder,
    cosine,
    sparse_tfidf,
    term_counts,
    tokenize,
)

logger = logging.getLogger("huginn")

MAX_RESULTS_CAP = 50
MAX_QUERY_CHARS = 1000


# ─── Ancestor query analysis ──────────────────────────────────────────

def analyze_query(query: str) -> dict[str, Any]:
    """Analyze a query the ancestor's way.

    Returns ``query_type``, ``key_terms`` (stopwords removed),
    ``strategy``, ``recommended_hops`` and ``word_count``.
    """
    safe_query = _check_query_text(query).strip()[:MAX_QUERY_CHARS]
    query_lower = safe_query.lower()
    words = query_lower.split()

    query_type = "factual"
    if any(w in query_lower for w in ["why", "how", "explain"]):
        query_type = "explanatory"
    elif any(w in query_lower for w in ["find", "search", "where"]):
        query_type = "search"
    elif any(w in query_lower for w in ["list", "all", "show"]):
        query_type = "enumeration"
    elif any(w in query_lower for w in ["compare", "difference", "vs"]):
        query_type = "comparison"

    key_terms = [w for w in words if w not in STOPWORDS and len(w) > 2]

    if query_type == "comparison":
        strategy, hop_count = "multi_hop", 2
    elif query_type == "enumeration":
        strategy, hop_count = "broad", 1
    elif len(key_terms) > 3:
        strategy, hop_count = "focused", 1
    else:
        strategy, hop_count = "standard", 1

    return {
        "query_type": query_type,
        "key_terms": key_terms,
        "strategy": strategy,
        "recommended_hops": hop_count,
        "word_count": len(words),
    }


def semantic_search(
    query: str, documents: list[str], top_k: int = 3
) -> list[tuple[int, float]]:
    """TF-IDF semantic search over caller-supplied documents.

    The ancestor's signature, reimplemented on stdlib sparse TF-IDF
    (no sklearn). Returns ``(index, score)`` pairs, best first,
    positive scores only.
    """
    _check_query_text(query)
    docs = _check_documents(documents)
    bounded_top_k = _check_count(top_k, "top_k")
    if not docs:
        return []
    doc_counts = [term_counts(tokenize(doc)) for doc in docs]
    df: dict[str, int] = {}
    for counts in doc_counts:
        for term in counts:
            df[term] = df.get(term, 0) + 1
    total = len(docs)
    query_vec = sparse_tfidf(term_counts(tokenize(query)), df, total)
    scored = []
    for idx, counts in enumerate(doc_counts):
        score = cosine(query_vec, sparse_tfidf(counts, df, total))
        if score > 0.0:
            scored.append((idx, score))
    # RM-011 determinism pin: equal scores resolve by document index.
    scored.sort(key=lambda item: (-item[1], item[0]))
    bounded = max(1, min(bounded_top_k, len(docs)))
    return [(idx, float(score)) for idx, score in scored[:bounded]]


@dataclass
class RetrievalResult:
    """The result of one Huginn flight — the ancestor's shape."""

    query: str
    results: list[dict[str, Any]]
    relevance_scores: list[float]
    source_realm: str
    retrieval_time: float
    compressed: bool
    error: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


def _check_importance(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise HuginnValidationError(f"importance must be an int in [1, 10], got {value!r}")
    if not 1 <= value <= 10:
        raise HuginnValidationError(f"importance must be in [1, 10], got {value}")
    return int(value)


def _check_valence(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HuginnValidationError(f"emotional_valence must be a number in [-1, 1], got {value!r}")
    v = float(value)
    if not -1.0 <= v <= 1.0:
        raise HuginnValidationError(f"emotional_valence must be in [-1, 1], got {v}")
    return v


def _check_memory_id(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise HuginnValidationError(f"memory_id must be an int, got {type(value).__name__}")
    if value < 0:
        raise HuginnValidationError(f"memory_id must be >= 0, got {value}")
    if value > 9223372036854775807:
        raise HuginnValidationError(f"memory_id must be <= 9223372036854775807, got {value}")
    return int(value)


def _check_count(value: Any, what: str) -> int:
    """RM-026: an integer count (limit / top_k / max_results /
    hop_count), typed — the twin of muninn's RM-025 checker.

    Plain ints pass; finite integral floats are accepted as
    before (``int()`` semantics); everything else — strings,
    containers, NaN, infinities, bools — is a typed refusal
    instead of a bare ``TypeError``/``ValueError`` from ``int()``.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)) or (
        isinstance(value, float) and not (math.isfinite(value) and value.is_integer())
    ):
        raise HuginnValidationError(f"{what} must be an int, got {type(value).__name__}")
    return int(value)


def _check_no_lone_surrogates(value: str, what: str) -> str:
    """RM-034: a text must be honestly encodable as UTF-8.

    The twin of muninn's checker. A Python string can hold an
    unpaired surrogate code point (U+D800–U+DFFF) which UTF-8
    cannot encode, JSON can only smuggle as an escape, and
    SQLite cannot bind. Enforced in the facade, before any
    backend is touched, so the refusal holds on the local and
    Qdrant backends alike. Valid astral characters are single
    code points above U+FFFF and pass untouched.
    """
    for ch in value:
        if 0xD800 <= ord(ch) <= 0xDFFF:
            raise HuginnValidationError(f"{what} must not contain lone surrogates")
    return value


def _check_query_text(value: Any) -> str:
    """RM-026: every query-shaped argument is a string, typed.

    The one checker behind ``search`` / ``analyze_query`` /
    ``semantic_search`` / ``fly`` / ``multi_hop_retrieve``, so a
    non-string query is the same typed refusal everywhere
    instead of an ``AttributeError`` from ``.strip()`` inside
    the flight paths.
    """
    if not isinstance(value, str):
        raise HuginnValidationError("query_text must be a string")
    return _check_no_lone_surrogates(value, "query_text")


def _check_category(value: Any, *, allow_none: bool = False) -> str | None:
    """RM-026: a category is a string (or None on reads), typed.

    Before this slice the facade coerced with ``str()`` on
    writes (silently storing ``"123"``) and passed the raw
    value to the backends on reads, where a list died as an
    untyped SQLite ``ProgrammingError`` at bind time.
    """
    if value is None and allow_none:
        return None
    if not isinstance(value, str):
        raise HuginnValidationError("category must be a string")
    return _check_no_lone_surrogates(value, "category")


def _check_tag_list(tags: Any) -> list[Any]:
    """RM-026: the tags argument is a list/tuple (or None).

    A bare string is refused instead of exploding into
    single-character tags, and a non-iterable is a typed
    refusal instead of a bare ``TypeError``. Elements keep the
    historical ``str()`` coercion at the call site.
    """
    if tags is None:
        return []
    if isinstance(tags, (str, bytes)) or not isinstance(tags, (list, tuple)):
        raise HuginnValidationError("tags must be a list of strings")
    return list(tags)


def _check_content_size(content: str, ceiling: int) -> None:
    """RM-027: content must fit the configured ceiling (typed).

    Size is the UTF-8 byte length of the content — what the
    store actually holds — so a multibyte character counts for
    what it costs, not for one. Enforced in the facade, so the
    refusal lands before any backend is touched.
    """
    size = len(content.encode("utf-8"))
    if size > ceiling:
        raise HuginnValidationError(
            f"content size {size} bytes exceeds max_content_bytes ({ceiling} bytes)"
        )


# RM-036: nesting bound for tag elements, the twin of muninn's.
# 100 containers deep is far beyond any honest tag shape, and
# far below the depth at which ``repr`` (the ``str()`` coercion
# of a container tag element) overflows the interpreter stack.
_MAX_STRUCTURE_DEPTH = 100


def _check_structure_depth(value: Any, what: str) -> None:
    """RM-036: a structured value must not nest too deep.

    The walk is iterative (explicit stack, path-scoped id set),
    so the check itself cannot overflow the stack it guards:
    before this slice, a tag element nested tens of thousands
    of containers deep escaped ``upsert_memory`` as a raw
    ``RecursionError`` from its ``repr``. A container already
    on the current path (a circular structure) is not
    descended into — ``repr`` renders those with an ellipsis,
    as it always has. A shared (DAG-shaped) substructure is
    walked once per occurrence and is not circular. Enforced
    in the facade, so the refusal holds on the local and
    Qdrant backends alike.
    """
    if not isinstance(value, (dict, list, tuple, set, frozenset)):
        return
    on_path: set[int] = set()
    stack: list[tuple[Any, int, bool]] = [(value, 1, False)]
    while stack:
        node, depth, exiting = stack.pop()
        if exiting:
            on_path.discard(id(node))
            continue
        if not isinstance(node, (dict, list, tuple, set, frozenset)):
            continue
        if id(node) in on_path:
            continue
        if depth > _MAX_STRUCTURE_DEPTH:
            raise HuginnValidationError(
                f"{what} nesting depth exceeds maximum of {_MAX_STRUCTURE_DEPTH}"
            )
        on_path.add(id(node))
        stack.append((node, depth, True))
        children: list[Any] = (
            list(node.keys()) + list(node.values())
            if isinstance(node, dict)
            else list(node)
        )
        stack.extend((child, depth + 1, False) for child in children)


def _check_tags_size(clean_tags: list[str], ceiling: int) -> None:
    """RM-036: the stored tags must fit the content ceiling.

    Huginn memories carry no caller metadata, so tags are the
    annotation payload and the RM-027 content ceiling bounds
    them uniformly: the measure is the UTF-8 byte length of
    the tags' JSON form, as the local backend stores them.
    Before this slice a tags list of any length was accepted,
    however enormous. Enforced in the facade, before any
    backend is touched.
    """
    size = len(json.dumps(clean_tags).encode("utf-8"))
    if size > ceiling:
        raise HuginnValidationError(
            f"tags size {size} bytes exceeds max_content_bytes ({ceiling} bytes)"
        )


def _check_documents(documents: Any) -> list[str]:
    """RM-026: ``semantic_search`` documents are a list of strings.

    Before this slice a bare string was silently iterated
    character by character and non-string documents were
    coerced inside the tokenizer; neither is a document list.
    """
    if (
        isinstance(documents, (str, bytes))
        or not isinstance(documents, (list, tuple))
        or any(not isinstance(doc, str) for doc in documents)
    ):
        raise HuginnValidationError("documents must be a list of strings")
    for doc in documents:
        _check_no_lone_surrogates(doc, "documents")
    return list(documents)


class HuginnMemory:
    """Semantic memory: upsert and search, over Qdrant or local store.

    Constructed exactly as Bifröst constructs it — ``HuginnMemory()``
    or ``HuginnMemory(config=None)`` — construction is cheap and lazy:
    no file is opened, no server is contacted, until the first
    operation. Thread-safe.
    """

    def __init__(self, config: HuginnConfig | None = None, **overrides: Any):
        if config is None:
            config = HuginnConfig(**overrides)
        elif overrides:
            from dataclasses import replace

            config = replace(config, **overrides)
        self.config = config
        self._lock = threading.RLock()
        self._backend: LocalBackend | QdrantBackend | None = None
        self._embedder: Embedder | None = None
        self._embedder_name: str | None = None
        self._fallback_reason: str | None = None
        self._closed = False
        self._flight_history: list[RetrievalResult] = []

    # ─── lazy construction (Slice 86 ground 3) ────────────────────────

    def _make_embedder(self, name: str) -> Embedder:
        if name == "hashing":
            return HashingEmbedder(dim=self.config.vector_dim)
        if name == "sentence-transformers":
            return SentenceTransformerEmbedder(model=self.config.st_model)
        raise HuginnConfigurationError(f"no vector embedder named {name!r}")

    def _ensure_backend(self) -> LocalBackend | QdrantBackend:
        if self._closed:
            raise HuginnBackendError("HuginnMemory is closed")
        if self._backend is not None:
            return self._backend
        with self._lock:
            if self._backend is not None:
                return self._backend
            wanted = self.config.backend
            if wanted == "local":
                self._backend = self._build_local()
                return self._backend
            if wanted == "qdrant":
                backend = self._build_qdrant()
                backend.ping()  # explicit: unreachable raises, loudly
                self._backend = backend
                return self._backend
            # auto: try Qdrant once; any failure → local, permanently.
            try:
                backend = self._build_qdrant()
                backend.ping()
                self._backend = backend
                logger.info("huginn: auto backend selected Qdrant at %s", self.config.qdrant_url)
            except Exception as exc:
                # RM-045: the fallback reason is recorded in
                # health() and logged at INFO — the Qdrant API
                # key must never ride it there (TH-06), and the
                # wrapped client wording is not ours to control.
                safe = scrub_api_key(str(exc), self.config.qdrant_api_key)
                self._fallback_reason = f"qdrant unavailable: {safe}"
                logger.info("huginn: auto backend fell back to local (%s)", safe)
                self._backend = self._build_local()
            return self._backend

    def _build_local(self) -> LocalBackend:
        embedder: Embedder | None = None
        if self.config.embedder != "tfidf":
            embedder = self._make_embedder(self.config.embedder)
            self._embedder = embedder
            self._embedder_name = self.config.embedder
        else:
            self._embedder_name = "tfidf"
        return LocalBackend(self.config, embedder=embedder)

    def _build_qdrant(self) -> QdrantBackend:
        name = self.config.embedder
        if name == "tfidf":
            name = "hashing"  # Qdrant needs fixed-space vectors
        embedder = self._make_embedder(name)
        self._embedder = embedder
        self._embedder_name = name
        return QdrantBackend(self.config, embedder=embedder)

    # ─── contract API (Bifröst) ───────────────────────────────────────

    def upsert_memory(
        self,
        content: str,
        category: str = "general",
        importance: int = 5,
        tags: list[str] | None = None,
        emotional_valence: float = 0.0,
        *,
        memory_id: int | None = None,
    ) -> int:
        """Store (or replace) one memory; returns its id (WRITE).

        Idempotent: the same content in the same category is the same
        memory. Pass ``memory_id`` to align the id with an external
        store (Bifröst merges backends by id).
        """
        if not isinstance(content, str) or not content.strip():
            raise HuginnValidationError("content must be a non-empty string")
        _check_no_lone_surrogates(content, "content")
        _check_content_size(content, self.config.max_content_bytes)
        importance = _check_importance(importance)
        emotional_valence = _check_valence(emotional_valence)
        if memory_id is not None:
            memory_id = _check_memory_id(memory_id)
        clean_category = _check_category(category)
        assert clean_category is not None  # allow_none=False: None already raised
        clean_tags = []
        for raw_tag in _check_tag_list(tags):
            _check_structure_depth(raw_tag, "tags")
            clean_tags.append(str(raw_tag))
        for tag in clean_tags:
            _check_no_lone_surrogates(tag, "tags")
        _check_tags_size(clean_tags, self.config.max_content_bytes)
        backend = self._ensure_backend()
        result = backend.upsert(
            content,
            category=clean_category,
            importance=importance,
            tags=clean_tags,
            emotional_valence=emotional_valence,
            memory_id=memory_id,
        )
        if self.config.debug_log_content:
            # RM-044: the ONLY road by which memory content
            # reaches a log — this flag, at DEBUG level.
            logger.debug("huginn: stored memory id=%d content=%r", result, content)
        return result

    def search(
        self,
        query_text: str,
        limit: int = 10,
        category: str | None = None,
        min_importance: int = 1,
    ) -> list[dict[str, Any]]:
        """Semantic search. PURE READ.

        Returns dicts with ``id, content, category, importance, tags,
        emotional_valence, score`` — best first. A blank query is an
        honest empty result, not an error.
        """
        _check_query_text(query_text)
        if not query_text.strip():
            return []
        limit = max(1, min(_check_count(limit, "limit"), 1000))
        if isinstance(min_importance, bool) or not isinstance(min_importance, int):
            raise HuginnValidationError("min_importance must be an int")
        if min_importance > 9223372036854775807:
            raise HuginnValidationError(
                f"min_importance must be <= 9223372036854775807, got {min_importance}"
            )
        backend = self._ensure_backend()
        results = backend.search(
            query_text,
            limit=limit,
            category=_check_category(category, allow_none=True),
            min_importance=min_importance,
        )
        if self.config.debug_log_content:
            # RM-044: content in logs only here, only at DEBUG,
            # only with the flag on (see upsert_memory()).
            logger.debug(
                "huginn: search query=%r returned %d results content=%r",
                query_text,
                len(results),
                [row.get("content") for row in results],
            )
        return results

    def get(self, memory_id: int) -> dict[str, Any] | None:
        """One memory by id, or None. PURE READ."""
        memory_id = _check_memory_id(memory_id)
        return self._ensure_backend().get(memory_id)

    def delete(self, memory_id: int) -> bool:
        """Remove one memory (WRITE). True when something was removed.

        Honest limit (RM-051, threat TH-11): on the local
        backend this removes the live rows only — the content
        can persist in WAL frames, in freed pages of the store
        file, and in every rolling backup generation until
        rotation. When the content itself must leave the disk,
        use :meth:`secure_forget`.
        """
        memory_id = _check_memory_id(memory_id)
        return self._ensure_backend().delete(memory_id)

    def secure_forget(self, memory_id: int) -> bool:
        """Remove one memory **and purge its content** (WRITE).

        Everything :meth:`delete` does, with the same return
        value, plus the RM-051 purge (threat TH-11; record in
        ``docs/SECURE_FORGET.md``). On the local backend: the
        delete runs under ``PRAGMA secure_delete=ON``, the
        WAL is checkpoint-truncated, the store file is
        rewritten with ``VACUUM``, and every pre-existing
        backup generation is discarded and replaced by one
        fresh snapshot of the purged store — at the cost of a
        full store rewrite and the loss of all older backup
        generations. The purge runs even when nothing live
        was removed, remediating an earlier plain delete's
        residue. On the Qdrant backend there are no local
        files: this is the server-side delete, and what the
        server's own snapshots retain is the operator's
        domain.
        """
        memory_id = _check_memory_id(memory_id)
        return self._ensure_backend().secure_forget(memory_id)

    def health(self) -> dict[str, Any]:
        """Backend health; never raises for backend trouble.

        ``status`` is ``"healthy"``, ``"degraded"`` (auto mode fell
        back to local — with ``fallback_reason``), or ``"unhealthy"``
        (explicit backend failing).
        """
        try:
            backend = self._ensure_backend()
            info = backend.health()
        except HuginnError as exc:
            return {
                "status": "unhealthy",
                "backend_configured": self.config.backend,
                # RM-045: defence in depth — a backend error
                # string is already key-scrubbed at its raise
                # site; scrub again here so no error text this
                # facade reports can carry the key (TH-06).
                "error": scrub_api_key(str(exc), self.config.qdrant_api_key),
                "error_type": type(exc).__name__,
            }
        info = dict(info)
        if self._fallback_reason:
            info["status"] = "degraded"
            info["fallback_reason"] = self._fallback_reason
        info["embedder"] = self._embedder_name
        info["backend_configured"] = self.config.backend
        return info

    def stats(self) -> dict[str, Any]:
        """Statistics (Bifröst calls health() for this; both exist)."""
        info = self.health()
        return info

    @property
    def last_search_stats(self) -> dict[str, Any]:
        """RM-053: the last local search's cost accounting.

        ``candidates_total`` (candidates the index offered),
        ``candidates_scored``, ``candidates_pruned`` (RM-061:
        TF-IDF candidates the posting-list bound excused from
        full scoring — their results are proven identical to
        the unpruned search's), ``cap`` (the
        ``max_search_candidates`` ceiling) and ``capped``
        (whether the ceiling bit). A dedicated property,
        deliberately NOT a ``health()`` field: health
        snapshots are pinned pure, so per-call accounting
        lives here. Reading it never constructs the backend
        (lazy construction is contractual): before the first
        search — and on the Qdrant backend, whose server
        owns its query cost — it reports the zero record
        carrying the configured cap. Returns a copy.
        """
        backend = self._backend
        if isinstance(backend, LocalBackend):
            return dict(backend.last_search_stats)
        return {
            "candidates_total": 0,
            "candidates_scored": 0,
            "candidates_pruned": 0,
            "cap": int(self.config.max_search_candidates),
            "capped": False,
        }

    def close(self) -> None:
        """Close the backend if one was built. Idempotent."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            if self._backend is not None:
                with contextlib.suppress(Exception):
                    self._backend.close()
                self._backend = None

    def __enter__(self) -> HuginnMemory:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ─── ancestor flight semantics ────────────────────────────────────

    def analyze_query(self, query: str) -> dict[str, Any]:
        """The ancestor's query analysis (see module function)."""
        return analyze_query(query)

    def fly(
        self, query: str, max_results: int = 5, compress: bool = True
    ) -> RetrievalResult:
        """Send Huginn flying over this store. PURE READ.

        Returns a :class:`RetrievalResult` — on backend failure the
        flight comes home empty with ``error`` set, as the ancestor's
        flights did, rather than crashing the thinker.
        """
        start = time.time()
        error: str | None = None
        results: list[dict[str, Any]] = []
        try:
            # RM-026: the count and the query are validated inside
            # the flight's error envelope — a bad argument comes
            # home as an error flight, never as an untyped raise.
            bounded = max(1, min(_check_count(max_results, "max_results"), MAX_RESULTS_CAP))
            safe_query = _check_query_text(query).strip()[:MAX_QUERY_CHARS]
            results = self.search(safe_query, limit=bounded)
        except HuginnError as exc:
            error = str(exc)
        if compress:
            results = [self._compress_result(r) for r in results]
        backend_kind = self._backend.kind if self._backend is not None else "unresolved"
        flight = RetrievalResult(
            query=query,
            results=results,
            relevance_scores=[float(r.get("score", 0.0)) for r in results],
            source_realm=f"huginn:{backend_kind}",
            retrieval_time=time.time() - start,
            compressed=compress,
            error=error,
        )
        with self._lock:
            self._flight_history.append(flight)
            if len(self._flight_history) > 100:
                self._flight_history = self._flight_history[-50:]
        return flight

    @staticmethod
    def _compress_result(result: dict[str, Any]) -> dict[str, Any]:
        """Ancestor compression: long strings truncated, long lists cut."""
        comp: dict[str, Any] = {}
        for key, value in result.items():
            if isinstance(value, str) and len(value) > 200:
                comp[key] = value[:200] + "..."
            elif isinstance(value, list) and len(value) > 5:
                comp[key] = value[:5]
            else:
                comp[key] = value
        return comp

    def multi_hop_retrieve(
        self,
        initial_query: str,
        hop_count: int = 2,
        max_results_per_hop: int = 3,
    ) -> list[RetrievalResult]:
        """Chained flights: each hop's findings seed the next query."""
        flights: list[RetrievalResult] = []
        current_query = _check_query_text(initial_query).strip()[:MAX_QUERY_CHARS]
        bounded_hops = max(1, min(_check_count(hop_count, "hop_count"), 5))
        bounded_per_hop = _check_count(max_results_per_hop, "max_results_per_hop")
        for _ in range(bounded_hops):
            flight = self.fly(current_query, max_results=bounded_per_hop)
            flights.append(flight)
            if not flight.results:
                break
            concepts = self._extract_concepts(flight.results)
            if not concepts:
                break
            current_query = f"{initial_query} {' '.join(concepts[:3])}"
        return flights

    @staticmethod
    def _extract_concepts(results: list[dict[str, Any]]) -> list[str]:
        concepts = set()
        for result in results:
            content = result.get("content", "")
            if isinstance(content, str):
                for word in content.lower().split():
                    if len(word) > 4 and word.isalpha():
                        concepts.add(word)
        return sorted(concepts)[:10]

    def get_flight_stats(self) -> dict[str, Any]:
        """Statistics over this object's flights. PURE READ."""
        with self._lock:
            history = list(self._flight_history)
        if not history:
            return {"total_flights": 0}
        total_time = sum(f.retrieval_time for f in history)
        total_results = sum(len(f.results) for f in history)
        realm_counts: dict[str, int] = {}
        for flight in history:
            realm_counts[flight.source_realm] = realm_counts.get(flight.source_realm, 0) + 1
        return {
            "total_flights": len(history),
            "total_results_retrieved": total_results,
            "total_flight_time": total_time,
            "avg_flight_time": total_time / len(history),
            "avg_results_per_flight": total_results / len(history),
            "realm_visits": realm_counts,
        }
