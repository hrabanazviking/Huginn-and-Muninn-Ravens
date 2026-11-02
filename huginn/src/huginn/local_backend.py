"""Huginn's local backend: a fully capable retrieval store with zero
infrastructure — one WAL SQLite file and a maintained inverted term
index.

Scoring modes (honestly labelled):
* ``tfidf`` (default): TF-IDF cosine over the inverted index.
  Lexical semantics — weighted word overlap. Candidate documents come
  from the term postings; no full scans, no N+1.
* embedder mode (``hashing`` / ``sentence-transformers``): vectors are
  stored per document and scored by dense cosine. The scan is linear
  over stored vectors — the right shape for a personal memory store
  (thousands of documents); very large corpora belong on Qdrant.
"""

from __future__ import annotations

import contextlib
import functools
import hashlib
import json
import logging
import sqlite3
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, TypeVar

from ._db import (
    _is_locked_error,
    open_store,
    store_coordination_lock,
    store_permissions_warning,
)
from .config import HuginnConfig
from .errors import HuginnStorageError, HuginnValidationError
from .text import Embedder, cosine, dense_cosine, sparse_tfidf, term_counts, tokenize

logger = logging.getLogger("huginn.local")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'general',
    importance INTEGER NOT NULL DEFAULT 5,
    tags TEXT NOT NULL DEFAULT '[]',
    emotional_valence REAL NOT NULL DEFAULT 0.0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(content_hash, category)
);
CREATE TABLE IF NOT EXISTS doc_terms (
    doc_id INTEGER NOT NULL,
    term TEXT NOT NULL,
    tf INTEGER NOT NULL,
    PRIMARY KEY (doc_id, term)
);
CREATE INDEX IF NOT EXISTS idx_terms_term ON doc_terms(term);
CREATE TABLE IF NOT EXISTS corpus_stats (
    term TEXT PRIMARY KEY,
    doc_freq INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS doc_vectors (
    doc_id INTEGER PRIMARY KEY,
    vector TEXT NOT NULL
);
"""


def _now() -> str:
    """The backend's one stored-timestamp source (RM-012).

    Every timestamp written to the store comes from here: UTC,
    ISO-8601, offset-aware. Monotonicity on top of the raw clock
    is :meth:`LocalBackend._tick`'s job.
    """
    return datetime.now(UTC).isoformat()


def _content_hash(content: str, category: str) -> str:
    """RM-047: the content hash — SHA-256 of category + content.

    The one hash function the idempotent-store path uses;
    tests inject a constant replacement for it to force the
    collisions SHA-256 makes implausible in nature (see
    docs/HASH_COLLISION.md).
    """
    return hashlib.sha256(f"{category}\x00{content}".encode()).hexdigest()


def _check_not_a_collision(stored_content: str, content: str, existing_id: int) -> None:
    """RM-047 (TH-08): the length+content double check.

    A row found by (content_hash, category) is the same memory
    only if its stored content has the same length as the
    incoming content *and* is the incoming content. Anything
    else is a hash collision: refuse loudly, naming only the
    existing id — never merge, never overwrite.
    """
    if len(stored_content) != len(content) or stored_content != content:
        raise HuginnValidationError(
            "content hash collision: a different memory already "
            f"holds this content hash (id {existing_id}); "
            "refusing to merge"
        )


_R = TypeVar("_R")


def _storage_write(
    operation: str,
) -> Callable[[Callable[..., _R]], Callable[..., _R]]:
    """Guard a local-backend write method (RM-029).

    A storage-layer failure during a write — above all SQLite's
    ``database or disk is full`` (SQLITE_FULL) when the filesystem
    fills mid-write — must never escape as a raw ``sqlite3.Error``:
    the caller is owed one of Huginn's typed errors. The failed
    call's transaction is rolled back first, so a half-applied
    write (an upsert that de-indexed the old document but never
    stored the new one) can never leak into a later commit, and
    the store stays open and consistent for the calls that follow.

    A lock held by another process past the busy timeout is the
    same discipline with its own message shape (RM-031): the
    guard names the contention instead of echoing SQLite's
    wording, so a caller can tell "another process has the
    store" apart from every other storage failure.

    The decorator preserves the wrapped method's return type —
    the same RM-030 repair as Muninn's twin, whose ``Any``-typed
    wrapper broke the RM-008 mypy floor (``warn_return_any``).
    """

    def decorator(fn: Callable[..., _R]) -> Callable[..., _R]:
        @functools.wraps(fn)
        def wrapper(self: LocalBackend, *args: Any, **kwargs: Any) -> _R:
            try:
                return fn(self, *args, **kwargs)
            except sqlite3.Error as exc:
                with contextlib.suppress(sqlite3.Error):
                    self._conn.rollback()
                if _is_locked_error(exc):
                    raise HuginnStorageError(
                        f"huginn write failed during {operation}: store is locked "
                        f"by another process (busy timeout expired)"
                    ) from exc
                raise HuginnStorageError(
                    f"huginn write failed during {operation}: {exc}"
                ) from exc

        return wrapper

    return decorator


class LocalBackend:
    """SQLite + inverted-index retrieval store."""

    kind = "local"

    def __init__(self, config: HuginnConfig, embedder: Embedder | None = None):
        self.config = config
        self._embedder = embedder
        self._lock = threading.RLock()
        self._ts_lock = threading.Lock()
        self._last_ts: datetime | None = None
        self._closed = False
        self._db_path = config.resolved_local_path()
        conn, report = open_store(
            self._db_path,
            busy_timeout_ms=config.busy_timeout_ms,
            backup_keep=config.backup_keep,
            auto_backup=config.auto_backup,
            schema_sql=SCHEMA_SQL,
            strict_path_safety=config.strict_path_safety,
        )
        self._conn = conn
        self.open_report = report
        self.recovered_from_backup = report.recovered_from_backup
        # RM-037: the heal pass is an open-time duty — it runs
        # under the per-store coordination lock, so it can never
        # interleave with another opener's open, heal or backup
        # duties on the same store file.
        with self._lock, store_coordination_lock(self._db_path):
            self._seed_last_ts_locked()
            self.last_heal_report = self._heal_locked()

    # ─── timestamp discipline (RM-012) ────────────────────────────────

    def _seed_last_ts_locked(self) -> None:
        """Seed the monotonic guard from the store's own history,
        so a reopen after a backwards clock move still issues
        timestamps strictly after everything already stored."""
        row = self._conn.execute("SELECT MAX(updated_at) FROM documents").fetchone()
        if row and row[0]:
            self._last_ts = datetime.fromisoformat(str(row[0]))

    def _tick(self) -> str:
        """Next stored timestamp: ``_now()``, monotonic (RM-012).

        A backwards (or stalled) system clock yields the last
        issued timestamp plus one microsecond instead, so a
        document's ``updated_at`` can never precede its
        ``created_at`` and updates never travel back in time.
        """
        candidate = datetime.fromisoformat(_now())
        with self._ts_lock:
            if self._last_ts is not None and candidate <= self._last_ts:
                candidate = self._last_ts + timedelta(microseconds=1)
            self._last_ts = candidate
        return candidate.isoformat()

    # ─── lifecycle ────────────────────────────────────────────────────

    def _ensure_open(self) -> sqlite3.Connection:
        if self._closed:
            raise HuginnStorageError("Huginn local backend is closed")
        return self._conn

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            with contextlib.suppress(sqlite3.Error):
                self._conn.close()

    # ─── index maintenance (lock held) ────────────────────────────────

    def _index_terms_locked(self, doc_id: int, counts: dict[str, int]) -> None:
        if counts:
            self._conn.executemany(
                "INSERT INTO doc_terms (doc_id, term, tf) VALUES (?, ?, ?)",
                [(doc_id, term, tf) for term, tf in counts.items()],
            )
            self._conn.executemany(
                "INSERT INTO corpus_stats (term, doc_freq) VALUES (?, 1)"
                " ON CONFLICT(term) DO UPDATE SET doc_freq = doc_freq + 1",
                [(term,) for term in counts],
            )

    def _deindex_terms_locked(self, doc_id: int) -> None:
        rows = self._conn.execute(
            "SELECT term FROM doc_terms WHERE doc_id = ?", (doc_id,)
        ).fetchall()
        if rows:
            self._conn.executemany(
                "UPDATE corpus_stats SET doc_freq = doc_freq - 1 WHERE term = ?",
                [(r[0],) for r in rows],
            )
            self._conn.execute("DELETE FROM corpus_stats WHERE doc_freq <= 0")
            self._conn.execute("DELETE FROM doc_terms WHERE doc_id = ?", (doc_id,))

    def _heal_locked(self) -> dict[str, Any]:
        """Repair term-index drift: orphans pruned, doc_freq recounted."""
        report = {"orphan_terms_pruned": 0, "orphan_vectors_pruned": 0, "doc_freq_fixed": 0}
        cur = self._conn.execute(
            "DELETE FROM doc_terms WHERE doc_id NOT IN (SELECT id FROM documents)"
        )
        report["orphan_terms_pruned"] = cur.rowcount
        cur = self._conn.execute(
            "DELETE FROM doc_vectors WHERE doc_id NOT IN (SELECT id FROM documents)"
        )
        report["orphan_vectors_pruned"] = cur.rowcount
        expected = {
            r[0]: int(r[1])
            for r in self._conn.execute(
                "SELECT term, COUNT(*) FROM doc_terms GROUP BY term"
            ).fetchall()
        }
        current = {
            r[0]: int(r[1])
            for r in self._conn.execute("SELECT term, doc_freq FROM corpus_stats").fetchall()
        }
        # RM-011 determinism pin: sorted, so the repair write order
        # never depends on set iteration (hash-seed) order.
        for term in sorted(set(expected) | set(current)):
            if expected.get(term) != current.get(term):
                report["doc_freq_fixed"] += 1
                if term in expected:
                    self._conn.execute(
                        "INSERT OR REPLACE INTO corpus_stats (term, doc_freq) VALUES (?, ?)",
                        (term, expected[term]),
                    )
                else:
                    self._conn.execute("DELETE FROM corpus_stats WHERE term = ?", (term,))
        self._conn.commit()
        if report["doc_freq_fixed"] or report["orphan_terms_pruned"]:
            logger.warning("huginn: local heal repaired %s", report)
        return report

    @_storage_write("heal")
    def heal(self) -> dict[str, Any]:
        with self._lock:
            self._ensure_open()
            self.last_heal_report = self._heal_locked()
            return dict(self.last_heal_report)

    # ─── writes ───────────────────────────────────────────────────────

    @_storage_write("upsert")
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
        counts = term_counts(tokenize(content))
        content_hash = _content_hash(content, category)
        at = self._tick()
        with self._lock:
            conn = self._ensure_open()
            target_id: int | None = None
            if memory_id is not None:
                row = conn.execute(
                    "SELECT id, content_hash, category FROM documents WHERE id = ?",
                    (memory_id,),
                ).fetchone()
                if row is not None:
                    target_id = int(row["id"])
                else:
                    clash = conn.execute(
                        "SELECT id, content FROM documents"
                        " WHERE content_hash = ? AND category = ?",
                        (content_hash, category),
                    ).fetchone()
                    if clash is not None:
                        # RM-047: a different memory under this
                        # hash is a collision, not a clash.
                        _check_not_a_collision(
                            clash["content"], content, int(clash["id"])
                        )
                        raise HuginnValidationError(
                            f"memory_id {memory_id} is free but this content already "
                            f"lives at id {int(clash['id'])}; upsert there instead"
                        )
            if target_id is None:
                row = conn.execute(
                    "SELECT id, content FROM documents"
                    " WHERE content_hash = ? AND category = ?",
                    (content_hash, category),
                ).fetchone()
                if row is not None:
                    # RM-047 (TH-08): the idempotent hit counts
                    # only after the length+content double
                    # check — a colliding memory is refused,
                    # never silently merged by the update below.
                    _check_not_a_collision(row["content"], content, int(row["id"]))
                    target_id = int(row["id"])
            if target_id is not None:
                self._deindex_terms_locked(target_id)
                conn.execute("DELETE FROM doc_vectors WHERE doc_id = ?", (target_id,))
                conn.execute(
                    "UPDATE documents SET content = ?, content_hash = ?, category = ?,"
                    " importance = ?, tags = ?, emotional_valence = ?, updated_at = ?"
                    " WHERE id = ?",
                    (
                        content, content_hash, category, importance,
                        json.dumps(tags), emotional_valence, at, target_id,
                    ),
                )
                doc_id = target_id
            elif memory_id is not None:
                cur = conn.execute(
                    "INSERT INTO documents"
                    " (id, content, content_hash, category, importance, tags,"
                    "  emotional_valence, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        memory_id, content, content_hash, category, importance,
                        json.dumps(tags), emotional_valence, at, at,
                    ),
                )
                if cur.lastrowid is None:
                    raise HuginnStorageError(
                        "document insert reported success but returned no row id"
                    )
                doc_id = int(cur.lastrowid)
            else:
                cur = conn.execute(
                    "INSERT INTO documents"
                    " (content, content_hash, category, importance, tags,"
                    "  emotional_valence, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        content, content_hash, category, importance,
                        json.dumps(tags), emotional_valence, at, at,
                    ),
                )
                if cur.lastrowid is None:
                    raise HuginnStorageError(
                        "document insert reported success but returned no row id"
                    )
                doc_id = int(cur.lastrowid)
            self._index_terms_locked(doc_id, counts)
            if self._embedder is not None:
                vector = self._embedder.embed(content)
                conn.execute(
                    "INSERT OR REPLACE INTO doc_vectors (doc_id, vector) VALUES (?, ?)",
                    (doc_id, json.dumps(vector)),
                )
            conn.commit()
            return doc_id

    @_storage_write("delete")
    def delete(self, memory_id: int) -> bool:
        with self._lock:
            conn = self._ensure_open()
            self._deindex_terms_locked(memory_id)
            conn.execute("DELETE FROM doc_vectors WHERE doc_id = ?", (memory_id,))
            cur = conn.execute("DELETE FROM documents WHERE id = ?", (memory_id,))
            conn.commit()
            return cur.rowcount > 0

    # ─── reads (pure) ─────────────────────────────────────────────────

    def _row_to_doc(self, row: sqlite3.Row, score: float | None = None) -> dict[str, Any]:
        doc = {
            "id": int(row["id"]),
            "content": row["content"],
            "category": row["category"],
            "importance": int(row["importance"]),
            "tags": json.loads(row["tags"] or "[]"),
            "emotional_valence": float(row["emotional_valence"]),
        }
        if score is not None:
            doc["score"] = float(score)
        return doc

    def get(self, memory_id: int) -> dict[str, Any] | None:
        with self._lock:
            row = self._ensure_open().execute(
                "SELECT * FROM documents WHERE id = ?", (memory_id,)
            ).fetchone()
        return self._row_to_doc(row) if row else None

    def count(self) -> int:
        with self._lock:
            return int(
                self._ensure_open().execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            )

    def search(
        self,
        query_text: str,
        *,
        limit: int,
        category: str | None,
        min_importance: int,
    ) -> list[dict[str, Any]]:
        with self._lock:
            conn = self._ensure_open()
            if self._embedder is not None:
                return self._search_vectors_locked(
                    conn, query_text, limit, category, min_importance
                )
            return self._search_tfidf_locked(
                conn, query_text, limit, category, min_importance
            )

    def _candidate_docs_locked(
        self,
        conn: sqlite3.Connection,
        doc_ids: list[int],
        category: str | None,
        min_importance: int,
    ) -> dict[int, sqlite3.Row]:
        if not doc_ids:
            return {}
        placeholders = ",".join("?" * len(doc_ids))
        sql = f"SELECT * FROM documents WHERE id IN ({placeholders})"
        params: list[Any] = list(doc_ids)
        if category:
            sql += " AND category = ?"
            params.append(category)
        if min_importance > 1:
            sql += " AND importance >= ?"
            params.append(min_importance)
        return {int(r["id"]): r for r in conn.execute(sql, params).fetchall()}

    def _search_tfidf_locked(
        self,
        conn: sqlite3.Connection,
        query_text: str,
        limit: int,
        category: str | None,
        min_importance: int,
    ) -> list[dict[str, Any]]:
        q_counts = term_counts(tokenize(query_text))
        if not q_counts:
            return []
        total_docs = int(conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0])
        if total_docs == 0:
            return []
        placeholders = ",".join("?" * len(q_counts))
        candidate_ids = [
            int(r[0])
            for r in conn.execute(
                f"SELECT DISTINCT doc_id FROM doc_terms WHERE term IN ({placeholders})",
                list(q_counts),
            ).fetchall()
        ]
        docs = self._candidate_docs_locked(conn, candidate_ids, category, min_importance)
        if not docs:
            return []
        # Full term sets for the surviving candidates (needed for norms).
        doc_ids = list(docs)
        ph = ",".join("?" * len(doc_ids))
        term_rows = conn.execute(
            f"SELECT doc_id, term, tf FROM doc_terms WHERE doc_id IN ({ph})",
            doc_ids,
        ).fetchall()
        per_doc: dict[int, dict[str, int]] = {}
        all_terms = set(q_counts)
        for doc_id, term, tf in term_rows:
            per_doc.setdefault(int(doc_id), {})[term] = int(tf)
            all_terms.add(term)
        # One batched doc_freq lookup for every involved term.
        tph = ",".join("?" * len(all_terms))
        df = {
            r[0]: int(r[1])
            for r in conn.execute(
                f"SELECT term, doc_freq FROM corpus_stats WHERE term IN ({tph})",
                list(all_terms),
            ).fetchall()
        }
        query_vec = sparse_tfidf(q_counts, df, total_docs)
        scored = []
        for doc_id, counts in per_doc.items():
            doc_vec = sparse_tfidf(counts, df, total_docs)
            score = cosine(query_vec, doc_vec)
            if score > 0.0:
                scored.append((score, doc_id))
        # RM-011 determinism pin: equal scores resolve by doc id.
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [self._row_to_doc(docs[doc_id], score) for score, doc_id in scored[:limit]]

    def _search_vectors_locked(
        self,
        conn: sqlite3.Connection,
        query_text: str,
        limit: int,
        category: str | None,
        min_importance: int,
    ) -> list[dict[str, Any]]:
        assert self._embedder is not None
        query_vec = self._embedder.embed(query_text)
        rows = conn.execute("SELECT doc_id, vector FROM doc_vectors").fetchall()
        candidate_ids = [int(r["doc_id"]) for r in rows]
        docs = self._candidate_docs_locked(conn, candidate_ids, category, min_importance)
        vectors = {int(r["doc_id"]): json.loads(r["vector"]) for r in rows}
        scored = []
        for doc_id in docs:
            score = dense_cosine(query_vec, vectors[doc_id])
            if score > 0.0:
                scored.append((score, doc_id))
        # RM-011 determinism pin: equal scores resolve by doc id.
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [self._row_to_doc(docs[doc_id], score) for score, doc_id in scored[:limit]]

    # ─── health ───────────────────────────────────────────────────────

    def health(self) -> dict[str, Any]:
        with self._lock:
            conn = self._ensure_open()
            try:
                row = conn.execute("PRAGMA quick_check").fetchone()
                integrity = str(row[0]) if row else "unknown"
            except sqlite3.Error:
                integrity = "failed"
            documents = int(conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0])
            terms = int(conn.execute("SELECT COUNT(*) FROM corpus_stats").fetchone()[0])
        return {
            "status": "healthy" if integrity == "ok" else "degraded",
            "backend": "local",
            "db_path": str(self._db_path),
            "integrity": integrity,
            "recovered_from_backup": self.recovered_from_backup,
            "documents": documents,
            "vocabulary": terms,
            "sqlite_version": sqlite3.sqlite_version,
            # RM-042: None for an owner-only store file; a
            # warning string when an existing file is looser
            # than 0600 (opening never re-permissions it).
            "file_permissions_warning": store_permissions_warning(self._db_path),
        }
