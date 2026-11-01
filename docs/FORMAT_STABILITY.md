# Store-Format Stability Promise (RM-022)

What a raven store *is*, on disk and on the wire, and which
parts of that shape are contractual — with the migration
promise attached to each part. Everything below was reviewed
against the code at this slice (`muninn/src/muninn/_db.py` +
`core.py`, `huginn/src/huginn/_db.py` + `local_backend.py` +
`qdrant_backend.py`, the RM-004 golden schemas) and is pinned
by `tests/test_format_stability.py` in both packages: every
table and key named here must appear in this document.

## The files (both packages, identical discipline)

A store is a small family of files around the configured
`db_path`:

| File | What it is | Promise |
|---|---|---|
| `<db_path>` | The SQLite database (WAL mode, `synchronous=FULL`) | The format this document governs. |
| `<db_path>-wal`, `<db_path>-shm` | SQLite's own WAL sidecars | SQLite-owned; never hand-edited, never part of the promise beyond "the store opens in WAL mode". Safe to leave to SQLite. |
| `<db_path>.bak-1` … `.bak-N` | Rolling backup generations (N = `backup_keep`, default 3) | Each is a complete store file in exactly the live store's format (made through SQLite's backup API from a verified-healthy store), so a generation can be restored by the open path — or copied over the main file by hand in an emergency — with no conversion. |
| `<db_path>.bak-tmp` | Transient snapshot target during a backup | Not a store; may be absent or partial after a crash and is never read as one. |

Durability contract (both stores): WAL + `synchronous=FULL`
— a `kill -9` loses at most the uncommitted transaction. On
open, a corrupt main store is restored from the newest
backup generation that itself verifies (loudly, via
`recovered_from_backup`); if none verifies, opening raises
the package's typed storage error rather than starting
empty over lost data.

## Muninn tables

Pinned byte-for-byte (normalised) by RM-004's golden schema
snapshot: `activation_log`, `deleted_nodes`,
`hebbian_connections`, `meta`, `node_activation`, `nodes`,
plus indexes `idx_activation_memory` and `idx_conn_b`.

| Table | Class | Promise |
|---|---|---|
| `hebbian_connections` | **Shared schema — law** | Consumed across stores (Bifröst's bridge reads Muninn's wiring). Shape changes only through the Part X schema-version slices, with migration proof against the pinned Bifröst contract and a Bifröst re-verification in the same slice. |
| `activation_log` | **Shared schema — law** | Same rule as `hebbian_connections`. Memory ids are integers, always (`memory_id INTEGER`). |
| `nodes` | Contractual | The memory rows every public read returns; `UNIQUE(content_hash, category, path)` is part of the promise (RM-013: a `remember` retry returns the first write's id). |
| `node_activation` | Contractual | Per-node activation counters + confidence; keyed by integer `memory_id`. |
| `deleted_nodes` | Contractual | Tombstones for forgotten integer ids; a re-remembered id clears its tombstone. |
| `meta` | Contractual | The key/value home for store-level state (registry below). |

## Huginn local tables

Pinned by RM-004's golden snapshot: `corpus_stats`,
`doc_terms`, `doc_vectors`, `documents`, `meta`, plus index
`idx_terms_term`.

| Table | Class | Promise |
|---|---|---|
| `documents` | Contractual | The document rows; integer `id`, `UNIQUE(content_hash, category)` (RM-013: an `upsert_memory` retry replaces in place under the same id). |
| `doc_terms`, `corpus_stats` | Contractual | The TF-IDF index over `documents`, keyed by integer `doc_id`; rebuilt/repaired by the store's own heal pass if it drifts. |
| `doc_vectors` | Contractual | Stored embedding vectors as JSON text, keyed by integer `doc_id`. |
| `meta` | Contractual | Same registry discipline as Muninn's. |

## The `meta` registry (both stores)

| Key | Written by | Promise |
|---|---|---|
| `schema_version` = `"1"` | The open path, on every open, both packages | The format version of the store. See the migration promise below — today it is *recorded*, not yet *gated on*. |
| `decay_last_run_at` (Muninn only) | `decay_wall_clock()` (RM-021), only when that opt-in mode runs | An ISO-8601 UTC timestamp. Absence means the mode has never run. Readers must tolerate absence and corruption (RM-021 re-arms instead of raising). |

Rules for all future keys: **additive only**; a key's
meaning, once shipped, never changes in place (a new meaning
gets a new key); unknown keys are ignored by readers, never
treated as corruption; every new key is registered in this
table in the slice that introduces it.

## Schema version & the migration promise

- Both stores are at `schema_version` **"1"**. There is no
  migration registry yet: on open, the code applies its
  `CREATE TABLE IF NOT EXISTS` schema and records the
  version; it does not compare a store's recorded version
  against its own. Muninn's `health()` reports
  `schema_version` so callers can see the recorded format.
- A format change **today** therefore ships only under the
  discipline the slices have actually used: golden snapshot
  updated in the same commit, Bifröst contract
  re-verification when the shared schema or public surface
  moves, and the change recorded in the slice log. Anything
  less is a breach of this promise.
- The machinery that turns this into in-code migration is
  already on the roadmap and this promise defers to it:
  RM-132 (Part X) builds the ordered, transactional
  migration registry on `meta.schema_version`, exercised by
  a synthetic v1→v2 migration; RM-082 defines the
  foreign-schema behaviour (migrate on open once the
  registry exists; until then a store whose shape the code
  cannot reconcile is surfaced through the heal/refusal
  paths, never silently overwritten). When RM-132 lands,
  this section is updated to name the registry as the
  governing mechanism.

## Values, not just tables

- **Ids are integers** everywhere they cross a boundary:
  Muninn memory ids, Huginn document ids, and Qdrant point
  ids (a memory id when known, else a content-hash-derived
  integer).
- **Stored timestamps** are UTC ISO-8601 with a `+00:00`
  offset (RM-012), issued monotonically per store.
- **Content identity** is a SHA-256 `content_hash` in both
  stores; the hash input is the stored content, never a
  wall-clock value.

## The Qdrant side (construction, not live proof)

Huginn's Qdrant backend creates its collection
(`collection_name`, default `huginn_memories`) with
`VectorParams(size=<embedder dim>, distance=COSINE)` — 384
for the default hashing embedder — and stores points under
integer ids with the document fields as payload. Changing
the collection name, the vector dimension, or the payload
shape is a format change under the same discipline as the
tables above. **A live Qdrant round-trip is NOT PROVEN**, so
this section promises what the code constructs, not what a
live server has been observed to hold.

## What is *not* promised

- The physical bytes of the database file (page layout,
  free-page reuse, WAL contents) — the promise is at the
  logical schema + values level (RM-011 makes the same
  cut for determinism).
- Result ordering beyond the deterministic orders pinned
  in RM-011.
- Anything about another project's stores (Mímir's
  `memories` table, a Hermes profile layout): the ravens
  read those only through the contracts of the bridges
  that own them.
