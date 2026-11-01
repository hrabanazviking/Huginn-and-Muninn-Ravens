"""Muninn — Hebbian associative memory.

Muninn is Memory: Odin's raven who flies out and returns with what was
kept. This module is the modern, auditable form of the ancestors'
design (NorseSagaEngine ``yggdrasil/ravens/muninn.py`` + the Yggdrasil
Cognitive Architecture TDD):

* **Nodes** — memories with content, hierarchical path, type/category,
  importance (1–10), emotional valence, tags, metadata.
* **Activation** — every activation is logged (``activation_log``);
  repeated activation restores confidence (TDD: *repeated successful
  thoughts strengthen memory*).
* **Hebbian wiring** — co-activated memories wire together:
  ``strength ← 1 − (1 − strength)(1 − learning_rate)``, bounded in
  [0, 1], with a co-activation count. Connections are stored as
  directed rows in both directions, kept symmetric by this API, because
  the Bifröst bridge reads them directionally.
* **Decay** — low-use state fades multiplicatively
  (``strength *= 0.5 ** (days / half_life)``); edges that fall below
  the prune threshold are deleted and counted.
* **Consolidation** — strong edges are marked consolidated (sleep);
  structural damage is repaired by the same pass.

Read/write honesty (Slice 86, ground 2): every read method here is a
**pure read** — ``get_node``, ``retrieve`` (default), ``get_by_path``,
``get_children``, ``get_associations``, ``spread_activation``,
``activation_count``, ``health``, ``stats``, ``dump`` never mutate the
store, and tests prove it. The write APIs are named as writes:
``activate``, ``activate_batch``, ``associate``, ``store``/``remember``,
``update``, ``delete``/``forget``, ``move``, ``decay``, ``consolidate``,
``heal_structure``. The single reinforcing-read variant is explicit and
opt-in: ``retrieve(..., touch=True)``.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import math
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from itertools import combinations
from typing import Any

from ._db import open_store, take_backup
from .config import MuninnConfig
from .errors import MuninnStorageError, MuninnValidationError

logger = logging.getLogger("muninn")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    content_is_json INTEGER NOT NULL DEFAULT 0,
    content_hash TEXT NOT NULL,
    path TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT 'general',
    importance INTEGER NOT NULL DEFAULT 5,
    emotional_valence REAL NOT NULL DEFAULT 0.0,
    tags TEXT NOT NULL DEFAULT '[]',
    metadata TEXT NOT NULL DEFAULT '{}',
    access_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(content_hash, category, path)
);
CREATE TABLE IF NOT EXISTS activation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id INTEGER NOT NULL,
    activated_at TEXT NOT NULL,
    emotional_valence REAL NOT NULL DEFAULT 0.0,
    source TEXT NOT NULL DEFAULT 'api'
);
CREATE INDEX IF NOT EXISTS idx_activation_memory ON activation_log(memory_id);
CREATE TABLE IF NOT EXISTS hebbian_connections (
    memory_a_id INTEGER NOT NULL,
    memory_b_id INTEGER NOT NULL,
    strength REAL NOT NULL DEFAULT 0.0,
    co_activation_count INTEGER NOT NULL DEFAULT 0,
    consolidated INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    last_coactivated_at TEXT,
    PRIMARY KEY (memory_a_id, memory_b_id)
);
CREATE INDEX IF NOT EXISTS idx_conn_b ON hebbian_connections(memory_b_id);
CREATE TABLE IF NOT EXISTS node_activation (
    memory_id INTEGER PRIMARY KEY,
    total_activations INTEGER NOT NULL DEFAULT 0,
    confidence REAL NOT NULL DEFAULT 1.0,
    last_activated_at TEXT
);
CREATE TABLE IF NOT EXISTS deleted_nodes (
    memory_id INTEGER PRIMARY KEY,
    deleted_at TEXT NOT NULL
);
"""


def _now() -> str:
    """The package's one stored-timestamp source (RM-012).

    Every timestamp written to the store comes from here: UTC,
    ISO-8601, offset-aware. Monotonicity on top of the raw clock
    is :meth:`HebbianMemory._tick`'s job.
    """
    return datetime.now(UTC).isoformat()


# Meta-table key carrying the wall-clock decay marker (RM-021):
# the ISO timestamp of the last decay_wall_clock() run.
_DECAY_MARKER_KEY = "decay_last_run_at"


def _check_memory_id(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise MuninnValidationError(f"memory_id must be an int, got {type(value).__name__}")
    if value < 0:
        raise MuninnValidationError(f"memory_id must be >= 0, got {value}")
    if value > 9223372036854775807:
        raise MuninnValidationError(f"memory_id must be <= 9223372036854775807, got {value}")
    return int(value)


def _check_strength(value: Any) -> float:
    """RM-025: a unit-interval float, typed on every bad shape."""
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not 0.0 <= float(value) <= 1.0
    ):
        raise MuninnValidationError("strength must be in [0, 1]")
    return float(value)


def _check_delta(value: Any) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not 0.0 < float(value) <= 1.0
    ):
        raise MuninnValidationError("delta must be in (0, 1]")
    return float(value)


def _check_min_strength(value: Any) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not 0.0 <= float(value) <= 1.0
    ):
        raise MuninnValidationError("min_strength must be in [0, 1]")
    return float(value)


def _check_attenuation(value: Any) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not 0.0 < float(value) <= 1.0
    ):
        raise MuninnValidationError("attenuation must be in (0, 1]")
    return float(value)


def _check_threshold(value: Any) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not 0.0 < float(value) <= 1.0
    ):
        raise MuninnValidationError("threshold must be in (0, 1]")
    return float(value)


