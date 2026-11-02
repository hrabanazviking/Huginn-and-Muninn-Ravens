# Muninn — User Guide

Muninn is Hebbian associative memory in one SQLite file. You store
memory nodes, you activate them as they are used, and memories that are
used together wire themselves together. Strong wiring can be marked
consolidated, unused wiring fades with decay, and the store heals its
own structure.

- Package: `muninn`, version 1.0.0, MIT licence
- Python: >= 3.11
- Dependencies: none — the core is Python standard library only
- Store: one SQLite file, WAL mode, `synchronous=FULL`

This guide describes the code as it is. Every signature below is copied
from `muninn/src/muninn/core.py` and `muninn/src/muninn/config.py`.

## Install

```bash
pip install ./muninn          # or: pip install -e ./muninn
```

Importing the package constructs nothing and opens no file. A store
opens only when you create a `HebbianMemory` (or `Muninn`) object, and
that object opens only its own file.

```python
from muninn import HebbianMemory, MemoryNode, Muninn
from muninn.config import MuninnConfig
```

## Concepts

### Memory nodes

A node is one stored memory. The `MemoryNode` dataclass has:

| Field | Type | Meaning |
|---|---|---|
| `id` | `int` | Integer id, assigned by the store (autoincrement) |
| `content` | `str` or any JSON-serializable value | The memory itself. Strings are stored as text; other JSON-serializable values are stored as JSON and returned decoded |
| `path` | `str`, default `""` | Hierarchical path, for example `"people/family"` — used by `get_by_path`, `get_children`, `get_tree_structure`, and `move`. Paths are normalised on write and on read (RM-028): empty/`.` segments and trailing slashes collapse, `..` climbs and clamps at the root, only `/` separates, and the normalised path is capped at 64 segments / 2048 UTF-8 bytes — see `docs/PATHOLOGICAL_PATHS.md` |
| `memory_type` | `str`, default `"fact"` on the dataclass | The node's type. In the database this column is called `category`. `MemoryNode.category` is a read-only property alias for `memory_type` |
| `importance` | `int`, 1–10, default `5` | How much this memory matters. Used for result ordering and for backpressure pruning |
| `emotional_valence` | `float`, −1.0 to 1.0, default `0.0` | Emotional charge of the memory |
| `tags` | `list[str]`, default `[]` | Tags. On write they are stringified, stripped, lowercased, and truncated to 64 characters each; empty tags are dropped |
| `metadata` | `dict`, default `{}` | Free-form JSON-serializable metadata |
| `access_count` | `int`, default `0` | How many times this node has been activated (including via `retrieve(..., touch=True)`) |
| `created_at`, `updated_at` | `datetime` | UTC timestamps |

`MemoryNode.to_dict()` returns all of the above as a plain dict, with
both `memory_type` and `category` keys (same value) and ISO-format
timestamps. `MemoryNode.from_dict(data)` rebuilds a node from such a
dict; it accepts either `memory_type` or `category`.

Identity and idempotency: the store has a unique index on
`(content_hash, category, path)`. Storing the same content under the
same category and path returns the existing node's id instead of
creating a duplicate. That makes `remember` / `store` safe to retry.

### Activation logging

Activation is the record that a memory was used.

`activate(memory_id)` and `activate_batch(...)` do three things per id:

1. Append one row to the `activation_log` table
   (`memory_id`, `activated_at`, `emotional_valence`, `source`).
2. Increment that id's counter in `node_activation`
   (`total_activations`) and restore its confidence toward 1.0 with
   `confidence ← confidence + learning_rate * (1.0 − confidence)`,
   capped at 1.0.
3. If a node with that id lives in this store, increment the node's
   `access_count` and update its `updated_at`.

Notes that matter:

- Activation works for ids that have no node in this store. Cross-store
  ids (for example Mímir row ids in a Bifröst deployment) are legal:
  the log and counter are kept, and no node row is required.
- `activate` is an event and is intentionally **not** idempotent.
  Calling it twice logs two activations.
- `activation_count(memory_id)` counts rows in the log. It is a pure
  read.

### Hebbian co-activation wiring

When memories are activated together, they wire together.
`activate_batch(ids)` activates each unique id once and then
strengthens every unordered pair in both directions.

Connections are stored in `hebbian_connections` as directed rows in
**both** directions — an `a→b` row and a `b→a` row — and the API keeps
the two directions symmetric (same strength, same co-activation count),
because some readers query them directionally.

Each strengthening applies the bounded rule:

```text
strength ← 1 − (1 − strength)(1 − learning_rate)
```

- Strengths always stay in [0, 1].
- A first wiring starts at exactly `learning_rate` (default 0.1).
- With the default rate, repeated co-activation approaches 1.0 without
  ever reaching past it: after *n* co-activations of a pair that
  started unwired, strength is `1 − (1 − learning_rate) ** n`.
- Each strengthening also increments `co_activation_count` and records
  `last_coactivated_at`.

`associate(a, b)` wires a pair manually — see the walk-through below.

### Spread activation

`spread_activation(seed_ids, ...)` walks the wiring outward from seed
memories. Seeds start at activation 1.0. Each hop multiplies by the
edge strength and by `attenuation` (default 0.5). It returns
`{memory_id: activation}`, strongest first, seeds included. It is a
pure read — spreading does not log activations and does not change any
strength.

