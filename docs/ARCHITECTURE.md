# Architecture — muninn + huginn (the Ravens)

This document describes how the two packages in this repository are
designed, how they are kept apart, and how other systems compose them.
It is a reference document: every statement here traces to the package
sources or to `docs/BUILD_NOTES_2026-10-30.md`. Where the build notes
and the code disagree, the code wins, and the disagreement is noted
(see §11).

Both packages are version 1.0.0, MIT-licensed, require Python ≥ 3.11,
and have stdlib-only cores (`dependencies = []` in both
`pyproject.toml` files). Huginn's only dependencies are optional
extras: `huginn[qdrant]` (`qdrant-client>=1.9,<2`) and
`huginn[embeddings]` (`sentence-transformers>=2.2,<6`).

---

## 1. The two packages at a glance

| | muninn | huginn |
|---|---|---|
| Role | **Memory** — associative memory | **Thought** — retrieval |
| Main class | `HebbianMemory` (plus the ancestor-shaped `Muninn` facade) | `HuginnMemory` |
| What it stores | Memory nodes, an activation log, and Hebbian wiring between integer memory ids | Documents (local backend) or Qdrant points (Qdrant backend) |
| What it answers | "What is wired to what, and how strongly?" "How often has this id been activated?" "What spreads from these seeds?" | "Which stored texts are most relevant to this query text?" |
| Storage | One SQLite file | One SQLite file (local backend) or a Qdrant collection (Qdrant backend) |
| Default store path | `~/.hermes/memory/muninn_hebbian.db` | `~/.hermes/memory/huginn_local.db` (local backend) |
| Reinforcement | Yes — `activate` / `activate_batch` / `associate` are the reinforcing writes | No — Huginn has no reinforcing read and no reinforcing write of its own; reinforcement is Muninn's job |
| Package top-level exports | `HebbianMemory`, `Muninn`, `MemoryNode`, `MuninnConfig`, the four `Muninn*` error types, `__version__` | `HuginnMemory`, `HuginnConfig`, `RetrievalResult`, `analyze_query`, `semantic_search`, the five `Huginn*` error types, `__version__` |

The names are the design statement, taken from the ancestors
(NorseSagaEngine's `yggdrasil/ravens/` and the Yggdrasil Cognitive
Architecture TDD, per BUILD_NOTES §2):

- **Muninn is Memory.** It keeps what was stored, logs every
  activation, and wires memories that fire together.
- **Huginn is Thought.** It flies out over what is stored and returns
  with what is relevant to a query.

Neither package does the other's job. Muninn's own `retrieve()` is a
filter/substring lookup over its nodes (ancestor semantics), not
semantic search; Huginn performs no Hebbian wiring and keeps no
activation log.

## 2. Independence: the packages never depend on each other

This is a hard structural rule, not a preference:

- Neither package imports the other. There is no shared library
  package between them.
- Each package is independently installable (`pip install ./muninn`,
  `pip install ./huginn`) and independently usable.
- Importing either package constructs nothing and opens no file
  (stated in both packages' `__init__.py` docstrings and proven by
  tests referenced in BUILD_NOTES §5).
- Each memory object opens **only its own store**. `HuginnMemory`
  never touches Muninn's file and vice versa (BUILD_NOTES §1.4,
  ground 3; tested).

### 2.1 Deliberate duplication of the store machinery

Because the packages must not depend on each other, the SQLite store
machinery — WAL open, integrity check, rolling backups, restore on
corruption — is implemented **twice**, once in
`muninn/src/muninn/_db.py` and once in
`huginn/src/huginn/_db.py`. The two files are near-identical in
discipline and differ in their error type (`MuninnStorageError` vs
`HuginnStorageError`), logger name, and message wording. BUILD_NOTES
§3 states this plainly: "the storage discipline is implemented per
package (small, deliberate duplication — the packages must not depend
on each other)."

The same applies to the small validation helpers: `_check_memory_id`,
`_check_importance`, and `_check_valence` exist in both
`muninn/core.py` and `huginn/core.py`, raising each package's own
`…ValidationError`.

Composition therefore happens **above** the packages, in the caller —
never inside them. See §3.

## 3. How they compose: Bifröst (and Hermes) on top

The ravens are libraries. The composer of record is **Bifröst**
(Bifröst's contract is extracted in full in BUILD_NOTES §1, from
`hrabanazviking/bifrost` v1.0.0 @ `b66e98cc`); Hermes also reads
Muninn's store directly (see §4.2).

