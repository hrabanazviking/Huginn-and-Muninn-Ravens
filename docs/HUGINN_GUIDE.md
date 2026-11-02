# Huginn — User Guide

Huginn is semantic retrieval: you upsert memories, then search them
by meaning-shaped queries and get scored results back. It runs over
two real backends — its own local SQLite store, or a Qdrant server —
behind one facade, and it is honest about which one it is using and
what its scores actually mean.

- Package: `huginn`, version 1.0.0, MIT licence
- Python: >= 3.11
- Dependencies: none for the core — standard library only. Qdrant and
  neural embeddings are optional extras (see *Extras*)

This guide describes the code as it is. Every signature below is
copied from `huginn/src/huginn/core.py`, `huginn/src/huginn/config.py`,
`huginn/src/huginn/local_backend.py`, `huginn/src/huginn/qdrant_backend.py`,
and `huginn/src/huginn/text.py`.

## Install

```bash
pip install ./huginn                    # local backend, zero infrastructure
pip install './huginn[qdrant]'          # + Qdrant support
pip install './huginn[embeddings]'      # + neural embeddings
```

Importing the package constructs nothing, opens no file, and touches
no network. Construction of a `HuginnMemory` is also cheap and lazy —
see *Backends*.

```python
from huginn import HuginnMemory, HuginnConfig, RetrievalResult
from huginn import analyze_query, semantic_search
```

## Concepts

### Semantic retrieval

You store text memories with a category, importance, tags, and
emotional valence. You search with a query string. You get back a
list of dicts — best first — each with:

```text
id, content, category, importance, tags, emotional_valence, score
```

What `score` means depends on the backend and embedder in effect.
Huginn labels this honestly instead of calling everything "semantic"
— see *Scoring honesty* below. `health()` always names the effective
backend and embedder, so you never have to guess.

### The three backends: `auto`, `local`, `qdrant`

The `backend` config field selects one of three modes:

- **`"local"`** — Huginn's own store: one WAL SQLite file plus a
  maintained inverted term index. Never touches the network.
- **`"qdrant"`** — a Qdrant server (collection of vector points).
  Explicit mode: if anything fails, it raises — see *Failure
  behaviour*.
- **`"auto"`** (the default) — try Qdrant, fall back to local.

How `auto` works, exactly (from `HuginnMemory._ensure_backend`):

1. Nothing is probed at construction. The backend is built **lazily
   on first use** — the first `upsert_memory`, `search`, `get`,
   `delete`, or `health` call.
2. On that first use, Qdrant is probed **once**: the client is built
   and `ping()` calls `get_collections()` against `qdrant_url` with
   the configured `qdrant_timeout` (default 2.0 seconds).
3. If the probe succeeds, this object uses Qdrant.
4. If **anything** fails — no server, connection refused, timeout, or
   the `qdrant-client` package not installed — the object falls back
   to the local backend **permanently for this object**. It does not
   re-probe on later calls.
5. The reason is recorded and reported: `health()` returns
   `status="degraded"` with a `fallback_reason` string of the form
   `"qdrant unavailable: <underlying error>"`.

A missing Qdrant in `auto` mode never crashes the caller. A **new**
`HuginnMemory` object probes again for itself — the fallback is
per-object, not global.

With no config and no Qdrant server anywhere, `HuginnMemory()` works:
it lands on the local backend and says so in `health()`. That is the
contract the defaults are built for.

### Scoring honesty

This section states plainly what each scoring mode is — and is not.

- **Local backend, default embedder `"tfidf"`** — the score is
  **TF-IDF cosine**: *lexical* semantics. It is weighted word overlap:
  tokenize (lowercase, stopwords and 1-character tokens removed),
  weight terms by term frequency × smoothed inverse document
  frequency, and take the cosine between the query vector and the
  document vector. It is genuinely useful, but it does not know that
  two different words mean similar things. Only documents sharing at
  least one query term are candidates, and only positive scores are
  returned.
- **The `hashing` embedder** — deterministic feature hashing. Each
  token is hashed (SHA-256) into a fixed-dimension bucket with a sign;
  counts accumulate signed and the vector is L2-normalized. Cosine over
  these vectors is lexical overlap in vector form — deterministic (same
  text, same vector, on any machine, forever), stdlib-only, and still
  **not** neural. In local embedder mode, stored per-document vectors
  are scored by dense cosine with a linear scan. On the Qdrant
  backend, hashing is the default embedder.
