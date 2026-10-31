# BUILD_NOTES — The Ravens (muninn + huginn)

Commissioned by Volmarr, 2026-10-30: *"Look at the ancestors and the glossary
and what they are supposed to be, and build them true, as robust, self-healing,
error-correcting, threaded, crash-proof, very efficient modules that can be
useful in all my projects for their functions."*

This tree is standalone: two independent, installable packages. No remote.
Integration into Hermes/Bifröst deployments is a later slice, not this build.

---

## 1. The extracted Bifröst contract (the glossary — hard requirements)

Source: `hrabanazviking/bifrost` @ `b66e98cc8a79d4dede22ba11d68a1a5ecd22ebd6`
(v1.0.0), read in full: `src/bifrost/core.py`, `src/bifrost/config.py`,
`src/bifrost/bridges/memory_bridge.py`, `tests/test_bifrost.py`,
`tests/test_hebbian_guard.py`. Cross-checked against Hermes'
`plugins/volmarr-core/memory_fabric.py` (incl. the Slice 87 read-only probe).

### 1.1 Muninn — what Bifröst calls

| Call (verbatim from core.py / guard tests) | Requirement |
|---|---|
| `from muninn import HebbianMemory` | exported at package top level |
| `from muninn.config import MuninnConfig` | module `muninn.config`, class `MuninnConfig` |
| `MuninnConfig(db_path=<str>)` | dataclass, `db_path` keyword; may contain `~` |
| `HebbianMemory(config)` | positional config |
| `muninn.activate(memory_id)` / `activate(id, emotional_valence=float)` | logs one activation (a WRITE, by name) |
| `muninn.activate_batch(ids, emotional_valence=float)` | logs each activation AND wires all pairs |
| `muninn.get_associations(memory_id, min_strength=float)` | list of dicts, each with `"strength"`; Bifröst takes `[0]` as the boost → must be sorted by strength DESC |
| `muninn._get_conn()` | returns a `sqlite3.Connection` (Row factory); Bifröst runs raw SQL `SELECT COUNT(*) as cnt FROM activation_log WHERE memory_id = ?` on it and reads `row["cnt"]` |
| `muninn.decay(days=float)` | returns a dict |
| `muninn.consolidate()` | returns a dict |
| `muninn.health()` | dict containing `"status": "healthy"` when well |
| `muninn.stats()` | dict containing `"total_activations"` and `"total_connections"` (guard tests) |
| `muninn.close()` | idempotent (bridge double-close tested) |

### 1.2 Muninn — the shared store schema (cross-package law)

The Muninn store file (default `muninn_hebbian.db`) is read *directly* by two
other codebases, so these tables/columns are contractual:

- `activation_log` — columns `memory_id`, `activated_at`, `emotional_valence`,
  `source` (BifrostMemory inserts `(memory_id, activated_at, emotional_valence,
  source)` by name; the Hermes Slice 87 probe requires this table to exist).
- `hebbian_connections` — columns `memory_a_id`, `memory_b_id`, `strength`,
  `co_activation_count` (BifrostMemory's boost query selects exactly these;
  Slice 87 requires the table). Connections are stored as **directed rows in
  both directions** (a→b and b→a, kept symmetric by the API), because the
  bridge's boost query is directional (`WHERE memory_a_id IN (recent)`).
- Memory ids are **integers** (they are Mímir row ids across the bridge).

### 1.3 Huginn — what Bifröst calls

| Call | Requirement |
|---|---|
| `from huginn import HuginnMemory` | exported at package top level |
| `HuginnMemory(config=None)` | **must work with no config and no Qdrant server** — Bifröst never passes its `qdrant_url`; defaults must land on a working local backend |
| `huginn.upsert_memory(content=, category=, importance=, tags=, emotional_valence=)` | returns the stored vector id (int) |
| `huginn.search(query_text=, limit=, category=None, min_importance=int)` | list of dicts with keys `id, content, category, importance, tags (list), emotional_valence, score` |
| `huginn.health()` | dict containing `"status"` |
| `huginn.close()` | optional for Bifröst (`hasattr` check); provided, idempotent |

### 1.4 The three Slice 86 NO-GO grounds — how this build answers them

1. **Unauditable packages** → the packages now exist, in full, in this tree,
   with tests for every mutation semantic (what decay prunes, what
   consolidation rewrites, what an activation writes).
2. **Hidden writes on read paths** → in *these* packages, every read API
   (`get_associations`, `get_node`, `retrieve`, `search`, `fly`, `health`,
   `stats`, `activation_count`, `spread_activation`) is a **pure read**,
   proven by tests that snapshot the store's write-tables before/after.
   The only write-on-activity APIs are named as writes: `activate`,
   `activate_batch`, `associate`, and `retrieve(..., touch=True)` /
   `search(..., reinforce=True)` where the reinforcing variant is explicit,
   opt-in, named, documented and tested. (Bifröst's own `search()`/`recall()`
   write-on-read behaviour is Bifröst's documented design choice, calling
   these named write APIs — it is not hidden inside the ravens.)