Bifröst's composition, as recorded in BUILD_NOTES §1 and §5:

- Bifröst constructs each raven separately, in its own shape:
  - `HebbianMemory(MuninnConfig(db_path=...))` — positional config,
    `db_path` the only field Bifröst sets.
  - `HuginnMemory(config=None)` — no config at all. Huginn's defaults
    are therefore a contract: with no config and no Qdrant server
    anywhere, Huginn must come up on its local backend and work.
- Bifröst's bridge (`BifrostBridge`, verified end-to-end in
  BUILD_NOTES §5) holds the three stores of that deployment — Mímir,
  Muninn, Huginn — and merges by integer id: its `store()` returns
  both a `mimir_id` and a `huginn_id`; its `search()` merges
  Huginn-sourced results with composite scores; its `recall()` grows
  Muninn's activation log (by exactly 1 in the verified run); a
  search past the guard threshold wires Muninn connections through
  the named write APIs.
- The TDD's *memory-guided thought* scoring (novelty × weight +
  memory × similarity) lives in Bifröst's composite scorer, **not**
  in Huginn (BUILD_NOTES §2.2). Huginn returns honest per-backend
  scores; Muninn returns honest strengths and counts. Combining them
  is the composer's work.
- Bifröst's own `search()`/`recall()` write-on-read behaviour is
  Bifröst's documented design choice, implemented by Bifröst calling
  the ravens' *named* write APIs (`activate`, `activate_batch`). It
  is not hidden inside the ravens (BUILD_NOTES §1.4, ground 2).

Nothing in either raven knows that Bifröst, Mímir, or Hermes exists.
The only traces of the composer inside the packages are compatibility
seams that are part of each package's own public contract (§4).

## 4. Shared cross-store conventions

These conventions are what make independent composition possible.
They are contractual: other codebases rely on them.

### 4.1 Integer memory ids — one id space

- Memory ids are **integers** everywhere: node/document ids, ids in
  the activation log, both ends of every Hebbian connection, Huginn
  point ids.
- In Bifröst deployments these integers are **Mímir row ids across
  the Bifröst bridge** (BUILD_NOTES §1.2). One id space serves every
  store, which is why Muninn deliberately departed from the ancestor:
  the ancestor's node ids were 16-hex content hashes; here ids are
  integers and duplicate protection is instead provided by a
  content-hash unique index (BUILD_NOTES §2.1).
- Validation is identical in both packages: an id must be an `int`
  (bools are rejected), and `>= 0`. Violations raise
  `…ValidationError` before any write.
- Id `0` is legal by validation. Note the asymmetry this creates:
  SQLite `AUTOINCREMENT` ids start at 1, but activation/wiring APIs
  accept ids that have no node in Muninn's store at all — see §4.4.
- Huginn aligns to the same space two ways: `upsert_memory(...,
  memory_id=...)` lets the caller pin the id to an external store's
  id ("Bifröst merges backends by id"); without `memory_id`, the
  local backend assigns an autoincrement id and the Qdrant backend
  derives the point id deterministically from the content hash (see
  `docs/DATA_STRUCTURES.md`).

### 4.2 The contractual shared schema (Muninn)

Muninn's store file is read **directly** by two other codebases, so
part of its schema is a cross-package contract, not an implementation
detail. BUILD_NOTES §1.2 lists it:

- Table **`activation_log`** — columns `memory_id`, `activated_at`,
  `emotional_valence`, `source`. Bifröst's `BifrostMemory` inserts
  `(memory_id, activated_at, emotional_valence, source)` by name, and
  the Hermes Slice 87 probe requires this table to exist.
- Table **`hebbian_connections`** — columns `memory_a_id`,
  `memory_b_id`, `strength`, `co_activation_count`. Bifröst's boost
  query selects exactly these columns; the Slice 87 probe requires
  the table.

The full column lists (the contract columns are a subset of what the
tables actually carry) are in `docs/DATA_STRUCTURES.md`.

Two further seams belong to the same contract:

- **`HebbianMemory._get_conn()`** returns the store's own
  `sqlite3.Connection` (Row factory enabled). Bifröst's
  `_get_activation_count` runs a raw
  `SELECT COUNT(*) as cnt FROM activation_log WHERE memory_id = ?`
  through it and reads `row["cnt"]`. The method's docstring states
  the terms: callers must treat the connection as read-mostly and
  must not commit behind Muninn's back.
- **Ordering of `get_associations`** is contractual: results are
  ordered by strength DESC (then co-activation count DESC), because
  Bifröst consumes `[0]["strength"]` as its associative boost.

