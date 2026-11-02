# Huginn — interface

The Thought Raven: semantic retrieval over your memories. Qdrant
when genuinely available; a fully capable local store when not.
Stdlib-only core. Python ≥ 3.11.

## Install

```bash
pip install ./huginn                    # local backend, zero infra
pip install './huginn[qdrant]'          # + Qdrant support
pip install './huginn[embeddings]'      # + neural embeddings
```

## The contract surface (Bifröst-compatible)

```python
from huginn import HuginnMemory

h = HuginnMemory(config=None)           # ← exactly Bifröst's call
h.upsert_memory(content=..., category=..., importance=5,
                tags=[...], emotional_valence=0.0)   # -> int id (WRITE)
h.search(query_text=..., limit=10, category=None,
         min_importance=1)              # -> [{id, content, category,
                                        #     importance, tags,
                                        #     emotional_valence, score}] (READ)
h.health()                              # {"status": ...} (READ)
h.close()                               # idempotent
```

With no config and no Qdrant server anywhere, this works: default
`backend="auto"` falls back to the local store and says so in
`health()` (`status: "degraded"`, `fallback_reason`). Construction is
lazy — nothing is opened or contacted until the first operation.

## Backends and scoring honesty

- **local** — one WAL SQLite file + a maintained inverted term index.
  Default scoring is **TF-IDF cosine: lexical semantics** (weighted
  word overlap), honestly labelled. With `embedder="hashing"` or
  `"sentence-transformers"`, per-document vectors are stored and
  scored by dense cosine.
- **qdrant** — points in a Qdrant collection. Vectors come from the
  configured embedder: `hashing` by default (deterministic,
  stdlib; lexical overlap in vector form), or
  `sentence-transformers` for true neural embeddings.
- **auto** — probe Qdrant once (short timeout) on first use; any
  failure selects local permanently for that object. An explicit
  `backend="qdrant"` instead raises `HuginnBackendError` — loud.

`health()` always reports the effective `backend` and `embedder`.

Identity: upserting the same content in the same category is the same
memory (idempotent). Pass `memory_id=` to align ids with an external
store. `get(id)` / `delete(id)` complete the API. All local reads are
pure; Huginn has **no reinforcing read** — reinforcement is Muninn's
job.

## Ancestor semantics

`analyze_query(query)` — query type, key terms, strategy, hops (the
ancestor's analysis, stopwords and all). `fly(query, max_results,
compress)` → `RetrievalResult` over this store; backend failures come
home as an empty flight with `error` set, never a crash.
`multi_hop_retrieve(...)` chains flights by extracted concepts.
`semantic_search(query, documents, top_k)` — TF-IDF over
caller-supplied documents, the ancestor's signature, stdlib-only.
`get_flight_stats()` summarizes flights. (The ancestor's realm
routing is not carried: realms were game machinery, not a library
contract.)

## Failure behaviour

- Invalid arguments raise `HuginnValidationError` before any write.
- Explicit-backend failures raise `HuginnBackendError`; a missing
  optional dependency raises `HuginnConfigurationError`.
- The local store has Muninn's durability discipline: WAL +
  `synchronous=FULL`, integrity-checked open, recovery from the
  newest verified rolling backup (loud; `health()` shows
  `recovered_from_backup`), and `HuginnStorageError` instead of
  silent data loss. Its term index self-heals on open (orphans
  pruned, doc-frequencies recounted — report in the backend's
  `last_heal_report`).
- Threading: all backends serialize internally; safe concurrently.
  Concurrent openers — several objects on one local store file, in
  one process or across processes — are supported (RM-037,
  `docs/CONCURRENT_OPENERS.md`).

Errors: `HuginnError` → `HuginnValidationError`,
`HuginnConfigurationError`, `HuginnStorageError`, `HuginnBackendError`.