3. **Lazy, separate construction** → importing either package constructs
   nothing and opens no file. Each memory object opens **only its own
   store**. `HuginnMemory` never touches Muninn's file and vice versa
   (tested). Backend selection in Huginn is lazy (first use), never at
   import.

---

## 2. Ancestor fidelity

Ancestors: NorseSagaEngine `yggdrasil/ravens/muninn.py` (794 lines),
`huginn.py` (542), `raven_rag.py`, `yggdrasil/cognition/huginn_advanced.py`,
their INTERFACE/README/PATTERNS/TESTS docs, and the Yggdrasil Cognitive
Architecture TDD.

### 2.1 Muninn (Memory) — carried forward

- Memory **nodes** with content, hierarchical `path`, type/category,
  importance (1–10), tags, metadata, access counts, timestamps —
  `MemoryNode` dataclass with `to_dict`/`from_dict`, as the ancestor had.
- Ancestor API names kept on a compatibility surface: `store`, `retrieve`,
  `get_by_path`, `get_children`, `update`, `delete`, `move`,
  `get_tree_structure`, `heal_structure`, `get_stats`, `dump`.
- **Self-healing structure** was the ancestor's signature (`heal_structure()`
  rebuilt indexes and counted fixes) — kept, and deepened: index repair is
  now store-level integrity + edge repair (see §3).
- TDD semantics: *repeated successful thoughts strengthen memory*
  (confidence += learning), *low-use memories decay* (confidence *= decay
  factor), *consolidation prunes redundant nodes and merges similar
  concepts* (sleep). These map to `activate`/reinforcement, `decay()`,
  `consolidate()`.
- Deliberate departures (contract-driven, recorded honestly):
  - Node ids are **integers**, not the ancestor's 16-hex content hashes:
    Bifröst keys Muninn state by Mímir's integer ids, and one id space
    must serve both. Duplicate-store protection is kept by a content-hash
    unique index instead (idempotent `store`).
  - Storage is **one SQLite file**, not the ancestor's per-node JSON files:
    required for transactions, WAL crash-safety and indexed lookup.
  - The ancestor's `retrieve()` silently incremented access counts
    (a hidden write on a read). Here `retrieve` is pure by default;
    `touch=True` is the named, opt-in reinforcing read.

### 2.2 Huginn (Thought) — carried forward

- `analyze_query()` — the ancestor's query analysis (query_type, key_terms
  with the same stopword set, strategy, recommended_hops, word_count),
  kept as a module function and a method.
- `RetrievalResult` dataclass and `fly()` — a flight returns scored results
  with timing and an error field, as the ancestor's did; it now flies over
  Huginn's own store.
- `multi_hop_retrieve()` — chained flights with concept extraction.
- `semantic_search(query, documents, top_k)` — the ancestor's TF-IDF
  semantic search over caller-supplied documents, reimplemented on a
  stdlib sparse TF-IDF (no sklearn dependency); returns `(index, score)`.
- `get_flight_stats()` — flight history statistics.
- The ancestor's realm-routing (`route_query`) is **not** carried: realms
  were NorseSagaEngine game machinery, not a memory-library contract.
  Recorded here as a deliberate omission.
- The TDD's *memory-guided thought* scoring (novelty × weight + memory ×
  similarity) lives in Bifröst's composite scorer, not in Huginn; Huginn
  returns honest per-backend scores.

---

## 3. Shared engineering design (both packages)

Each package is independently installable, so the storage discipline is
implemented per package (small, deliberate duplication — the packages must
not depend on each other).

- **SQLite, WAL mode**, `synchronous=FULL`, `busy_timeout` (default
  5000 ms), `foreign_keys=ON`. One shared connection per store object,
  `check_same_thread=False`, every public method serialized by an
  `threading.RLock`; writes run in explicit transactions (all-or-nothing
  per API call).
- **Crash-proof**: WAL + FULL sync means a `kill -9` mid-write loses at
  most the uncommitted transaction; committed work survives. Proven by a
  subprocess kill test in each package.
- **Self-healing**: on open — `PRAGMA quick_check`; if the main file is
  corrupt, restore from the newest *verified* rolling backup
  (`<db>.bak-1..N`, SQLite backup API), log at ERROR level, and expose
  `recovered_from_backup` / health detail. On every open, a heal pass
  repairs structural drift (Muninn: self-edges, edges touching deleted
  nodes, asymmetric directed pairs, activation-counter drift; Huginn:
  term-index/doc-freq drift) and returns a report dict.