Hermes' side of the contract is read-only: its
`plugins/volmarr-core/memory_fabric.py` and the Slice 87 probe read
the Muninn store file directly and require the two tables above to
exist (BUILD_NOTES §1).

### 4.3 Directed rows in both directions

Hebbian connections are stored as **directed rows in both
directions**: a connection between `a` and `b` is two rows in
`hebbian_connections`, `(a, b)` and `(b, a)`, with the primary key
`(memory_a_id, memory_b_id)`.

Why: the Bifröst bridge reads connections directionally — its boost
query is `WHERE memory_a_id IN (recent)` (BUILD_NOTES §1.2) — so a
single undirected row could not serve both directions of lookup.

The symmetry is maintained by Muninn's API, never assumed:

- Every write path that creates or strengthens a pair
  (`activate_batch`, `associate`) writes both directed rows in the
  same transaction.
- The heal pass (§7.3) repairs drift between the two directions:
  a missing reverse row is inserted as a copy of the existing row;
  a pair whose two directions disagree on strength or count is
  reconciled to the stronger strength, the larger count, and the
  smaller (logical AND) `consolidated` flag.
- `stats()["total_connections"]` therefore counts directed rows, not
  logical pairs — the verified Bifröst run in BUILD_NOTES §5 reports
  "connections 0 → 2" for one wired pair, i.e. two directed rows.

### 4.4 External ids are legal in Muninn

Muninn's activation and wiring APIs operate on integer ids whether or
not a node with that id lives in Muninn's own `nodes` table:

- `activate(id)` always logs and counts; it bumps a node's
  `access_count` only "if a node with this id lives in this store".
- Edges to ids never registered as nodes are legal by design
  (cross-store ids, e.g. Mímir ids) and are **not** pruned by the heal
  pass (Muninn `INTERFACE.md`; BUILD_NOTES §3.1).
- The one exception is deliberate forgetting: `forget(id)` writes a
  tombstone in `deleted_nodes`, and heal prunes edges touching
  tombstoned ids. Activating or associating an id again clears its
  tombstone.

This is what lets one store serve as the wiring layer for ids owned
by another store.

### 4.5 Lazy, separate construction

Construction discipline differs per package, by design:

- **Import**: importing either package constructs nothing, opens no
  file, and (Huginn) touches no network.
- **Muninn**: `HebbianMemory(config)` opens its store at construction
  — only its own store — applies the schema idempotently, runs the
  integrity/recovery pass, then runs the structural heal pass and
  keeps the report as `last_heal_report`. Construction is safe from
  any thread; all methods are serialized internally afterwards.
- **Huginn**: `HuginnMemory(config=None)` is cheap and fully lazy —
  no file is opened and no server is contacted until the first
  operation. Backend selection happens on first use
  (`_ensure_backend`), never at import or construction. Huginn's
  local backend, when built, opens its store (with the same
  integrity/recovery/heal discipline as Muninn) at that moment; the
  Qdrant backend imports its client lazily and contacts the server
  only on first use.

### 4.6 The pure-reads law

Every read method in both packages is a **pure read** — it never
mutates the store. BUILD_NOTES §1.4 (ground 2) records this as the
answer to a Slice 86 NO-GO ground ("hidden writes on read paths"),
and BUILD_NOTES §5 records that tests prove it by snapshotting the
stores' write-tables before and after reads.

Pure reads:

- Muninn: `get_node`, `retrieve` (default), `get_by_path`,
  `get_children`, `get_associations`, `spread_activation`,
  `activation_count`, `get_tree_structure`, `health`, `stats` /
  `get_stats`, `dump`.
- Huginn: `search`, `get`, `fly`, `analyze_query`,
  `get_flight_stats`, `health`, `stats`. (One in-memory exception,
  not a store write: `fly` appends the flight to the object's own
  in-memory flight history.)

Writes are **named as writes**:

- Muninn: `activate`, `activate_batch`, `associate`,
  `store` / `remember`, `update`, `delete` / `forget`, `move`,
  `decay`, `consolidate`, `heal_structure`, plus `backup` (writes
  files beside the store).
- Huginn: `upsert_memory`, `delete`. (The local backend's `heal()`
  is a write, but it is a backend-level method, not exposed on the
  `HuginnMemory` facade; the facade-level equivalent of maintenance
  simply does not exist in Huginn.)

