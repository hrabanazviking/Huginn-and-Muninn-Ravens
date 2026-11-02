# RM-063 — Warm caches

**Class:** UNIT
**Slices:** RM-063 (Part V — Speed)

Both ravens gain an optional, bounded, in-memory cache for
their single-item read:

- **Muninn** — `HebbianMemory.get_node(memory_id)`, caching
  `MemoryNode` values.
- **Huginn** — `HuginnMemory.get(memory_id)`, caching document
  dicts. The cache lives in the facade, so it covers both
  backends (local and Qdrant) with one invalidation discipline.

## Configuration

One new field per package, with the same name and the same
default:

| Field | Default | Meaning |
|---|---|---|
| `cache_size` | `0` | Maximum entries the cache may hold. `0` disables the cache. Validated `>= 0`; a negative or non-integer value is a typed configuration error (`cache_size must be >= 0`). |

The default is **off** for a deliberate reason (the RM-055
secure-defaults judgement, extended in this slice and recorded
in `docs/SECURE_DEFAULTS.md`): a warm cache trades freshness
for speed, and the safe default is the pre-RM-063 behaviour —
every `get_node` / `get` reads the store. Enabling the cache
is an explicit, per-object choice.

## Semantics

- **Bounded, LRU.** The cache holds at most `cache_size`
  entries. A hit marks its entry most-recently-used; inserting
  beyond the bound evicts the least-recently-used entry first.
  Evictions are counted.
- **Hits are copies.** A hit returns a deep copy of the cached
  value, and the cache stores a deep copy of what the store
  returned. Mutating a returned node/dict — its content, tags
  or metadata — never changes the cache or the store.
- **Misses are never cached.** A `get_node` / `get` for an id
  that does not exist returns `None` and stores nothing, so a
  missing id is re-checked against the store on every call and
  a later creation is seen at once.
- **Own writes always invalidate.** Every write through the
  *same object* invalidates the entries it changes, before
  the next read can happen:
  - Muninn: `remember` / `remember_many` (their ids, and any
    backpressure victims — invalidated inside the backpressure
    road itself, the one place that knows them),
    `update` / `move`, `activate` / `activate_batch` (an
    activation changes the node's `access_count` and
    `updated_at`), `retrieve(..., touch=True)` (the same
    change, for the nodes it returns), `forget`,
    `secure_forget` / `delete`.
  - Huginn: `upsert_memory` (the id it returns), `delete`,
    `secure_forget`.
  A hit is therefore never stale for this object's own writes.
- **Per-object only — the staleness window, stated plainly.**
  The cache belongs to one object. A write through *another*
  object or process on the same store file — or directly on a
  Qdrant server — is **not** seen by this object's cache: a
  cached entry keeps serving the value this object last read
  until the entry is evicted or this object writes that id
  itself. This is the documented price of the cache, and it is
  why the cache is off by default. Hosts that share a store
  between writers should leave it off, or enable it only on
  objects whose view may lag.
- **Pure reads stay pure.** The cache is memory only: it never
  writes the store, and `health()` / `stats()` are untouched
  by it. `close()` drops the cache.

## Accounting — `cache_stats`

Each object exposes a dedicated `cache_stats` property (the
RM-053 pattern: per-call/per-object accounting lives outside
the pinned-pure `health()`/`stats()` snapshots):

```python
{
    "enabled": bool,   # cache_size > 0
    "size": int,       # entries currently held
    "cap": int,        # the configured cache_size
    "hits": int,       # lifetime hits for this object
    "misses": int,     # lifetime misses (enabled gets only)
    "evictions": int,  # lifetime LRU evictions
    "hit_rate": float, # hits / (hits + misses); 0.0 if none
}
```

Reading `cache_stats` touches nothing — on Huginn it does not
even construct the backend (lazy construction is contractual).
Invalidation removes entries but never rewrites the counters,
so the hit rate is an honest lifetime record for the object.
With the cache disabled the counters stay at zero.

## Acceptance (UNIT)

Pinned by `tests/test_warm_caches.py` in both packages:
default-off behaviour and zeroed stats; typed validation;
exact hit/miss accounting; misses never cached; bounded size
with LRU eviction order; invalidation on every write road
named above (including backpressure victims and
`retrieve(touch=True)`); caller-mutation copy safety; the
per-object staleness window and its end at an own write;
`health()`/`stats()` purity under cached reads; a hit proven
not to read the store (a raw-SQL change behind the object's
back is invisible to a hit and visible to the next miss);
on Huginn, `cache_stats` proven not to construct the backend
and the facade cache proven against a counting toy backend
(the backend-agnostic road the Qdrant backend rides).
