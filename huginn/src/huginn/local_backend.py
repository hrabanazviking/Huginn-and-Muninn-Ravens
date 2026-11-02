"""Huginn's local backend: a fully capable retrieval store with zero
infrastructure — one WAL SQLite file and a maintained inverted term
index.

Scoring modes (honestly labelled):
* ``tfidf`` (default): TF-IDF cosine over the inverted index.
  Lexical semantics — weighted word overlap. Candidate documents come
  from the term postings; no full scans, no N+1.
* embedder mode (``hashing`` / ``sentence-transformers``): vectors are
  stored per document and scored by dense cosine. The scan is linear
  over the *surviving* candidates — the RM-062 in-store prefilter
  applies the RM-053 candidate cap and the category/importance
  filter in SQL before any vector is fetched, so a filtered or
  capped search never transfers the vectors it excludes; the
  survivors are still scored one by one — the right shape for a
  personal memory store (thousands of documents); very large
  corpora belong on Qdrant. Measured at 100k documents in
  ``docs/VECTOR_SCAN.md``.
"""

from __future__ import annotations

import contextlib
import functools
import hashlib
import json
import logging
import math
import sqlite3
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, TypeVar

from ._crypto import (
    StoreCipher,
    meta_and_count_from_connection,
    new_store_cipher,
    open_store_cipher,
    probe_store,
    require_cryptography,
)
from ._db import (
    _error_kind,
    _is_full_error,
    _is_locked_error,
    open_store,
    purge_forgotten_content,
    secure_delete_enabled,
    store_coordination_lock,
    store_permissions_warning,
)
from .config import HuginnConfig
from .errors import HuginnStorageError, HuginnValidationError
from .text import Embedder, cosine, dense_cosine, idf, sparse_tfidf, term_counts, tokenize

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
    store" apart from every other storage failure. A full disk
    is classified the same way (RM-054, ``_is_full_error``) and
    named with the package's own fixed wording; every other
    storage failure is named by the underlying exception's
    class only — SQLite's text is never echoed, because SQLite
    can generate it from the store file itself (TH-14).

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
                if _is_full_error(exc):
                    # RM-054: the disk-full wording is the
                    # package's own fixed text (the RM-029 shape,
                    # kept), never an echo of SQLite's message.
                    raise HuginnStorageError(
                        f"huginn write failed during {operation}: "
                        f"database or disk is full"
                    ) from exc
                raise HuginnStorageError(
                    f"huginn write failed during {operation}: {_error_kind(exc)}"
                ) from exc

        return wrapper

    return decorator