The single reinforcing read in either package is explicit and
opt-in: Muninn's **`retrieve(..., touch=True)`**, which activates
each returned node after selecting it. The default `touch=False` is
a pure read. This deliberately reverses the ancestor, whose
`retrieve()` silently incremented access counts (BUILD_NOTES §2.1).

**Huginn has no reinforcing read at all** — no parameter, no variant.
BUILD_NOTES §1.4 mentions a `search(..., reinforce=True)` shape in
passing; the code has no such parameter, and BUILD_NOTES §3.2 itself
corrects the record ("the parameter does not exist"). The code is
documented here: `HuginnMemory.search` takes exactly
`(query_text, limit=10, category=None, min_importance=1)`.
Reinforcement is Muninn's job; a composer that wants a search to
reinforce memory calls Muninn's named write APIs itself, as Bifröst
does.

### 4.7 Shared store discipline

Both local stores (Muninn's, and Huginn's local backend) follow the
identical discipline, implemented per package (§2.1):

- SQLite in **WAL journal mode**, `synchronous=FULL`,
  `foreign_keys=ON`, configurable `busy_timeout` (default 5000 ms).
- **One shared connection** per store object,
  `check_same_thread=False`; every public method is serialized by a
  `threading.RLock` — the lock is the thread-safety, the flag is what
  permits the shared connection.
- Writes commit per API call; multi-step writes such as
  `activate_batch` are fully transactional (the whole batch or none
  of it).
- **Crash-proofing**: WAL + FULL sync means a `kill -9` mid-write
  loses at most the uncommitted transaction; committed work survives
  reopen. Proven by subprocess kill tests in each package
  (BUILD_NOTES §3, §5).
- **Integrity on open**: `PRAGMA quick_check`. A healthy store opens
  normally. A corrupt store (or a file that is not a database at
  all) triggers restore from rolling backups (§7.2); if no backup
  verifies, opening raises the package's `…StorageError` — neither
  package ever silently starts empty over a corrupt store.
- **Rolling backups** beside the store file: `<db>.bak-1` …
  `<db>.bak-N` (`N` = `backup_keep`, default 3), made through
  SQLite's backup API from a verified-healthy store. See
  `docs/DATA_STRUCTURES.md` for the full on-disk layout.
- **Schema version** `"1"`, recorded in each store's `meta` table
  under the key `schema_version` at every open, and reported by
  Muninn's `health()` as `schema_version: "1"`.
- Validation before writes: invalid arguments raise
  `…ValidationError` before any write happens, so a validation
  failure never leaves a partial mutation behind. There is no silent
  clamping of caller data (numeric *limits* such as `top_k` and
  `limit` are bounded, as documented per method in
  `docs/DATA_STRUCTURES.md`).

## 5. Muninn design (Memory)

Source: `muninn/src/muninn/core.py`, `config.py`.

### 5.1 Model

Three ideas, one store:

1. **Nodes** — stored memories: content (a string, or any
   JSON-serializable value), hierarchical `path`, category (the
   dataclass calls it `memory_type`; `category` is its alias),
   `importance` 1–10, `emotional_valence` −1..1, tags, metadata,
   access count, timestamps. Full field list in
   `docs/DATA_STRUCTURES.md`.
2. **Activation** — every activation is an event, appended to
   `activation_log` and counted in `node_activation`. Repeated
   activation also restores confidence toward 1.0 (TDD: *repeated
   successful thoughts strengthen memory*).
3. **Hebbian wiring** — co-activated ids wire together in
   `hebbian_connections`, with a strength in [0, 1] and a
   co-activation count.

### 5.2 The Hebbian update

On each co-activation of a pair, in both directed rows:

```
strength ← 1 − (1 − strength) · (1 − learning_rate)
co_activation_count ← co_activation_count + 1
```

with `learning_rate` = `MuninnConfig.learning_rate`, default 0.1.
A first wiring inserts at exactly `strength = learning_rate`,
`co_activation_count = 1`. The rule is bounded: strength approaches
1 asymptotically and never exceeds it. (Verified exactly in tests:
52 co-activations → 0.99535, BUILD_NOTES §5.)

Activation itself applies the same shape to confidence, inside
`node_activation`:

```
confidence ← MIN(1.0, confidence + learning_rate · (1.0 − confidence))
```

starting from 1.0 on an id's first activation.

`associate(a, b, strength=… | delta=…)` is the manual wiring entry
point: `strength=` sets both rows to an exact value; `delta=` (or
neither argument) applies the bounded update once, with `delta` as
this call's learning rate.

### 5.3 Decay