- **`sentence-transformers`** — the **only neural embedder**. It loads
  a real sentence-transformers model (default `all-MiniLM-L6-v2`) and
  scores by dense cosine over its embeddings. It requires the
  `embeddings` extra.
- **NOT PROVEN:** the `sentence-transformers` path was **not** proven
  in the build verification, because the extra was not installed in
  the verification environment. The hashing embedder path **was**
  proven end-to-end. See `docs/BUILD_NOTES_2026-10-30.md` §5.
- **NOT PROVEN:** a live Qdrant **server** round-trip. The Qdrant
  backend is proven against a faithful fake client placed in
  `sys.modules` (round trip, filters, derived ids, error roads). No
  Qdrant server existed in the verification environment, so no claim
  is made about a real server.

Two more scoring facts from the code:

- With a Qdrant backend, `embedder="tfidf"` cannot be used directly —
  Qdrant needs fixed-space vectors — so it resolves to `"hashing"`,
  and `health()` reports the effective embedder honestly as
  `"hashing"`.
- Scores from different backends/embedders are not comparable to each
  other. Always read `health()["embedder"]` and
  `health()["backend"]` alongside any score.

### Identity and idempotency

- Local backend: a memory's identity is `(content_hash, category)`,
  where the hash is over `category + "\x00" + content`. Upserting the
  same content in the same category updates the same document and
  returns the same id. The same content in a different category is a
  different memory.
- Qdrant backend: a point's id is the caller's `memory_id` when given,
  otherwise derived deterministically from the content hash (the first
  16 hex digits as a big integer), so re-upserting the same memory
  targets the same point.
- Pass `memory_id=` to `upsert_memory` to align Huginn's id with an
  external store (Bifröst merges backends by id).
  - Local backend detail: if the given `memory_id` already exists, the
    upsert updates that document (even if its content changes). If the
    id is free but the same content already lives at a different id,
    the upsert raises `HuginnValidationError` telling you to upsert
    there instead — it will not silently duplicate or move the memory.

### Read honesty

`search`, `get`, and `fly` are pure reads. **Huginn has no reinforcing
read at all.** The `search` method has no `reinforce` parameter —
reinforcement (activation logging, wiring) is Muninn's job, not
Huginn's. Searching never changes the store.

### The local store's index and self-healing

The local backend keeps three supporting tables beside `documents`:
`doc_terms` (the inverted index: per-document term frequencies),
`corpus_stats` (document frequency per term), and `doc_vectors`
(per-document vectors, only in embedder mode). On open, a heal pass
prunes orphan term/vector rows whose document is gone and recounts
every term's document frequency from the index; the report is kept on
the backend as `last_heal_report`
(`{"orphan_terms_pruned", "orphan_vectors_pruned", "doc_freq_fixed"}`).

Durability matches Muninn's discipline: WAL + `synchronous=FULL`,
integrity-checked open, rolling backups — see *Failure behaviour*.

## Usage walk-through

The examples use `backend="local"` with a temporary file so they run
anywhere with no server and no extras. The API is identical on the
other backends.

### Create a `HuginnMemory`

```python
import tempfile
from pathlib import Path

from huginn import HuginnMemory
from huginn.config import HuginnConfig

tmp = Path(tempfile.mkdtemp())
h = HuginnMemory(HuginnConfig(
    backend="local",
    local_db_path=str(tmp / "huginn.db"),
))
```

The contract construction — exactly what Bifröst calls — is:

```python
h2 = HuginnMemory(config=None)   # == HuginnMemory()
h2.close()
```

That uses all defaults: `backend="auto"`, local path
`~/.hermes/memory/huginn_local.db`. Keyword overrides also work, with
or without a config object:

```python
h3 = HuginnMemory(backend="local", local_db_path=str(tmp / "h3.db"))
h3.close()
```

Construction is lazy: no file is opened and no server is contacted
until the first operation. `close()` is idempotent, and the object is
a context manager:

```python
with HuginnMemory(HuginnConfig(backend="local",
                               local_db_path=str(tmp / "ctx.db"))) as hh:
    hh.upsert_memory("stored inside a with block")
```

### Upsert memories: `upsert_memory`

```python
upsert_memory(content, category="general", importance=5, tags=None,
              emotional_valence=0.0, *, memory_id=None) -> int
```

