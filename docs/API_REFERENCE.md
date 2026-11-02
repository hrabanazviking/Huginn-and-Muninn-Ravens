# API Reference — Muninn and Huginn

Complete public API of both packages, taken from the source code.
If this document and the code ever disagree, the code wins.

Both packages are version **1.0.0**, MIT-licensed, require
**Python >= 3.11**, and have stdlib-only cores. Optional extras exist
only in Huginn (`qdrant`, `embeddings`).

Every entry is marked:

- **READ (pure)** — never mutates the store. Proven pure where a
  table-snapshot test exists (see `docs/RELIABILITY.md`).
- **WRITE** — mutates the store (or, for `close` / `backup`, manages
  the store's lifecycle / files).

Validation rule that applies everywhere, in both packages: invalid
arguments raise the package's `…ValidationError` **before** any write
happens. A validation failure never leaves a partial mutation behind.

Importing either package constructs nothing and opens no file.

---

# Part 1 — `muninn` (Hebbian associative memory)

Package exports (`muninn/__init__.py`, `__all__`):

```python
from muninn import (
    HebbianMemory, Muninn, MemoryNode, MuninnConfig,
    MuninnError, MuninnValidationError,
    MuninnConfigurationError, MuninnStorageError,
)
# muninn.__version__ == "1.0.0"
# Bifröst imports the config as: from muninn.config import MuninnConfig
```

## 1.1 `MuninnConfig` — `muninn/config.py`

```python
@dataclass
class MuninnConfig:
    db_path: str = "~/.hermes/memory/muninn_hebbian.db"
    learning_rate: float = 0.1
    decay_half_life_days: float = 30.0
    confidence_half_life_days: float = 90.0
    prune_threshold: float = 0.01
    consolidation_threshold: float = 0.8
    busy_timeout_ms: int = 5000
    backup_keep: int = 3
    auto_backup: bool = True
    max_nodes: int = 20000
    max_content_bytes: int = 1048576
    max_metadata_bytes: int = 65536
    strict_path_safety: bool = False
    debug_log_content: bool = False
```

| Field | Meaning |
|---|---|
| `db_path` | SQLite store file. `~` is expanded. The parent directory is created on open. |
| `learning_rate` | Hebbian bounded-learning rate in `(0, 1]`. On each co-activation, `strength ← 1 − (1 − strength)(1 − rate)`; a first wiring starts at exactly `learning_rate`. |
| `decay_half_life_days` | Edge-strength half-life used by `decay()`. Must be `> 0`. |
| `confidence_half_life_days` | Node-confidence half-life used by `decay()`. Must be `> 0`. |
| `prune_threshold` | In `[0, 1)`. Edges whose decayed strength falls below this are deleted by `decay()`. |
| `consolidation_threshold` | In `(0, 1]`. Edges at or above this strength are marked consolidated by `consolidate()`. |
| `busy_timeout_ms` | SQLite busy timeout (`>= 0`). |
| `backup_keep` | Rolling backup generations kept beside the store (`>= 0`; `0` disables backups). |
| `auto_backup` | Take/refresh a rolling backup on open (when the store changed since the last backup) and before `decay()` / `consolidate()`. |
| `max_nodes` | Backpressure ceiling (`>= 1`): storing beyond it prunes the lowest-value nodes (lowest importance, then lowest access count, then oldest update). |
| `max_content_bytes` | Oversize ceiling (`>= 1`, RM-027): one node's stored content, in UTF-8 bytes of the stored text. Above it, `remember`/`update` refuse with a typed validation error before any write. See `docs/OVERSIZE_POLICY.md`. |
| `max_metadata_bytes` | Oversize ceiling (`>= 1`, RM-027): one node's metadata, in UTF-8 bytes of its serialized JSON form. Same refusal discipline as `max_content_bytes`. |
| `strict_path_safety` | Path safety (RM-041, threat TH-02): when `True`, opening refuses a symlinked store path (the file or any parent component) and a store whose parent directory is world-writable, with a typed `MuninnStorageError` before anything is created. Default `False` — paths are `~`-expanded, never symlink-resolved, parents unchecked (the recorded behaviour). See `docs/PATH_SAFETY.md`. |
| `debug_log_content` | Log redaction (RM-044, threat TH-05): when `True`, `remember`/`retrieve` may emit memory content in log records at DEBUG level only — the sole road by which content ever reaches a log. Default `False` — no log record at any level carries memory content. See `docs/LOG_REDACTION.md`. |

All values are validated in `__post_init__`; an illegal value raises
`MuninnConfigurationError` at construction, never mid-write.

### `MuninnConfig.resolved_path() -> pathlib.Path`

**READ (pure).** The store path with `~` expanded (not
symlink-resolved).

The module also defines `DEFAULT_DB_PATH = "~/.hermes/memory/muninn_hebbian.db"`.

## 1.2 Errors — `muninn/errors.py`

Four classes:

| Class | Bases | Raised when |
|---|---|---|
| `MuninnError` | `Exception` | Base class for every error Muninn raises deliberately. |
| `MuninnValidationError` | `MuninnError`, `ValueError` | Caller supplied an invalid argument (bad id type, out-of-range value, empty/`None` content, …). Raised before any write. Also raised for any text carrying a lone surrogate (unpaired U+D800–U+DFFF): `{field} must not contain lone surrogates` — content (including strings nested in JSON-shaped content), metadata, tags, category, path and the `retrieve` filters are all checked before any write (RM-034, see `docs/UNICODE_GAUNTLET.md`). Valid Unicode of every script is stored verbatim, never normalised. Also raised for a JSON-shaped content, metadata or tag-element value nested deeper than 100 containers (`{field} nesting depth exceeds maximum of 100`) and for a cleaned tags list whose stored JSON form exceeds `max_metadata_bytes` (`tags size {n} bytes exceeds max_metadata_bytes ({c} bytes)`) — both before any write (RM-036, see `docs/ADVERSARIAL_TAGS_METADATA.md`). |
| `MuninnConfigurationError` | `MuninnError`, `ValueError` | A `MuninnConfig` value is out of its legal range. |
| `MuninnStorageError` | `MuninnError` | The store could not be opened, read, written, or healed — including unrecoverable corruption (main store *and* every rolling backup failed integrity). Muninn never silently starts empty over a corrupt store. Also raised by any operation on a closed `HebbianMemory` (via `_get_conn()`), by any write that fails in the storage layer (e.g. a full disk: `muninn write failed during {operation}: database or disk is full`, RM-029) — the failed call is rolled back first, so no partial write survives — and on open when the store's location is read-only (`muninn store {path} is read-only and cannot be opened for writing`, RM-030), immediately, before any connection or restore attempt. Also raised when another process holds the store's write lock past the busy timeout — on open (`muninn store {path} is locked by another process (busy timeout {ms} ms expired)`) and on writes (`muninn write failed during {operation}: store is locked by another process (busy timeout expired)`), RM-031; contention never takes the restore road. Also raised on open for a partial file state: a main store truncated to zero bytes takes the corruption road above, and a non-empty write-ahead log without its main file and without a verified backup raises `muninn store {path} has a write-ahead log but no main file and no rolling backup verified; refusing to start empty over lost memory` (RM-032). Also raised on open, before any other check, when the store path is not a database file at all: a directory raises `muninn store {path} is a directory, not a database file; refusing to open` and any other non-regular file raises `muninn store {path} is not a regular file; refusing to open` (RM-033). |

## 1.3 `MemoryNode` — `muninn/core.py`

```python
@dataclass
class MemoryNode:
    id: int
    content: Any
    path: str = ""
    memory_type: str = "fact"
    importance: int = 5
    emotional_valence: float = 0.0
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    access_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

Notes on the shape:

- `content` is a string, or any JSON-serializable value (stored as
  JSON and decoded back on read). Node ids are **integers**.
- In the store, `memory_type` lives in the `nodes.category` column;
  the two words name the same field.

### `MemoryNode.category` — property

**READ (pure).** Alias for `memory_type` (Bifröst-era vocabulary).

### `MemoryNode.to_dict() -> Dict[str, Any]`

**READ (pure).** Returns a dict with keys `id`, `content`, `path`,
`memory_type`, `category` (same value as `memory_type`),
`importance`, `emotional_valence`, `tags` (a copy), `metadata`
(a copy), `access_count`, `created_at`, `updated_at` (the last two
as ISO-format strings).

### `MemoryNode.from_dict(data: Dict[str, Any]) -> MemoryNode` — classmethod

**READ (pure).** Inverse of `to_dict()`. Requires `data["id"]`.
`memory_type` falls back to `data["category"]`, then `"fact"`.
Missing timestamps default to now (UTC); `datetime` values and
ISO strings are both accepted.

## 1.4 `HebbianMemory` — `muninn/core.py`

The main class. Class attribute: `MAX_QUERY_RESULTS = 1000`.

Public instance attributes set at construction:

- `config: MuninnConfig`
- `open_report: OpenReport` (see §1.6)
- `recovered_from_backup: bool` — `True` when the store had to be
  restored from a rolling backup on open.
- `last_heal_report: Dict[str, Any]` — the most recent heal report
  (the open-time heal at construction, then updated by
  `heal_structure()` and `consolidate()`).

### Construction and lifecycle

#### `HebbianMemory(config: MuninnConfig | None = None, **overrides: Any)`

**WRITE** (opens/creates the store, runs integrity check, possible
backup restore, the schema setup, the open-time heal pass, and —
when `auto_backup` is on and the store changed — a rolling backup).

- `HebbianMemory(MuninnConfig(db_path=...))` is the exact shape
  Bifröst uses (positional config).
- With `config=None`, a `MuninnConfig(**overrides)` is built.
- With both a config and `overrides`, the overrides are applied via
  `dataclasses.replace(config, **overrides)`.
- Construction opens **only this store** — never any other package's
  file — and is safe to perform from any thread.

#### `close() -> None`

**Lifecycle.** Closes the store connection. **Idempotent** — closing
twice is a no-op. After close, operations raise `MuninnStorageError`
(via `_get_conn()`).

Also usable as a context manager: `__enter__() -> HebbianMemory`,
`__exit__(*exc) -> None` (calls `close()`).

#### `backup() -> str | None`

**WRITE (store files).** Commits any pending transaction, then takes
a rolling backup now through SQLite's backup API (see
`docs/RELIABILITY.md`). Returns the newest backup's path as a string,
or `None` when `backup_keep` is `0` or the backup failed verification
(a failed backup never destroys older generations).

#### `_get_conn() -> sqlite3.Connection` — documented internal seam

**READ (internal seam).** Returns the store's one shared connection
(Row factory enabled). This is private by name but contractual in
practice: Bifröst's `_get_activation_count` runs raw SQL through it —
`SELECT COUNT(*) as cnt FROM activation_log WHERE memory_id = ?` —
and reads `row["cnt"]`. Raises `MuninnStorageError` if the memory is
closed. Callers must treat the connection as read-mostly and must not
commit behind Muninn's back.

### Activation and wiring (writes)

#### `activate(memory_id: int, *, emotional_valence: float = 0.0, source: str = "api") -> int`

**WRITE.** Logs one activation of `memory_id`:

- inserts one `activation_log` row (`memory_id`, `activated_at`,
  `emotional_valence`, `source`);
- increments the id's counter in `node_activation` and restores its
  confidence toward 1.0 (`conf ← conf + learning_rate · (1 − conf)`,
  capped at 1.0);
- if a node with this id lives in this store, bumps its
  `access_count` and `updated_at`;
- clears any tombstone for the id (the caller's world says the id
  lives again).

Returns the id's new total activation count. Ids need not be nodes in
this store — external ids (e.g. another store's row ids) are legal.
`memory_id` must be an `int >= 0` (bools rejected);
`emotional_valence` must be in `[-1, 1]`.

`activate` is an event and is intentionally **not idempotent**:
calling it twice logs two activations.

#### `activate_batch(memory_ids: List[int], *, emotional_valence: float = 0.0, source: str = "api") -> Dict[str, Any]`

**WRITE.** The Hebbian co-activation operation. Each **unique** id is
activated once (same effects as `activate`), then every unordered
pair is wired: both directed rows (`a→b` and `b→a`) are strengthened
by the bounded rule `strength ← 1 − (1 − strength)(1 − learning_rate)`
(a first wiring starts at `learning_rate`), with
`co_activation_count += 1`. Fully transactional — a crash leaves
either the whole batch or none of it. Accepts a list or tuple;
anything else raises `MuninnValidationError`. Batches of 64 or more
unique ids are generated in bulk inside SQLite with identical
semantics and counts (RM-035, `docs/HUGE_BATCH_ATOMICITY.md`):
Python-side memory is O(unique ids) at any batch size, and the
report below is exact at 10k ids (49,995,000 pairs).

Returns:

```python
{
    "activated": int,                  # unique ids activated
    "pairs_wired": int,                # unordered pairs processed
    "connections_created": int,        # pairs with no prior wiring
    "connections_strengthened": int,   # pairs_wired - connections_created
}
```

#### `associate(memory_a: int, memory_b: int, *, strength: float | None = None, delta: float | None = None) -> float`

**WRITE.** Manually wire two memories; returns the new strength of
the `a→b` row.

- With `strength` (must be in `[0, 1]`): set both directed rows to
  exactly it (`co_activation_count += 1`).
- With `delta`, or with neither argument: apply the bounded Hebbian
  update using `delta` as this call's learning rate (default: the
  config's `learning_rate`); `delta` must be in `(0, 1]`.
- Passing both `strength` and `delta` raises
  `MuninnValidationError`, as does associating a memory with itself.
- Also clears tombstones for both ids.

### Pure reads over the wiring

#### `get_associations(memory_id: int, min_strength: float = 0.0, limit: int = 100) -> List[Dict[str, Any]]`

**READ (pure).** Associations of a memory, **strongest first**
(`strength DESC`, then `co_activation_count DESC`). Ordering is
contractual: Bifröst consumes `[0]["strength"]` as its associative
boost. `min_strength` must be in `[0, 1]`; `limit` is clamped to
`[1, 10000]`. Each dict:

```python
{
    "memory_id": int,              # the other end of the edge
    "strength": float,             # in [0, 1]
    "co_activation_count": int,
    "consolidated": bool,
    "last_coactivated_at": str | None,   # ISO timestamp
}
```

#### `activation_count(memory_id: int) -> int`

**READ (pure).** How many activations this id has logged
(`COUNT(*)` over `activation_log`).

#### `spread_activation(seed_ids: List[int], *, depth: int = 2, attenuation: float = 0.5, min_strength: float = 0.0, limit: int = 1000) -> Dict[int, float]`

**READ (pure).** Breadth-first spread over edges with
`strength >= min_strength`. Seeds start at `1.0`; each hop multiplies
by edge strength and `attenuation` (must be in `(0, 1]`). `depth` is
clamped to `[0, 10]`. Returns `{memory_id: activation}` with seeds
included, strongest first in iteration order, truncated to at most
`max(1, limit)` entries. A node keeps the strongest value any path
gives it.

### Node API

#### `remember(content: Any, *, category: str = "general", path: str = "", importance: int = 5, tags: Optional[List[str]] = None, emotional_valence: float = 0.0, metadata: Optional[Dict[str, Any]] = None) -> int`

**WRITE.** Store a memory node; returns its integer id.

- **Idempotent by content hash:** storing the same content under the
  same `category` and `path` returns the existing node's id instead
  of duplicating it (unique index on `(content_hash, category, path)`)
  — safe under retries, including concurrent retries.
- `content` must not be `None`; a string is stored as-is, any other
  JSON-serializable value is stored as JSON. `importance` must be an
  `int` in `[1, 10]`; `emotional_valence` in `[-1, 1]`; `metadata`
  must be JSON-serializable.
- Tags are normalized: stringified, stripped, lowercased, truncated
  to 64 chars; empty tags dropped.
- Storing a **new** node may trigger backpressure: if the store then
  exceeds `config.max_nodes`, the lowest-value nodes are pruned
  (with their wiring, and tombstoned).

#### `store(content: Any, path: str = "", memory_type: str = "fact", importance: int = 5, tags: Optional[List[str]] = None, metadata: Optional[Dict[str, Any]] = None, *, emotional_valence: float = 0.0) -> int`

**WRITE.** Ancestor-shaped alias of `remember()`, with
`category = memory_type`. Same idempotency and validation.

#### `get_node(memory_id: int) -> Optional[MemoryNode]`

**READ (pure).** One node by id, or `None`.

#### `retrieve(query: Optional[str] = None, path: Optional[str] = None, tags: Optional[List[str]] = None, memory_type: Optional[str] = None, top_k: int = 5, *, category: Optional[str] = None, touch: bool = False) -> List[MemoryNode]`

**READ (pure) by default; WRITE when `touch=True`.**

- `query` is a case-insensitive substring match over content (JSON
  content is matched against its JSON text).
- `path` matches that exact path or anything under it
  (`path` or `path/...`).
- `tags` matches nodes carrying **any** of the given tags
  (case-insensitive).
- `memory_type` filters the category; `category` (keyword-only) is
  an alias and takes precedence when both are given.
- Results sort by importance descending, then `updated_at`
  descending. `top_k` is clamped to `[1, MAX_QUERY_RESULTS]`.
- **`touch=True` is the only reinforcing read in either package.**
  It is explicit and opt-in: each returned node is also activated
  (with its own stored `emotional_valence`, source
  `"retrieve:touch"`). The default `touch=False` never writes —
  proven by table-snapshot tests.

#### `get_by_path(path: str) -> List[MemoryNode]`

**READ (pure).** All nodes at exactly `path`, ordered by importance
descending, then `updated_at` descending. The argument is
normalised first (RM-028, below), so any spelling of the path
finds the same nodes.

#### `get_children(parent_path: str) -> Dict[str, List[MemoryNode]]`

**READ (pure).** Nodes at any path strictly under `parent_path`
(prefix `parent_path + "/"`), grouped by their full path. Each group
is ordered by importance descending. The parent is normalised
first; `get_children("")` returns every node at a non-root path,
and `%` / `_` / `\` inside a segment match literally, never as
LIKE wildcards.

**Path normalisation (RM-028).** Every node path — written by
`remember` / `store` / `update` / `move`, queried by `retrieve`,
`get_by_path` and `get_children` — passes through one normaliser:
split on `/`, drop empty and `.` segments, let `..` remove the
previous segment (clamped at the root), re-join with single
`/`s. Only `/` separates segments. Non-string paths raise
`MuninnValidationError`, as do normalised paths over 64
segments or 2048 UTF-8 bytes. Full record:
`docs/PATHOLOGICAL_PATHS.md`.

#### `update(node_id: int, content: Any = None, **fields: Any) -> bool`

**WRITE.** Update a node's fields. Returns `False` when no such node
exists; `True` when the node exists (including when there was
nothing to change).

- `content` (positional-or-keyword, default `None` = unchanged)
  replaces the content (and its hash / JSON flag).
- Allowed `fields`: `importance`, `emotional_valence`, `tags`,
  `metadata`, `path`, `memory_type`, `category` (the last two both
  set the stored category). Any other field name raises
  `MuninnValidationError`, as do out-of-range values.
- An update that would duplicate an existing node (same content,
  category, path) rolls back and raises `MuninnValidationError`.
- `updated_at` is refreshed on any real update.

#### `forget(memory_id: int) -> bool`

**WRITE.** Remove a memory's node and **all** its wiring (both
directions). The id is tombstoned in `deleted_nodes` — even when
nothing existed — so the heal pass can prune any later stray edge
that references it. The `activation_log` is **kept** (it is a log),
and `node_activation` counters are not removed. Returns `True` when
a node or any wiring was actually removed. A later activation of the
same id clears the tombstone.

#### `delete(node_id: int) -> bool`

**WRITE.** Ancestor-shaped alias of `forget()`.

#### `move(node_id: int, new_path: str) -> bool`

**WRITE.** Move a node to a new hierarchical path. Exactly
`update(node_id, path=str(new_path))`, including its return value.

#### `get_tree_structure() -> Dict[str, Any]`

**READ (pure).** The hierarchical path tree with node counts: nested
dicts keyed by path segment, each level that holds nodes directly
carrying `"_nodes": <count>`. Nodes at the empty path contribute no
segments and do not appear.

#### `dump(limit: int = 50) -> Dict[str, Any]`

**READ (pure).** Debug dump: `{"stats": <stats() dict>, "nodes":
[<MemoryNode.to_dict()>, ...]}` for the highest-importance nodes
(then most recently updated). `limit` is clamped to `[1, 500]`.

### Maintenance (writes, named)

#### `heal_structure() -> Dict[str, Any]`

**WRITE.** Run the self-healing pass now and return its report; also
stored as `last_heal_report`. Fixes (also run automatically on every
open):

```python
{
    "self_edges_pruned": int,      # rows with memory_a_id == memory_b_id deleted
    "dangling_edges_pruned": int,  # rows touching a tombstoned (forgotten) id deleted
    "pairs_repaired": int,         # missing reverse rows inserted; disagreeing pairs reconciled
    "counters_fixed": int,         # node_activation totals reconciled with activation_log
    "fixes": int,                  # sum of the four counts above
}
```

Details: a disagreeing directed pair is reconciled to the
**stronger** strength and the **larger** co-activation count (and
`consolidated = min` of the two). Counter reconciliation counts the
log per id: a missing counter row is inserted (confidence 1.0), a
wrong total is corrected. Edges to ids that were never registered as
nodes and never forgotten are **legal by design** (cross-store ids)
and are not pruned.

#### `decay(days: float = 1.0) -> Dict[str, Any]`

**WRITE.** Fade state by elapsed `days` (must be a number `>= 0`).

- Edge strengths multiply by `0.5 ** (days / decay_half_life_days)`.
- Edges below `consolidation_threshold` are unmarked
  (`consolidated = 0`); edges below `prune_threshold` are deleted.
- Node confidences (`node_activation`) multiply by
  `0.5 ** (days / confidence_half_life_days)`.
- If `auto_backup` is on, a rolling backup is taken first.
- Deterministic and safe to re-run.

Returns:

```python
{
    "days": float,
    "edge_factor": float,
    "confidence_factor": float,
    "edges_decayed": int,        # connection rows updated (both directions)
    "edges_pruned": int,         # connection rows deleted
    "confidences_decayed": int,  # node_activation rows updated
}
```

#### `consolidate(threshold: float | None = None) -> Dict[str, Any]`

**WRITE.** Mark strong edges consolidated (sleep).

- `threshold` defaults to `config.consolidation_threshold` (0.8);
  must be in `(0, 1]`.
- Edges at or above the threshold are marked `consolidated = 1`;
  edges below it are unmarked.
- If `auto_backup` is on, a rolling backup is taken first.
- The heal pass runs as part of consolidation.
- Node content is never rewritten. Safe to re-run (a second run
  reports `newly_consolidated == 0` when nothing changed).

Returns:

```python
{
    "threshold": float,
    "newly_consolidated": int,   # directed rows newly marked
    "unmarked": int,             # directed rows newly unmarked
    "total_consolidated": int,   # directed rows marked after the pass
    "heal": <heal report dict>,
}
```

### Health and stats (pure reads)

#### `health() -> Dict[str, Any]`

**READ (pure)** (integrity via `PRAGMA quick_check`).

```python
{
    "status": "healthy" | "degraded",   # "healthy" iff integrity == "ok"
    "db_path": str,
    "integrity": str,                   # quick_check result, or "failed"
    "recovered_from_backup": bool,
    "nodes": int,
    "connections": int,                 # directed rows
    "activations": int,                 # activation_log rows
    "schema_version": "1",
    "file_permissions_warning": str | None,  # RM-042: warning when an existing
                                             # store file is looser than 0600;
                                             # see docs/FILE_PERMISSIONS.md
}
```

#### `stats() -> Dict[str, Any]`

**READ (pure).**

```python
{
    "total_nodes": int,
    "total_connections": int,           # directed rows
    "total_activations": int,
    "consolidated_connections": int,    # directed rows
    "strongest_connection": float,      # 0.0 when there are no edges
    "categories": Dict[str, int],       # node count per category
    "db_path": str,
}
```

Bifröst's guard tests require the keys `total_activations` and
`total_connections`; both are present.

#### `get_stats() -> Dict[str, Any]`

**READ (pure).** Ancestor-shaped alias of `stats()`.

## 1.5 `Muninn` — ancestor-compatible facade

```python
class Muninn(HebbianMemory):
    def __init__(
        self,
        data_path: str | None = None,
        *,
        config: MuninnConfig | None = None,
        **overrides: Any,
    )
```

**WRITE** (same open behaviour as `HebbianMemory`). Accepts the
ancestor's construction shape:

- `Muninn(data_path=...)`: `data_path` may be a directory (the store
  becomes `<dir>/muninn_hebbian.db`) or a path ending in `.db`
  (used as the store file itself). `~` is expanded.
- With an explicit `config`, `data_path` is ignored.
- With neither, a default `MuninnConfig()` is used.
- `**overrides` are forwarded to `HebbianMemory.__init__`.

All methods are inherited from `HebbianMemory`, unchanged.

## 1.6 `OpenReport` — `muninn/_db.py`

Reachable as `muninn._db.OpenReport` (not exported at package top
level). A `HebbianMemory` instance's `open_report` attribute holds
one, describing what happened while its store opened:

```python
@dataclass
class OpenReport:
    recovered_from_backup: bool = False
    restored_backup: str | None = None   # path of the backup restored, if any
    backup_taken: bool = False           # a fresh rolling backup was taken on open
    integrity: str = "ok"
```

The same module holds the store machinery used above:
`_connect(path, busy_timeout_ms)`, `take_backup(db_path, keep)`,
and `open_store(...)`. They are internal; `OpenReport` is documented
here because its instances are part of the observable surface.

## 1.7 Muninn store schema (contractual parts)

Tables: `meta`, `nodes`, `activation_log`, `hebbian_connections`,
`node_activation`, `deleted_nodes`. Two parts are contractual across
projects (see `docs/INTEGRATION.md`):

- `activation_log(memory_id, activated_at, emotional_valence, source)`
- `hebbian_connections(memory_a_id, memory_b_id, strength,
  co_activation_count, consolidated, created_at, last_coactivated_at)`
  — directed rows stored in **both** directions, kept symmetric by
  the API.
- `meta` carries `schema_version = "1"`.

---

# Part 2 — `huginn` (semantic retrieval)

Package exports (`huginn/__init__.py`, `__all__`):

```python
from huginn import (
    HuginnMemory, HuginnConfig, RetrievalResult,
    analyze_query, semantic_search,
    HuginnError, HuginnValidationError, HuginnConfigurationError,
    HuginnStorageError, HuginnBackendError,
)
# huginn.__version__ == "1.0.0"
```

Backends, embedders and text helpers live in submodules:
`huginn.config` (constants), `huginn.local_backend.LocalBackend`,
`huginn.qdrant_backend.QdrantBackend`, `huginn.text` (embedders and
TF-IDF machinery).

## 2.1 `HuginnConfig` and constants — `huginn/config.py`

```python
BACKENDS = ("auto", "local", "qdrant")
EMBEDDERS = ("tfidf", "hashing", "sentence-transformers")
DEFAULT_LOCAL_DB_PATH = "~/.hermes/memory/huginn_local.db"

@dataclass
class HuginnConfig:
    backend: str = "auto"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    collection_name: str = "huginn_memories"
    local_db_path: str = DEFAULT_LOCAL_DB_PATH
    embedder: str = "tfidf"
    vector_dim: int = 384
    st_model: str = "all-MiniLM-L6-v2"
    qdrant_timeout: float = 2.0
    busy_timeout_ms: int = 5000
    backup_keep: int = 3
    auto_backup: bool = True
    max_content_bytes: int = 1048576
    strict_path_safety: bool = False
    debug_log_content: bool = False
```

| Field | Meaning |
|---|---|
| `backend` | One of `BACKENDS`. `"auto"` (default) probes Qdrant once, lazily, on first use, and falls back to the local backend **permanently for that object** if anything fails, recording why for `health()`. `"local"` never touches the network. `"qdrant"` is explicit: failures raise `HuginnBackendError`. |
| `qdrant_url` | Qdrant server URL. Non-empty string. |
| `qdrant_api_key` | Optional Qdrant API key. |
| `collection_name` | Qdrant collection for memories. Non-empty string. |
| `local_db_path` | SQLite file for the local backend. Non-empty string. |
| `embedder` | One of `EMBEDDERS`. `"tfidf"` (default): the local backend's native lexical scoring, no vectors. `"hashing"`: deterministic feature-hashing vectors (stdlib). `"sentence-transformers"`: neural embeddings, needs the `embeddings` extra. With a Qdrant backend, `"tfidf"` resolves to `"hashing"` (Qdrant needs fixed-space vectors); `health()` reports the effective embedder honestly. |
| `vector_dim` | Hashing-embedder dimension (and Qdrant collection size for that embedder). Must be `>= 8`. |
| `st_model` | sentence-transformers model name. |
| `qdrant_timeout` | Seconds for the auto-probe and Qdrant calls. Must be `> 0`. |
| `busy_timeout_ms` / `backup_keep` / `auto_backup` | Same store discipline as Muninn's config. |
| `max_content_bytes` | Oversize ceiling (`>= 1`, RM-027): one memory's content, in UTF-8 bytes. Above it, `upsert_memory` refuses with a typed validation error in the facade, before any backend is touched. Huginn memories carry no caller metadata, so there is no metadata ceiling here. See `docs/OVERSIZE_POLICY.md`. |
| `strict_path_safety` | Path safety (RM-041, threat TH-02): when `True`, opening the **local** store refuses a symlinked store path (the file or any parent component) and a store whose parent directory is world-writable, with a typed `HuginnStorageError` before anything is created. Default `False` — paths are `~`-expanded, never symlink-resolved, parents unchecked (the recorded behaviour). The Qdrant backend has no local file and is unaffected. See `docs/PATH_SAFETY.md`. |
| `debug_log_content` | Log redaction (RM-044, threat TH-05): when `True`, the facade's `upsert_memory`/`search` may emit memory content in log records at DEBUG level only — the sole road by which content ever reaches a log. Default `False` — no log record at any level carries memory content. See `docs/LOG_REDACTION.md`. |

All values are validated in `__post_init__`; illegal values raise
`HuginnConfigurationError` at construction.

### `HuginnConfig.resolved_local_path() -> pathlib.Path`

**READ (pure).** `local_db_path` with `~` expanded.

## 2.2 Errors — `huginn/errors.py`

Five classes:

| Class | Bases | Raised when |
|---|---|---|
| `HuginnError` | `Exception` | Base class for every error Huginn raises deliberately. |
| `HuginnValidationError` | `HuginnError`, `ValueError` | Caller supplied an invalid argument. Raised before any write. Also raised for any text carrying a lone surrogate (unpaired U+D800–U+DFFF): `{field} must not contain lone surrogates` — `upsert_memory`'s content, category and tags, every query-shaped argument and `semantic_search`'s documents are checked in the facade before any backend is touched (RM-034, see `docs/UNICODE_GAUNTLET.md`). Valid Unicode of every script is stored verbatim, never normalised. Also raised in the facade for a tag element nested deeper than 100 containers (`tags nesting depth exceeds maximum of 100`) and for a cleaned tags list whose JSON form exceeds `max_content_bytes` (`tags size {n} bytes exceeds max_content_bytes ({c} bytes)`) — both before any backend is touched (RM-036, see `docs/ADVERSARIAL_TAGS_METADATA.md`). |
| `HuginnConfigurationError` | `HuginnError`, `ValueError` | A `HuginnConfig` value is illegal, or a configured optional dependency (`qdrant-client`, `sentence-transformers`) is missing. |
| `HuginnStorageError` | `HuginnError` | The local store could not be opened, read, written, or healed — including unrecoverable corruption (main store and every rolling backup failed integrity). Also raised by `LocalBackend` operations after close, by any local write that fails in the storage layer (e.g. a full disk: `huginn write failed during {operation}: database or disk is full`, RM-029) — the failed call is rolled back first, so no partial write survives — and on open when the store's location is read-only (`huginn store {path} is read-only and cannot be opened for writing`, RM-030), immediately, before any connection or restore attempt. Also raised when another process holds the local store's write lock past the busy timeout — on open (`huginn store {path} is locked by another process (busy timeout {ms} ms expired)`) and on writes (`huginn write failed during {operation}: store is locked by another process (busy timeout expired)`), RM-031; contention never takes the restore road. Also raised on open for a partial file state: a main store truncated to zero bytes takes the corruption road above, and a non-empty write-ahead log without its main file and without a verified backup raises `huginn store {path} has a write-ahead log but no main file and no rolling backup verified; refusing to start empty over lost memory` (RM-032) — the facade's `health()` reports that refusal as `unhealthy`, naming the error. Also raised on open, before any other check, when the store path is not a database file at all: a directory raises `huginn store {path} is a directory, not a database file; refusing to open` and any other non-regular file raises `huginn store {path} is not a regular file; refusing to open` (RM-033) — likewise reported by `health()` as `unhealthy`. |
| `HuginnBackendError` | `HuginnError` | The selected backend failed at operation time (e.g. an explicit Qdrant backend whose server is unreachable), or an operation is attempted on a closed `HuginnMemory`. |

The one designed non-error: with `backend="auto"`, a missing Qdrant
is answered by the local backend and reported in `health()` — it
never raises into the caller.

## 2.3 `HuginnMemory` — `huginn/core.py`

The facade over the two backends. Public attribute: `config`.

Module constants in `huginn/core.py`: `MAX_RESULTS_CAP = 50`
(flight result cap), `MAX_QUERY_CHARS = 1000` (query truncation for
analysis and flights).

### Construction and lifecycle

#### `HuginnMemory(config: HuginnConfig | None = None, **overrides: Any)`

**Lazy — neither READ nor WRITE at construction.** No file is
opened, no server is contacted, until the first operation.
`HuginnMemory(config=None)` — Bifröst's exact call — works with no
Qdrant server anywhere: the defaults land on the local backend.
With both a config and `overrides`, overrides are applied via
`dataclasses.replace`.

Backend selection happens once, on first use:

- `"local"` → build a `LocalBackend`.
- `"qdrant"` → build a `QdrantBackend` and `ping()` it; unreachable
  raises `HuginnBackendError`, loudly.
- `"auto"` → try Qdrant once (build + `ping()`); **any** exception
  selects the local backend permanently for this object, stores the
  reason as the fallback reason, and `health()` thereafter reports
  `status: "degraded"` with `fallback_reason`.

#### `close() -> None`

**Lifecycle.** Closes the backend if one was built. **Idempotent.**
After close, operations that need a backend raise
`HuginnBackendError("HuginnMemory is closed")` (though `health()`
converts that into an `"unhealthy"` report — see below).

Context manager: `__enter__() -> HuginnMemory`,
`__exit__(*exc) -> None` (calls `close()`).

### Contract API

#### `upsert_memory(content: str, category: str = "general", importance: int = 5, tags: Optional[List[str]] = None, emotional_valence: float = 0.0, *, memory_id: Optional[int] = None) -> int`

**WRITE.** Store (or replace) one memory; returns its id.

- `content` must be a non-empty string; `importance` an `int` in
  `[1, 10]`; `emotional_valence` in `[-1, 1]`; `memory_id`, when
  given, an `int >= 0`. Violations raise `HuginnValidationError`
  before any write. Tags are stringified as given (no case-folding,
  unlike Muninn).
- **Idempotent:** the same content in the same category is the same
  memory (content-hash identity — see the backends, §2.5–2.6, for
  exactly how each one keys it). Re-upserting replaces the stored
  fields and re-indexes / re-embeds.
- Pass `memory_id` to align the id with an external store (Bifröst
  merges backends by id). On the local backend, asking for a free
  `memory_id` whose content already lives at a different id raises
  `HuginnValidationError` — upsert at the existing id instead.

#### `search(query_text: str, limit: int = 10, category: Optional[str] = None, min_importance: int = 1) -> List[Dict[str, Any]]`

**READ (pure).** Semantic search, best first. There is **no**
`reinforce` parameter — Huginn has no reinforcing read at all;
reinforcement is Muninn's job.

- A non-string `query_text` raises `HuginnValidationError`; a blank
  query is an honest empty result (`[]`), not an error.
- `limit` is clamped to `[1, 1000]`. `min_importance` must be an
  `int` (bools rejected); filtering applies only when it is `> 1`.
- `category=None` searches all categories.
- Each result dict has exactly the keys:

```python
{
    "id": int,
    "content": str,
    "category": str,
    "importance": int,
    "tags": List[str],
    "emotional_valence": float,
    "score": float,   # backend score; TF-IDF / cosine scores are in (0, 1]
}
```

Only positive scores are returned.

#### `get(memory_id: int) -> Optional[Dict[str, Any]]`

**READ (pure).** One memory by id, or `None`. The dict has the same
keys as a search result **without** `score`.

#### `delete(memory_id: int) -> bool`

**WRITE.** Remove one memory (document, its index postings / vector,
and — on Qdrant — its point). `True` when something was removed.

#### `health() -> Dict[str, Any]`

**READ (pure)** with respect to the store — but note it *triggers
lazy backend construction* on first call, like every operation.
Never raises for backend trouble:

- On success it returns the backend's health dict (see §2.5 / §2.6),
  plus `embedder` (effective embedder name: `"tfidf"`, `"hashing"`,
  or `"sentence-transformers"`) and `backend_configured` (the
  config's `backend` value). When auto mode fell back, `status` is
  overwritten to `"degraded"` and `fallback_reason` is added.
- If ensuring the backend raises a `HuginnError` (e.g. explicit
  Qdrant unreachable, or the memory is closed), it returns instead:

```python
{
    "status": "unhealthy",
    "backend_configured": str,
    "error": str,
    "error_type": str,   # exception class name
}
```

So `status` is one of `"healthy"`, `"degraded"` (auto fell back to
local), or `"unhealthy"` (explicit backend failing).

#### `stats() -> Dict[str, Any]`

**READ (pure).** Exactly `health()` — Bifröst calls `health()` for
this purpose; both exist and return the same dict.

### Ancestor flight semantics

#### `analyze_query(query: str) -> Dict[str, Any]` — method

**READ (pure).** Delegates to the module function `analyze_query`
(§2.4).

#### `fly(query: str, max_results: int = 5, compress: bool = True) -> RetrievalResult`

**READ (pure)** with respect to the store; it does append the flight
to this object's in-memory flight history ( capped: when the history
exceeds 100 entries it is trimmed to the last 50).

- Flies `search()` over this store. `max_results` is clamped to
  `[1, MAX_RESULTS_CAP]` (50). The query is stripped and truncated
  to `MAX_QUERY_CHARS` (1000) for the search; the `RetrievalResult`
  keeps the original `query`.
- `compress=True` applies ancestor compression to each result:
  strings longer than 200 chars are truncated to 200 + `"..."`,
  lists longer than 5 are cut to 5.
- On a backend `HuginnError`, the flight comes home empty with
  `error` set — it does not raise.

#### `multi_hop_retrieve(initial_query: str, hop_count: int = 2, max_results_per_hop: int = 3) -> List[RetrievalResult]`

**READ (pure)** with respect to the store (each hop is a `fly()`, so
flights are recorded in the history). Chained flights: each hop's
results seed the next query.

- `hop_count` is clamped to `[1, 5]`.
- After each flight, concepts are extracted from result contents
  (whitespace-split words, alphabetic, length > 4, deduplicated,
  sorted, at most 10); the next query is
  `f"{initial_query} {' '.join(concepts[:3])}"`.
- Stops early when a flight returns no results or no concepts.

#### `get_flight_stats() -> Dict[str, Any]`

**READ (pure).** Statistics over this object's flights. With no
flights yet: `{"total_flights": 0}`. Otherwise:

```python
{
    "total_flights": int,
    "total_results_retrieved": int,
    "total_flight_time": float,        # seconds, summed
    "avg_flight_time": float,
    "avg_results_per_flight": float,
    "realm_visits": Dict[str, int],    # count per source_realm
}
```

## 2.4 Module functions and `RetrievalResult` — `huginn/core.py`

### `analyze_query(query: str) -> Dict[str, Any]`

**READ (pure).** The ancestor's query analysis. The query is handled
as `(query or "")`, stripped, truncated to 1000 chars.

```python
{
    "query_type": str,        # see below
    "key_terms": List[str],   # see below
    "strategy": str,          # see below
    "recommended_hops": int,
    "word_count": int,        # words in the (truncated) query
}
```

- `query_type`: `"explanatory"` if the lowercased query contains
  `why`, `how`, or `explain`; else `"search"` for `find`, `search`,
  `where`; else `"enumeration"` for `list`, `all`, `show`; else
  `"comparison"` for `compare`, `difference`, `vs`; else
  `"factual"`. (Checks run in that order, as substring matches.)
- `key_terms`: whitespace-split words of the lowercased query that
  are not in `STOPWORDS` and have length `> 2`. (Unlike `tokenize`,
  no punctuation stripping is done here.)
- `strategy` / `recommended_hops`: comparison → `"multi_hop"`, 2;
  enumeration → `"broad"`, 1; more than 3 key terms → `"focused"`, 1;
  otherwise `"standard"`, 1.

### `semantic_search(query: str, documents: List[str], top_k: int = 3) -> List[Tuple[int, float]]`

**READ (pure).** TF-IDF semantic search over caller-supplied
documents — the ancestor's signature, reimplemented on stdlib sparse
TF-IDF (no sklearn). Returns `(index, score)` pairs, best first,
positive scores only; `top_k` is clamped to `[1, len(documents)]`.
An empty `documents` list returns `[]`. Nothing is stored.

### `RetrievalResult`

```python
@dataclass
class RetrievalResult:
    query: str
    results: List[Dict[str, Any]]
    relevance_scores: List[float]
    source_realm: str
    retrieval_time: float
    compressed: bool
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

The result of one flight. `source_realm` is `"huginn:local"` or
`"huginn:qdrant"` for flights made by `fly()` (`"huginn:unresolved"`
when no backend was built and the flight errored). `relevance_scores`
mirrors the `score` of each entry in `results`, in order.

## 2.5 `LocalBackend` — `huginn/local_backend.py`

The zero-infrastructure backend: one WAL SQLite file plus a
maintained inverted term index. Tables: `meta`, `documents`,
`doc_terms`, `corpus_stats`, `doc_vectors`. `meta` carries
`schema_version = "1"`.

```python
class LocalBackend:
    kind = "local"
    def __init__(self, config: HuginnConfig, embedder: Optional[Embedder] = None)
```

Construction opens the store (integrity check, possible backup
restore, schema, open-time heal) — **WRITE** in the same sense as
`HebbianMemory` construction. Public attributes: `config`,
`open_report` (a `huginn._db.OpenReport`, same shape as Muninn's),
`recovered_from_backup: bool`, `last_heal_report: Dict[str, Any]`.

Scoring modes:

- `embedder is None` (config embedder `"tfidf"`): TF-IDF cosine over
  the inverted index — **lexical** semantics (weighted word
  overlap). Candidates come from the term postings; no full scan.
  A query with no surviving tokens returns `[]`.
- Otherwise: per-document vectors are stored in `doc_vectors` and
  scored by dense cosine, scanning all stored vectors.

Methods:

| Method | Kind | Signature and semantics |
|---|---|---|
| `close() -> None` | Lifecycle | Close the connection. Idempotent. Later operations raise `HuginnStorageError`. |
| `heal() -> Dict[str, Any]` | WRITE | Run the index heal now; returns (and stores as `last_heal_report`): `{"orphan_terms_pruned": int, "orphan_vectors_pruned": int, "doc_freq_fixed": int}` — `doc_terms` / `doc_vectors` rows whose document is gone are deleted; every term's `corpus_stats.doc_freq` is recounted from `doc_terms` and corrected (rows inserted, updated, or deleted to match). Also runs on every open. |
| `upsert(content: str, *, category: str, importance: int, tags: List[str], emotional_valence: float, memory_id: Optional[int] = None) -> int` | WRITE | The backend form of `upsert_memory` (arguments already validated by the facade). Identity is the `(content_hash, category)` unique key, where the hash is SHA-256 of `category + "\x00" + content`. Re-upsert replaces fields, de-indexes the old terms, re-indexes, and replaces the stored vector when an embedder is configured — all in one transaction. |
| `delete(memory_id: int) -> bool` | WRITE | De-index, drop the vector, delete the document — one transaction. `True` iff a document row was removed. |
| `get(memory_id: int) -> Optional[Dict[str, Any]]` | READ (pure) | Document dict (no `score`), or `None`. |
| `count() -> int` | READ (pure) | Number of documents. |
| `search(query_text: str, *, limit: int, category: Optional[str], min_importance: int) -> List[Dict[str, Any]]` | READ (pure) | Scored document dicts, best first, positive scores only, at most `limit`. `category` filters exactly; `min_importance` filters only when `> 1`. |
| `health() -> Dict[str, Any]` | READ (pure) | `{"status": "healthy" \| "degraded", "backend": "local", "db_path": str, "integrity": str, "recovered_from_backup": bool, "documents": int, "vocabulary": int, "sqlite_version": str, "file_permissions_warning": str \| None}` where `vocabulary` is the number of terms in `corpus_stats`, status is `"healthy"` iff `quick_check` is `"ok"`, and `file_permissions_warning` (RM-042) is a warning string when an existing store file is looser than owner-only `0600`, else `None` (see `docs/FILE_PERMISSIONS.md`). |

`huginn._db.OpenReport` has the same four fields as Muninn's
(`recovered_from_backup`, `restored_backup`, `backup_taken`,
`integrity`). Note: `LocalBackend` has **no** `ping()` and **no**
`backup()` method in the source — backups happen inside
`huginn._db.open_store` on open; there is no public take-a-backup
call on this backend.

## 2.6 `QdrantBackend` — `huginn/qdrant_backend.py`

Qdrant vector store behind the same backend shape. Requires the
`qdrant` extra (`qdrant-client>=1.9,<2`). The client is imported
lazily and the server is contacted only on use — constructing the
backend touches no network.

```python
class QdrantBackend:
    kind = "qdrant"
    def __init__(self, config: HuginnConfig, embedder: Embedder)
```

The embedder is required (HuginnMemory supplies the hashing
embedder when the config says `"tfidf"`).

Identity: a point's id is the caller's `memory_id` when given, else
derived deterministically from the content hash — the first 16 hex
characters of the SHA-256 of `category + "\x00" + content`,
interpreted as a big-endian integer. Re-upserting the same content
in the same category therefore targets the same point (idempotent).
The payload stored per point: `content`, `category`, `importance`,
`tags`, `emotional_valence`, `content_hash`. The collection is
created on first use if missing, with cosine distance and vector
size = the embedder's `dim`.

Methods (all backend failures are wrapped in `HuginnBackendError`;
a missing `qdrant-client` raises `HuginnConfigurationError`):

| Method | Kind | Signature and semantics |
|---|---|---|
| `ping() -> None` | READ (network) | Raise unless the server answers (`get_collections()`). `HuginnConfigurationError` if the client package is missing; `HuginnBackendError` for any server failure. |
| `upsert(content: str, *, category: str, importance: int, tags: List[str], emotional_valence: float, memory_id: Optional[int] = None) -> int` | WRITE | Embed the content, upsert one point, return the point id. Pings and ensures the collection first. |
| `delete(memory_id: int) -> bool` | WRITE | `False` when no such point exists; otherwise deletes it and returns `True`. |
| `get(memory_id: int) -> Optional[Dict[str, Any]]` | READ | Retrieve one point → document dict (no `score`), or `None`. |
| `search(query_text: str, *, limit: int, category: Optional[str], min_importance: int) -> List[Dict[str, Any]]` | READ | Embed the query and search the collection (uses `query_points` when the client offers it, else the older `search`). `category` becomes an exact-match filter condition; `min_importance > 1` becomes a `>=` range condition. Result dicts carry `score` from the point. |
| `count() -> int` | READ | Number of points in the collection. |
| `health() -> Dict[str, Any]` | READ | Pings, counts, returns `{"status": "healthy", "backend": "qdrant", "qdrant_url": str, "collection": str, "documents": int}`. Raises `HuginnBackendError` when the server does not answer. |
| `close() -> None` | Lifecycle | Close the client if one was built. Idempotent. |

Note: `QdrantBackend` has **no** `heal()` method in the source —
healing is a local-store concept. (`HuginnMemory` never calls
`heal()` on either backend; the local heal runs inside
`LocalBackend` construction and via its public `heal()`.)

## 2.7 Text machinery and embedders — `huginn/text.py`

Honesty labels from the module itself: `tfidf` scoring is **lexical**
semantics (weighted word overlap), not neural embedding similarity;
the hashing embedder approximates lexical overlap in vector form;
`sentence-transformers` is the only neural embedder.

### `STOPWORDS: frozenset[str]`

**READ (pure) constant.** The ancestor Huginn's stopword set, kept
verbatim: 54 words — articles, auxiliaries, common prepositions and
adverbs (`"the"`, `"a"`, `"an"`, `"is"`, `"are"`, …, `"when"`,
`"where"`, `"why"`, `"how"`). Used by both `tokenize` and
`analyze_query`.

### `tokenize(text: str) -> list[str]`

**READ (pure).** Lowercase word tokens: matches of the Unicode regex
`[^\W_]+` over `str(text).lower()`, keeping tokens with length `> 1`
that are not in `STOPWORDS`.

### `term_counts(tokens: Iterable[str]) -> dict[str, int]`

**READ (pure).** Occurrence count per token.

### `idf(doc_freq: int, total_docs: int) -> float`

**READ (pure).** Smoothed inverse document frequency,
`log(1 + (total_docs − doc_freq + 0.5) / (doc_freq + 0.5))`, always
positive; returns `0.0` when `total_docs <= 0`.

### `sparse_tfidf(counts: dict[str, int], df: dict[str, int], total_docs: int) -> dict[str, float]`

**READ (pure).** TF-IDF sparse vector for one document/query:
`{term: (count / total_count) * idf(df.get(term, 0), total_docs)}`.
Empty counts → `{}`.

### `cosine(a: dict[str, float], b: dict[str, float]) -> float`

**READ (pure).** Cosine similarity of two sparse vectors; `0.0`
when either is empty or the dot product is not positive; the result
is capped at `1.0`.

### `dense_cosine(a: Sequence[float], b: Sequence[float]) -> float`

**READ (pure).** Cosine similarity of two dense vectors (zipped to
the shorter); `0.0` for empty or zero-norm inputs; result clamped
to `[0, 1]`.

### `Embedder` — protocol

```python
class Embedder(Protocol):
    name: str
    dim: int
    def embed(self, text: str) -> list[float]: ...
```

Any object with `name`, `dim`, and `embed(text)` satisfies it.

### `HashingEmbedder(dim: int = 384)`

**READ (pure) per call.** Deterministic feature-hashing embedder
(stdlib only). Attributes: `name = "hashing"`, `dim`.

`embed(text: str) -> list[float]`: each token (via `tokenize`) is
SHA-256-hashed to a bucket (`first 4 digest bytes, little-endian,
mod dim`) and a sign (`digest[4]` even → `+1`, odd → `−1`); counts
accumulate signed; the result is L2-normalized (a tokenless text
yields the zero vector). Same text always gives the same vector, on
any machine.

### `SentenceTransformerEmbedder(model: str = "all-MiniLM-L6-v2")`

Neural embedder behind the `embeddings` extra. Attributes:
`name = "sentence-transformers"`, `dim` (read from the loaded
model). Construction raises `HuginnConfigurationError` when
`sentence-transformers` is not installed, with the install hint in
the message.

`embed(text: str) -> list[float]`: the model's encoding of the one
text, with normalized embeddings, as plain floats.

---

# Part 3 — Idempotency matrix (RM-013)

What happens when a call is repeated with identical arguments —
the retry question every caller eventually faces. One row per
public API entry point, each row proven by exactly one test in
`tests/test_idempotency.py` of the owning package (test names
carry the row id). Scope: the exported surface of both packages —
`HebbianMemory` / `Muninn` and `HuginnMemory`, the module
functions, and the documented `LocalBackend.heal` seam. Huginn
rows are proven on the local backend; the Qdrant backend mirrors
the upsert identity and pure reads by construction, but a live
Qdrant round-trip is **NOT PROVEN**, so no Qdrant row is claimed
proven here.

The three classes:

- **I — Idempotent.** An identical repeat leaves the logical
  store state unchanged and returns an equal result. Pure reads
  are I trivially (and their tests also prove the store did not
  move). Two honest exceptions to "equal result": a removal row
  returns its *already-done* signal on the repeat (`True` →
  `False`) while the state stays put, and a write row stamped
  with RM-012's monotonic `_tick` may carry a newer `updated_at`
  — the row says so where it applies; every other field is equal.
- **R — Safely re-runnable.** A repeat never errors, duplicates
  a record, or corrupts anything, but it applies its defined
  effect again. Safe to schedule, unsafe to mistake for I.
- **N — Intentionally not.** Every call is a new *event* by
  design — an activation, a strengthening, a flight. A caller
  who is unsure whether a call landed must **not** blind-retry
  an N row: the retry is a second event, and the counts will
  faithfully say so.

## 3.1 Muninn — `HebbianMemory` (the `Muninn` facade inherits every row)

| Row | API | Class | What a repeat does |
|---|---|---|---|
| M-01 | construction / reopen | R | Reopening a closed store returns the same logical state, `recovered_from_backup == False` on a healthy store. Construction is also safe concurrently: several objects may open the same store at once, in one process or across processes (RM-037, `docs/CONCURRENT_OPENERS.md`). |
| M-02 | `close()` | I | Second and later closes are no-ops. |
| M-03 | `backup()` | R | Re-takes the rolling backup (generations rotate, bounded by `backup_keep`); the store itself never changes; returns the newest generation's path both times. |
| M-04 | `activate(id)` | **N** | Logs a **second** activation: the returned total and `activation_count` advance by one per call. This is the operation itself — never blind-retry. |
| M-05 | `activate_batch(ids)` | **N** | Logs every id again and strengthens every pair again (`connections_created` drops to 0, the strengthening and the counts are real). |
| M-06 | `associate(a, b, …)` | **N** | A co-activation event: `co_activation_count` advances on every call. With explicit `strength=` the strength value is pinned but the count still advances; with `delta=` / default the strength itself climbs toward 1.0. |
| M-07 | `get_associations(id)` | I | Pure read; equal result, store unmoved. |
| M-08 | `activation_count(id)` | I | Pure read. |
| M-09 | `spread_activation(ids)` | I | Pure read. |
| M-10 | `remember(content, …)` | I | Same content + category + path returns the **same id**, no duplicate node. A retry carrying different fields still returns that id and the **first write wins** (the differing fields are ignored) — update deliberately via `update()` instead. |
| M-11 | `store(content, …)` | I | Alias of `remember` (category = `memory_type`); same row. |
| M-12 | `get_node(id)` | I | Pure read. |
| M-13 | `retrieve(…, touch=False)` | I | Pure read — the default reinforces nothing. |
| M-14 | `retrieve(…, touch=True)` | **N** | The one explicitly named reinforcing read: every touch logs an activation per returned node, per call. |
| M-15 | `get_by_path(path)` | I | Pure read. |
| M-16 | `get_children(path)` | I | Pure read. |
| M-17 | `update(id, …)` | I* | Same field values land identically; returns `True` both times (`False` both times for a missing id). *Only `updated_at` may advance, via the monotonic `_tick`.* |
| M-18 | `forget(id)` | I | First call removes node + wiring (`True`); the repeat returns `False` and the state does not move (the tombstone is re-stamped, nothing else). |
| M-19 | `delete(id)` | I | Alias of `forget`; same row. |
| M-20 | `move(id, path)` | I* | `update(id, path=…)`; same row as M-17. |
| M-21 | `get_tree_structure()` | I | Pure read. |
| M-22 | `heal_structure()` | I | A repeat on a healed store reports the same zero fixes; connections unchanged. |
| M-23 | `decay(days)` | R | Safe to run on any schedule — and cumulative by definition: `decay(d)` twice composes to `decay(2d)` (strengths equal to float precision; row proven against a single `decay(2)`). Never mistake a re-run for a no-op. |
| M-24 | `consolidate(threshold)` | I | The repeat marks nothing new: `newly_consolidated == 0`, totals unchanged. |
| M-25 | `health()` | I | Pure read. |
| M-26 | `stats()` / `get_stats()` | I | Pure reads; the alias returns exactly `stats()`. |
| M-27 | `dump(limit)` | I | Pure read. |
| M-28 | `MemoryNode.to_dict()` / `from_dict()` | I | Pure functions; the round trip is a fixed point (`from_dict(to_dict(n)) == n`, repeatably). |
| M-29 | `decay_wall_clock()` | R | The RM-021 opt-in mode: the first call only arms the meta-table marker (0 days); a repeat at the same clock reading decays exactly 0 further days, and repeats compose exactly like M-23 across elapsed time. A blind retry is safe — it can never double-decay the same span, because the marker advances with each run and never moves backward. |

## 3.2 Huginn — `HuginnMemory` and module functions (local backend)

| Row | API | Class | What a repeat does |
|---|---|---|---|
| H-01 | construction / reopen | R | Construction is lazy (no file until first use); reopening returns the same documents, `recovered_from_backup == False` on a healthy store. First use is also safe concurrently: several objects may open the same local store at once, in one process or across processes (RM-037, `docs/CONCURRENT_OPENERS.md`). |
| H-02 | `close()` | I | Second and later closes are no-ops — including closing before the lazy backend was ever built. |
| H-03 | `upsert_memory(content, …)` (no id) | I | Same content + category returns the **same id**, one document. Upsert means *replace*: a repeat carrying new fields updates that same document in place (contrast Muninn M-10, where the first write wins). |
| H-04 | `upsert_memory(…, memory_id=k)` | I | The explicit-id form lands on `k` every time; replacing the content under `k` twice leaves exactly the second content, once. |
| H-05 | `search(query)` | I | Pure read; a blank query returns `[]`, repeatably. |
| H-06 | `get(id)` | I | Pure read. |
| H-07 | `delete(id)` | I | First call removes (`True`); the repeat returns `False`, state unmoved. |
| H-08 | `health()` | I | Pure read at the logical level (the first call on a fresh object may build the lazy backend — after that, repeats are equal and move nothing). |
| H-09 | `stats()` | I | Exactly `health()`, repeatably. |
| H-10 | `analyze_query(q)` (method + module function) | I | Pure function of the query text; never touches the store. |
| H-11 | `semantic_search(q, docs)` (module) | I | Pure function of its arguments. |
| H-12 | `fly(query)` | **N** | Store-pure — the documents never move, and the flight's results repeat exactly (retrieval time excluded) — but every flight **appends one record to the in-memory flight history** (`get_flight_stats` counts it). A flight is an event, not a query. |
| H-13 | `multi_hop_retrieve(query)` | **N** | One `fly` per hop, so one history record per hop per call; results repeat, history accumulates. |
| H-14 | `get_flight_stats()` | I | Pure read — reading the stats appends no flight. |
| H-15 | `LocalBackend.heal()` | I | A repeat on a healed backend reports the same all-zero report; the document count is unchanged. |

Retry guidance, in one line per class: **I** — retry freely;
**R** — retry knowing the effect applies again; **N** — never
blind-retry, reconcile first (e.g. read `activation_count`, or
accept that the event happened twice).

---

*End of the API reference. For why the stores underneath behave the
way they do, see `docs/RELIABILITY.md`. For putting the packages to
work inside another project, see `docs/INTEGRATION.md`.*