`decay(days)` (default `days=1.0`) fades state multiplicatively:

```
edge strength ← strength · 0.5 ** (days / decay_half_life_days)        (default half-life 30 d)
confidence    ← confidence · 0.5 ** (days / confidence_half_life_days)  (default half-life 90 d)
```

Edges whose decayed strength falls below `prune_threshold` (default
0.01) are deleted and counted; edges that fall below the
consolidation threshold (default 0.8) are un-marked as consolidated
along the way. Decay is deterministic and safe to re-run. If
`auto_backup` is on, a rolling backup is taken before the mutation.

### 5.4 Consolidation

`consolidate(threshold=None)` (default threshold =
`consolidation_threshold`, 0.8): edges at or above the threshold are
marked `consolidated = 1`, edges below it are un-marked, and the
heal pass runs as part of consolidation ("sleep also tidies").
Consolidation never rewrites node content. If `auto_backup` is on, a
rolling backup is taken first.

Note: Bifröst's own `consolidation_threshold` config is dead in
Bifröst itself; the parameter here is real (BUILD_NOTES §3.1).

### 5.5 Spread activation

`spread_activation(seed_ids, depth=2, attenuation=0.5,
min_strength=0.0, limit=1000)` is a pure-read breadth-first walk over
the directed wiring: seeds start at 1.0; each hop multiplies by
`edge strength · attenuation`; a node's level is the maximum value
reaching it. Returns `{memory_id: activation}` strongest first,
seeds included.

### 5.6 Node semantics and idempotency

- `remember(...)` / `store(...)`: storing the same content under the
  same category and path returns the existing node's id instead of
  duplicating it — enforced by `UNIQUE(content_hash, category, path)`
  and an `INSERT OR IGNORE` + select-back. Safe under retries.
- `activate` is an event and is intentionally **not** idempotent.
- `close`, `decay`, and `consolidate` are safe to retry / re-run.
- **Backpressure** (ancestor behaviour): when storing a *new* node
  pushes the node count past `max_nodes` (default 20000), the
  lowest-value nodes (ordered by importance ASC, access count ASC,
  updated-at ASC) are pruned — node row, wiring, and a tombstone are
  written — and the prune is logged as a warning.
- `Muninn` is a compatibility facade over `HebbianMemory` accepting
  the ancestor's construction shape (`Muninn(data_path=...)`, a
  directory or a `.db` file); the storage underneath is the same
  single SQLite store.

### 5.7 Configuration

`MuninnConfig` is a dataclass, validated at construction
(`MuninnConfigurationError` on any out-of-range value):

| Field | Default | Meaning |
|---|---|---|
| `db_path` | `~/.hermes/memory/muninn_hebbian.db` | Store file; `~` expanded; parent directory created on open |
| `learning_rate` | 0.1 | Hebbian rate, in (0, 1] |
| `decay_half_life_days` | 30.0 | Edge-strength half-life for `decay()` |
| `confidence_half_life_days` | 90.0 | Confidence half-life for `decay()` |
| `prune_threshold` | 0.01 | Decayed edges below this are deleted |
| `consolidation_threshold` | 0.8 | Edges at/above this are marked consolidated |
| `busy_timeout_ms` | 5000 | SQLite busy timeout |
| `backup_keep` | 3 | Rolling backup generations kept |
| `auto_backup` | True | Refresh backup on open when the store changed; back up before `decay` / `consolidate` |
| `max_nodes` | 20000 | Backpressure ceiling for stored nodes |

## 6. Huginn design (Thought)

Sources: `huginn/src/huginn/core.py`, `local_backend.py`,
`qdrant_backend.py`, `text.py`, `config.py`.

### 6.1 Facade and backends

`HuginnMemory` is a facade over one of two backends, which share one
method shape (`upsert`, `search`, `get`, `delete`, `count`,
`health`, `close`, and a `kind` class attribute, `"local"` or
`"qdrant"`):

- **Local backend** (`LocalBackend`) — a fully capable retrieval
  store with zero infrastructure: one WAL SQLite file plus a
  maintained inverted term index.
- **Qdrant backend** (`QdrantBackend`) — points in a Qdrant
  collection, behind the optional `huginn[qdrant]` extra.

Backend selection is governed by `HuginnConfig.backend`:

| Setting | Behaviour |
|---|---|
| `"auto"` (default) | On first use, Qdrant is probed once (`ping()` — a `get_collections()` call — with `qdrant_timeout`, default 2.0 s). Any failure — no server, no client package — falls back to the local backend **permanently for this object**; the reason is recorded and `health()` reports `status: "degraded"` with `fallback_reason`. A missing Qdrant never crashes the caller. |
| `"local"` | Never touches the network. |
| `"qdrant"` | Explicit: the first-use `ping()` failure raises `HuginnBackendError`, loudly. (A missing `qdrant-client` package stays a `HuginnConfigurationError` — a packaging fact, not a server failure.) |

### 6.2 Scoring honesty

Huginn labels its scores for what they are, in code and in
`health()` (which always names the effective `embedder`):

- Local backend, default (`embedder="tfidf"`): **TF-IDF cosine** —
  lexical semantics, i.e. weighted word overlap. Not neural
  embeddings, and nothing pretends otherwise.
- `embedder="hashing"`: a deterministic feature-hashing embedder
  (stdlib SHA-256; tokens hashed into a fixed-dimension space with
  signed accumulation, L2-normalized). Cosine over hashing vectors
  approximates lexical overlap in vector form.
- `embedder="sentence-transformers"`: the only neural embedder,
  behind the `embeddings` extra (default model `all-MiniLM-L6-v2`).
- Qdrant needs fixed-space vectors, so with a Qdrant backend
  `embedder="tfidf"` resolves to `"hashing"`, and `health()`
  reports the resolved name.

With an embedder configured, the local backend stores a vector per
document and scores by dense cosine in a linear scan over stored
vectors — the code comments call this "the right shape for a
personal memory store (thousands of documents); very large corpora
belong on Qdrant". (BUILD_NOTES §3.2 describes this mode as
"reranking lexical candidates by vector cosine"; the code does a
full linear scan over stored vectors, not a rerank of lexical
candidates. Code wins — see §11.)

### 6.3 Local backend: index, not scans

In TF-IDF mode the local backend never full-scans for candidates:

- `documents` holds the texts; `doc_terms` is the inverted index
  (one row per (document, term) with its term frequency);
  `corpus_stats` holds each term's document frequency;
  `doc_vectors` holds per-document vectors in embedder modes only
  (in pure TF-IDF mode it stays empty).