`content` must be a non-empty string (after stripping). `importance`
must be an int in [1, 10]; `emotional_valence` a number in [−1, 1];
`memory_id`, when given, an int >= 0 — violations raise
`HuginnValidationError` before any write. Returns the memory's id.

```python
raven_id = h.upsert_memory(
    "Ravens fly out at dawn and return with news at dusk",
    category="lore",
    importance=7,
    tags=["ravens", "dawn"],
    emotional_valence=0.3,
)
wolf_id = h.upsert_memory(
    "Wolves hunt in packs across the winter hills",
    category="lore",
    importance=6,
)
oak_id = h.upsert_memory(
    "The old oak marks the boundary of the farm",
    category="places",
    importance=5,
)
```

Idempotency — the same content in the same category is the same
memory:

```python
same = h.upsert_memory(
    "Ravens fly out at dawn and return with news at dusk",
    category="lore",
    importance=8,   # fields update in place
    tags=["ravens", "dawn"],
    emotional_valence=0.3,
)
assert same == raven_id
```

Note: an upsert writes the fields you pass. Omitting `tags` or
`emotional_valence` on a re-upsert writes their defaults (`[]` and
`0.0`) over the stored values — pass them again if you want to keep
them.

Aligning ids with an external store, with `memory_id=`:

```python
aligned = h.upsert_memory(
    "A memory owned by another store",
    category="external",
    memory_id=4242,
)
assert aligned == 4242
```

### Search: `search`

```python
search(query_text, limit=10, category=None, min_importance=1)
    -> list[dict]
```

Pure read. `limit` is clamped to 1..1000. `min_importance` must be an
int (it acts as a filter only when > 1). Results are best first, each
a dict with `id, content, category, importance, tags,
emotional_valence, score`.

```python
hits = h.search("ravens at dawn", limit=5)
print(hits[0]["id"])       # raven_id
print(hits[0]["content"])  # "Ravens fly out at dawn and return ..."
print(hits[0]["score"])    # a float in (0, 1] — TF-IDF cosine here
```

Filters:

```python
lore_only = h.search("winter hills", category="lore")
important = h.search("ravens", min_importance=7)
print([r["id"] for r in lore_only])   # [wolf_id]
print([r["id"] for r in important])   # [raven_id] (importance now 8)
```

A blank query is an honest empty result, not an error:

```python
assert h.search("") == []
assert h.search("   ") == []
```

A non-string query raises `HuginnValidationError`.

### Get and delete

```python
doc = h.get(raven_id)
# {"id": raven_id, "content": ..., "category": "lore",
#  "importance": 8, "tags": ["ravens", "dawn"],
#  "emotional_valence": 0.3}   — note: no "score" key on get()
print(h.get(999999))          # None

print(h.delete(oak_id))       # True — something was removed
print(h.delete(oak_id))       # False — already gone
```

Both validate the id (`int`, >= 0, bools rejected) and raise
`HuginnValidationError` otherwise. `get` is a pure read; `delete` is
a write.

### Health: `health` and `stats`

```python
health() -> dict
```

`health()` never raises for backend trouble. On the local backend:

```python
info = h.health()
# {"status": "healthy",
#  "backend": "local",
#  "db_path": "...",
#  "integrity": "ok",                # from PRAGMA quick_check
#  "recovered_from_backup": False,
#  "documents": 3,                   # raven, wolf, and the aligned memory;
#                                    # the oak was deleted above
#  "vocabulary": <distinct indexed terms>,
#  "file_permissions_warning": None,  # RM-042: a warning string when an
#                                     # existing local store file is looser
#                                     # than 0600 (see FILE_PERMISSIONS.md)
#  "embedder": "tfidf",
#  "backend_configured": "local"}
```

The facade adds `embedder` and `backend_configured` to whatever the
backend itself reports. If the local store's integrity check fails,
the backend reports `status="degraded"`.

Degraded status — the `auto` fallback. This example needs no server,
because there is (presumably) no Qdrant at the default URL and, in a
core-only install, no `qdrant-client` either:

```python
auto = HuginnMemory(HuginnConfig(
    backend="auto",
    local_db_path=str(tmp / "auto.db"),
))
auto.upsert_memory("Anything, to force the first-use probe")
info = auto.health()
print(info["status"])           # "degraded"
print(info["backend"])          # "local"
print(info["backend_configured"])  # "auto"
print(info["fallback_reason"])  # "qdrant unavailable: <reason>"
auto.close()
```