### Decay — two half-lives

`decay(days)` fades state multiplicatively:

```text
factor = 0.5 ** (days / half_life)
```

There are **two separate half-lives**, both configurable:

- Edge strengths use `decay_half_life_days` (default 30.0 days).
- Node confidences (in `node_activation`) use
  `confidence_half_life_days` (default 90.0 days).

After fading, `decay` also:

- Unmarks `consolidated` on edges now below the consolidation
  threshold.
- Deletes edges whose strength fell below `prune_threshold`
  (default 0.01) and counts them in the returned dict.

Decay is deterministic and safe to re-run. `decay(days=0)` fades
nothing (factor 1.0) but still applies the prune/unmark steps.

Since RM-064, `decay` and `consolidate` run in committed
chunks of `maintenance_chunk_size` rows (default 1000):
the atomicity is per chunk — an interrupted run leaves
the store at a chunk boundary, stated in the reports as
`atomicity` / `chunks` / `chunk_size` — and an optional
`progress` callable is called after each committed chunk
with an event dict (`operation`, `phase`, `chunk`,
`processed`, `total`). The final state is exactly the
old full-store result at any chunk size; see
`docs/MAINTENANCE_SCALE.md`.

### Consolidation

`consolidate()` is the "sleep" pass:

- Edges at or above the threshold (default: the config's
  `consolidation_threshold`, 0.8) are marked `consolidated = 1`.
- Edges below the threshold are unmarked.
- The self-healing pass (below) runs as part of consolidation.
- Node content is **never** rewritten by consolidation.

### Self-healing structure

On open, and whenever you call `heal_structure()` or `consolidate()`,
Muninn repairs structural drift and returns a report counting every
fix:

- `self_edges_pruned` — connections from a memory to itself are
  deleted.
- `dangling_edges_pruned` — connections touching a tombstoned id (see
  below) are deleted.
- `pairs_repaired` — a missing reverse directed row is inserted; if
  the two directions of a pair disagree, both are reconciled to the
  stronger strength and the larger co-activation count (consolidated
  flag reconciled to the minimum, the conservative value).
- `counters_fixed` — `node_activation` totals are reconciled against
  the `activation_log`: missing counter rows are inserted and wrong
  totals are corrected.
- `fixes` — the sum of the four counts above.

Edges to ids that were never registered as nodes are **not** pruned —
only edges to explicitly forgotten (tombstoned) ids are. That is by
design, so cross-store ids stay legal.

The report from the open-time heal is kept on the object as
`mem.last_heal_report`.

### Tombstones

`forget(memory_id)` / `delete(node_id)`:

- Deletes the node row and all of its wiring (both directions).
- Writes a tombstone row in `deleted_nodes` — even if nothing existed
  to delete — as the standing record that this id was deliberately
  forgotten. The heal pass uses tombstones to prune any later stray
  edge that references the id.
- Returns `True` when anything (node or wiring) was actually removed,
  otherwise `False`.
- The activation **log is kept** — it is a log.
- A later `activate(...)` or `associate(...)` involving that id clears
  its tombstone: the caller's world says the id lives again.
- This removes the live rows only: the content can persist in WAL
  frames, in freed pages of the store file, and in every rolling
  backup generation until rotation (threat TH-11). When the content
  itself must leave the disk, use `secure_forget(...)` below.

### Backpressure: `max_nodes`

Storing a **new** node when the store already holds `max_nodes` nodes
(default 20000) triggers backpressure: the lowest-value nodes are
pruned until the count is back at the cap. "Lowest-value" means ordered
by importance ascending, then `access_count` ascending, then
`updated_at` ascending (oldest first). Pruned nodes lose their wiring
and are tombstoned, exactly as if forgotten. A warning is logged.
Re-storing existing content (the idempotent path) does not trigger
backpressure, because no new node is created.

### Read / write honesty

Every read method is a pure read — it never mutates the store:
`get_node`, `retrieve` (by default), `get_by_path`, `get_children`,
`get_tree_structure`, `get_associations`, `spread_activation`,
`activation_count`, `health`, `stats`, `get_stats`, `dump`.

The write methods are named as writes: `remember`, `remember_many`,
`store`, `update`, `move`, `forget`, `delete`, `activate`,
`activate_batch`, `associate`, `decay`, `consolidate`,
`heal_structure`, `backup`.