# RM-061: full term sets are fetched for pruning survivors in
# batches of this many candidates — large enough that the
# per-batch queries stay few, small enough that the threshold
# check between batches stops the fetching early. The batch
# size is part of the algorithm's determinism: the same store
# and query always score and prune the same candidates.
# (128, raised from the first draft's 64 during the slice's
# own gate runs: every batch costs a term fetch plus a
# doc_freq lookup, and on a corpus where the bound prunes
# nothing those round trips are pure overhead — halving the
# batch count halves that overhead while the benchmark
# corpus's 230 candidates still span two batches, so the
# gate record keeps showing the narrowing.)
_PRUNE_BATCH = 128


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
        #: RM-053: the last local search's cost accounting
        #: (candidates the index offered, candidates actually
        #: scored, the ceiling, whether it bit) — surfaced by
        #: the facade's ``last_search_stats`` property. A
        #: dedicated accessor, deliberately NOT a ``health()``
        #: field: health snapshots are pinned pure, so
        #: per-call accounting lives here. RM-061 adds
        #: ``candidates_pruned``: TF-IDF candidates the
        #: posting-list bound proved could not reach the
        #: result limit, so their full term sets were never
        #: fetched or scored (always 0 on the vector road).
        self.last_search_stats: dict[str, Any] = {
            "candidates_total": 0,
            "candidates_scored": 0,
            "candidates_pruned": 0,
            "cap": int(config.max_search_candidates),
            "capped": False,
        }
        # RM-049: store encryption setup and the open-time key
        # proof run BEFORE the store is opened, on pure pre-reads,
        # so a refused open (wrong passphrase, a plain open of a
        # marked store, the flag switched on over an existing
        # plain store) leaves the store byte-for-byte untouched.
        self._cipher: StoreCipher | None = None
        self._pending_encryption_meta: dict[str, str] | None = None
        self._deferred_encryption = False
        probe_ok, existing_meta, existing_rows = probe_store(
            self._db_path, "SELECT COUNT(*) FROM documents"
        )
        if config.store_encryption:
            require_cryptography()
            passphrase = config.encryption_passphrase or ""
            if existing_meta is not None:
                self._cipher = open_store_cipher(passphrase, existing_meta, self._db_path)
            elif probe_ok and existing_rows > 0:
                raise HuginnStorageError(
                    f"huginn store {self._db_path} is not encrypted but "
                    f"already holds documents; refusing to open it with "
                    f"store_encryption enabled"
                )
            elif probe_ok or not self._db_path.exists():
                self._cipher, self._pending_encryption_meta = new_store_cipher(passphrase)
            else:
                # The file exists but the probe could not read it
                # (a corrupt main store whose backup may restore
                # an encrypted store): the key proof is deferred
                # to the post-open check, on the live connection.
                self._deferred_encryption = True
        elif existing_meta is not None:
            raise HuginnStorageError(
                f"huginn store {self._db_path} is encrypted; refusing "
                f"to open it without store_encryption enabled"
            )
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
            if self._pending_encryption_meta is not None:
                # RM-049: a new encrypted store takes its marker
                # and wrapped key now, inside the open-time lock,
                # before any document can be written.
                self._write_encryption_meta_locked(self._pending_encryption_meta)
                self._pending_encryption_meta = None
            elif self._deferred_encryption:
                self._establish_deferred_cipher_locked()
            elif (
                meta_and_count_from_connection(
                    self._conn, "SELECT COUNT(*) FROM documents"
                )[0]
                is not None
                and self._cipher is None
            ):
                # RM-049 post-open re-check: the open restored a
                # marked store (e.g. from an encrypted backup)
                # that the pre-read could not see. Never serve it
                # plain — close and refuse.
                self._conn.close()
                self._closed = True
                raise HuginnStorageError(
                    f"huginn store {self._db_path} is encrypted; refusing "
                    f"to open it without store_encryption enabled"
                )
            self._seed_last_ts_locked()
            self.last_heal_report = self._heal_locked()

    def _write_encryption_meta_locked(self, meta: dict[str, str]) -> None:
        """RM-049: write a new store's encryption header (lock held)."""
        for key, value in meta.items():
            self._conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                (key, value),
            )
        self._conn.commit()

    def _establish_deferred_cipher_locked(self) -> None:
        """RM-049: the key proof for a store the pre-read could
        not settle (lock held) — judged on the live connection
        after ``open_store``'s restore road has run. A marked
        store is unlocked (a wrong passphrase refuses, having
        served nothing); an unmarked store holding documents is
        the plain-store refusal; an empty unmarked store takes
        a fresh header."""
        passphrase = self.config.encryption_passphrase or ""
        meta, rows = meta_and_count_from_connection(
            self._conn, "SELECT COUNT(*) FROM documents"
        )
        if meta is not None:
            try:
                self._cipher = open_store_cipher(passphrase, meta, self._db_path)
            except HuginnStorageError:
                self._conn.close()
                self._closed = True
                raise
        elif rows > 0:
            self._conn.close()
            self._closed = True
            raise HuginnStorageError(
                f"huginn store {self._db_path} is not encrypted but "
                f"already holds documents; refusing to open it with "
                f"store_encryption enabled"
            )
        else:
            self._cipher, meta = new_store_cipher(passphrase)
            self._write_encryption_meta_locked(meta)
        self._deferred_encryption = False

    # ─── store encryption transforms (RM-049) ─────────────────────────

    def _enc_value(self, text: str, aad: str) -> str:
        """Seal a stored value when encryption is on (else identity)."""
        return self._cipher.encrypt(text, aad) if self._cipher is not None else text

    def _dec_value(self, value: str, aad: str) -> str:
        """Open a stored value when encryption is on (else identity)."""
        return self._cipher.decrypt(value, aad) if self._cipher is not None else value

    def _term_tag(self, term: str) -> str:
        """The stored form of one index term: the term itself, or
        — with encryption on — its keyed HMAC tag, so TF-IDF's
        equality-only comparisons run unchanged over tags."""
        if self._cipher is None:
            return term
        return self._cipher.lookup_tag(b"term\x00" + term.encode("utf-8"))

    def _stored_content_hash(self, content: str, category: str, plain_hash: str) -> str:
        """The hash the store keeps: the plain SHA-256, or — with
        encryption on — the keyed lookup tag over exactly the
        plain hash's input (category ‖ content, RM-047)."""
        if self._cipher is None:
            return plain_hash
        return self._cipher.lookup_tag(f"{category}\x00{content}".encode())

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
        if self._cipher is not None:
            # RM-049: the index stores keyed tags of the tokens;
            # TF-IDF compares terms for equality only, so the
            # scoring over tags is the plaintext computation.
            counts = {self._term_tag(term): tf for term, tf in counts.items()}
        content_hash = self._stored_content_hash(
            content, category, _content_hash(content, category)
        )
        stored_content = self._enc_value(content, "documents.content")
        stored_tags = self._enc_value(json.dumps(tags), "documents.tags")
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
                        # RM-049: the double check compares the
                        # DECRYPTED stored content.
                        _check_not_a_collision(
                            self._dec_value(clash["content"], "documents.content"),
                            content,
                            int(clash["id"]),
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
                    # RM-049: the check compares DECRYPTED content.
                    _check_not_a_collision(
                        self._dec_value(row["content"], "documents.content"),
                        content,
                        int(row["id"]),
                    )
                    target_id = int(row["id"])
            if target_id is not None:
                self._deindex_terms_locked(target_id)
                conn.execute("DELETE FROM doc_vectors WHERE doc_id = ?", (target_id,))
                conn.execute(
                    "UPDATE documents SET content = ?, content_hash = ?, category = ?,"
                    " importance = ?, tags = ?, emotional_valence = ?, updated_at = ?"
                    " WHERE id = ?",
                    (
                        stored_content, content_hash, category, importance,
                        stored_tags, emotional_valence, at, target_id,
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
                        memory_id, stored_content, content_hash, category, importance,
                        stored_tags, emotional_valence, at, at,
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
                        stored_content, content_hash, category, importance,
                        stored_tags, emotional_valence, at, at,
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
                    (doc_id, self._enc_value(json.dumps(vector), "doc_vectors.vector")),
                )
            conn.commit()
            return doc_id

    def _delete_rows_locked(self, memory_id: int) -> bool:
        """Delete one document's rows (lock held, uncommitted).

        The shared row work of :meth:`delete` and
        :meth:`secure_forget` (RM-051): the term-index rows,
        the vector, and the document itself. The caller
        commits.
        """
        conn = self._ensure_open()
        self._deindex_terms_locked(memory_id)
        conn.execute("DELETE FROM doc_vectors WHERE doc_id = ?", (memory_id,))
        cur = conn.execute("DELETE FROM documents WHERE id = ?", (memory_id,))
        return cur.rowcount > 0

    @_storage_write("delete")
    def delete(self, memory_id: int) -> bool:
        with self._lock:
            removed = self._delete_rows_locked(memory_id)
            self._ensure_open().commit()
            return removed

    @_storage_write("secure_forget")
    def secure_forget(self, memory_id: int) -> bool:
        """Delete one document **and purge its content from the disk**.

        Everything :meth:`delete` does, plus the RM-051 purge
        (threat TH-11; record in ``docs/SECURE_FORGET.md``):
        the delete runs under ``PRAGMA secure_delete=ON``
        (restored afterwards), the WAL is checkpoint-truncated,
        the store is rewritten with ``VACUUM``, the WAL is
        truncated again, and every pre-existing backup
        generation is discarded and replaced by one fresh
        snapshot of the purged store (when ``backup_keep``
        allows one). The purge runs even when nothing live
        was removed, remediating an earlier plain delete's
        residue. Cost: a full store rewrite and the loss of
        all older backup generations — see the record doc.
        """
        with self._lock:
            conn = self._ensure_open()
            with secure_delete_enabled(conn):
                removed = self._delete_rows_locked(memory_id)
                conn.commit()
                purge_forgotten_content(
                    self._db_path, conn, self.config.backup_keep
                )
            return removed

    # ─── reads (pure) ─────────────────────────────────────────────────

    def _row_to_doc(self, row: sqlite3.Row, score: float | None = None) -> dict[str, Any]:
        doc = {
            "id": int(row["id"]),
            "content": self._dec_value(row["content"], "documents.content"),
            "category": row["category"],
            "importance": int(row["importance"]),
            "tags": json.loads(self._dec_value(row["tags"] or "[]", "documents.tags")),
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

    def _record_search_locked(
        self,
        candidates_total: int,
        candidates_scored: int,
        candidates_pruned: int = 0,
    ) -> None:
        """RM-053: record one search's cost accounting.

        The cap bit is judged on the candidates the index
        offered *before* truncation, so a search whose
        candidates were cut records ``capped`` even when the
        category/importance filter later drops some of the
        survivors. Counts only — never content (RM-044).
        RM-061: ``candidates_pruned`` counts the TF-IDF
        candidates the posting-list bound excused from full
        scoring; the vector road always records 0.
        """
        cap = int(self.config.max_search_candidates)
        capped = candidates_total > cap
        self.last_search_stats = {
            "candidates_total": int(candidates_total),
            "candidates_scored": int(candidates_scored),
            "candidates_pruned": int(candidates_pruned),
            "cap": cap,
            "capped": capped,
        }
        if capped:
            logger.warning(
                "huginn: local search candidate cap bit: %d candidates "
                "at cap %d; lowest-id candidates scored, result is partial",
                candidates_total,
                cap,
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
        if self._cipher is not None:
            # RM-049: queries are transformed with the same keyed
            # tag as the index, before any lookup.
            q_counts = {self._term_tag(term): tf for term, tf in q_counts.items()}
        if not q_counts:
            self._record_search_locked(0, 0)
            return []
        total_docs = int(conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0])
        if total_docs == 0:
            self._record_search_locked(0, 0)
            return []
        placeholders = ",".join("?" * len(q_counts))
        # RM-053: the candidate set is capped deterministically
        # (lowest ids first) at config.max_search_candidates;
        # the uncapped total is what _record_search_locked
        # judges the bite by.
        candidate_ids = sorted(
            int(r[0])
            for r in conn.execute(
                f"SELECT DISTINCT doc_id FROM doc_terms WHERE term IN ({placeholders})",
                list(q_counts),
            ).fetchall()
        )
        candidates_total = len(candidate_ids)
        candidate_ids = candidate_ids[: int(self.config.max_search_candidates)]
        docs = self._candidate_docs_locked(conn, candidate_ids, category, min_importance)
        if not docs:
            self._record_search_locked(candidates_total, 0)
            return []
        # RM-061 — posting-list pruning (top-term candidate
        # narrowing). The old road fetched every surviving
        # candidate's FULL term set and scored it. This road
        # first bounds the candidates from the query terms'
        # posting lists alone: for each candidate, the dot
        # product with the query is exact from the postings
        # (a cosine numerator only ever involves shared
        # terms), and its full vector norm is bounded from
        # below by the posting-only sub-vector's norm plus
        # the least the remaining terms can contribute —
        # every remaining token sits on a term whose idf is
        # at least the corpus minimum, and integer term
        # frequencies give sum(tf^2) >= sum(tf) over them,
        # with the candidate's total token count taken from
        # one aggregate query. So dot / (|query| * norm
        # bound) is a true UPPER bound on the candidate's
        # cosine score. (Cosine is
        # scale-invariant per document, so the bound is
        # computed on raw tf*idf weights; the per-document
        # total the TF normalizer divides by cancels.)
        # Candidates are then fully scored best-bound-first,
        # in batches; once `limit` exact scores stand, any
        # remaining candidate whose bound cannot beat — or
        # tie-and-outrank, by the RM-011 id tie-break — the
        # current limit-th score is pruned: its full term set
        # is never fetched. The bound carries a (1 + 1e-9)
        # safety factor so float summation order can never
        # make a prunable candidate of one that could truly
        # reach the limit. Pruning is therefore EXACT: the
        # results are the unpruned search's results, proven
        # by the parity tests in tests/test_candidate_pruning.py
        # and re-verified inside the gate script on every run.
        tph = ",".join("?" * len(q_counts))
        df = {
            r[0]: int(r[1])
            for r in conn.execute(
                f"SELECT term, doc_freq FROM corpus_stats WHERE term IN ({tph})",
                list(q_counts),
            ).fetchall()
        }
        query_vec = sparse_tfidf(q_counts, df, total_docs)
        query_norm = math.sqrt(sum(w * w for w in query_vec.values()))
        term_idf = {term: idf(df.get(term, 0), total_docs) for term in q_counts}
        # The corpus's minimum idf: idf falls as doc_freq
        # grows, so the most frequent term sets the floor
        # every term's weight respects.
        max_df_row = conn.execute("SELECT MAX(doc_freq) FROM corpus_stats").fetchone()
        idf_floor = idf(int(max_df_row[0]), total_docs) if max_df_row and max_df_row[0] else 0.0
        doc_ids = list(docs)
        ph = ",".join("?" * len(doc_ids))
        totals = {
            int(r[0]): int(r[1])
            for r in conn.execute(
                f"SELECT doc_id, SUM(tf) FROM doc_terms WHERE doc_id IN ({ph})"
                " GROUP BY doc_id",
                doc_ids,
            ).fetchall()
        }
        bounds: dict[int, float] = {}
        partial: dict[int, list[float]] = {}
        for doc_id, term, tf in conn.execute(
            f"SELECT doc_id, term, tf FROM doc_terms WHERE term IN ({tph})"
            f" AND doc_id IN ({ph})",
            [*q_counts, *doc_ids],
        ).fetchall():
            acc = partial.setdefault(int(doc_id), [0.0, 0.0, 0])
            raw = int(tf) * term_idf[term]
            acc[0] += query_vec[term] * raw
            acc[1] += raw * raw
            acc[2] += int(tf)
        for doc_id, (dot, norm_sq, query_tf) in partial.items():
            remaining = max(0, totals.get(doc_id, query_tf) - query_tf)
            norm_bound = math.sqrt(norm_sq + remaining * idf_floor * idf_floor)
            if dot > 0.0 and norm_bound > 0.0 and query_norm > 0.0:
                bounds[doc_id] = min(1.0, dot / (query_norm * norm_bound))
            else:
                bounds[doc_id] = 0.0
        # Best bound first; equal bounds resolve by doc id, so
        # the walk — and therefore the scored/pruned counts —
        # is deterministic (RM-011).
        order = sorted(bounds.items(), key=lambda item: (-item[1], item[0]))
        scored: list[tuple[float, int]] = []
        candidates_scored = 0
        idx = 0
        while idx < len(order):
            if scored and limit >= 1 and len(scored) >= limit:
                kth_score, kth_id = sorted(
                    scored, key=lambda item: (-item[0], item[1])
                )[limit - 1]
                bound, first_id = order[idx][1], order[idx][0]
                scaled = bound * (1.0 + 1e-9) + 1e-12
                if scaled < kth_score or (scaled <= kth_score and first_id > kth_id):
                    # This candidate cannot reach the limit —
                    # and neither can any later one: bounds are
                    # non-increasing along the walk, and a later
                    # candidate tying the bound has a larger id,
                    # so it loses the tie-break too.
                    break
            batch = order[idx : idx + _PRUNE_BATCH]
            idx += len(batch)
            batch_ids = [doc_id for doc_id, _ in batch]
            ph = ",".join("?" * len(batch_ids))
            term_rows = conn.execute(
                f"SELECT doc_id, term, tf FROM doc_terms WHERE doc_id IN ({ph})",
                batch_ids,
            ).fetchall()
            per_doc: dict[int, dict[str, int]] = {}
            new_terms: set[str] = set()
            for doc_id, term, tf in term_rows:
                per_doc.setdefault(int(doc_id), {})[term] = int(tf)
                if term not in df:
                    new_terms.add(term)
            if new_terms:
                # One batched doc_freq lookup per batch for the
                # terms the query's own lookup did not cover.
                tph = ",".join("?" * len(new_terms))
                df.update(
                    {
                        r[0]: int(r[1])
                        for r in conn.execute(
                            f"SELECT term, doc_freq FROM corpus_stats WHERE term IN ({tph})",
                            list(new_terms),
                        ).fetchall()
                    }
                )
            for doc_id, counts in per_doc.items():
                candidates_scored += 1
                doc_vec = sparse_tfidf(counts, df, total_docs)
                score = cosine(query_vec, doc_vec)
                if score > 0.0:
                    scored.append((score, doc_id))
        candidates_pruned = len(order) - candidates_scored
        self._record_search_locked(
            candidates_total, candidates_scored, candidates_pruned
        )
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
        # RM-062 — the in-store prefilter. The old road fetched
        # EVERY stored vector's text out of SQLite
        # (``SELECT doc_id, vector FROM doc_vectors``), sorted
        # and capped the rows in Python, and only then applied
        # the category/importance filter to the document rows —
        # so a filtered or capped search still paid the transfer
        # of every vector in the store (at 384 dimensions each
        # vector is ~4.8 KB of JSON text). The prefilter pushes
        # all three cuts into SQL, in the RM-053 order — the
        # candidate cap BEFORE the filter, lowest ids first:
        #   1. the candidate total is a COUNT, not a fetch;
        #   2. the capped candidate ids are selected in the
        #      store (ORDER BY doc_id, LIMIT the cap);
        #   3. the documents fetch (_candidate_docs_locked)
        #      applies category/importance in SQL, as it
        #      already did;
        #   4. only the surviving documents' vectors are
        #      fetched, by id — a filtered-out or capped-out
        #      vector never leaves the store, and (as since
        #      RM-053) is never decoded either.
        # What does NOT change: the survivors are scored by
        # the same linear dense-cosine scan in Python — no
        # index, no approximation — the result list and the
        # RM-053 accounting are exactly the old road's, and an
        # unfiltered search under the cap still fetches and
        # scores every vector. The gate record
        # (docs/VECTOR_SCAN.md) measures both halves at 100k
        # documents and records the verdict.
        candidates_total = int(
            conn.execute("SELECT COUNT(*) FROM doc_vectors").fetchone()[0]
        )
        if candidates_total == 0:
            self._record_search_locked(0, 0)
            return []
        candidate_ids = [
            int(r[0])
            for r in conn.execute(
                "SELECT doc_id FROM doc_vectors ORDER BY doc_id LIMIT ?",
                (int(self.config.max_search_candidates),),
            ).fetchall()
        ]
        docs = self._candidate_docs_locked(conn, candidate_ids, category, min_importance)
        if not docs:
            self._record_search_locked(candidates_total, 0)
            return []
        ph = ",".join("?" * len(docs))
        vectors = {
            int(r["doc_id"]): json.loads(self._dec_value(r["vector"], "doc_vectors.vector"))
            for r in conn.execute(
                f"SELECT doc_id, vector FROM doc_vectors WHERE doc_id IN ({ph})",
                list(docs),
            ).fetchall()
        }
        scored = []
        candidates_scored = 0
        for doc_id in docs:
            if doc_id not in vectors:
                continue
            candidates_scored += 1
            score = dense_cosine(query_vec, vectors[doc_id])
            if score > 0.0:
                scored.append((score, doc_id))
        self._record_search_locked(candidates_total, candidates_scored)
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