If Qdrant had answered the probe, `status` would be `"healthy"`,
`backend` would be `"qdrant"`, and there would be no
`fallback_reason`. On a Qdrant backend, `health()` reports
`{"status": "healthy", "backend": "qdrant", "qdrant_url": ...,
"collection": ..., "documents": ...}` plus the facade's `embedder`
and `backend_configured`.

If an explicitly configured backend fails, `health()` returns instead:

```python
# {"status": "unhealthy", "backend_configured": ...,
#  "error": "...", "error_type": "HuginnBackendError"}  (for example)
```

`stats()` exists as well and simply returns the same dict as
`health()`.

### Query analysis: `analyze_query`

Available both as a method and as a module-level function with the
same behaviour:

```python
analyze_query(query) -> dict
# {"query_type", "key_terms", "strategy", "recommended_hops", "word_count"}
```

- `query_type` is one of `"factual"` (default), `"explanatory"`
  (query contains why/how/explain), `"search"` (find/search/where),
  `"enumeration"` (list/all/show), or `"comparison"`
  (compare/difference/vs). The checks are an `if`/`elif` chain in
  that order — explanatory, search, enumeration, comparison — so the
  first matching branch wins. Note the tests are substring checks
  against the whole lowercased query, not whole-word matches.
- `key_terms` are the query's words with the ancestor's stopword set
  removed and words of length <= 2 dropped. Note: this analysis splits
  on whitespace and does not strip punctuation.
- `strategy` / `recommended_hops`: comparison → `"multi_hop"`, 2;
  enumeration → `"broad"`, 1; more than 3 key terms → `"focused"`, 1;
  otherwise `"standard"`, 1.
- The query is stripped and truncated to 1000 characters first.

```python
from huginn import analyze_query

print(analyze_query("compare ravens and wolves"))
# {"query_type": "comparison",
#  "key_terms": ["compare", "ravens", "and", "wolves"],
#  "strategy": "multi_hop", "recommended_hops": 2, "word_count": 4}

print(h.analyze_query("why do ravens return at dusk")["query_type"])
# "explanatory"
```

### Flights: `fly` and `RetrievalResult`

```python
fly(query, max_results=5, compress=True) -> RetrievalResult
```

A flight is a search wrapped in the ancestor's result shape. It is a
pure read. `max_results` is clamped to 1..50.

```python
from huginn import RetrievalResult

flight = h.fly("ravens at dawn", max_results=3)
print(isinstance(flight, RetrievalResult))  # True
print(flight.query)                         # "ravens at dawn"
print(flight.results)                       # list of result dicts
print(flight.relevance_scores)              # [score per result]
print(flight.source_realm)                  # "huginn:local"
print(flight.retrieval_time)                # seconds, float
print(flight.compressed)                    # True
print(flight.error)                         # None on success
print(flight.timestamp)                     # datetime (UTC)
```

With `compress=True` (the default), each result is compressed the
ancestor's way: string values longer than 200 characters are truncated
to 200 characters plus `"..."`, and list values longer than 5 items
are cut to the first 5. Pass `compress=False` for the raw result
dicts.

On backend failure, a flight does not raise: it comes home empty with
`error` set to the failure message and `results == []`. (Validation
errors are not flights — a non-string query, for example, is handled
before any backend call; the `error` field covers `HuginnError`s from
the search itself.)

Flights are remembered by the object (history is trimmed to the most
recent 50 once it passes 100 entries) for `get_flight_stats()`.

### Multi-hop retrieval: `multi_hop_retrieve`

```python
multi_hop_retrieve(initial_query, hop_count=2,
                   max_results_per_hop=3) -> list[RetrievalResult]
```

`hop_count` is clamped to 1..5. Each hop flies with the current query;
the concepts extracted from its results (content words longer than 4
characters, alphabetic, sorted, first 10 kept) seed the next query as
`f"{initial_query} {' '.join(concepts[:3])}"`. The chain stops early
when a hop returns no results or no concepts.

```python
flights = h.multi_hop_retrieve("ravens dawn", hop_count=2,
                               max_results_per_hop=2)
print(len(flights))              # 1 or 2, depending on what hop 1 found
print(flights[0].source_realm)   # "huginn:local"
```

### Search over your own documents: `semantic_search`