def _check_count(value: Any, what: str) -> int:
    """RM-025: an integer count (limit / depth / top_k), typed.

    Plain ints pass; finite integral floats are accepted as
    before (``int()`` semantics); everything else — strings,
    containers, NaN, infinities, bools — is a typed refusal
    instead of a bare ``TypeError``/``ValueError`` from ``int()``.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)) or (
        isinstance(value, float) and not (math.isfinite(value) and value.is_integer())
    ):
        raise MuninnValidationError(f"{what} must be an int, got {type(value).__name__}")
    return int(value)


def _check_tag_list(tags: Any) -> list[Any]:
    """RM-025: the tags argument is a list/tuple (or None)."""
    if tags is None:
        return []
    if isinstance(tags, (str, bytes)) or not isinstance(tags, (list, tuple)):
        raise MuninnValidationError("tags must be a list of strings")
    return list(tags)


def _check_importance(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise MuninnValidationError(f"importance must be an int in [1, 10], got {value!r}")
    if not 1 <= value <= 10:
        raise MuninnValidationError(f"importance must be in [1, 10], got {value}")
    return int(value)


def _check_valence(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MuninnValidationError(f"emotional_valence must be a number in [-1, 1], got {value!r}")
    v = float(value)
    if not -1.0 <= v <= 1.0:
        raise MuninnValidationError(f"emotional_valence must be in [-1, 1], got {v}")
    return v


def _content_payload(content: Any) -> tuple[str, int, str]:
    """(stored_text, is_json, content_hash) for node content."""
    if isinstance(content, str):
        return content, 0, hashlib.sha256(("s:" + content).encode()).hexdigest()
    try:
        text = json.dumps(content, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise MuninnValidationError(
            "content must be a string or JSON-serializable value"
        ) from exc
    return text, 1, hashlib.sha256(("j:" + text).encode()).hexdigest()


@dataclass
class MemoryNode:
    """A node in Muninn's memory — the ancestor's shape, integer-keyed."""

    id: int
    content: Any
    path: str = ""
    memory_type: str = "fact"
    importance: int = 5
    emotional_valence: float = 0.0
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    access_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def category(self) -> str:
        """Alias for ``memory_type`` (Bifröst-era vocabulary)."""
        return self.memory_type

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "path": self.path,
            "memory_type": self.memory_type,
            "category": self.memory_type,
            "importance": self.importance,
            "emotional_valence": self.emotional_valence,
            "tags": list(self.tags),
            "metadata": dict(self.metadata),
            "access_count": self.access_count,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryNode:
        def _dt(key: str) -> datetime:
            raw = data.get(key)
            if isinstance(raw, datetime):
                return raw
            if raw:
                return datetime.fromisoformat(str(raw))
            return datetime.now(UTC)

        return cls(
            id=int(data["id"]),
            content=data.get("content"),
            path=data.get("path", ""),
            memory_type=data.get("memory_type", data.get("category", "fact")),
            importance=int(data.get("importance", 5)),
            emotional_valence=float(data.get("emotional_valence", 0.0)),
            tags=list(data.get("tags", [])),
            metadata=dict(data.get("metadata", {})),
            access_count=int(data.get("access_count", 0)),
            created_at=_dt("created_at"),
            updated_at=_dt("updated_at"),
        )


class HebbianMemory:
    """Hebbian associative memory over one SQLite store.

    Constructed as ``HebbianMemory(MuninnConfig(db_path=...))`` — the
    exact shape Bifröst uses. Construction opens **only this store**
    (never any other package's), runs the integrity/self-heal pass,
    and is safe to perform from any thread; all methods are serialized
    internally and safe under concurrent use.
    """

    MAX_QUERY_RESULTS = 1000

    def __init__(self, config: MuninnConfig | None = None, **overrides: Any):
        if config is None:
            config = MuninnConfig(**overrides)
        elif overrides:
            from dataclasses import replace

            config = replace(config, **overrides)
        self.config = config
        self._lock = threading.RLock()
        self._ts_lock = threading.Lock()
        self._last_ts: datetime | None = None
        self._closed = False
        self._db_path = config.resolved_path()
        conn, report = open_store(
            self._db_path,
            busy_timeout_ms=config.busy_timeout_ms,
            backup_keep=config.backup_keep,
            auto_backup=config.auto_backup,
            schema_sql=SCHEMA_SQL,
        )
        self._conn = conn
        self.open_report = report
        #: True when the store had to be restored from a rolling backup.
        self.recovered_from_backup = report.recovered_from_backup
        with self._lock:
            self._seed_last_ts_locked()
            self.last_heal_report = self._heal_locked()

    # ─── timestamp discipline (RM-012) ────────────────────────────────

    def _seed_last_ts_locked(self) -> None:
        """Seed the monotonic guard from the store's own history.

        A store reopened after the system clock moved backwards
        must still never issue a timestamp at or before one it
        already carries.
        """
        peaks: list[str] = []
        for sql in (
            "SELECT MAX(activated_at) FROM activation_log",
            "SELECT MAX(updated_at) FROM nodes",
            "SELECT MAX(last_coactivated_at) FROM hebbian_connections",
            "SELECT MAX(last_activated_at) FROM node_activation",
            "SELECT MAX(deleted_at) FROM deleted_nodes",
        ):
            row = self._conn.execute(sql).fetchone()
            if row and row[0]:
                peaks.append(str(row[0]))
        if peaks:
            self._last_ts = max(datetime.fromisoformat(p) for p in peaks)

    def _tick(self) -> str:
        """Next stored timestamp: ``_now()``, monotonic (RM-012).

        If the system clock has moved backwards — or has not
        moved at all since the last issue — the result is the
        last issued timestamp plus one microsecond, so stored
        timestamps (above all the activation log) are strictly
        increasing in issue order no matter what the wall clock
        does.
        """
        candidate = datetime.fromisoformat(_now())
        with self._ts_lock:
            if self._last_ts is not None and candidate <= self._last_ts:
                candidate = self._last_ts + timedelta(microseconds=1)
            self._last_ts = candidate
        return candidate.isoformat()

    # ─── lifecycle ────────────────────────────────────────────────────

    def _get_conn(self) -> sqlite3.Connection:
        """The shared store connection (internal seam).

        Bifröst's ``_get_activation_count`` runs a raw ``SELECT`` over
        ``activation_log`` through this method; the connection is the
        store's own, Row-factory enabled. Callers must treat it as
        read-mostly and must not commit behind Muninn's back.
        """
        if self._closed:
            raise MuninnStorageError("HebbianMemory is closed")
        return self._conn

    def close(self) -> None:
        """Close the store. Idempotent — closing twice is a no-op."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            with contextlib.suppress(sqlite3.Error):
                self._conn.close()

    def __enter__(self) -> HebbianMemory:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def backup(self) -> str | None:
        """Take a rolling backup now; returns its path (or None)."""
        with self._lock:
            self._get_conn()
            self._conn.commit()
            taken = take_backup(self._db_path, self.config.backup_keep)
            return str(taken) if taken else None

    # ─── internal write helpers (lock held by callers) ────────────────

    def _log_activation_locked(
        self, memory_id: int, emotional_valence: float, source: str, at: str
    ) -> int:
        self._conn.execute(
            "INSERT INTO activation_log (memory_id, activated_at, emotional_valence, source)"
            " VALUES (?, ?, ?, ?)",
            (memory_id, at, emotional_valence, source),
        )
        lr = self.config.learning_rate
        self._conn.execute(
            "INSERT INTO node_activation (memory_id, total_activations, confidence,"
            " last_activated_at)"
            " VALUES (?, 1, 1.0, ?)"
            " ON CONFLICT(memory_id) DO UPDATE SET"
            "   total_activations = total_activations + 1,"
            "   confidence = MIN(1.0, confidence + ? * (1.0 - confidence)),"
            "   last_activated_at = excluded.last_activated_at",
            (memory_id, at, lr),
        )
        self._conn.execute(
            "UPDATE nodes SET access_count = access_count + 1, updated_at = ? WHERE id = ?",
            (at, memory_id),
        )
        self._conn.execute("DELETE FROM deleted_nodes WHERE memory_id = ?", (memory_id,))
        row = self._conn.execute(
            "SELECT total_activations FROM node_activation WHERE memory_id = ?",
            (memory_id,),
        ).fetchone()
        return int(row[0]) if row else 0

    def _wire_pair_locked(self, a: int, b: int, at: str) -> bool:
        """Strengthen the a↔b wiring (both directed rows). True if new."""
        lr = self.config.learning_rate
        created = False
        for x, y in ((a, b), (b, a)):
            exists = self._conn.execute(
                "SELECT 1 FROM hebbian_connections WHERE memory_a_id = ? AND memory_b_id = ?",
                (x, y),
            ).fetchone()
            if exists is None:
                created = True
            self._conn.execute(
                "INSERT INTO hebbian_connections"
                " (memory_a_id, memory_b_id, strength, co_activation_count,"
                "  consolidated, created_at, last_coactivated_at)"
                " VALUES (?, ?, ?, 1, 0, ?, ?)"
                " ON CONFLICT(memory_a_id, memory_b_id) DO UPDATE SET"
                "   strength = 1.0 - (1.0 - strength) * ?,"
                "   co_activation_count = co_activation_count + 1,"
                "   last_coactivated_at = excluded.last_coactivated_at",
                (x, y, lr, at, at, 1.0 - lr),
            )
        return created

    def _heal_locked(self) -> dict[str, Any]:
        """Repair structural drift. Caller holds the lock; commits."""
        report = {
            "self_edges_pruned": 0,
            "dangling_edges_pruned": 0,
            "pairs_repaired": 0,
            "counters_fixed": 0,
        }
        cur = self._conn.execute(
            "DELETE FROM hebbian_connections WHERE memory_a_id = memory_b_id"
        )
        report["self_edges_pruned"] = cur.rowcount
        cur = self._conn.execute(
            "DELETE FROM hebbian_connections"
            " WHERE memory_a_id IN (SELECT memory_id FROM deleted_nodes)"
            "    OR memory_b_id IN (SELECT memory_id FROM deleted_nodes)"
        )
        report["dangling_edges_pruned"] = cur.rowcount
        # Asymmetry repair: insert missing reverse rows; reconcile pairs
        # whose two directions disagree to the stronger of the two.
        rows = self._conn.execute(
            "SELECT memory_a_id, memory_b_id, strength, co_activation_count,"
            " consolidated, created_at, last_coactivated_at FROM hebbian_connections"
            " ORDER BY memory_a_id, memory_b_id"
        ).fetchall()
        by_pair = {(r[0], r[1]): r for r in rows}
        for (a, b), r in list(by_pair.items()):
            reverse = by_pair.get((b, a))
            if reverse is None:
                self._conn.execute(
                    "INSERT INTO hebbian_connections"
                    " (memory_a_id, memory_b_id, strength, co_activation_count,"
                    "  consolidated, created_at, last_coactivated_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (b, a, r[2], r[3], r[4], r[5], r[6]),
                )
                report["pairs_repaired"] += 1
            elif (reverse[2], reverse[3]) != (r[2], r[3]):
                strength = max(r[2], reverse[2])
                count = max(r[3], reverse[3])
                consolidated = min(r[4], reverse[4])
                self._conn.execute(
                    "UPDATE hebbian_connections SET strength = ?, co_activation_count = ?,"
                    " consolidated = ? WHERE (memory_a_id = ? AND memory_b_id = ?)"
                    " OR (memory_a_id = ? AND memory_b_id = ?)",
                    (strength, count, consolidated, a, b, b, a),
                )
                report["pairs_repaired"] += 1
        # Counter reconciliation: node_activation totals must equal the log.
        logged_rows = self._conn.execute(
            "SELECT memory_id, COUNT(*) AS c, MAX(activated_at) AS max_at"
            " FROM activation_log GROUP BY memory_id"
        ).fetchall()
        for memory_id, logged, max_at in logged_rows:
            row = self._conn.execute(
                "SELECT total_activations FROM node_activation WHERE memory_id = ?",
                (memory_id,),
            ).fetchone()
            if row is None:
                self._conn.execute(
                    "INSERT INTO node_activation"
                    " (memory_id, total_activations, confidence, last_activated_at)"
                    " VALUES (?, ?, 1.0, ?)",
                    (memory_id, logged, max_at),
                )
                report["counters_fixed"] += 1
            elif int(row[0]) != int(logged):
                self._conn.execute(
                    "UPDATE node_activation SET total_activations = ? WHERE memory_id = ?",
                    (logged, memory_id),
                )
                report["counters_fixed"] += 1
        self._conn.commit()
        report["fixes"] = sum(report.values())
        if report["fixes"]:
            logger.warning("muninn: heal repaired %s", report)
        return report

    # ─── write API: activation and wiring ─────────────────────────────

    def activate(
        self, memory_id: int, *, emotional_valence: float = 0.0, source: str = "api"
    ) -> int:
        """Log one activation of ``memory_id`` (a WRITE, by name).

        Inserts one ``activation_log`` row, increments the id's
        activation counter, restores its confidence toward 1.0, and —
        if a node with this id lives in this store — bumps its access
        count. Returns the id's new total activation count.
        """
        memory_id = _check_memory_id(memory_id)
        emotional_valence = _check_valence(emotional_valence)
        with self._lock:
            self._get_conn()
            total = self._log_activation_locked(
                memory_id, emotional_valence, str(source), self._tick()
            )
            self._conn.commit()
            return total

    def activate_batch(
        self,
        memory_ids: list[int],
        *,
        emotional_valence: float = 0.0,
        source: str = "api",
    ) -> dict[str, Any]:
        """Log activations for a co-active set AND wire every pair (WRITE).

        This is the Hebbian operation Bifröst's reinforcement calls:
        each unique id is activated once, then every unordered pair is
        strengthened in both directions. Fully transactional — a crash
        leaves either the whole batch or none of it.
        """
        if not isinstance(memory_ids, (list, tuple)):
            raise MuninnValidationError("memory_ids must be a list of ints")
        ids = list(dict.fromkeys(_check_memory_id(m) for m in memory_ids))
        emotional_valence = _check_valence(emotional_valence)
        at = self._tick()
        with self._lock:
            self._get_conn()
            for mid in ids:
                self._log_activation_locked(mid, emotional_valence, str(source), at)
            created = 0
            pairs = 0
            for a, b in combinations(ids, 2):
                pairs += 1
                if self._wire_pair_locked(a, b, at):
                    created += 1
            self._conn.commit()
            return {
                "activated": len(ids),
                "pairs_wired": pairs,
                "connections_created": created,
                "connections_strengthened": pairs - created,
            }

    def associate(
        self,
        memory_a: int,
        memory_b: int,
        *,
        strength: float | None = None,
        delta: float | None = None,
    ) -> float:
        """Manually wire two memories (WRITE). Returns the new strength.

        With ``strength``: set both directed rows to it (count +1).
        With ``delta`` (or neither): apply the bounded Hebbian update
        with ``delta`` as the learning rate for this call.
        """
        a = _check_memory_id(memory_a)
        b = _check_memory_id(memory_b)
        if a == b:
            raise MuninnValidationError("cannot associate a memory with itself")
        if strength is not None and delta is not None:
            raise MuninnValidationError("pass strength or delta, not both")
        # RM-025: both numeric arguments are fully validated BEFORE
        # any write — previously an invalid delta was only checked
        # inside the write loop, after a tombstone delete had
        # already been issued in the same uncommitted transaction.
        strength_value = _check_strength(strength) if strength is not None else None
        rate = (
            self.config.learning_rate if delta is None else _check_delta(delta)
        )
        at = self._tick()
        with self._lock:
            self._get_conn()
            for x, y in ((a, b), (b, a)):
                self._conn.execute("DELETE FROM deleted_nodes WHERE memory_id = ?", (x,))
                if strength_value is not None:
                    self._conn.execute(
                        "INSERT INTO hebbian_connections"
                        " (memory_a_id, memory_b_id, strength, co_activation_count,"
                        "  consolidated, created_at, last_coactivated_at)"
                        " VALUES (?, ?, ?, 1, 0, ?, ?)"
                        " ON CONFLICT(memory_a_id, memory_b_id) DO UPDATE SET"
                        "   strength = excluded.strength,"
                        "   co_activation_count = co_activation_count + 1,"
                        "   last_coactivated_at = excluded.last_coactivated_at",
                        (x, y, strength_value, at, at),
                    )
                else:
                    self._conn.execute(
                        "INSERT INTO hebbian_connections"
                        " (memory_a_id, memory_b_id, strength, co_activation_count,"
                        "  consolidated, created_at, last_coactivated_at)"
                        " VALUES (?, ?, ?, 1, 0, ?, ?)"
                        " ON CONFLICT(memory_a_id, memory_b_id) DO UPDATE SET"
                        "   strength = 1.0 - (1.0 - strength) * ?,"
                        "   co_activation_count = co_activation_count + 1,"
                        "   last_coactivated_at = excluded.last_coactivated_at",
                        (x, y, rate, at, at, 1.0 - rate),
                    )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT strength FROM hebbian_connections"
                " WHERE memory_a_id = ? AND memory_b_id = ?",
                (a, b),
            ).fetchone()
            return float(row[0]) if row else 0.0

    # ─── read API (pure reads — never mutate) ─────────────────────────

    def get_associations(
        self, memory_id: int, min_strength: float = 0.0, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Associations of a memory, strongest first. PURE READ.

        Each dict: ``memory_id`` (the other end), ``strength``,
        ``co_activation_count``, ``consolidated``, ``last_coactivated_at``.
        Bifröst consumes ``[0]["strength"]`` as its associative boost,
        so ordering by strength DESC is contractual.
        """
        memory_id = _check_memory_id(memory_id)
        min_strength = _check_min_strength(min_strength)
        limit = max(1, min(_check_count(limit, "limit"), 10000))
        with self._lock:
            rows = self._get_conn().execute(
                "SELECT memory_b_id, strength, co_activation_count, consolidated,"
                " last_coactivated_at FROM hebbian_connections"
                " WHERE memory_a_id = ? AND strength >= ?"
                " ORDER BY strength DESC, co_activation_count DESC, memory_b_id ASC"
                " LIMIT ?",
                (memory_id, float(min_strength), limit),
            ).fetchall()
        return [
            {
                "memory_id": int(r[0]),
                "strength": float(r[1]),
                "co_activation_count": int(r[2]),
                "consolidated": bool(r[3]),
                "last_coactivated_at": r[4],
            }
            for r in rows
        ]

    def activation_count(self, memory_id: int) -> int:
        """How many activations this id has logged. PURE READ."""
        memory_id = _check_memory_id(memory_id)
        with self._lock:
            row = self._get_conn().execute(
                "SELECT COUNT(*) FROM activation_log WHERE memory_id = ?",
                (memory_id,),
            ).fetchone()
        return int(row[0]) if row else 0

    def spread_activation(
        self,
        seed_ids: list[int],
        *,
        depth: int = 2,
        attenuation: float = 0.5,
        min_strength: float = 0.0,
        limit: int = 1000,
    ) -> dict[int, float]:
        """Activation spreading over the wiring. PURE READ.

        Seeds start at 1.0; each hop multiplies by edge strength and
        ``attenuation``. Returns ``{memory_id: activation}`` (seeds
        included), strongest first in iteration order.
        """
        if not isinstance(seed_ids, (list, tuple)):
            raise MuninnValidationError("seed_ids must be a list of ints")
        seeds = [_check_memory_id(m) for m in seed_ids]
        attenuation = _check_attenuation(attenuation)
        min_strength = _check_min_strength(min_strength)
        depth = max(0, min(_check_count(depth, "depth"), 10))
        limit = max(1, _check_count(limit, "limit"))
        levels: dict[int, float] = dict.fromkeys(seeds, 1.0)
        frontier = dict(levels)
        with self._lock:
            conn = self._get_conn()
            for _ in range(depth):
                next_frontier: dict[int, float] = {}
                for mid, level in frontier.items():
                    rows = conn.execute(
                        "SELECT memory_b_id, strength FROM hebbian_connections"
                        " WHERE memory_a_id = ? AND strength >= ?",
                        (mid, float(min_strength)),
                    ).fetchall()
                    for other, strength in rows:
                        value = level * float(strength) * float(attenuation)
                        if value > next_frontier.get(other, 0.0):
                            next_frontier[other] = value
                for mid, value in next_frontier.items():
                    if value > levels.get(mid, 0.0):
                        levels[mid] = value
                frontier = next_frontier
                if not frontier:
                    break
        # RM-011 determinism pin: ties on activation resolve by id, so
        # iteration order never depends on query-plan row order.
        ranked = sorted(levels.items(), key=lambda kv: (-kv[1], kv[0]))
        return dict(ranked[:limit])

    # ─── node API (ancestor semantics) ────────────────────────────────

    def remember(
        self,
        content: Any,
        *,
        category: str = "general",
        path: str = "",
        importance: int = 5,
        tags: list[str] | None = None,
        emotional_valence: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Store a memory node; returns its integer id (WRITE).

        Idempotent: storing the same content under the same category
        and path returns the existing node's id instead of duplicating
        it (content-hash unique index) — safe under retries.
        """
        if content is None:
            raise MuninnValidationError("content must not be None")
        importance = _check_importance(importance)
        emotional_valence = _check_valence(emotional_valence)
        text, is_json, content_hash = _content_payload(content)
        clean_tags = [
            str(t).strip().lower()[:64] for t in _check_tag_list(tags) if str(t).strip()
        ]
        try:
            meta_text = json.dumps(metadata or {}, sort_keys=True, default=str)
        except (TypeError, ValueError) as exc:
            raise MuninnValidationError("metadata must be JSON-serializable") from exc
        at = self._tick()
        with self._lock:
            self._get_conn()
            cur = self._conn.execute(
                "INSERT OR IGNORE INTO nodes"
                " (content, content_is_json, content_hash, path, category, importance,"
                "  emotional_valence, tags, metadata, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    text, is_json, content_hash, str(path), str(category), importance,
                    emotional_valence, json.dumps(clean_tags), meta_text, at, at,
                ),
            )
            if cur.rowcount == 1:
                if cur.lastrowid is None:
                    raise MuninnStorageError(
                        "node insert reported success but returned no row id"
                    )
                node_id = int(cur.lastrowid)
                is_new = True
            else:
                row = self._conn.execute(
                    "SELECT id FROM nodes WHERE content_hash = ? AND category = ? AND path = ?",
                    (content_hash, str(category), str(path)),
                ).fetchone()
                node_id = int(row[0])
                is_new = False
            self._conn.commit()
            if is_new:
                self._apply_backpressure_locked()
            return node_id

    def store(
        self,
        content: Any,
        path: str = "",
        memory_type: str = "fact",
        importance: int = 5,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        *,
        emotional_valence: float = 0.0,
    ) -> int:
        """Ancestor-shaped alias of :meth:`remember` (category = type)."""
        return self.remember(
            content,
            category=memory_type,
            path=path,
            importance=importance,
            tags=tags,
            emotional_valence=emotional_valence,
            metadata=metadata,
        )

    def _row_to_node(self, row: sqlite3.Row) -> MemoryNode:
        content = row["content"]
        if row["content_is_json"]:
            content = json.loads(content)
        return MemoryNode(
            id=int(row["id"]),
            content=content,
            path=row["path"],
            memory_type=row["category"],
            importance=int(row["importance"]),
            emotional_valence=float(row["emotional_valence"]),
            tags=json.loads(row["tags"] or "[]"),
            metadata=json.loads(row["metadata"] or "{}"),
            access_count=int(row["access_count"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def get_node(self, memory_id: int) -> MemoryNode | None:
        """One node by id, or None. PURE READ."""
        memory_id = _check_memory_id(memory_id)
        with self._lock:
            row = self._get_conn().execute(
                "SELECT * FROM nodes WHERE id = ?", (memory_id,)
            ).fetchone()
        return self._row_to_node(row) if row else None

    def retrieve(
        self,
        query: str | None = None,
        path: str | None = None,
        tags: list[str] | None = None,
        memory_type: str | None = None,
        top_k: int = 5,
        *,
        category: str | None = None,
        touch: bool = False,
    ) -> list[MemoryNode]:
        """Retrieve nodes by filters (ancestor semantics). PURE READ
        unless ``touch=True``.

        ``query`` is a case-insensitive substring match over content
        (the ancestor's semantics). Results sort by importance, then
        recency. With ``touch=True`` — the explicitly named reinforcing
        read — each returned node is also activated (see
        :meth:`activate`); the default is a pure read.
        """
        top_k = max(1, min(_check_count(top_k, "top_k"), self.MAX_QUERY_RESULTS))
        wanted_tags = [str(t).lower() for t in _check_tag_list(tags)] if tags else []
        wanted_type = category or memory_type
        sql = "SELECT * FROM nodes WHERE 1=1"
        params: list[Any] = []
        if wanted_type:
            sql += " AND category = ?"
            params.append(str(wanted_type))
        if path:
            sql += " AND (path = ? OR path LIKE ?)"
            params.extend([str(path), str(path).rstrip("/") + "/%"])
        rows_out: list[MemoryNode] = []
        with self._lock:
            rows = self._get_conn().execute(sql, params).fetchall()
            for row in rows:
                node = self._row_to_node(row)
                if wanted_tags and not any(t in node.tags for t in wanted_tags):
                    continue
                if query:
                    haystack = (
                        node.content if isinstance(node.content, str)
                        else json.dumps(node.content, default=str)
                    ).lower()
                    if str(query).lower() not in haystack:
                        continue
                rows_out.append(node)
            # RM-011 determinism pin: id breaks (importance, updated_at)
            # ties — identical timestamps must not leave order to chance.
            rows_out.sort(
                key=lambda n: (n.importance, n.updated_at, n.id), reverse=True
            )
            rows_out = rows_out[:top_k]
            if touch:
                at = self._tick()
                for node in rows_out:
                    self._log_activation_locked(
                        node.id, node.emotional_valence, "retrieve:touch", at
                    )
                self._conn.commit()
        return rows_out

    def get_by_path(self, path: str) -> list[MemoryNode]:
        """All nodes at exactly ``path``. PURE READ."""
        with self._lock:
            rows = self._get_conn().execute(
                "SELECT * FROM nodes WHERE path = ?"
                " ORDER BY importance DESC, updated_at DESC, id ASC",
                (str(path),),
            ).fetchall()
        return [self._row_to_node(r) for r in rows]

    def get_children(self, parent_path: str) -> dict[str, list[MemoryNode]]:
        """Nodes grouped by every path under ``parent_path``. PURE READ."""
        prefix = str(parent_path).rstrip("/") + "/"
        children: dict[str, list[MemoryNode]] = {}
        with self._lock:
            rows = self._get_conn().execute(
                "SELECT * FROM nodes WHERE path LIKE ?"
                " ORDER BY path, importance DESC, id ASC",
                (prefix + "%",),
            ).fetchall()
        for row in rows:
            node = self._row_to_node(row)
            children.setdefault(node.path, []).append(node)
        return children

    def update(self, node_id: int, content: Any = None, **fields: Any) -> bool:
        """Update a node's fields (WRITE). False when no such node."""
        node_id = _check_memory_id(node_id)
        allowed = {
            "importance", "emotional_valence", "tags", "metadata",
            "path", "memory_type", "category",
        }
        unknown = set(fields) - allowed
        if unknown:
            raise MuninnValidationError(f"unknown node fields: {sorted(unknown)}")
        with self._lock:
            self._get_conn()
            row = self._conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
            if row is None:
                return False
            updates: dict[str, Any] = {}
            if content is not None:
                text, is_json, content_hash = _content_payload(content)
                updates["content"] = text
                updates["content_is_json"] = is_json
                updates["content_hash"] = content_hash
            if "importance" in fields:
                updates["importance"] = _check_importance(fields["importance"])
            if "emotional_valence" in fields:
                updates["emotional_valence"] = _check_valence(fields["emotional_valence"])
            if "tags" in fields:
                updates["tags"] = json.dumps(
                    [
                        str(t).strip().lower()[:64]
                        for t in _check_tag_list(fields["tags"])
                        if str(t).strip()
                    ]
                )
            if "metadata" in fields:
                try:
                    updates["metadata"] = json.dumps(
                        fields["metadata"] or {}, sort_keys=True, default=str
                    )
                except (TypeError, ValueError) as exc:
                    raise MuninnValidationError(
                        "metadata must be JSON-serializable"
                    ) from exc
            if "path" in fields:
                updates["path"] = str(fields["path"])
            if "memory_type" in fields or "category" in fields:
                updates["category"] = str(fields.get("memory_type", fields.get("category")))
            if not updates:
                return True
            updates["updated_at"] = self._tick()
            assignments = ", ".join(f"{k} = ?" for k in updates)
            try:
                self._conn.execute(
                    f"UPDATE nodes SET {assignments} WHERE id = ?",
                    (*updates.values(), node_id),
                )
            except sqlite3.IntegrityError as exc:
                self._conn.rollback()
                raise MuninnValidationError(
                    "update would duplicate an existing node (same content, category, path)"
                ) from exc
            self._conn.commit()
            return True

    def forget(self, memory_id: int) -> bool:
        """Remove a memory's node and all its wiring (WRITE).

        The id is tombstoned so :meth:`heal_structure` can prune any
        edge that later references it; the activation *log* is kept —
        it is a log. Returns True when anything was removed. A later
        activation of the same id clears the tombstone (the caller's
        world says the id lives again).
        """
        memory_id = _check_memory_id(memory_id)
        with self._lock:
            self._get_conn()
            removed = False
            cur = self._conn.execute("DELETE FROM nodes WHERE id = ?", (memory_id,))
            removed = removed or cur.rowcount > 0
            cur = self._conn.execute(
                "DELETE FROM hebbian_connections WHERE memory_a_id = ? OR memory_b_id = ?",
                (memory_id, memory_id),
            )
            removed = removed or cur.rowcount > 0
            # The tombstone is written even when nothing existed: it is
            # the standing record that this id was deliberately
            # forgotten, so heal prunes any later stray edge to it.
            self._conn.execute(
                "INSERT OR REPLACE INTO deleted_nodes (memory_id, deleted_at) VALUES (?, ?)",
                (memory_id, self._tick()),
            )
            self._conn.commit()
            return removed

    def delete(self, node_id: int) -> bool:
        """Ancestor-shaped alias of :meth:`forget`."""
        return self.forget(node_id)

    def move(self, node_id: int, new_path: str) -> bool:
        """Move a node to a new hierarchical path (WRITE)."""
        return self.update(node_id, path=str(new_path))

    def get_tree_structure(self) -> dict[str, Any]:
        """The hierarchical path tree with node counts. PURE READ."""
        tree: dict[str, Any] = {}
        with self._lock:
            rows = self._get_conn().execute(
                "SELECT path, COUNT(*) AS c FROM nodes GROUP BY path ORDER BY path"
            ).fetchall()
        for path, count in rows:
            parts = [p for p in str(path).split("/") if p]
            current = tree
            for part in parts:
                current = current.setdefault(part, {})
            current["_nodes"] = int(count)
        return tree

    def _apply_backpressure_locked(self) -> None:
        """Ancestor backpressure: prune lowest-value nodes over the cap."""
        count = self._conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        overflow = int(count) - self.config.max_nodes
        if overflow <= 0:
            return
        victims = self._conn.execute(
            "SELECT id FROM nodes ORDER BY importance ASC, access_count ASC,"
            " updated_at ASC, id ASC LIMIT ?",
            (overflow,),
        ).fetchall()
        for (victim,) in victims:
            self._conn.execute("DELETE FROM nodes WHERE id = ?", (victim,))
            self._conn.execute(
                "DELETE FROM hebbian_connections WHERE memory_a_id = ? OR memory_b_id = ?",
                (victim, victim),
            )
            self._conn.execute(
                "INSERT OR REPLACE INTO deleted_nodes (memory_id, deleted_at) VALUES (?, ?)",
                (victim, self._tick()),
            )
        self._conn.commit()
        logger.warning("muninn: backpressure pruned %d lowest-value nodes", len(victims))

    # ─── maintenance: heal / decay / consolidate (WRITES, named) ──────

    def heal_structure(self) -> dict[str, Any]:
        """Run the self-healing pass now; returns its report (WRITE).

        Fixes: self-edges pruned; edges touching forgotten ids pruned;
        asymmetric directed pairs repaired (missing reverse inserted,
        disagreeing pairs reconciled to the stronger); activation
        counters reconciled against the activation log.
        """
        with self._lock:
            self._get_conn()
            self.last_heal_report = self._heal_locked()
            return dict(self.last_heal_report)

    def decay(self, days: float = 1.0) -> dict[str, Any]:
        """Fade strengths and confidences by elapsed ``days`` (WRITE).

        Edge strengths multiply by ``0.5 ** (days / edge_half_life)``;
        edges falling below the prune threshold are deleted. Node
        confidences multiply by their own half-life factor. Returns
        exact counts. Deterministic and safe to re-run.
        """
        if (
            isinstance(days, bool)
            or not isinstance(days, (int, float))
            or not math.isfinite(float(days))
            or float(days) < 0
        ):
            raise MuninnValidationError("days must be a number >= 0")
        days = float(days)
        edge_factor = 0.5 ** (days / self.config.decay_half_life_days)
        conf_factor = 0.5 ** (days / self.config.confidence_half_life_days)
        with self._lock:
            self._get_conn()
            if self.config.auto_backup:
                self._conn.commit()
                take_backup(self._db_path, self.config.backup_keep)
            cur = self._conn.execute(
                "UPDATE hebbian_connections SET strength = strength * ?", (edge_factor,)
            )
            decayed = cur.rowcount
            cur = self._conn.execute(
                "UPDATE hebbian_connections SET consolidated = 0 WHERE strength < ?",
                (self.config.consolidation_threshold,),
            )
            cur = self._conn.execute(
                "DELETE FROM hebbian_connections WHERE strength < ?",
                (self.config.prune_threshold,),
            )
            pruned = cur.rowcount
            cur = self._conn.execute(
                "UPDATE node_activation SET confidence = confidence * ?", (conf_factor,)
            )
            confidences = cur.rowcount
            self._conn.commit()
            return {
                "days": days,
                "edge_factor": edge_factor,
                "confidence_factor": conf_factor,
                "edges_decayed": decayed,
                "edges_pruned": pruned,
                "confidences_decayed": confidences,
            }

    def decay_wall_clock(self) -> dict[str, Any]:
        """Fade by the wall-clock time since the last such run (WRITE).

        The optional wall-clock mode (RM-021) — off by default:
        plain :meth:`decay` never reads the clock and never
        touches this mode's marker; the wall-clock mode runs
        only when this method is called. The store's meta table
        carries the marker (``decay_last_run_at``, an ISO-8601
        UTC timestamp from :func:`_now`).

        Behaviour at the edges, all deliberate:

        - First call (no marker stored): arms the marker at
          now and decays **0 days** — enabling the mode never
          surprises a store with a mass fade.
        - Clock jumped forward: decays the elapsed days and
          advances the marker to now.
        - Clock jumped backward (or has not moved): decays
          0 days and the marker does **not** move backward, so
          a later healthy reading cannot re-decay the same span.
        - A corrupt or timezone-naive marker is treated as no
          marker (re-armed at now, 0 days) and reported via
          ``marker_reset`` — the mode heals its own state.

        Returns :meth:`decay`'s report plus ``mode``,
        ``elapsed_days``, ``last_run_at``, ``run_at``,
        ``first_run``, ``marker_reset`` and ``marker_advanced``.
        """
        now = datetime.fromisoformat(_now())
        with self._lock:
            self._get_conn()
            row = self._conn.execute(
                "SELECT value FROM meta WHERE key = ?", (_DECAY_MARKER_KEY,)
            ).fetchone()
        previous: datetime | None = None
        marker_reset = False
        if row is not None and row[0]:
            try:
                parsed = datetime.fromisoformat(str(row[0]))
            except ValueError:
                marker_reset = True
            else:
                if parsed.tzinfo is None:
                    marker_reset = True
                else:
                    previous = parsed
        if previous is None:
            elapsed_days = 0.0
            advance_marker = True
        else:
            elapsed_days = max(0.0, (now - previous).total_seconds() / 86400.0)
            advance_marker = now > previous
        report = self.decay(elapsed_days)
        if advance_marker:
            with self._lock:
                self._get_conn()
                self._conn.execute(
                    "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                    (_DECAY_MARKER_KEY, now.isoformat()),
                )
                self._conn.commit()
        report.update(
            {
                "mode": "wall_clock",
                "elapsed_days": elapsed_days,
                "last_run_at": previous.isoformat() if previous is not None else None,
                "run_at": now.isoformat(),
                "first_run": previous is None and not marker_reset,
                "marker_reset": marker_reset,
                "marker_advanced": advance_marker,
            }
        )
        return report

    def consolidate(self, threshold: float | None = None) -> dict[str, Any]:
        """Mark strong edges consolidated; repair structure (WRITE).

        Edges at or above ``threshold`` (default: the config's
        consolidation threshold, 0.8) are marked ``consolidated``;
        edges below it are unmarked. The heal pass runs as part of
        consolidation (sleep also tidies). Node content is never
        rewritten by consolidation.
        """
        if threshold is None:
            threshold = self.config.consolidation_threshold
        threshold = _check_threshold(threshold)
        with self._lock:
            self._get_conn()
            if self.config.auto_backup:
                self._conn.commit()
                take_backup(self._db_path, self.config.backup_keep)
            cur = self._conn.execute(
                "UPDATE hebbian_connections SET consolidated = 1"
                " WHERE strength >= ? AND consolidated = 0",
                (float(threshold),),
            )
            marked = cur.rowcount
            cur = self._conn.execute(
                "UPDATE hebbian_connections SET consolidated = 0"
                " WHERE strength < ? AND consolidated = 1",
                (float(threshold),),
            )
            unmarked = cur.rowcount
            self._conn.commit()
            heal = self._heal_locked()
            total = self._conn.execute(
                "SELECT COUNT(*) FROM hebbian_connections WHERE consolidated = 1"
            ).fetchone()[0]
            return {
                "threshold": float(threshold),
                "newly_consolidated": marked,
                "unmarked": unmarked,
                "total_consolidated": int(total),
                "heal": heal,
            }

    # ─── health & stats (PURE READS) ──────────────────────────────────

    def health(self) -> dict[str, Any]:
        """Store health. PURE READ (integrity via quick_check)."""
        with self._lock:
            conn = self._get_conn()
            try:
                row = conn.execute("PRAGMA quick_check").fetchone()
                integrity = str(row[0]) if row else "unknown"
            except sqlite3.Error:
                integrity = "failed"
            nodes = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
            conns = conn.execute("SELECT COUNT(*) FROM hebbian_connections").fetchone()[0]
            acts = conn.execute("SELECT COUNT(*) FROM activation_log").fetchone()[0]
        return {
            "status": "healthy" if integrity == "ok" else "degraded",
            "db_path": str(self._db_path),
            "integrity": integrity,
            "recovered_from_backup": self.recovered_from_backup,
            "nodes": int(nodes),
            "connections": int(conns),
            "activations": int(acts),
            "schema_version": "1",
            "sqlite_version": sqlite3.sqlite_version,
        }

    def stats(self) -> dict[str, Any]:
        """Store statistics. PURE READ."""
        with self._lock:
            conn = self._get_conn()
            total_nodes = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
            total_connections = conn.execute(
                "SELECT COUNT(*) FROM hebbian_connections"
            ).fetchone()[0]
            total_activations = conn.execute(
                "SELECT COUNT(*) FROM activation_log"
            ).fetchone()[0]
            consolidated = conn.execute(
                "SELECT COUNT(*) FROM hebbian_connections WHERE consolidated = 1"
            ).fetchone()[0]
            strongest = conn.execute(
                "SELECT MAX(strength) FROM hebbian_connections"
            ).fetchone()[0]
            categories = {
                str(r[0]): int(r[1])
                for r in conn.execute(
                    "SELECT category, COUNT(*) FROM nodes GROUP BY category"
                ).fetchall()
            }
        return {
            "total_nodes": int(total_nodes),
            "total_connections": int(total_connections),
            "total_activations": int(total_activations),
            "consolidated_connections": int(consolidated),
            "strongest_connection": float(strongest) if strongest is not None else 0.0,
            "categories": categories,
            "db_path": str(self._db_path),
        }

    def get_stats(self) -> dict[str, Any]:
        """Ancestor-shaped alias of :meth:`stats`."""
        return self.stats()

    def dump(self, limit: int = 50) -> dict[str, Any]:
        """Debug dump: stats + highest-importance nodes. PURE READ."""
        limit = max(1, min(int(limit), 500))
        with self._lock:
            rows = self._get_conn().execute(
                "SELECT * FROM nodes ORDER BY importance DESC, updated_at DESC,"
                " id ASC LIMIT ?",
                (limit,),
            ).fetchall()
        return {
            "stats": self.stats(),
            "nodes": [self._row_to_node(r).to_dict() for r in rows],
        }


class Muninn(HebbianMemory):
    """Ancestor-compatible facade over :class:`HebbianMemory`.

    The NorseSagaEngine ancestor was constructed with a data directory
    and kept per-node JSON files; this facade accepts the same shape
    (``Muninn(data_path=...)`` — a directory or a ``.db`` file) while
    the storage underneath is the single crash-proof SQLite store.
    All ancestor method names are inherited.
    """

    def __init__(
        self,
        data_path: str | None = None,
        *,
        config: MuninnConfig | None = None,
        **overrides: Any,
    ):
        if config is None:
            if data_path:
                from pathlib import Path

                p = Path(str(data_path)).expanduser()
                db = p if p.suffix == ".db" else p / "muninn_hebbian.db"
                config = MuninnConfig(db_path=str(db))
            else:
                config = MuninnConfig()
        super().__init__(config, **overrides)
