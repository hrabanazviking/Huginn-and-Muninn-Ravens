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
``update``, ``delete``/``forget``, ``secure_forget``, ``move``, ``decay``,
``consolidate``, ``heal_structure``. The single reinforcing-read variant
is explicit and opt-in: ``retrieve(..., touch=True)``.
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
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from itertools import combinations
from typing import Any, TypeVar

from ._attest import (
    AttestationChain,
    chain_head_meta,
    meta_from_connection,
    new_attestation_chain,
    open_attestation_chain,
    probe_attestation,
    sync_chain_head,
    verify_attestation,
)
from ._crypto import (
    StoreCipher,
    meta_and_count_from_connection,
    new_store_cipher,
    open_store_cipher,
    probe_store,
    require_cryptography,
)
from ._db import (
    _is_locked_error,
    open_store,
    purge_forgotten_content,
    secure_delete_enabled,
    store_coordination_lock,
    store_permissions_warning,
    take_backup,
)
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


def _check_no_lone_surrogates(value: str, what: str) -> str:
    """RM-034: a text must be honestly encodable as UTF-8.

    A Python string can hold an unpaired surrogate code point
    (U+D800–U+DFFF) — constructible via ``\\udXXX`` escapes or
    a careless decode — which UTF-8 cannot encode, JSON can
    only smuggle as an escape, and SQLite cannot bind. Before
    this slice such a value escaped as a raw
    ``UnicodeEncodeError``, died untyped at the SQLite bind,
    or was silently stored as a JSON escape and handed back
    as a string no other system can encode. Every text that
    enters the store (or names a search over it) passes here
    first and is refused typed. Valid astral characters are
    single code points above U+FFFF in a Python string and
    pass untouched — only the D800–DFFF range is refused.
    """
    for ch in value:
        if 0xD800 <= ord(ch) <= 0xDFFF:
            raise MuninnValidationError(f"{what} must not contain lone surrogates")
    return value


def _check_value_no_lone_surrogates(
    value: Any, what: str, _seen: set[int] | None = None
) -> None:
    """RM-034: the surrogate check over a JSON-shaped value.

    Strings are checked wherever they sit — dict keys and
    values, list/tuple/set items, nested as deep as the value
    goes. A non-string scalar that JSON would stringify
    (metadata is dumped with ``default=str``) is checked in
    its string form. A container already being walked (a
    circular structure) is skipped: ``json.dumps`` refuses
    those itself, with the established typed message.
    """
    if isinstance(value, str):
        _check_no_lone_surrogates(value, what)
        return
    if isinstance(value, dict):
        if _seen is None:
            _seen = set()
        if id(value) in _seen:
            return
        _seen.add(id(value))
        for key, item in value.items():
            _check_value_no_lone_surrogates(key, what, _seen)
            _check_value_no_lone_surrogates(item, what, _seen)
        return
    if isinstance(value, (list, tuple, set, frozenset)):
        if _seen is None:
            _seen = set()
        if id(value) in _seen:
            return
        _seen.add(id(value))
        for item in value:
            _check_value_no_lone_surrogates(item, what, _seen)
        return
    if value is not None and not isinstance(value, (bool, int, float)):
        _check_no_lone_surrogates(str(value), what)


def _content_hash(text: str, is_json: int) -> str:
    """RM-047: the content hash — SHA-256 of the stored text with
    its kind prefix (``s:`` for a string, ``j:`` for JSON).

    This is the one hash function the idempotent-store path
    uses; tests inject a constant replacement for it to force
    the collisions SHA-256 makes implausible in nature (see
    docs/HASH_COLLISION.md).
    """
    prefix = "j:" if is_json else "s:"
    return hashlib.sha256((prefix + text).encode()).hexdigest()