A standalone module function — no store involved. It runs TF-IDF
cosine over caller-supplied documents using the same stdlib machinery
as the local backend:

```python
from huginn import semantic_search

semantic_search(query, documents, top_k=3) -> list[tuple[int, float]]
```

Returns `(index, score)` pairs, best first, positive scores only,
at most `top_k` (clamped to 1..len(documents)). An empty document
list returns `[]`.

```python
docs = [
    "Ravens fly out at dawn",
    "Wolves hunt in packs",
    "Ravens return at dusk with news",
]
print(semantic_search("ravens dawn", docs, top_k=2))
# [(0, <score>), (2, <score>)] — indices into `docs`, best first
```

This is lexical TF-IDF scoring, with the same honesty label as the
local backend's default.

### Flight statistics: `get_flight_stats`

```python
print(h.get_flight_stats())
# {"total_flights": 3,
#  "total_results_retrieved": ...,
#  "total_flight_time": ...,
#  "avg_flight_time": ...,
#  "avg_results_per_flight": ...,
#  "realm_visits": {"huginn:local": 3}}
```

Before any flight, it returns exactly `{"total_flights": 0}`.
Pure read.

### Closing

```python
h.close()
h.close()   # no-op the second time
```

Using a closed object raises `HuginnBackendError`
("HuginnMemory is closed") on the next operation.

## Configuration — every `HuginnConfig` field

From `huginn/src/huginn/config.py`. All fields are validated in
`__post_init__` at construction; a bad value raises
`HuginnConfigurationError` immediately.

```python
from huginn.config import HuginnConfig
config = HuginnConfig()   # all defaults — the Bifröst contract shape
```

| Field | Type | Default | Meaning | Validation |
|---|---|---|---|---|
| `backend` | `str` | `"auto"` | `"auto"` probes Qdrant once, lazily, and falls back to local permanently for that object on any failure (reason in `health()`). `"local"` never touches the network. `"qdrant"` is explicit — failures raise `HuginnBackendError` | Must be one of `("auto", "local", "qdrant")` |
| `qdrant_url` | `str` | `"http://localhost:6333"` | Qdrant server URL | Must be a non-empty string |
| `qdrant_api_key` | `str \| None` | `None` | Optional Qdrant API key, passed to the client | No validation in the code |
| `collection_name` | `str` | `"huginn_memories"` | Qdrant collection for memories. Created on first use if missing, with cosine distance and vector size = the embedder's dimension | Must be a non-empty string |
| `local_db_path` | `str` | `"~/.hermes/memory/huginn_local.db"` (`DEFAULT_LOCAL_DB_PATH`) | SQLite file for the local backend. `~` is expanded (`resolved_local_path()`); the parent directory is created on open | Must be a non-empty string |
| `embedder` | `str` | `"tfidf"` | `"tfidf"` — the local backend's native lexical TF-IDF scoring, no vectors. `"hashing"` — deterministic feature-hashing vectors (stdlib). `"sentence-transformers"` — neural embeddings, needs the `embeddings` extra. On a Qdrant backend, `"tfidf"` resolves to `"hashing"` (reported in `health()`) | Must be one of `("tfidf", "hashing", "sentence-transformers")` |
| `vector_dim` | `int` | `384` | Hashing-embedder dimension, and the Qdrant collection vector size when the hashing embedder is used. (A sentence-transformers embedder reports its own model dimension instead) | Must be >= 8 |
| `st_model` | `str` | `"all-MiniLM-L6-v2"` | sentence-transformers model name, used only when `embedder="sentence-transformers"` | No validation in the code |
| `qdrant_timeout` | `float` | `2.0` | Seconds — passed to the Qdrant client as its timeout; this is what bounds the `auto` probe and Qdrant calls | Must be > 0 |
| `busy_timeout_ms` | `int` | `5000` | SQLite busy timeout for the local store | Must be >= 0 |
| `backup_keep` | `int` | `3` | Rolling backup generations kept beside the local store. `0` disables backups — and therefore disables corruption recovery | Must be >= 0 |
| `auto_backup` | `bool` | `True` | Take/refresh a rolling backup of the local store on open, when it changed since the last backup | No range check — used as a boolean flag |
| `max_content_bytes` | `int` | `1048576` | Oversize ceiling (RM-027): one memory's content, in UTF-8 bytes; above it `upsert_memory` is refused with a typed error in the facade, before any backend is touched (see `docs/OVERSIZE_POLICY.md`) | Must be >= 1 |
| `strict_path_safety` | `bool` | `False` | Path safety (RM-041, threat TH-02): when `True`, opening the **local** store refuses a symlinked store path (the file or any parent component) and a store whose parent directory is world-writable, with a typed storage error before anything is created — for locked-down deployments. Default `False` keeps the recorded behaviour (paths never symlink-resolved, parents unchecked; see `docs/PATH_SAFETY.md`). The Qdrant backend has no local file | No range check — used as a boolean flag |
| `debug_log_content` | `bool` | `False` | Log redaction (RM-044, threat TH-05): when `True`, the facade's `upsert_memory`/`search` may emit memory content in log records at DEBUG level only — the sole road by which content ever reaches a log. Default `False`: no log record at any level carries memory content (see `docs/LOG_REDACTION.md`) | No range check — used as a boolean flag |