- A search takes candidate document ids from the query terms'
  postings (`SELECT DISTINCT doc_id FROM doc_terms WHERE term IN
  (…)`), applies the category / min-importance filters to those
  candidates, then scores survivors with sparse TF-IDF cosine,
  batched lookups throughout (BUILD_NOTES §3: "no N+1 query
  patterns"). Only positive scores are returned, best first.
- Tokenizing is shared machinery (`text.py`): lowercase Unicode word
  tokens, stopwords removed, 1-character tokens removed. The
  stopword set is the ancestor's, kept verbatim.
- Upserts maintain the index transactionally with the document:
  old term rows are de-indexed (document frequencies decremented,
  zero-frequency terms deleted) before the new term rows are
  indexed; a replaced document's stored vector is deleted and
  re-embedded.
- Upsert identity mirrors Muninn's idempotency: the same content in
  the same category is the same memory, keyed by
  `UNIQUE(content_hash, category)`. Pinning with `memory_id=` has one
  guarded edge case — if the requested id is free but the content
  already lives at a different id, the upsert raises
  `HuginnValidationError` telling the caller to upsert at the
  existing id, rather than duplicating the memory under two ids.

### 6.4 Qdrant backend

- The client is imported lazily and the server is contacted only on
  first use; constructing the backend object touches no network.
- Identity: a point's id is the caller's `memory_id` when given,
  else derived deterministically from the content hash
  (`int.from_bytes(bytes.fromhex(content_hash[:16]), "big")`), so
  re-upserting the same memory targets the same point.
- The collection (default name `huginn_memories`) is ensured lazily:
  `get_collection`, and on any exception `create_collection` with
  cosine distance and vector size = the embedder's dimension.
  Creation failure raises `HuginnBackendError`.
- Searches use `query_points` when the client provides it, falling
  back to the older `search` method otherwise; category and
  min-importance become a Qdrant `Filter` (exact match on
  `category`, `Range(gte=…)` on `importance`).
- Every operation `ping()`s first; server failures are wrapped as
  `HuginnBackendError` with the operation named ("Qdrant upsert
  failed: …", and so on).
- Status of this backend against a real server: **NOT PROVEN** —
  see §10.

### 6.5 Flights (ancestor semantics)

On top of the contract API, Huginn carries the ancestor's flight
vocabulary:

- `analyze_query(query)` — module function and method: query type
  (`factual` / `explanatory` / `search` / `enumeration` /
  `comparison`, by keyword), key terms (stopwords removed), strategy
  and recommended hops.
- `fly(query, max_results=5, compress=True)` → `RetrievalResult`.
  A flight is a pure read over the store; on backend failure the
  flight comes home empty with `error` set, as the ancestor's
  flights did, rather than crashing the thinker. With
  `compress=True`, long string values in results are truncated to
  200 characters + `"..."` and long lists to 5 entries.
- `multi_hop_retrieve(...)` — chained flights: each hop's findings
  seed the next query (up to 3 extracted concepts appended to the
  initial query); stops early when a hop returns nothing or yields
  no concepts.
- `semantic_search(query, documents, top_k)` — the ancestor's
  signature: TF-IDF over caller-supplied documents, stdlib sparse
  vectors, returns `(index, score)` pairs.
- `get_flight_stats()` — statistics over this object's flights.
- Deliberately **not** carried: the ancestor's realm routing
  (`route_query`) — realms were NorseSagaEngine game machinery, not
  a memory-library contract (BUILD_NOTES §2.2).

### 6.6 Configuration

`HuginnConfig` is a dataclass, validated at construction:

| Field | Default | Meaning |
|---|---|---|
| `backend` | `"auto"` | One of `"auto"`, `"local"`, `"qdrant"` |
| `qdrant_url` | `http://localhost:6333` | Qdrant server URL (Bifröst's own default; Bifröst never passes it, so Huginn carries the same default) |
| `qdrant_api_key` | None | Optional Qdrant API key |
| `collection_name` | `huginn_memories` | Qdrant collection for memories |
| `local_db_path` | `~/.hermes/memory/huginn_local.db` | SQLite file for the local backend |
| `embedder` | `"tfidf"` | One of `"tfidf"`, `"hashing"`, `"sentence-transformers"` |
| `vector_dim` | 384 | Hashing-embedder dimension (and Qdrant collection size for it); must be ≥ 8 |
| `st_model` | `all-MiniLM-L6-v2` | sentence-transformers model name |
| `qdrant_timeout` | 2.0 | Seconds for the auto-probe and Qdrant calls |
| `busy_timeout_ms` | 5000 | SQLite busy timeout (local backend) |
| `backup_keep` | 3 | Rolling backup generations (local backend) |
| `auto_backup` | True | Rolling backup discipline (local backend) |

## 7. Durability, recovery, and self-healing

### 7.1 The durability contract

For both SQLite stores (Muninn's and Huginn's local), from the
`_db.py` docstrings: WAL + `synchronous=FULL` means a `kill -9`
mid-write loses at most the uncommitted transaction; every committed
write survives reopen.

### 7.2 Rolling backups and restore on open

- A backup is a file copy made through SQLite's own backup API from
  a verified-healthy store, so a backup is never a snapshot of
  corruption: the snapshot is written to `<db>.bak-tmp`, verified
  with `quick_check`, and only then rotated into place
  (`.bak-1` → `.bak-2` → …); a failed backup never destroys the
  previous generations.
- A fresh backup is taken on open only when the store existed and
  changed since the newest backup was taken (mtime comparison), so
  repeated opens do not push out useful generations with identical
  snapshots. Muninn additionally backs up before `decay()` /
  `consolidate()` when `auto_backup` is on, and on demand via
  `HebbianMemory.backup()`.
- On open, if the main store fails `quick_check` (or cannot be
  opened as a database at all), the newest backup that itself passes
  `quick_check` is restored over it, WAL sidecars are removed before
  and after the copy, and the recovery is logged at ERROR level and
  reported (`open_report.recovered_from_backup`,
  `recovered_from_backup` attribute, and `health()`).
- If no backup verifies, opening raises `…StorageError`. Data loss
  is always loud; silent empty starts do not exist here.

### 7.3 Structural heal passes

Separate from file integrity, each store repairs *structural* drift
in a heal pass that runs on every open and returns a report dict
(full key lists in `docs/DATA_STRUCTURES.md`):

- **Muninn** (`_heal_locked`, also run by `heal_structure()` and by
  `consolidate()`): prune self-edges; prune edges touching
  tombstoned (forgotten) ids; repair asymmetric directed pairs
  (§4.3); reconcile `node_activation` counters against the
  activation log (insert missing counter rows, correct totals that
  disagree with `COUNT(*)` in the log). The report is kept on the
  object as `last_heal_report`.
- **Huginn local** (`_heal_locked`, also run by the backend's
  `heal()`): prune term rows and vector rows whose document no
  longer exists; recount every term's document frequency from
  `doc_terms` and correct `corpus_stats` to match.

Note what heal does *not* do: Muninn's heal does not prune edges to
external ids that were never nodes (§4.4), and neither heal rewrites
stored content.

## 8. Error design

Both packages raise typed errors and let the caller decide policy;
nothing swallows an exception into fake success. Full hierarchies
and trigger lists are in `docs/DATA_STRUCTURES.md`.

- Muninn: `MuninnError` → `MuninnValidationError` (also a
  `ValueError`), `MuninnConfigurationError` (also a `ValueError`),
  `MuninnStorageError`.
- Huginn: `HuginnError` → `HuginnValidationError` (also a
  `ValueError`), `HuginnConfigurationError` (also a `ValueError`),
  `HuginnStorageError`, `HuginnBackendError`.

The one designed exception to "failures raise" is Huginn's
`backend="auto"`: a missing Qdrant there is a configuration fact,
answered by the local backend and reported in `health()` — never by
raising into the caller (`huginn/errors.py` docstring). Huginn's
`health()` itself never raises for backend trouble; it returns
`status: "unhealthy"` with the error named. And `fly()` converts a
backend failure into an empty `RetrievalResult` with `error` set.

## 9. Threading

- Each store object owns one `threading.RLock` and one shared
  connection (`check_same_thread=False`); every public method takes
  the lock. Huginn's backends each own an RLock as well, and
  `HuginnMemory` has its own lock for backend construction and
  flight history.
- Huginn's lazy backend construction is double-checked under the
  lock, so concurrent first use builds exactly one backend.
- Race behaviour is test-proven per BUILD_NOTES §5 (Muninn: 8-thread
  races with exact totals; Huginn: 6-thread races).

## 10. What is NOT PROVEN

Stated plainly, from BUILD_NOTES §5, and still true of the code as
read for this document:

- **Live Qdrant server round-trip — NOT PROVEN.** No Qdrant server
  exists on the build VM. The Qdrant backend is proven against a
  faithful fake client stood up in `sys.modules` (mapping, filters,
  derived ids, error roads), not against a real server.
- **The sentence-transformers embedder path — NOT PROVEN.** The
  `embeddings` extra was not installed in the build environment;
  the class is implemented and raises `HuginnConfigurationError`
  with install instructions when the package is missing, but no
  neural embedding was produced there. The hashing embedder path
  **is** proven end-to-end.
- **Performance on unloaded hardware — NOT PROVEN.** The benchmark
  numbers in BUILD_NOTES §4 were measured on a loaded VM (twelve
  campaign keepers running) and are labelled there as indicative,
  not promises. They are not repeated as guarantees here; see
  BUILD_NOTES §4 for the table itself.

What *is* proven (BUILD_NOTES §5): both package suites green
(muninn 36 passed, huginn 27 passed, 0 failed); Bifröst's own suites
against the real ravens (25 passed, 0 failed); an end-to-end run
through `BifrostBridge` (store/search/recall/decay/consolidate/
health/stats, double `close()` safe); kill-9 durability and
corruption-recovery tests in both packages.

## 11. Known disagreements between BUILD_NOTES and the code

Code wins in every case below; this document follows the code.

1. **Huginn `search` reinforce parameter.** BUILD_NOTES §1.4 lists
   `search(..., reinforce=True)` among reinforcing variants; §3.2
   first shows `search(..., reinforce=False)` and then corrects
   itself: "the parameter does not exist." The code confirms §3.2's
   correction — `HuginnMemory.search` and both backends' `search`
   have no `reinforce` parameter, and Huginn has no reinforcing
   read at all.
2. **Huginn local embedder-mode search.** BUILD_NOTES §3.2 says the
   local backend with a sentence-transformers embedder works by
   "reranking lexical candidates by vector cosine". The code
   (`LocalBackend._search_vectors_locked`) does a linear scan over
   **all** stored vectors in `doc_vectors`, for any embedder mode;
   there is no lexical-candidate rerank step.
3. **Shared error-hierarchy summary.** BUILD_NOTES §3 lists the
   typed hierarchies as "`…ValidationError`, `…StorageError`,
   `…ConfigurationError`, `…BackendError`" for both packages.
   Muninn has no BackendError: its hierarchy is exactly
   `MuninnValidationError`, `MuninnConfigurationError`,
   `MuninnStorageError`. Only Huginn has a `…BackendError`.