def _content_payload(content: Any) -> tuple[str, int, str]:
    """(stored_text, is_json, content_hash) for node content."""
    if isinstance(content, str):
        _check_no_lone_surrogates(content, "content")
        return content, 0, _content_hash(content, 0)
    _check_structure_depth(content, "content")
    _check_value_no_lone_surrogates(content, "content")
    try:
        text = json.dumps(content, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise MuninnValidationError(
            "content must be a string or JSON-serializable value"
        ) from exc
    return text, 1, _content_hash(text, 1)


def _check_content_size(text: str, ceiling: int) -> None:
    """RM-027: stored content must fit the configured ceiling.

    Size is the UTF-8 byte length of the stored text — what the
    store actually holds — so a multibyte character counts for
    what it costs, not for one. Refusal is typed and happens
    before any write.
    """
    size = len(text.encode("utf-8"))
    if size > ceiling:
        raise MuninnValidationError(
            f"content size {size} bytes exceeds max_content_bytes ({ceiling} bytes)"
        )


def _check_metadata_size(meta_text: str, ceiling: int) -> None:
    """RM-027: serialized metadata must fit its ceiling (typed)."""
    size = len(meta_text.encode("utf-8"))
    if size > ceiling:
        raise MuninnValidationError(
            f"metadata size {size} bytes exceeds max_metadata_bytes ({ceiling} bytes)"
        )


# RM-036: nesting bound for JSON-shaped values (content,
# metadata) and for tag elements. 100 containers deep is far
# beyond any honest memory shape, and far below the depth at
# which the recursive walks below (surrogate check,
# ``json.dumps``, ``repr`` of a tag element) overflow the
# interpreter stack.
_MAX_STRUCTURE_DEPTH = 100


def _check_structure_depth(value: Any, what: str) -> None:
    """RM-036: a JSON-shaped value must not nest too deep.

    The walk is iterative (explicit stack, path-scoped id set),
    so the check itself cannot overflow the stack it guards:
    before this slice, content or metadata nested a few
    thousand containers deep escaped as a raw
    ``RecursionError``. A container already on the current
    path (a circular structure) is not descended into —
    ``json.dumps`` refuses those itself with the established
    typed serializability message, and ``repr`` renders them
    with an ellipsis. A shared (DAG-shaped) substructure is
    walked once per occurrence and is not circular.
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
            raise MuninnValidationError(
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
    """RM-036: the stored tags must fit the metadata ceiling.

    Tags are the node's annotation payload alongside metadata,
    so the RM-027 metadata ceiling bounds them uniformly: the
    measure is the UTF-8 byte length of the tags' stored JSON
    form. Before this slice a tags list of any length was
    accepted, however enormous.
    """
    size = len(json.dumps(clean_tags).encode("utf-8"))
    if size > ceiling:
        raise MuninnValidationError(
            f"tags size {size} bytes exceeds max_metadata_bytes ({ceiling} bytes)"
        )


# RM-028: node-path bounds, applied to the normalised path.
_MAX_PATH_SEGMENTS = 64
_MAX_PATH_BYTES = 2048


def _normalize_path(value: Any) -> str:
    """RM-028: fold a node path to its one canonical spelling.

    Node paths are store-internal hierarchical labels, never
    filesystem paths. The defined behaviour (docs/
    PATHOLOGICAL_PATHS.md): split on ``/``; empty segments
    (leading / trailing / doubled slashes) and ``.`` segments
    drop; ``..`` removes the previous kept segment and clamps
    at the root, so no spelling escapes the store root; the
    rest are kept verbatim — backslashes and unicode separator
    look-alikes are ordinary segment characters, only ``/``
    separates. The root is ``""``. Non-strings, a depth over
    64 segments, or a size over 2048 UTF-8 bytes (both measured
    after normalisation) are typed refusals.
    """
    if not isinstance(value, str):
        raise MuninnValidationError(
            f"path must be a string, got {type(value).__name__}"
        )
    _check_no_lone_surrogates(value, "path")
    segments: list[str] = []
    for segment in value.split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            if segments:
                segments.pop()
            continue
        segments.append(segment)
    if len(segments) > _MAX_PATH_SEGMENTS:
        raise MuninnValidationError(
            f"path depth {len(segments)} exceeds maximum of "
            f"{_MAX_PATH_SEGMENTS} segments"
        )
    normalized = "/".join(segments)
    size = len(normalized.encode("utf-8"))
    if size > _MAX_PATH_BYTES:
        raise MuninnValidationError(
            f"path size {size} bytes exceeds maximum of {_MAX_PATH_BYTES} bytes"
        )
    return normalized


def _like_prefix_pattern(path: str) -> str:
    """RM-028: an escaped LIKE pattern matching every path
    strictly under ``path`` (to be used with ``ESCAPE '\\'``).

    ``\\``, ``%`` and ``_`` in a segment are literal characters,
    never wildcards. The root's pattern matches any non-empty
    path; the caller still excludes the root row itself.
    """
    escaped = (
        path.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )
    return escaped + "/%" if escaped else "%"


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


# RM-035: at or above this many unique ids, activate_batch takes
# the bulk road (_activate_batch_bulk_locked). Below it, the
# original per-pair loop is both faster and already proven.
_HUGE_BATCH_MIN_IDS = 64

_R = TypeVar("_R")


def _storage_write(
    operation: str,
) -> Callable[[Callable[..., _R]], Callable[..., _R]]:
    """Guard a public write method (RM-029).

    A storage-layer failure during a write — above all SQLite's
    ``database or disk is full`` (SQLITE_FULL) when the filesystem
    fills mid-write — must never escape as a raw ``sqlite3.Error``:
    the caller is owed one of Muninn's typed errors. The failed
    call's transaction is rolled back first, so no half-applied
    write can leak into a later commit, and the store stays open
    and consistent for the calls that follow.

    A lock held by another process past the busy timeout is the
    same discipline with its own message shape (RM-031): the
    guard names the contention instead of echoing SQLite's
    wording, so a caller can tell "another process has the
    store" apart from every other storage failure.

    The decorator preserves the wrapped method's return type
    (RM-030 repair: the original ``Any``-typed wrapper silently
    broke the RM-008 mypy floor — ``warn_return_any`` — in every
    alias method that returns a guarded write's result).
    """

    def decorator(fn: Callable[..., _R]) -> Callable[..., _R]:
        @functools.wraps(fn)
        def wrapper(self: HebbianMemory, *args: Any, **kwargs: Any) -> _R:
            try:
                return fn(self, *args, **kwargs)
            except sqlite3.Error as exc:
                with contextlib.suppress(sqlite3.Error):
                    self._conn.rollback()
                if _is_locked_error(exc):
                    raise MuninnStorageError(
                        f"muninn write failed during {operation}: store is locked "
                        f"by another process (busy timeout expired)"
                    ) from exc
                raise MuninnStorageError(
                    f"muninn write failed during {operation}: {exc}"
                ) from exc

        return wrapper

    return decorator


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
        #: RM-053: the last ``spread_activation`` call's cost
        #: accounting (candidate edges examined, the ceiling,
        #: whether it bit, nodes returned). A dedicated
        #: attribute, deliberately NOT a ``stats()`` /
        #: ``health()`` field: those snapshots are pinned
        #: pure by the read-purity invariant (a read must not
        #: change them), so per-call accounting lives here.
        self.last_spread_activation_stats: dict[str, Any] = {
            "candidates_examined": 0,
            "cap": int(config.max_spread_candidates),
            "capped": False,
            "nodes_returned": 0,
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
            self._db_path, "SELECT COUNT(*) FROM nodes"
        )
        if config.store_encryption:
            require_cryptography()
            passphrase = config.encryption_passphrase or ""
            if existing_meta is not None:
                self._cipher = open_store_cipher(passphrase, existing_meta, self._db_path)
            elif probe_ok and existing_rows > 0:
                raise MuninnStorageError(
                    f"muninn store {self._db_path} is not encrypted but "
                    f"already holds memories; refusing to open it with "
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
            raise MuninnStorageError(
                f"muninn store {self._db_path} is encrypted; refusing "
                f"to open it without store_encryption enabled"
            )
        # RM-050: integrity attestation setup, on the same
        # pre-read pattern — a marked store opened without the
        # flag refuses here, before the store is touched, and a
        # file the probe cannot read defers its judgement to
        # the post-open check on the live connection.
        self._attest_chain: AttestationChain | None = None
        self._pending_attestation_meta: dict[str, str] | None = None
        self._deferred_attestation = False
        #: RM-050: the open-time attestation verdict —
        #: "ok", "tamper_detected", or "not_enabled".
        self.integrity_attestation_status: str = "not_enabled"
        attest_probe_ok, attest_meta = probe_attestation(self._db_path)
        if config.integrity_attestation:
            attest_passphrase = config.integrity_passphrase or ""
            if attest_meta is not None:
                self._attest_chain = open_attestation_chain(
                    attest_passphrase, attest_meta, self._db_path
                )
            elif attest_probe_ok or not self._db_path.exists():
                self._attest_chain, self._pending_attestation_meta = (
                    new_attestation_chain(attest_passphrase)
                )
            else:
                self._deferred_attestation = True
        elif attest_meta is not None:
            raise MuninnStorageError(
                f"muninn store {self._db_path} carries integrity attestation; "
                f"refusing to open it without integrity_attestation enabled"
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
        #: True when the store had to be restored from a rolling backup.
        self.recovered_from_backup = report.recovered_from_backup
        # RM-037: the heal pass is an open-time duty — it runs
        # under the per-store coordination lock, so it can never
        # interleave with another opener's open, heal or backup
        # duties on the same store file.
        with self._lock, store_coordination_lock(self._db_path):
            if self._pending_encryption_meta is not None:
                # RM-049: a new encrypted store takes its marker
                # and wrapped key now, inside the open-time lock,
                # before any memory can be written.
                self._write_encryption_meta_locked(self._pending_encryption_meta)
                self._pending_encryption_meta = None
            elif self._deferred_encryption:
                self._establish_deferred_cipher_locked()
            elif (
                meta_and_count_from_connection(
                    self._conn, "SELECT COUNT(*) FROM nodes"
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
                raise MuninnStorageError(
                    f"muninn store {self._db_path} is encrypted; refusing "
                    f"to open it without store_encryption enabled"
                )
            # RM-050: attestation is established or verified
            # inside the same open-time lock, before any
            # activation can be written.
            if self._pending_attestation_meta is not None:
                self._establish_attestation_locked(self._pending_attestation_meta)
                self._pending_attestation_meta = None
            elif config.integrity_attestation:
                live_meta = meta_from_connection(self._conn)
                if live_meta is not None:
                    # Rebuild from the live store's own header —
                    # the open may have restored a backup whose
                    # header is the one that counts.
                    try:
                        self._attest_chain = open_attestation_chain(
                            config.integrity_passphrase or "",
                            live_meta,
                            self._db_path,
                        )
                    except MuninnStorageError:
                        self._conn.close()
                        self._closed = True
                        raise
                    self._verify_attestation_locked()
                else:
                    # The deferred case (the pre-read could not
                    # settle the file) landing on an unmarked
                    # store: take a fresh header, bootstrapped
                    # over the rows as found.
                    self._attest_chain, fresh_meta = new_attestation_chain(
                        config.integrity_passphrase or ""
                    )
                    self._establish_attestation_locked(fresh_meta)
            elif meta_from_connection(self._conn) is not None:
                # RM-050 post-open re-check: the open restored a
                # marked store the pre-read could not see. Never
                # serve it unattested — close and refuse.
                self._conn.close()
                self._closed = True
                raise MuninnStorageError(
                    f"muninn store {self._db_path} carries integrity attestation; "
                    f"refusing to open it without integrity_attestation enabled"
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
        served nothing); an unmarked store holding memories is
        the plain-store refusal; an empty unmarked store takes
        a fresh header."""
        passphrase = self.config.encryption_passphrase or ""
        meta, rows = meta_and_count_from_connection(
            self._conn, "SELECT COUNT(*) FROM nodes"
        )
        if meta is not None:
            try:
                self._cipher = open_store_cipher(passphrase, meta, self._db_path)
            except MuninnStorageError:
                self._conn.close()
                self._closed = True
                raise
        elif rows > 0:
            self._conn.close()
            self._closed = True
            raise MuninnStorageError(
                f"muninn store {self._db_path} is not encrypted but "
                f"already holds memories; refusing to open it with "
                f"store_encryption enabled"
            )
        else:
            self._cipher, meta = new_store_cipher(passphrase)
            self._write_encryption_meta_locked(meta)
        self._deferred_encryption = False

    # ─── integrity attestation (RM-050) ───────────────────────────────

    def _establish_attestation_locked(self, meta: dict[str, str]) -> None:
        """RM-050: bootstrap the chain over the log as found (lock held).

        Rows already in the store are chained in id order and
        the header is written with the resulting head/count —
        the store is attested from this open forward, in the
        state this open found it.
        """
        chain = self._attest_chain
        if chain is None:
            return
        for memory_id, at, valence, source in self._conn.execute(
            "SELECT memory_id, activated_at, emotional_valence, source"
            " FROM activation_log ORDER BY id"
        ):
            chain.advance(int(memory_id), str(at), float(valence), str(source))
        for key, value in {**meta, **chain_head_meta(chain)}.items():
            self._conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                (key, value),
            )
        self._conn.commit()
        self.integrity_attestation_status = "ok"

    def _verify_attestation_locked(self) -> None:
        """RM-050: the open-time verdict (lock held).

        Detection is *reported*, never silently repaired and
        never a refusal: the store opens, the verdict rides on
        this object and in ``health()``, and a failure is
        logged at ERROR — the caller's audit trail has been
        tampered with (or the passphrase is wrong, which the
        chain cannot tell apart, by design), and that fact is
        the caller's to act on.
        """
        chain = self._attest_chain
        if chain is None:
            return
        self.integrity_attestation_status = verify_attestation(self._conn, chain)
        if self.integrity_attestation_status != "ok":
            logger.error(
                "muninn: integrity attestation FAILED for store %s — the "
                "activation log does not match its HMAC chain "
                "(tampering, or a wrong integrity_passphrase)",
                self._db_path,
            )

    def _advance_attestation_locked(
        self, memory_id: int, at: str, emotional_valence: float, source: str
    ) -> None:
        """RM-050: chain one activation row about to be inserted.

        The stored head is re-read first (the authority — a
        rolled-back transaction must not leave the in-memory
        chain ahead of the store), then the chain advances and
        the new head/count are written in the caller's own
        transaction, so a log row and its chain link land or
        roll back together.
        """
        chain = self._attest_chain
        if chain is None:
            return
        meta = meta_from_connection(self._conn)
        if meta is not None:
            sync_chain_head(chain, meta, self._db_path)
        chain.advance(memory_id, at, emotional_valence, source)
        self._conn.executemany(
            "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
            tuple(chain_head_meta(chain).items()),
        )

    # ─── store encryption transforms (RM-049) ─────────────────────────

    def _enc_value(self, text: str, aad: str) -> str:
        """Seal a stored value when encryption is on (else identity)."""
        return self._cipher.encrypt(text, aad) if self._cipher is not None else text

    def _dec_value(self, value: str, aad: str) -> str:
        """Open a stored value when encryption is on (else identity)."""
        return self._cipher.decrypt(value, aad) if self._cipher is not None else value

    def _stored_content_hash(self, text: str, is_json: int, plain_hash: str) -> str:
        """The hash the store keeps: the plain SHA-256, or — with
        encryption on — the keyed lookup tag over exactly the
        plain hash's input (kind prefix ‖ content, RM-047), so
        the idempotent-store path compares tags in the store and
        plaintext after decryption."""
        if self._cipher is None:
            return plain_hash
        prefix = "j:" if is_json else "s:"
        return self._cipher.lookup_tag((prefix + text).encode("utf-8"))

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

    @_storage_write("backup")
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
        self._advance_attestation_locked(memory_id, at, emotional_valence, source)
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

    @_storage_write("activate")
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

    @_storage_write("activate_batch")
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

        RM-035: batches of ``_HUGE_BATCH_MIN_IDS`` or more unique ids
        take the bulk road (``_activate_batch_bulk_locked``) — the
        same writes, the same counts, the same one transaction, but
        the pairs are generated inside SQLite instead of one Python
        loop iteration (and four statements) per pair, so a 10k-id
        batch is bounded by the size of its own result set, not by
        Python-side pair handling. Smaller batches keep the original
        per-pair loop.
        """
        if not isinstance(memory_ids, (list, tuple)):
            raise MuninnValidationError("memory_ids must be a list of ints")
        ids = list(dict.fromkeys(_check_memory_id(m) for m in memory_ids))
        emotional_valence = _check_valence(emotional_valence)
        at = self._tick()
        with self._lock:
            self._get_conn()
            if len(ids) >= _HUGE_BATCH_MIN_IDS:
                return self._activate_batch_bulk_locked(
                    ids, emotional_valence, str(source), at
                )
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

    def _activate_batch_bulk_locked(
        self, ids: list[int], emotional_valence: float, source: str, at: str
    ) -> dict[str, Any]:
        """RM-035: ``activate_batch`` for huge batches, in bulk SQL.

        Caller holds the lock and has validated every id. The writes
        are exactly the per-id / per-pair writes of the loop road,
        restated set-at-a-time:

        * activations: the four writes of ``_log_activation_locked``
          as ``executemany`` over generators — the id list is the
          only Python-side structure, so peak memory is O(ids), never
          O(pairs) (a 10k batch wires ~50M pairs);
        * pair counts come from arithmetic (``n(n-1)/2``) minus a
          count of the pairs already wired in BOTH directions (the
          loop road's ``created`` is exactly "not already complete":
          ``_wire_pair_locked`` reports a pair created when either
          directed row was missing, drift included);
        * the wiring itself is one ``INSERT … SELECT`` over a TEMP
          staging table joined to itself, with the same
          insert-strength (``learning_rate``) and the same bounded
          strengthening update on conflict as ``_wire_pair_locked``.

        The secondary index ``idx_conn_b`` is dropped for the insert
        and recreated before commit, inside the same transaction:
        maintaining it row-by-row turns the insert's sequential
        primary-key writes into random secondary-index writes (the
        measured bottleneck — docs/HUGE_BATCH_ATOMICITY.md), while a
        rollback restores the dropped index with everything else, so
        the store never observably lacks it. The recreated index is
        created with the exact ``SCHEMA_SQL`` statement, so the
        RM-004/RM-022 schema pins are untouched.
        """
        conn = self._conn
        lr = self.config.learning_rate
        conn.executemany(
            "INSERT INTO activation_log (memory_id, activated_at, emotional_valence, source)"
            " VALUES (?, ?, ?, ?)",
            ((mid, at, emotional_valence, source) for mid in ids),
        )
        # RM-050: the chain advances per row in id order — an
        # O(ids) Python loop like the activation writes above,
        # never O(pairs) — and the head lands in this same
        # transaction.
        if self._attest_chain is not None:
            for mid in ids:
                self._advance_attestation_locked(mid, at, emotional_valence, source)
        conn.executemany(
            "INSERT INTO node_activation (memory_id, total_activations, confidence,"
            " last_activated_at)"
            " VALUES (?, 1, 1.0, ?)"
            " ON CONFLICT(memory_id) DO UPDATE SET"
            "   total_activations = total_activations + 1,"
            "   confidence = MIN(1.0, confidence + ? * (1.0 - confidence)),"
            "   last_activated_at = excluded.last_activated_at",
            ((mid, at, lr) for mid in ids),
        )
        conn.executemany(
            "UPDATE nodes SET access_count = access_count + 1, updated_at = ? WHERE id = ?",
            ((at, mid) for mid in ids),
        )
        conn.executemany(
            "DELETE FROM deleted_nodes WHERE memory_id = ?",
            ((mid,) for mid in ids),
        )
        pairs = len(ids) * (len(ids) - 1) // 2
        created = 0
        if pairs:
            conn.execute("DROP TABLE IF EXISTS temp.muninn_batch_ids")
            conn.execute(
                "CREATE TEMP TABLE muninn_batch_ids (memory_id INTEGER PRIMARY KEY)"
            )
            conn.executemany(
                "INSERT INTO muninn_batch_ids (memory_id) VALUES (?)",
                ((mid,) for mid in ids),
            )
            complete = conn.execute(
                "SELECT COUNT(*) FROM hebbian_connections f"
                " JOIN hebbian_connections r"
                "   ON r.memory_a_id = f.memory_b_id"
                "  AND r.memory_b_id = f.memory_a_id"
                " JOIN muninn_batch_ids x ON x.memory_id = f.memory_a_id"
                " JOIN muninn_batch_ids y ON y.memory_id = f.memory_b_id"
                " WHERE f.memory_a_id < f.memory_b_id"
            ).fetchone()
            created = pairs - int(complete[0])
            conn.execute("DROP INDEX IF EXISTS idx_conn_b")
            conn.execute(
                "INSERT INTO hebbian_connections"
                " (memory_a_id, memory_b_id, strength, co_activation_count,"
                "  consolidated, created_at, last_coactivated_at)"
                " SELECT x.memory_id, y.memory_id, ?, 1, 0, ?, ?"
                " FROM muninn_batch_ids x"
                " JOIN muninn_batch_ids y ON x.memory_id <> y.memory_id"
                " ON CONFLICT(memory_a_id, memory_b_id) DO UPDATE SET"
                "   strength = 1.0 - (1.0 - strength) * ?,"
                "   co_activation_count = co_activation_count + 1,"
                "   last_coactivated_at = excluded.last_coactivated_at",
                (lr, at, at, 1.0 - lr),
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_conn_b"
                " ON hebbian_connections(memory_b_id)"
            )
            conn.execute("DROP TABLE IF EXISTS temp.muninn_batch_ids")
        conn.commit()
        return {
            "activated": len(ids),
            "pairs_wired": pairs,
            "connections_created": created,
            "connections_strengthened": pairs - created,
        }

    @_storage_write("associate")
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

        Query cost ceiling (RM-053, threat TH-13): one call
        examines at most ``config.max_spread_candidates``
        candidate edges (neighbour rows). When the ceiling is
        reached the expansion stops and the call returns what
        it has; the bite is recorded in
        ``last_spread_activation_stats``, where ``capped``
        is True and ``candidates_examined``
        equals the ceiling. The walk is deterministic when the
        cap bites — frontier nodes and neighbours are
        considered in id order — and below the ceiling the
        result is exactly the unbounded walk's.
        """
        if not isinstance(seed_ids, (list, tuple)):
            raise MuninnValidationError("seed_ids must be a list of ints")
        seeds = [_check_memory_id(m) for m in seed_ids]
        attenuation = _check_attenuation(attenuation)
        min_strength = _check_min_strength(min_strength)
        depth = max(0, min(_check_count(depth, "depth"), 10))
        limit = max(1, _check_count(limit, "limit"))
        cap = int(self.config.max_spread_candidates)
        examined = 0
        capped = False
        levels: dict[int, float] = dict.fromkeys(seeds, 1.0)
        frontier = dict(levels)
        with self._lock:
            conn = self._get_conn()
            for _ in range(depth):
                next_frontier: dict[int, float] = {}
                for mid in sorted(frontier):
                    if capped:
                        break
                    level = frontier[mid]
                    rows = conn.execute(
                        "SELECT memory_b_id, strength FROM hebbian_connections"
                        " WHERE memory_a_id = ? AND strength >= ?",
                        (mid, float(min_strength)),
                    ).fetchall()
                    for other, strength in sorted(rows, key=lambda r: int(r[0])):
                        if examined >= cap:
                            capped = True
                            break
                        examined += 1
                        value = level * float(strength) * float(attenuation)
                        if value > next_frontier.get(other, 0.0):
                            next_frontier[other] = value
                for mid, value in next_frontier.items():
                    if value > levels.get(mid, 0.0):
                        levels[mid] = value
                frontier = next_frontier
                if capped or not frontier:
                    break
        # RM-011 determinism pin: ties on activation resolve by id, so
        # iteration order never depends on query-plan row order.
        ranked = sorted(levels.items(), key=lambda kv: (-kv[1], kv[0]))
        result = dict(ranked[:limit])
        self.last_spread_activation_stats = {
            "candidates_examined": examined,
            "cap": cap,
            "capped": capped,
            "nodes_returned": len(result),
        }
        if capped:
            # Counts only — never content (RM-044 discipline).
            logger.warning(
                "muninn: spread_activation candidate cap bit: examined %d "
                "candidate edges at cap %d; result is partial",
                examined,
                cap,
            )
        return result

    # ─── node API (ancestor semantics) ────────────────────────────────

    @_storage_write("remember")
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
        it (content-hash unique index) — safe under retries. The hit
        is verified by a length+content double check (RM-047): a
        different memory under the same hash raises a typed collision
        error instead of being silently merged.
        """
        if content is None:
            raise MuninnValidationError("content must not be None")
        importance = _check_importance(importance)
        emotional_valence = _check_valence(emotional_valence)
        clean_path = _normalize_path(path)
        clean_category = _check_no_lone_surrogates(str(category), "category")
        text, is_json, content_hash = _content_payload(content)
        stored_hash = self._stored_content_hash(text, is_json, content_hash)
        _check_content_size(text, self.config.max_content_bytes)
        clean_tags = []
        for raw_tag in _check_tag_list(tags):
            _check_structure_depth(raw_tag, "tags")
            cleaned_tag = str(raw_tag).strip().lower()[:64]
            if cleaned_tag:
                clean_tags.append(cleaned_tag)
        for tag in clean_tags:
            _check_no_lone_surrogates(tag, "tags")
        _check_tags_size(clean_tags, self.config.max_metadata_bytes)
        _check_structure_depth(metadata or {}, "metadata")
        _check_value_no_lone_surrogates(metadata or {}, "metadata")
        try:
            meta_text = json.dumps(metadata or {}, sort_keys=True, default=str)
        except (TypeError, ValueError) as exc:
            raise MuninnValidationError("metadata must be JSON-serializable") from exc
        _check_metadata_size(meta_text, self.config.max_metadata_bytes)
        at = self._tick()
        with self._lock:
            self._get_conn()
            cur = self._conn.execute(
                "INSERT OR IGNORE INTO nodes"
                " (content, content_is_json, content_hash, path, category, importance,"
                "  emotional_valence, tags, metadata, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    self._enc_value(text, "nodes.content"), is_json, stored_hash,
                    clean_path, clean_category, importance,
                    emotional_valence, self._enc_value(json.dumps(clean_tags), "nodes.tags"),
                    self._enc_value(meta_text, "nodes.metadata"), at, at,
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
                    "SELECT id, content, content_is_json FROM nodes"
                    " WHERE content_hash = ? AND category = ? AND path = ?",
                    (stored_hash, clean_category, clean_path),
                ).fetchone()
                # RM-047 (TH-08): the hash alone does not prove
                # identity. The idempotent hit is accepted only
                # after the length+content double check — the
                # stored text's length and then the stored text
                # itself (and its kind) must equal what this
                # call tried to store. A hash collision — real,
                # crafted, or forced by an injected hash — lands
                # here with different text under one hash, and
                # is refused loudly instead of silently merging
                # two memories into the existing node's id.
                # RM-049: with encryption on, the double check
                # compares the DECRYPTED stored content against
                # the incoming plaintext (the store itself only
                # ever saw the lookup tag above).
                stored_text = self._dec_value(row["content"], "nodes.content")
                if (
                    len(stored_text) != len(text)
                    or stored_text != text
                    or int(row["content_is_json"]) != is_json
                ):
                    existing_id = int(row["id"])
                    self._conn.rollback()
                    raise MuninnValidationError(
                        "content hash collision: a different memory already "
                        f"holds this content hash (id {existing_id}); "
                        "refusing to merge"
                    )
                node_id = int(row["id"])
                is_new = False
            self._conn.commit()
            if is_new:
                self._apply_backpressure_locked()
            if self.config.debug_log_content:
                # RM-044: the ONLY road by which memory content
                # reaches a log — this flag, at DEBUG level.
                logger.debug(
                    "muninn: stored memory id=%d content=%r", node_id, text
                )
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
        content = self._dec_value(row["content"], "nodes.content")
        if row["content_is_json"]:
            content = json.loads(content)
        return MemoryNode(
            id=int(row["id"]),
            content=content,
            path=row["path"],
            memory_type=row["category"],
            importance=int(row["importance"]),
            emotional_valence=float(row["emotional_valence"]),
            tags=json.loads(self._dec_value(row["tags"] or "[]", "nodes.tags")),
            metadata=json.loads(self._dec_value(row["metadata"] or "{}", "nodes.metadata")),
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

    @_storage_write("retrieve")
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
        if query:
            _check_no_lone_surrogates(str(query), "query")
        wanted_tags = []
        if tags:
            for raw_tag in _check_tag_list(tags):
                _check_structure_depth(raw_tag, "tags")
                wanted_tags.append(str(raw_tag).lower())
        for tag in wanted_tags:
            _check_no_lone_surrogates(tag, "tags")
        wanted_type = category or memory_type
        if wanted_type:
            _check_no_lone_surrogates(str(wanted_type), "category")
        sql = "SELECT * FROM nodes WHERE 1=1"
        params: list[Any] = []
        if wanted_type:
            sql += " AND category = ?"
            params.append(str(wanted_type))
        clean_path = _normalize_path(path) if path is not None else None
        if clean_path:
            sql += " AND (path = ? OR path LIKE ? ESCAPE '\\')"
            params.extend([clean_path, _like_prefix_pattern(clean_path)])
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
        if self.config.debug_log_content:
            # RM-044: content in logs only here, only at DEBUG,
            # only with the flag on (see remember()).
            logger.debug(
                "muninn: retrieve query=%r returned %d nodes content=%r",
                query,
                len(rows_out),
                [node.content for node in rows_out],
            )
        return rows_out

    def get_by_path(self, path: str) -> list[MemoryNode]:
        """All nodes at exactly ``path``. PURE READ."""
        clean_path = _normalize_path(path)
        with self._lock:
            rows = self._get_conn().execute(
                "SELECT * FROM nodes WHERE path = ?"
                " ORDER BY importance DESC, updated_at DESC, id ASC",
                (clean_path,),
            ).fetchall()
        return [self._row_to_node(r) for r in rows]

    def get_children(self, parent_path: str) -> dict[str, list[MemoryNode]]:
        """Nodes grouped by every path under ``parent_path``. PURE READ."""
        clean_parent = _normalize_path(parent_path)
        children: dict[str, list[MemoryNode]] = {}
        with self._lock:
            rows = self._get_conn().execute(
                "SELECT * FROM nodes WHERE path LIKE ? ESCAPE '\\'"
                " AND path <> ''"
                " ORDER BY path, importance DESC, id ASC",
                (_like_prefix_pattern(clean_parent),),
            ).fetchall()
        for row in rows:
            node = self._row_to_node(row)
            children.setdefault(node.path, []).append(node)
        return children

    @_storage_write("update")
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
                _check_content_size(text, self.config.max_content_bytes)
                updates["content"] = self._enc_value(text, "nodes.content")
                updates["content_is_json"] = is_json
                updates["content_hash"] = self._stored_content_hash(
                    text, is_json, content_hash
                )
            if "importance" in fields:
                updates["importance"] = _check_importance(fields["importance"])
            if "emotional_valence" in fields:
                updates["emotional_valence"] = _check_valence(fields["emotional_valence"])
            if "tags" in fields:
                clean_update_tags = []
                for raw_tag in _check_tag_list(fields["tags"]):
                    _check_structure_depth(raw_tag, "tags")
                    cleaned_tag = str(raw_tag).strip().lower()[:64]
                    if cleaned_tag:
                        clean_update_tags.append(cleaned_tag)
                for tag in clean_update_tags:
                    _check_no_lone_surrogates(tag, "tags")
                _check_tags_size(clean_update_tags, self.config.max_metadata_bytes)
                updates["tags"] = self._enc_value(
                    json.dumps(clean_update_tags), "nodes.tags"
                )
            if "metadata" in fields:
                _check_structure_depth(fields["metadata"] or {}, "metadata")
                _check_value_no_lone_surrogates(fields["metadata"] or {}, "metadata")
                try:
                    meta_text = json.dumps(
                        fields["metadata"] or {}, sort_keys=True, default=str
                    )
                except (TypeError, ValueError) as exc:
                    raise MuninnValidationError(
                        "metadata must be JSON-serializable"
                    ) from exc
                _check_metadata_size(meta_text, self.config.max_metadata_bytes)
                updates["metadata"] = self._enc_value(meta_text, "nodes.metadata")
            if "path" in fields:
                updates["path"] = _normalize_path(fields["path"])
            if "memory_type" in fields or "category" in fields:
                updates["category"] = _check_no_lone_surrogates(
                    str(fields.get("memory_type", fields.get("category"))), "category"
                )
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

    def _forget_rows_locked(self, memory_id: int) -> bool:
        """Delete one node's rows + tombstone (lock held, uncommitted).

        The shared row work of :meth:`forget` and
        :meth:`secure_forget` (RM-051): the node, all its wiring,
        and the standing tombstone — written even when nothing
        existed, as the record that this id was deliberately
        forgotten, so heal prunes any later stray edge to it.
        The caller commits.
        """
        removed = False
        cur = self._conn.execute("DELETE FROM nodes WHERE id = ?", (memory_id,))
        removed = removed or cur.rowcount > 0
        cur = self._conn.execute(
            "DELETE FROM hebbian_connections WHERE memory_a_id = ? OR memory_b_id = ?",
            (memory_id, memory_id),
        )
        removed = removed or cur.rowcount > 0
        self._conn.execute(
            "INSERT OR REPLACE INTO deleted_nodes (memory_id, deleted_at) VALUES (?, ?)",
            (memory_id, self._tick()),
        )
        return removed

    @_storage_write("forget")
    def forget(self, memory_id: int) -> bool:
        """Remove a memory's node and all its wiring (WRITE).

        The id is tombstoned so :meth:`heal_structure` can prune any
        edge that later references it; the activation *log* is kept —
        it is a log. Returns True when anything was removed. A later
        activation of the same id clears the tombstone (the caller's
        world says the id lives again).

        Honest limit (RM-051, threat TH-11): this removes the live
        rows only. The content can persist in WAL frames, in freed
        pages of the store file, and in every rolling backup
        generation until rotation. When the content itself must
        leave the disk, use :meth:`secure_forget`.
        """
        memory_id = _check_memory_id(memory_id)
        with self._lock:
            self._get_conn()
            removed = self._forget_rows_locked(memory_id)
            self._conn.commit()
            return removed

    @_storage_write("secure_forget")
    def secure_forget(self, memory_id: int) -> bool:
        """Remove a memory **and purge its content from the disk** (WRITE).

        Everything :meth:`forget` does — node, wiring, tombstone,
        the same return value — plus the purge plain forget cannot
        promise (RM-051, threat TH-11; record in
        ``docs/SECURE_FORGET.md``): the delete runs under
        ``PRAGMA secure_delete=ON`` (the connection's previous
        setting is restored afterwards), the WAL is
        checkpoint-truncated, the store file is rewritten with
        ``VACUUM`` so freed pages are rebuilt away, the WAL is
        truncated again, and every pre-existing backup generation
        is discarded and replaced by one fresh snapshot of the
        purged store (when ``backup_keep`` allows one). After a
        successful call, no file of the store's family — main
        file, ``-wal``, ``-shm``, backups — holds the forgotten
        content. The purge runs even when nothing live was
        removed, so calling it for an id an earlier plain
        ``forget`` already deleted remediates that forget's
        residue.

        The cost, stated plainly: a full rewrite of the store
        file (time and temporary disk space on the order of the
        store's size, under an exclusive lock) and the loss of
        all older backup generations — the recovery history is
        replaced by the single fresh snapshot. The activation
        *log* is kept, exactly as in :meth:`forget`: it carries
        ids and timestamps, never content. Close other openers
        of the store first: a reader holding an old snapshot
        can keep WAL frames alive and make the rewrite fail
        with a locked-store error (the row deletion has already
        committed by then; re-run ``secure_forget`` to re-run
        the purge).
        """
        memory_id = _check_memory_id(memory_id)
        with self._lock:
            self._get_conn()
            with secure_delete_enabled(self._conn):
                removed = self._forget_rows_locked(memory_id)
                self._conn.commit()
                purge_forgotten_content(
                    self._db_path, self._conn, self.config.backup_keep
                )
            return removed

    def delete(self, node_id: int) -> bool:
        """Ancestor-shaped alias of :meth:`forget`."""
        return self.forget(node_id)

    def move(self, node_id: int, new_path: str) -> bool:
        """Move a node to a new hierarchical path (WRITE)."""
        return self.update(node_id, path=new_path)

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

    @_storage_write("heal_structure")
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

    @_storage_write("decay")
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

    @_storage_write("decay_wall_clock")
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

    @_storage_write("consolidate")
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
            # RM-042: None for an owner-only store file; a
            # warning string when an existing file is looser
            # than 0600 (opening never re-permissions it).
            "file_permissions_warning": store_permissions_warning(self._db_path),
            # RM-050: the open-time attestation verdict —
            # "ok" / "tamper_detected" on an attested store,
            # "not_enabled" when the flag is off.
            "integrity_attestation": self.integrity_attestation_status,
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