Example — local store with hashing vectors:

```python
config = HuginnConfig(
    backend="local",
    local_db_path=str(tmp / "vectors.db"),
    embedder="hashing",
    vector_dim=256,
)
hv = HuginnMemory(config)
hv.upsert_memory("Ravens fly out at dawn")
print(hv.health()["embedder"])   # "hashing"
print([r["id"] for r in hv.search("ravens dawn")])
hv.close()
```

```python
from huginn import HuginnConfigurationError

try:
    HuginnConfig(backend="sometimes")
except HuginnConfigurationError as exc:
    print(exc)  # backend must be one of ('auto', 'local', 'qdrant')
```

## Extras

The core installs with no dependencies. Two optional extras exist in
`huginn/pyproject.toml`:

| Extra | Install | Adds | Needed for |
|---|---|---|---|
| `qdrant` | `pip install './huginn[qdrant]'` | `qdrant-client>=1.9,<2` | Any Qdrant backend use, including a successful `auto` probe |
| `embeddings` | `pip install './huginn[embeddings]'` | `sentence-transformers>=2.2,<6` | `embedder="sentence-transformers"` only |

They combine: `pip install './huginn[qdrant,embeddings]'` gives a
Qdrant backend with neural embeddings.

Honesty notes on the extras:

- Without the `qdrant` extra, `backend="auto"` still works — the
  missing package is one of the probe failures that falls back to
  local, with the reason in `health()`.
- Without the `qdrant` extra, explicit `backend="qdrant"` raises
  `HuginnConfigurationError` (a packaging fact, not a server failure)
  — see below.
- The `sentence-transformers` path is **NOT PROVEN** in the build
  verification (the extra was not installed there); the hashing path
  is proven. See *Scoring honesty*.

## Failure behaviour

Errors are typed. The one designed exception is `backend="auto"`,
where a missing Qdrant is a configuration fact answered by the local
backend and reported in `health()` — never by raising into the caller.

```python
from huginn import (
    HuginnError,                # base class for all deliberate errors
    HuginnValidationError,      # bad caller argument (also a ValueError)
    HuginnConfigurationError,   # bad config, or a missing optional dependency (also a ValueError)
    HuginnStorageError,         # local store could not be opened/read/written/healed
    HuginnBackendError,         # the selected backend failed at operation time
)
```

### Validation before any write

Invalid arguments raise `HuginnValidationError` before any write:

- `upsert_memory` with content that is not a string, or is empty /
  whitespace-only; `importance` not an int in [1, 10];
  `emotional_valence` not a number in [−1, 1]; `memory_id` not an
  int >= 0.
- The local backend's `memory_id` clash: the id is free but the same
  content already lives at another id (the error names that id).
- `search` with a non-string query, or a non-int `min_importance`.
- `get` / `delete` with an id that is not an int >= 0.

```python
from huginn import HuginnValidationError

try:
    h.upsert_memory("   ")
except HuginnValidationError as exc:
    print(exc)  # content must be a non-empty string
```

A blank (but valid) query to `search` is **not** an error: it returns
`[]` honestly.

### Explicit `backend="qdrant"` raises loudly

With `backend="qdrant"` there is no fallback. The first operation
builds the backend and pings the server:

- Server unreachable (or any ping failure) → `HuginnBackendError`,
  with the URL and the underlying error in the message.