- **Rolling backups**: taken on open when the store changed since the
  last backup (and before `decay`/`consolidate` maintenance), kept to
  `backup_keep` (default 3) generations.
- **Error-correcting**: typed exception hierarchies
  (`MuninnError`/`HuginnError` → `…ValidationError`, `…StorageError`,
  `…ConfigurationError`, `…BackendError`). Invalid inputs (bad id types,
  importance outside 1–10, valence outside −1..1, empty content,
  non-string queries) raise `…ValidationError` with a plain message —
  never silent clamping of caller data, never partial writes.
  Idempotency where semantics allow: `store`/`upsert_memory` dedupe by
  content hash; double `close()` is a no-op; maintenance ops are safely
  re-runnable.
- **Efficiency**: indexed lookups everywhere (term inverted index in
  Huginn; PK/indexed edges and activation log in Muninn); batched writes
  (`executemany`, one transaction per batch); no N+1 query patterns.
- **No hidden behaviour**: libraries raise typed errors and let callers
  decide policy. Nothing here swallows exceptions into fake success.

### 3.1 Muninn specifics

- Tables: `meta`, `nodes`, `activation_log` (§1.2), `hebbian_connections`
  (§1.2), `node_activation` (per-id counters: total, last_activated_at,
  confidence), `deleted_nodes` (tombstones so `heal` can prune edges of
  explicitly forgotten ids while edges to *external* ids — e.g. Mímir ids
  never registered as nodes here — stay legal by design).
- Hebbian update (bounded, classic): on co-activation of a pair,
  `strength ← 1 − (1 − strength) · (1 − learning_rate)` (default rate
  0.1, initial strength = learning_rate), `co_activation_count += 1`.
  Strengths stay in [0, 1]; Bifröst's `muninn_weight` (0.2) is used by
  callers as a `min_strength` filter, so the scale matters and is kept.
- `decay(days)`: strengths and node confidences multiply by
  `0.5 ** (days / half_life)` (edges default half-life 30 d, confidence
  90 d); edges falling below `prune_threshold` (0.01) are deleted and
  counted in the returned dict. Deterministic, re-runnable, tested.
- `consolidate(threshold=0.8)`: marks edges at/above threshold
  `consolidated=1` (and unmarks any that decayed below), prunes
  self/dangling edges, repairs asymmetry; returns counts. It never
  rewrites node content. (Bifröst's `consolidation_threshold` config is
  dead in Bifröst itself; the parameter here is real.)
- `spread_activation(seed_ids, depth, attenuation)` — pure-read BFS over
  edges ≥ `min_strength`, returning `{id: activation}`.

### 3.2 Huginn specifics

- Backends behind one facade:
  - **local** (default, zero infrastructure): SQLite store + a maintained
    inverted term index; scoring is **TF-IDF cosine** — honestly
    labelled *lexical* semantics (word-overlap, not neural embeddings).
  - **qdrant** (optional extra `huginn[qdrant]`, `qdrant-client>=1.9,<2`):
    vectors from a pluggable embedder. Default embedder is a
    deterministic **feature-hashing** embedder (stdlib; honestly
    labelled: lexical-overlap vectors, dimension from config).
    `huginn[embeddings]` adds sentence-transformers for true neural
    embeddings (`embedder="sentence-transformers"`); with that embedder
    the local backend also works, reranking lexical candidates by
    vector cosine.
- `backend="auto"` (default): Qdrant is probed lazily on first use with
  a short timeout; any failure → fall back to local **permanently for
  that object**, record the reason, report `status: "degraded"` +
  `backend: "local"` + reason in `health()`. A missing Qdrant can never
  crash the caller. Explicit `backend="qdrant"` with no server raises
  `HuginnBackendError` — loud, typed, honest.
- Upsert identity: ids are Huginn-local autoincrement ints unless the
  caller passes `memory_id=` to align with an external store (Bifröst
  merges backends by id). Re-upserting identical content is idempotent
  (content-hash dedupe within category).
- `search(..., reinforce=False)`: pure read by default. There is no
  hidden reinforcement in Huginn at all — reinforcement is Muninn's job;
  the parameter does not exist. (Recorded to keep §1.4-2 unambiguous.)

---

## 4. Benchmarks

Measured on this VM (loaded — twelve campaign keepers running; numbers
indicative, not promises), Python 3.12.3, SQLite 3.45.1.
Scripts: `muninn/scripts/benchmark.py`, `huginn/scripts/benchmark.py`.

Measured 2026-10-30 ~23:57 EDT.

**muninn** (5,000 nodes seeded):