There is exactly **one** reinforcing read, and it is explicit and
opt-in: `retrieve(..., touch=True)`. With `touch=True`, each returned
node is also activated (logged with source `"retrieve:touch"`, using
the node's own emotional valence). The default `touch=False` never
reinforces.

## Usage walk-through

All examples below use a temporary file so you can run them as-is.
In real use, pass your real path — or omit the config to use the
default path `~/.hermes/memory/muninn_hebbian.db`.

### Create a store

```python
import tempfile
from pathlib import Path

from muninn import HebbianMemory
from muninn.config import MuninnConfig

tmp = Path(tempfile.mkdtemp())
mem = HebbianMemory(MuninnConfig(db_path=str(tmp / "muninn.db")))
```

`HebbianMemory` also accepts keyword overrides instead of a config
object, and both forms can be combined (overrides replace fields on a
given config):

```python
mem2 = HebbianMemory(db_path=str(tmp / "other.db"), learning_rate=0.2)
mem2.close()
```

The object is a context manager; `close()` is idempotent:

```python
with HebbianMemory(MuninnConfig(db_path=str(tmp / "ctx.db"))) as m:
    m.remember("stored inside a with block")
# m is closed here; closing again is a no-op
```

### Store memories: `remember` and `store`

```python
raven_id = mem.remember(
    "Ravens fly out at dawn and return at dusk",
    category="lore",
    path="animals/ravens",
    importance=7,
    tags=["Ravens", " dawn "],
    emotional_valence=0.3,
    metadata={"source": "field notes"},
)
print(raven_id)  # an int, e.g. 1
```

Signature (from the code):

```python
remember(content, *, category="general", path="", importance=5,
         tags=None, emotional_valence=0.0, metadata=None) -> int
```

- `content` may be a string or any JSON-serializable value.
- Storing the same content with the same `category` and `path` again
  returns the same id — no duplicate is created:

```python
again = mem.remember(
    "Ravens fly out at dawn and return at dusk",
    category="lore",
    path="animals/ravens",
)
assert again == raven_id
```

`store(...)` is the ancestor-shaped alias — same behaviour, with
`memory_type` instead of `category`, and `path` as a positional
argument:

```python
store(content, path="", memory_type="fact", importance=5,
      tags=None, metadata=None, *, emotional_valence=0.0) -> int

oak_id = mem.store(
    "The old oak marks the boundary",
    path="places",
    memory_type="fact",
    importance=5,
)
```

### Store many at once: `remember_many`

```python
remember_many(items) -> list[int]
```

The batch form of `remember` (RM-060): `items` is a list of
dicts, each carrying `remember`'s arguments by name —
`content` (required) plus any of `category`, `path`,
`importance`, `tags`, `emotional_valence`, `metadata`. The
ids come back in input order.

```python
ids = mem.remember_many([
    {"content": "First of the batch", "category": "lore"},
    {"content": "Second of the batch", "importance": 8},
])
```

The contract differs from calling `remember` in a loop in
four stated ways: every item is validated and hashed once,
*before* anything is written; all inserts land in **one
transaction** — a bad item (or a hash collision) anywhere
rolls the whole batch back, where a loop's earlier calls
would stay stored; the whole batch carries one timestamp;
and backpressure runs **once**, after the commit. Per item,
idempotency is `remember`'s own: content that already lives
under its category+path returns that node's id, and a
duplicate inside the batch shares its first occurrence's
id. The 10k-node ingest record against the loop is in
`docs/BULK_REMEMBER.md`.

### Read one node: `get_node`

Pure read. Returns a `MemoryNode` or `None`.

```python
node = mem.get_node(raven_id)
print(node.content)           # "Ravens fly out at dawn and return at dusk"
print(node.category)          # "lore"  (alias for node.memory_type)
print(node.tags)              # ["ravens", "dawn"]  (normalised on write)
print(node.access_count)      # 0 — nothing has activated it yet
print(mem.get_node(999999))   # None
```

With `cache_size` set above 0, `get_node` serves repeats
from this object's bounded warm cache (RM-063): hits are
copies, own writes invalidate, and the hit rate is visible
in `mem.cache_stats`. The cache is per-object only — see
`docs/WARM_CACHES.md` for the staleness window that buys
the speed.

### Retrieve: `retrieve`, `touch=False` by default

```python
retrieve(query=None, path=None, tags=None, memory_type=None,
         top_k=5, *, category=None, touch=False) -> list[MemoryNode]
```

- `query` is a case-insensitive substring match over content.
- `path` matches that exact path and everything under it.
- `tags` keeps nodes that have at least one of the given tags
  (compared lowercased against the stored, normalised tags).
- `memory_type` and `category` are the same filter; if both are
  given, `category` wins (`category or memory_type` in the code).
- Results sort by importance descending, then `updated_at` descending,
  and are cut to `top_k` (clamped to 1..1000, the class constant
  `HebbianMemory.MAX_QUERY_RESULTS`).

```python
hits = mem.retrieve(query="ravens")
print([n.id for n in hits])   # [raven_id]
print(mem.get_node(raven_id).access_count)  # still 0 — pure read
```

`touch=True` is the only reinforcing read:

```python
hits = mem.retrieve(query="ravens", touch=True)
print(mem.get_node(raven_id).access_count)  # 1
print(mem.activation_count(raven_id))       # 1
```

### Browse by path: `get_by_path`, `get_children`, `get_tree_structure`

```python
by_path = mem.get_by_path("animals/ravens")   # nodes at exactly this path
print([n.id for n in by_path])                # [raven_id]

mem.remember("Wolves hunt in packs", category="lore",
             path="animals/wolves", importance=6)
children = mem.get_children("animals")
# {"animals/ravens": [MemoryNode(...)], "animals/wolves": [MemoryNode(...)]}
print(sorted(children))

tree = mem.get_tree_structure()
# {"animals": {"ravens": {"_nodes": 1}, "wolves": {"_nodes": 1}},
#  "places": {"_nodes": 1}}
print(tree)
```

All three are pure reads. `get_children` groups nodes by every path
strictly under the parent path (`get_children("")` returns every
pathed node, grouped by path). Path arguments are normalised the
same way as on writes (RM-028), so `get_by_path("/animals/ravens/")`
finds the node stored at `animals/ravens`, and `%`/`_` inside a
segment are literal characters, never wildcards. `get_tree_structure` returns a nested
dict following the `/`-separated path parts, with a `"_nodes"` count
at each path that holds nodes.

### Update and move: `update`, `move`

```python
update(node_id, content=None, **fields) -> bool
```

Allowed fields: `importance`, `emotional_valence`, `tags`, `metadata`,
`path`, `memory_type`, `category`. Any other field name raises
`MuninnValidationError`. Returns `False` when no such node exists,
`True` on success (including a no-field update of an existing node).

```python
print(mem.update(raven_id, importance=9, tags=["ravens", "omens"]))  # True
print(mem.update(999999, importance=3))                              # False

relocated = mem.remember("A ford crosses the river", path="places")
print(mem.move(relocated, "places/water"))   # True — move() is update(path=...)
print([n.id for n in mem.get_by_path("places/water")])  # [relocated]
```

Updating content (or path/category) so that the node would duplicate
another node's `(content, category, path)` raises
`MuninnValidationError` and leaves the store unchanged.

### Forget: `forget` / `delete`

```python
print(mem.forget(relocated))   # True — node and wiring removed, id tombstoned
print(mem.get_node(relocated)) # None
print(mem.forget(relocated))   # False — nothing left to remove
```

`delete(node_id)` is the ancestor-shaped alias of `forget`.

### Secure forget: `secure_forget`

```python
print(mem.secure_forget(relocated))  # True — removed AND purged from disk
```

`secure_forget(memory_id)` does everything `forget` does — same
validation, same tombstone, same return value — and then purges the
forgotten content from every file the store keeps (RM-051, threat
TH-11; the full record is `docs/SECURE_FORGET.md`): the delete runs
under `PRAGMA secure_delete=ON`, the WAL is checkpoint-truncated,
the store file is rewritten with `VACUUM`, and every rolling backup
generation is discarded and replaced by one fresh snapshot of the
purged store. The purge runs even when nothing live was removed, so
it also remediates a past plain `forget`.

The cost is stated, not hidden: a full rewrite of the store file
(time and temporary space on the order of the store's size) and the
loss of all older backup generations. Close other openers of the
store first — a reader holding an old snapshot can keep WAL frames
alive and make the rewrite fail with a typed locked-store error
(the row deletion has already committed; re-run `secure_forget` to
re-run the purge).

### Activate: `activate`, `activate_batch`, `activation_count`

```python
activate(memory_id, *, emotional_valence=0.0, source="api") -> int
```

Returns the id's new total activation count.

```python
a = mem.remember("Iron rusts in salt air", category="fact")
b = mem.remember("Ships are tarred before winter", category="fact")

print(mem.activate(a))        # 1
print(mem.activate(a))        # 2 — activate is not idempotent
print(mem.activation_count(a))  # 2 (pure read)
```

`activate_batch` activates a co-active set **and** wires every pair —
this is the Hebbian operation:

```python
activate_batch(memory_ids, *, emotional_valence=0.0,
               source="api") -> dict

result = mem.activate_batch([a, b])
# {"activated": 2, "pairs_wired": 1,
#  "connections_created": 1, "connections_strengthened": 0}
```

Duplicate ids in the input are de-duplicated (each unique id is
activated once). The whole batch is one transaction: either the whole
batch lands or none of it does. Calling it again strengthens the same
pair instead of creating a new one (`connections_created` drops to 0,
`connections_strengthened` rises).

Huge batches scale (RM-035, `docs/HUGE_BATCH_ATOMICITY.md`): at 64
or more unique ids the batch is generated inside SQLite in the same
one transaction — the counts stay exact (a 10k-id batch wires
49,995,000 pairs, proven row-for-row by
`muninn/scripts/huge_batch_bench.py`) and Python-side memory stays
bounded by the id list, never by the pair count. What a huge batch
costs is what it must: ~105 bytes of store per directed row, so a
first-time 10k batch grows the database by roughly 10 GB.

### Wire manually: `associate`, `get_associations`

```python
associate(memory_a, memory_b, *, strength=None, delta=None) -> float
```

- With `strength=`: set both directed rows to exactly that strength
  (must be in [0, 1]); co-activation count still increments.
- With `delta=`: apply the bounded Hebbian update using `delta` as
  this call's learning rate (must be in (0, 1]).
- With neither: apply the bounded update with the config's
  `learning_rate`.
- Passing both `strength` and `delta` raises `MuninnValidationError`,
  as does associating a memory with itself.
- Returns the pair's new strength (`a→b` row).

```python
c = mem.remember("Tar keeps water out of seams", category="fact")
print(mem.associate(b, c))                    # 0.1 with the default rate
print(mem.associate(b, c))                    # 0.19 = 1 - (1-0.1)(1-0.1)
print(mem.associate(b, c, strength=0.75))     # 0.75
```

```python
get_associations(memory_id, min_strength=0.0, limit=100) -> list[dict]
```

Pure read, strongest first. Each dict has `memory_id` (the other end),
`strength`, `co_activation_count`, `consolidated` (bool), and
`last_coactivated_at`:

```python
assocs = mem.get_associations(b)
# [{"memory_id": c, "strength": 0.75, "co_activation_count": 3,
#   "consolidated": False, "last_coactivated_at": "..."}]
strong_only = mem.get_associations(b, min_strength=0.5)
```

### Spread activation

```python
spread_activation(seed_ids, *, depth=2, attenuation=0.5,
                  min_strength=0.0, limit=1000) -> dict[int, float]
```

Pure read. `depth` is clamped to 0..10; `attenuation` must be in
(0, 1].

```python
spread = mem.spread_activation([b], depth=1)
# b itself at 1.0, plus each neighbour at strength * 0.5, e.g.
# {b: 1.0, c: 0.375, a: ...}
print(spread[b])  # 1.0
```

### Decay

```python
decay(days=1.0) -> dict
```

```python
report = mem.decay(days=30.0)
# {"days": 30.0,
#  "edge_factor": 0.5,          # 0.5 ** (30 / 30) with default half-lives
#  "confidence_factor": 0.7937...,  # 0.5 ** (30 / 90)
#  "edges_decayed": <rows faded>,
#  "edges_pruned": <rows deleted for falling below prune_threshold>,
#  "confidences_decayed": <node_activation rows faded>}
```

`days` must be a number >= 0. If `auto_backup` is on (the default), a
rolling backup is taken before the maintenance writes.

### Consolidate and heal

```python
consolidate(threshold=None) -> dict
heal_structure() -> dict
```

```python
report = mem.consolidate()
# {"threshold": 0.8,
#  "newly_consolidated": <edges newly marked>,
#  "unmarked": <edges unmarked for falling below threshold>,
#  "total_consolidated": <all consolidated directed rows>,
#  "heal": {"self_edges_pruned": 0, "dangling_edges_pruned": 0,
#           "pairs_repaired": 0, "counters_fixed": 0, "fixes": 0}}

heal = mem.heal_structure()   # just the heal report, on demand
print(heal["fixes"])
```

`threshold`, when given, must be in (0, 1]. Note the counts are over
directed rows, so one symmetric pair contributes 2 rows.

### Health, stats, dump

All pure reads.

```python
health = mem.health()
# {"status": "healthy",            # "degraded" if integrity != "ok"
#  "db_path": "...",
#  "integrity": "ok",              # from PRAGMA quick_check
#  "recovered_from_backup": False,
#  "nodes": ..., "connections": ..., "activations": ...,
#  "schema_version": "1",
#  "file_permissions_warning": None}  # RM-042: a warning string when an
#                                     # existing store file is looser than
#                                     # owner-only 0600 (see FILE_PERMISSIONS.md)

stats = mem.stats()
# {"total_nodes": ..., "total_connections": ...,
#  "total_activations": ..., "consolidated_connections": ...,
#  "strongest_connection": ...,   # 0.0 when there are no connections
#  "categories": {"lore": 2, "fact": 3, ...},
#  "db_path": "..."}
```

`get_stats()` is the ancestor-shaped alias of `stats()`.

```python
dumped = mem.dump(limit=50)   # limit clamped to 1..500
# {"stats": {...}, "nodes": [node.to_dict(), ...]}
# nodes are the highest-importance ones, newest-updated first
```

### Backup

```python
path = mem.backup()   # -> str path of the newest backup, or None
```

`backup()` commits and takes a rolling backup now, returning its path
— or `None` when `backup_keep` is 0. Backups live beside the store as
`<db file>.bak-1`, `.bak-2`, … up to `backup_keep` generations, and are
made through SQLite's backup API from a verified-healthy store.

### The `Muninn` ancestor facade

`Muninn` is a subclass of `HebbianMemory` with the ancestor's
constructor shape: a data directory (or a `.db` file) instead of a
config.

```python
from muninn import Muninn

# A directory: the store is <dir>/muninn_hebbian.db
legacy = Muninn(data_path=str(tmp / "legacy-data"))
legacy.store("Kept the ancestor's way", path="notes", memory_type="fact")
print(legacy.get_tree_structure())
legacy.close()

# A .db file path is used as the store file itself:
direct = Muninn(data_path=str(tmp / "direct.db"))
direct.close()

# No argument: the default MuninnConfig path is used.
# Keyword overrides work too, e.g. Muninn(data_path=..., learning_rate=0.2)
```

All `HebbianMemory` methods are inherited unchanged.

### Closing

```python
mem.close()
mem.close()   # no-op the second time
```

Using a closed object raises `MuninnStorageError`
("HebbianMemory is closed") on the next operation that touches the
store.

## Configuration — every `MuninnConfig` field

From `muninn/src/muninn/config.py`. All fields are validated in
`__post_init__` at construction; a bad value raises
`MuninnConfigurationError` immediately, never mid-write.

```python
from muninn.config import MuninnConfig
config = MuninnConfig(db_path="~/.hermes/memory/muninn_hebbian.db")
```

| Field | Type | Default | Meaning | Validation |
|---|---|---|---|---|
| `db_path` | `str` | `"~/.hermes/memory/muninn_hebbian.db"` (`DEFAULT_DB_PATH`) | SQLite store file. `~` is expanded (`resolved_path()`); the parent directory is created on open | Must be a non-empty string (after the `isinstance` check, `.strip()` must be non-empty) |
| `learning_rate` | `float` | `0.1` | Hebbian bounded-learning rate. On each co-activation, `strength ← 1 − (1 − strength)(1 − rate)`; a first wiring starts at exactly this value. Also the rate at which activation restores confidence | Must be in (0, 1] |
| `decay_half_life_days` | `float` | `30.0` | Edge-strength half-life for `decay()`: strengths multiply by `0.5 ** (days / decay_half_life_days)` | Must be > 0 |
| `confidence_half_life_days` | `float` | `90.0` | Node-confidence half-life for `decay()`: confidences multiply by `0.5 ** (days / confidence_half_life_days)` | Must be > 0 |
| `prune_threshold` | `float` | `0.01` | Edges whose decayed strength falls below this are deleted by `decay()` | Must be in [0, 1) |
| `consolidation_threshold` | `float` | `0.8` | Edges at or above this strength are marked consolidated by `consolidate()` (and edges that decay below it are unmarked by `decay()`) | Must be in (0, 1] |
| `busy_timeout_ms` | `int` | `5000` | SQLite busy timeout — how long a locked store is awaited before an error is raised | Must be >= 0 |
| `backup_keep` | `int` | `3` | Rolling backup generations kept beside the store (`<db>.bak-1` … `.bak-N`). `0` disables backups — and therefore disables corruption recovery | Must be >= 0 |
| `auto_backup` | `bool` | `True` | Take/refresh a rolling backup on open (only when the store changed since the last backup) and before `decay()` / `consolidate()` maintenance | No range check — used as a boolean flag |
| `max_nodes` | `int` | `20000` | Backpressure ceiling: storing a new node beyond it prunes the lowest-value nodes (see Concepts) | Must be >= 1 |
| `max_content_bytes` | `int` | `1048576` | Oversize ceiling (RM-027): one node's stored content, in UTF-8 bytes of the stored text; above it the write is refused with a typed error before anything is stored (see `docs/OVERSIZE_POLICY.md`) | Must be >= 1 |
| `max_metadata_bytes` | `int` | `65536` | Oversize ceiling (RM-027): one node's metadata, in UTF-8 bytes of its serialized JSON form; same refusal discipline | Must be >= 1 |
| `strict_path_safety` | `bool` | `False` | Path safety (RM-041, threat TH-02): when `True`, opening refuses a symlinked store path (the file or any parent component) and a store whose parent directory is world-writable, with a typed storage error before anything is created — for locked-down deployments. Default `False` keeps the recorded behaviour (paths never symlink-resolved, parents unchecked; see `docs/PATH_SAFETY.md`) | No range check — used as a boolean flag |
| `debug_log_content` | `bool` | `False` | Log redaction (RM-044, threat TH-05): when `True`, `remember`/`retrieve` may emit memory content in log records at DEBUG level only — the sole road by which content ever reaches a log. Default `False`: no log record at any level carries memory content (see `docs/LOG_REDACTION.md`) | No range check — used as a boolean flag |
| `store_encryption` | `bool` | `False` | Store encryption (RM-049, threat TH-09): when `True`, the store's content-bearing values are sealed with application-level envelope encryption (per-store data key wrapped under `encryption_passphrase`) before they reach SQL, and `content_hash` becomes a keyed lookup tag. A marked store is encrypted for its whole life and refuses plain opens. Default `False` — encryption cannot default on, because it needs a passphrase a default cannot invent (see `docs/STORE_ENCRYPTION.md`) | No range check — used as a boolean flag |
| `encryption_passphrase` | `str \| None` | `None` | The passphrase the store's data key is wrapped under (RM-049). Required when `store_encryption` is `True`; excluded from `repr`; never stored, logged, or placed in an error string. There is no recovery: a lost passphrase is a lost store | Must be a string or `None` |
| `integrity_attestation` | `bool` | `False` | Integrity attestation (RM-050, threat TH-10): when `True`, every `activation_log` row extends an HMAC-SHA256 chain keyed by `integrity_passphrase` (never stored), and each open verifies the chain and reports the verdict in `health()`'s `integrity_attestation` field — raw-SQL tampering with the log is detectable on open. A marked store refuses to open without the flag. Default `False` (see `docs/INTEGRITY_ATTESTATION.md`) | No range check — used as a boolean flag |
| `integrity_passphrase` | `str \| None` | `None` | The passphrase the attestation chain key is derived from (RM-050). Required when `integrity_attestation` is `True`; excluded from `repr`; never stored, logged, or placed in an error string | Must be a string or `None` |
| `max_spread_candidates` | `int` | `100000` | Query cost ceiling (RM-053, threat TH-13): the maximum candidate edges (neighbour rows) one `spread_activation` call may examine. When the ceiling bites the expansion stops deterministically (id order) and the call returns what it has; the bite is recorded in `last_spread_activation_stats` (see `docs/QUERY_COST_CAPS.md`) | Must be >= 1 |
| `cache_size` | `int` | `0` | Warm cache (RM-063): the maximum nodes this object's `get_node` cache holds in memory (LRU eviction). `0` disables it — every `get_node` reads the store. Own writes always invalidate; the cache is per-object only, so another object's writes are not seen until eviction or an own write to that id (see `docs/WARM_CACHES.md`). Accounting in `cache_stats` | Must be >= 0 |
| `maintenance_chunk_size` | `int` | `1000` | Chunked maintenance (RM-064): `decay` / `consolidate` commit in chunks of at most this many rows (per-chunk atomicity, stated in their reports; optional `progress` callback per committed chunk — see `docs/MAINTENANCE_SCALE.md`). | Must be >= 1 |

**Secure defaults (RM-055, threat TH-15).** Every default
in this table was re-judged for safety in one recorded
review, `docs/SECURE_DEFAULTS.md`; none changed. The three
judgements to carry into a deployment: backups are on and
keep 3 generations (the copies inherit the store's
permissions); every capability that could leak content,
weaken transport, or attest/encrypt is off until you turn
it on, and the passphrases are never invented for you; and
`strict_path_safety` stays `False` by deliberate,
recorded choice — turn it on for locked-down deployments.

Example — a small, fast-fading store for a test:

```python
config = MuninnConfig(
    db_path=str(tmp / "small.db"),
    learning_rate=0.25,
    decay_half_life_days=7.0,
    confidence_half_life_days=14.0,
    max_nodes=100,
)
```

```python
from muninn import MuninnConfigurationError

try:
    MuninnConfig(learning_rate=0.0)
except MuninnConfigurationError as exc:
    print(exc)  # "learning_rate must be in (0, 1]"
```

## Failure behaviour

Errors are typed. Nothing fakes success.

```python
from muninn import (
    MuninnError,                # base class for all deliberate errors
    MuninnValidationError,      # bad caller argument (also a ValueError)
    MuninnConfigurationError,   # bad config value (also a ValueError)
    MuninnStorageError,         # store could not be opened/read/written/healed
)
```

### Validation before any write

Invalid arguments raise `MuninnValidationError` **before** any write
happens, so a validation failure never leaves a partial mutation
behind. Checked cases include:

- `memory_id` / `node_id` that is not an `int` (bools included), or is
  negative.
- `importance` that is not an `int` in [1, 10].
- `emotional_valence` that is not a number in [−1, 1].
- `content=None` in `remember`, or content that is not
  JSON-serializable; metadata that is not JSON-serializable.
- `activate_batch` with a non-list/tuple argument.
- `associate` with the same id twice, with both `strength` and
  `delta`, with `strength` outside [0, 1], or with `delta` outside
  (0, 1].
- `get_associations` with `min_strength` outside [0, 1].
- `spread_activation` with `attenuation` outside (0, 1].
- `decay` with `days` negative, a bool, or not a number.
- `consolidate` with a threshold outside (0, 1].
- `update` with an unknown field name, or an update that would
  duplicate another node's `(content, category, path)`.

```python
from muninn import MuninnValidationError

try:
    mem.remember("bad importance", importance=99)
except MuninnValidationError as exc:
    print(exc)  # importance must be in [1, 10], got 99
# nothing was stored
```

### Storage errors

Store open/read/write/heal failures raise `MuninnStorageError`. Using
a closed `HebbianMemory` also raises `MuninnStorageError`.

A write that fails in the storage layer — for example against a
full disk — surfaces as `MuninnStorageError` naming the operation
(`muninn write failed during remember: database or disk is full`),
with the failed call rolled back so no partial write survives; the
store stays open and consistent afterwards (RM-029, see
`docs/DISK_FULL.md`).

Error messages are hygienic by rule (RM-054, see
`docs/ERROR_MESSAGE_HYGIENE.md`): a typed error's message is
built only from fixed text, package-computed values, the store
path you yourself supplied, and — where an underlying SQLite
failure is wrapped — that failure's *class name*, never its
text. SQLite can generate its text from the store file itself
(a trigger's message is file content), so the text is never
forwarded; it remains available on the exception chain
(`__cause__`) for callers who want it.

A store whose location is read-only — a read-only filesystem, a
read-only directory, or a store file marked read-only — is
refused *on open* with `MuninnStorageError`
(`muninn store {path} is read-only and cannot be opened for
writing`), immediately, before any connection or backup-restore
attempt, and the failed open touches nothing. There is no
read-only mode: a Muninn store is opened for writing or not at
all (RM-030, see `docs/READONLY_FILESYSTEM.md`).

A store locked by another process is awaited up to
`busy_timeout_ms`; if the lock is still held when the timeout
expires, the open fails with `MuninnStorageError`
(`muninn store {path} is locked by another process (busy timeout
{ms} ms expired)`) and a write on an already-open store fails
with the contention form of the write error (`muninn write
failed during {operation}: store is locked by another process
(busy timeout expired)`), rolled back like any failed write.
Contention is never mistaken for corruption, and pure reads
proceed against a WAL snapshot while a writer holds the lock
(RM-031, see `docs/LOCKED_STORE.md`).

Partial file states are defined too: a main store truncated
to zero bytes takes the corruption road (restore from a
verified backup, else the typed refusal) instead of opening
as a silently empty store; a non-empty write-ahead log left
without its main file restores a verified backup or raises
`muninn store {path} has a write-ahead log but no main file
and no rolling backup verified; refusing to start empty over
lost memory`; and a `.bak-tmp` left behind by a killed backup
is removed on open and is never read as a store or a restore
candidate (RM-032, see `docs/PARTIAL_FILE_STATES.md`).

A path that is not a database file at all is refused before
anything else: a directory at the store path raises
`muninn store {path} is a directory, not a database file;
refusing to open` — with or without a backup beside it, and
the directory is never deleted or replaced to make room for
a restore — and any other non-regular file raises
`muninn store {path} is not a regular file; refusing to
open`. A text file is a corrupt store and takes the
corruption road above (RM-033, see
`docs/NON_DATABASE_FILES.md`).

Text in any script is welcome and is stored verbatim — RTL
scripts, emoji ZWJ sequences, combining marks, astral-plane
characters — with no normalisation: the decomposed and
precomposed spellings of a word are different memories. The
one refused shape is a **lone surrogate** (an unpaired
U+D800–U+DFFF code point, which UTF-8, JSON and SQLite
cannot hold honestly): content, metadata, tags, category,
path and the `retrieve` filters are checked before any
write and refused with `… must not contain lone
surrogates` (RM-034, see `docs/UNICODE_GAUNTLET.md`).

Adversarial annotation shapes are bounded too: JSON-shaped
content, metadata and tag elements may nest at most 100
containers deep — deeper is refused with
`… nesting depth exceeds maximum of 100`, checked
iteratively before any recursive walk, so a value nested
thousands deep is a typed refusal and never a
`RecursionError` — and the cleaned tags list, in its stored
JSON form, must fit `max_metadata_bytes`, the same ceiling
that bounds metadata. Self-referential content/metadata are
still refused as not JSON-serializable, and a
self-referential tag element still renders through `repr`'s
ellipsis (RM-036, see `docs/ADVERSARIAL_TAGS_METADATA.md`).

Durability: the store runs in WAL mode with `synchronous=FULL`, and
batch writes are single transactions. A `kill -9` mid-write loses at
most the uncommitted transaction; committed work survives reopening.

### Corruption recovery from rolling backups

On open, the store is checked with `PRAGMA quick_check` (a file that
is not a database at all takes the same road):

1. If the main store fails the check, Muninn tries the rolling
   backups newest-first (`.bak-1`, `.bak-2`, … up to `backup_keep`).
   Each candidate must itself pass `quick_check`.
2. The first verified backup is restored over the main store (WAL
   sidecars are removed), the recovery is logged at ERROR level, and
   the object reports it: `mem.recovered_from_backup` is `True`, and
   `health()` carries `"recovered_from_backup": True`. The full detail
   is on `mem.open_report` (including `restored_backup`).
3. If **no** backup verifies, opening raises `MuninnStorageError` —
   Muninn **never silently starts empty** over a corrupt store. Data
   loss is always loud.

Rolling backups are refreshed on open when the store changed since
the last backup (with `auto_backup=True`), taken before `decay()` and
`consolidate()`, and taken on demand by `backup()`. A backup is only
rotated into place after the new snapshot itself verifies, so a failed
backup never destroys the previous generations.

Practical consequence: keep `backup_keep >= 1` (default 3) on any
store you care about. With `backup_keep=0` there is nothing to recover
from, and a corrupt store is a loud `MuninnStorageError`, not a fresh
start.

### Threading

One shared connection per object, with every public method serialized
by an internal re-entrant lock. Objects are safe under concurrent use
from multiple threads.

### Concurrent openers

Two or more objects may hold the same store file at once — in one
process or across processes (RM-037, `docs/CONCURRENT_OPENERS.md`).
Committed writes through one object are visible through the others
at once and never lose each other; ordinary reads and writes are
serialized by SQLite (WAL + `busy_timeout_ms`, with the RM-031 typed
contention error on expiry), while the open-time duties and every
backup are serialized per store by a coordination lock (in-process
lock + `flock` on the sibling `<db_path>.open-lock` file). Closing
one object leaves the others working. One limit to know: the RM-012
timestamp guard is per object, so timestamps from *different*
objects may repeat or invert by microseconds.

## Quick reference

| Method | Kind | Returns |
|---|---|---|
| `remember(content, *, category, path, importance, tags, emotional_valence, metadata)` | write | `int` id |
| `store(content, path, memory_type, importance, tags, metadata, *, emotional_valence)` | write | `int` id |
| `get_node(memory_id)` | pure read | `MemoryNode \| None` |
| `retrieve(query, path, tags, memory_type, top_k, *, category, touch=False)` | pure read (`touch=True`: write) | `list[MemoryNode]` |
| `get_by_path(path)` | pure read | `list[MemoryNode]` |
| `get_children(parent_path)` | pure read | `dict[str, list[MemoryNode]]` |
| `get_tree_structure()` | pure read | nested `dict` |
| `update(node_id, content=None, **fields)` | write | `bool` |
| `move(node_id, new_path)` | write | `bool` |
| `forget(memory_id)` / `delete(node_id)` | write | `bool` |
| `secure_forget(memory_id)` | write | `bool` |
| `activate(memory_id, *, emotional_valence, source)` | write | `int` new total |
| `activate_batch(memory_ids, *, emotional_valence, source)` | write | report `dict` |
| `associate(a, b, *, strength=None, delta=None)` | write | `float` new strength |
| `get_associations(memory_id, min_strength=0.0, limit=100)` | pure read | `list[dict]` |
| `spread_activation(seed_ids, *, depth, attenuation, min_strength, limit)` | pure read | `dict[int, float]` |
| `activation_count(memory_id)` | pure read | `int` |
| `decay(days=1.0)` | write | report `dict` |
| `consolidate(threshold=None)` | write | report `dict` |
| `heal_structure()` | write | heal report `dict` |
| `health()` / `stats()` / `get_stats()` / `dump(limit=50)` | pure read | `dict` |
| `backup()` | write | `str \| None` |
| `close()` | — | idempotent |