- `qdrant-client` not installed → `HuginnConfigurationError` with the
  install instruction (`pip install 'huginn[qdrant]'`). This stays a
  configuration error even when raised during `ping()` — a missing
  package is a packaging fact, not a server failure.
- Later operation failures (upsert, search, get, delete, count, …)
  are likewise wrapped as `HuginnBackendError`.

```python
from huginn import HuginnBackendError

dead = HuginnMemory(HuginnConfig(
    backend="qdrant",
    qdrant_url="http://localhost:6399",   # nothing listening there
))
try:
    dead.upsert_memory("this cannot land")
except HuginnBackendError as exc:
    print(exc)  # Qdrant at http://localhost:6399 unreachable: ...
```

`health()` is the exception to "raises": it catches `HuginnError`s
and returns the `"unhealthy"` dict described above, so health checks
never crash the caller.

And `fly()` is the other designed soft landing: backend failures come
home as an empty flight with `error` set, instead of raising.

### Missing optional dependencies raise `HuginnConfigurationError`

Both optional dependencies fail the same typed way, at the point of
use, with the install command in the message:

- `embedder="sentence-transformers"` without the `embeddings` extra →
  `HuginnConfigurationError`:
  `embedder='sentence-transformers' needs the 'embeddings' extra: pip install 'huginn[embeddings]'`.
  This is raised when the embedder is constructed — which, because
  backend construction is lazy, means on the first operation, not at
  `HuginnMemory(...)` construction.
- `backend="qdrant"` (explicit, or the `auto` probe) without the
  `qdrant` extra → `HuginnConfigurationError`:
  `backend='qdrant' needs the 'qdrant' extra: pip install 'huginn[qdrant]'`.
  In `auto` mode this error is caught by the fallback like any other
  probe failure, and its text becomes part of the `fallback_reason`.

An unknown embedder name cannot reach this code from a config —
`HuginnConfig` rejects any `embedder` outside
`("tfidf", "hashing", "sentence-transformers")` at construction.

### Local store corruption recovery

The local backend uses the same store machinery discipline as Muninn:

- WAL mode + `synchronous=FULL`: a `kill -9` mid-write loses at most
  the uncommitted transaction.