| operation | result |
|---|---|
| `remember()` × 5,000 | 986 ms total (0.20 ms/node, incl. WAL FULL commit each) |
| `activate()` × 20,000 | 2,821 ms total (0.14 ms/call) |
| `activate_batch(5 ids)` × 2,000 | 1,275 ms total (0.64 ms/batch; wires 20 pairs per batch) |
| `get_associations()` × 5,000 | 371 ms (0.07 ms/read) |
| `spread_activation(depth=2)` × 1,000 | 375 ms (0.37 ms/call) |
| `decay(days=1)` full store | 193 ms (incl. pre-maintenance backup snapshot) |
| `consolidate()` full store | 99 ms (incl. backup snapshot) |
| `stats()` | 1.1 ms |

Store after seeding: 5,000 nodes, 812 connection rows, 30,000
activations.

**huginn, local TF-IDF backend** (5,000 documents; note the synthetic
corpus uses a 22-word vocabulary, so every query term matches most
documents — a worst case for candidate-set size; natural corpora skew
far better):

| operation | result |
|---|---|
| `upsert_memory()` × 5,000 | 4,113 ms total (0.82 ms/doc incl. indexing) |
| `search(limit=10)` | median 16.5 ms, p95 80.9 ms |
| `search(limit=10, category=…)` | median 1.7 ms, p95 55.9 ms |

## 5. Verification log

Verified 2026-10-30 late evening / 2026-10-31 ~00:0x EDT.
Environment: Python 3.12.3 venvs on this VM.

**Package suites** (runner output only):
- muninn: **36 passed, 0 failed** (`/tmp/ravens-venv`).
- huginn: **27 passed, 0 failed** (same venv).

Coverage highlights — muninn: full Bifröst call-shape contract incl.
raw-SQL `_get_conn()` activation counts and the hebbian-guard
scenario; Hebbian math exactness (52 co-activations → 0.99535);
read purity by table snapshot; 8-thread races with exact totals;
kill-9 subprocess (≥30 committed batches, per-id log counts tie
exactly, integrity ok); header-corruption recovery from rolling
backup with data intact + ERROR log; corruption-without-backup typed
error; heal repairing raw-SQL-inserted self/dangling/asymmetric edges
and counter drift; import-constructs-nothing. huginn: Bifröst call
shapes and result dict keys; ranking/filters; explicit-id upsert and
clash refusal; search purity; index-drift heal; ancestor
analyze_query/fly/multi-hop/semantic_search; Qdrant backend against a
fake in-`sys.modules` client (round trip, filters, derived ids);
auto-fallback (dead server, missing client) vs explicit-loud;
6-thread races; kill-9; corruption recovery; lazy construction.

**Bifröst integration** (fresh venv `/tmp/bifrost-verify-venv`:
`pip install -e muninn -e huginn` + Bifröst from the pinned scratch
clone @ `b66e98cc`):
- **Bifröst's own test suites: 25 passed, 0 failed**
  (`tests/test_bifrost.py` + `tests/test_hebbian_guard.py` — the
  guard scenarios run against the real muninn).
- **End-to-end through `BifrostBridge` public API: PASS** —
  `_ensure_muninn()`/`_ensure_huginn()` construct the real classes;
  `store()` returns both `mimir_id` and `huginn_id`; `search()`
  merges huginn-sourced results with composite scores; `recall()`
  grows the Muninn activation log by exactly 1; with fixtures past
  the guard threshold, a 2-result search wires connections 0 → 2
  (both directions stored); `decay()` and `consolidate()` return
  proper reports through the bridge; `health()` shows Mímir healthy,
  Muninn healthy, Huginn **degraded — auto fell back to local because
  `qdrant-client` was not installed in that venv, with the reason
  stated**; `stats()` aggregates all three; double `close()` safe.
- **Qdrant-client-present roads** (client installed into the verify
  venv afterwards): `backend="auto"` against a dead URL falls back
  to local with `fallback_reason` recorded; `backend="qdrant"`
  against a dead URL raises `HuginnBackendError`. Environment note:
  this VM's `no_proxy` contains a bracketed IPv6 entry that httpx
  misparses ("Invalid port: ':1]'") — with a cleaned `no_proxy`, the
  recorded reason is the honest "[Errno 111] Connection refused".
  The package degrades correctly under both; the env defect is the
  VM's, already known from other campaigns' test noise.
- Observed Bifröst-side behaviour (not a raven defect): memories
  added via `bridge.store()` are not visible to Mímir FTS search
  until an FTS rebuild, because Bifröst's schema has no FTS sync
  triggers — its own suite seeds FTS the same way. Huginn covers
  those memories immediately.

**NOT PROVEN (stated plainly):**
- Live Qdrant **server** round-trip — no server exists on this VM;
  the Qdrant backend is proven against a faithful fake client
  (mapping, filters, derived ids, error roads), not a real server.
- The `sentence-transformers` embedder path — extra not installed
  here; the hashing embedder path IS proven end-to-end.
- Performance on unloaded hardware — benchmark numbers above are
  from this loaded VM by design of the commission.