- On open, `PRAGMA quick_check` verifies the store. If the main file
  fails (or is not a database at all), the newest rolling backup
  (`<db>.bak-1` … `.bak-N`, made via SQLite's backup API) that itself
  passes `quick_check` is restored over it, loudly. `health()` then
  shows `"recovered_from_backup": True`.
- If no backup verifies, opening raises `HuginnStorageError` — the
  local store never silently starts empty over lost data.
- Rolling backups are refreshed on open when the store changed (with
  `auto_backup=True`), up to `backup_keep` generations. Keep
  `backup_keep >= 1` (default 3) on any store you care about.
- Separately, the local index self-heals on every open (orphan rows
  pruned, document frequencies recounted — see *Concepts*).

Operations on a closed local backend raise `HuginnStorageError`;
operations on a closed `HuginnMemory` raise `HuginnBackendError`.

A local write that fails in the storage layer — for example
against a full disk — surfaces as `HuginnStorageError` naming the
operation (`huginn write failed during upsert: database or disk
is full`), with the failed call rolled back so no partial write
survives; the store stays open and consistent afterwards (RM-029,
see `docs/DISK_FULL.md`).

A local store whose location is read-only — a read-only
filesystem, a read-only directory, or a store file marked
read-only — is refused *on open* with `HuginnStorageError`
(`huginn store {path} is read-only and cannot be opened for
writing`), immediately, before any connection or backup-restore
attempt, and the failed open touches nothing; `health()` reports
the refusal as `unhealthy` with that error named. There is no
read-only mode (RM-030, see `docs/READONLY_FILESYSTEM.md`).

A local store locked by another process is awaited up to
`busy_timeout_ms`; if the lock is still held when the timeout
expires, the open fails with `HuginnStorageError`
(`huginn store {path} is locked by another process (busy timeout
{ms} ms expired)`) — reported by `health()` as `unhealthy` with
that error named — and a write on an already-open store fails
with the contention form of the write error (`huginn write
failed during {operation}: store is locked by another process
(busy timeout expired)`), rolled back like any failed write.
Contention is never mistaken for corruption, and pure reads
proceed against a WAL snapshot while a writer holds the lock
(RM-031, see `docs/LOCKED_STORE.md`).

Partial file states are defined too (local backend): a main
store truncated to zero bytes takes the corruption road
(restore from a verified backup, else the typed refusal)
instead of opening as a silently empty store; a non-empty
write-ahead log left without its main file restores a
verified backup or raises `huginn store {path} has a
write-ahead log but no main file and no rolling backup
verified; refusing to start empty over lost memory` —
reported by `health()` as `unhealthy` with that error named;
and a `.bak-tmp` left behind by a killed backup is removed on
open and is never read as a store or a restore candidate
(RM-032, see `docs/PARTIAL_FILE_STATES.md`).

A path that is not a database file at all is refused before
anything else (local backend): a directory at the store path
raises `huginn store {path} is a directory, not a database
file; refusing to open` — with or without a backup beside
it, and the directory is never deleted or replaced to make
room for a restore — and any other non-regular file raises
`huginn store {path} is not a regular file; refusing to
open`; `health()` reports both as `unhealthy` with the error
named. A text file is a corrupt store and takes the
corruption road above (RM-033, see
`docs/NON_DATABASE_FILES.md`).

Text in any script is welcome and is stored verbatim — RTL
scripts, emoji ZWJ sequences, combining marks, astral-plane
characters — with no normalisation: the decomposed and
precomposed spellings of a word are different documents. The
one refused shape is a **lone surrogate** (an unpaired
U+D800–U+DFFF code point, which UTF-8, JSON and SQLite
cannot hold honestly): `upsert_memory`'s content, category
and tags, every query-shaped argument, and
`semantic_search`'s documents are checked in the facade,
before any backend is touched, and refused with `… must
not contain lone surrogates` (RM-034, see
`docs/UNICODE_GAUNTLET.md`). Inside `fly`, the refusal
comes home as an error flight naming it, as flights do.

Adversarial tag shapes are bounded too: a tag element may
nest at most 100 containers deep — deeper is refused with
`tags nesting depth exceeds maximum of 100`, checked
iteratively in the facade before the `str()` coercion whose
`repr` used to overflow the stack — and the cleaned tags
list, in its JSON form, must fit `max_content_bytes`, the
ceiling that bounds content. A self-referential tag element
still renders through `repr`'s ellipsis (RM-036, see
`docs/ADVERSARIAL_TAGS_METADATA.md`).

### Threading

All backends serialize internally with a lock, and `HuginnMemory`
serializes backend construction; objects are safe under concurrent
use from multiple threads.

### Concurrent openers

Two or more objects may hold the same *local* store file at once —
in one process or across processes (RM-037,
`docs/CONCURRENT_OPENERS.md`). Committed writes through one object
are visible through the others at once and never lose each other;
ordinary reads and writes are serialized by SQLite (WAL +
`busy_timeout_ms`, with the RM-031 typed contention error on
expiry), while the open-time duties and every backup are serialized
per store by a coordination lock (in-process lock + `flock` on the
sibling `<db_path>.open-lock` file). Closing one object leaves the
others working. One limit to know: the RM-012 timestamp guard is
per object, so `updated_at` values from *different* objects may
repeat or invert by microseconds. On the Qdrant backend there is
no local file to coordinate: concurrent objects are concurrent
clients of one server (live round-trip still NOT PROVEN).

## Quick reference

| Method / function | Kind | Returns |
|---|---|---|
| `HuginnMemory(config=None, **overrides)` | lazy construction | object |
| `upsert_memory(content, category="general", importance=5, tags=None, emotional_valence=0.0, *, memory_id=None)` | write | `int` id |
| `search(query_text, limit=10, category=None, min_importance=1)` | pure read | `list[dict]` with `score` |
| `get(memory_id)` | pure read | `dict \| None` (no `score`) |
| `delete(memory_id)` | write | `bool` |
| `health()` | pure read, never raises for backend trouble | `dict` |
| `stats()` | pure read | same dict as `health()` |
| `analyze_query(query)` (method and module function) | pure | analysis `dict` |
| `fly(query, max_results=5, compress=True)` | pure read | `RetrievalResult` |
| `multi_hop_retrieve(initial_query, hop_count=2, max_results_per_hop=3)` | pure read | `list[RetrievalResult]` |
| `semantic_search(query, documents, top_k=3)` (module function) | pure | `list[tuple[int, float]]` |
| `get_flight_stats()` | pure read | `dict` |
| `close()` | — | idempotent |
