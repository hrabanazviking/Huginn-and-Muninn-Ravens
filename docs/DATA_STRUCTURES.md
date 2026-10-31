# Data structures — muninn + huginn

The whole data structure of both packages, in one place: every
SQLite table with its columns, types, defaults, keys and indexes;
the Qdrant point/payload shape; the on-disk file layout; the
in-memory structures; the exact dict shapes returned by every public
method; and the full error hierarchy of both packages.

Every entry traces to the sources: `SCHEMA_SQL` in
`muninn/src/muninn/core.py` and `huginn/src/huginn/local_backend.py`,
the backend code in `huginn/src/huginn/qdrant_backend.py`, the text
machinery in `huginn/src/huginn/text.py`, the store machinery in both
`_db.py` files, both `config.py` and `errors.py` files, both
`INTERFACE.md` files, and `docs/BUILD_NOTES_2026-10-30.md`. Where the
build notes and the code disagree, the code is documented (see §10).

Conventions used in the tables below: types are the SQLite declared
types verbatim; "nullable" means the column declaration carries no
`NOT NULL`; timestamps are TEXT holding ISO-8601 UTC strings produced
by each module's `_now()` (`datetime.now(timezone.utc).isoformat()`),
unless a row says otherwise.

---

## 1. Muninn — SQLite tables

Source: `SCHEMA_SQL` in `muninn/src/muninn/core.py`, applied
idempotently (`CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT
EXISTS`) at every open by `open_store` in `muninn/src/muninn/_db.py`.

Default file: `~/.hermes/memory/muninn_hebbian.db`
(`MuninnConfig.db_path`; `~` expanded by `resolved_path()`).

The schema declares no `FOREIGN KEY` clauses in any table, even
though connections are opened with `PRAGMA foreign_keys=ON`.
Referential discipline is maintained by the API and the heal pass,
not by the database.

### 1.1 `meta`

| Column | Type | Constraints |
|---|---|---|
| `key` | TEXT | PRIMARY KEY |
| `value` | TEXT | NOT NULL |

Key/value store for store-level facts. The one key the code writes
is `schema_version`, set to `"1"` (`SCHEMA_VERSION` in
`muninn/_db.py`) by `INSERT OR REPLACE` at every open.

### 1.2 `nodes`

One row per stored memory node.

| Column | Type | Constraints / default |
|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `content` | TEXT | NOT NULL. The stored text (see encoding note below) |
| `content_is_json` | INTEGER | NOT NULL DEFAULT 0. 1 when `content` holds a JSON serialization of a non-string value, 0 when it holds a plain string |
| `content_hash` | TEXT | NOT NULL. See hash note below |
| `path` | TEXT | NOT NULL DEFAULT `''`. Hierarchical path |
| `category` | TEXT | NOT NULL DEFAULT `'general'`. The node's type (the `MemoryNode` dataclass calls this field `memory_type`) |
| `importance` | INTEGER | NOT NULL DEFAULT 5. Validated to 1–10 on write |
| `emotional_valence` | REAL | NOT NULL DEFAULT 0.0. Validated to [−1, 1] on write |
| `tags` | TEXT | NOT NULL DEFAULT `'[]'`. JSON array of strings (lowercased, stripped, each truncated to 64 chars on write) |
| `metadata` | TEXT | NOT NULL DEFAULT `'{}'`. JSON object serialized with sorted keys |
| `access_count` | INTEGER | NOT NULL DEFAULT 0. Incremented by activation (only when the activated id is a node in this store) |
| `created_at` | TEXT | NOT NULL. ISO-8601 UTC |
| `updated_at` | TEXT | NOT NULL. ISO-8601 UTC |

Keys and indexes:

- PRIMARY KEY: `id` (AUTOINCREMENT — ids are never reused).
- UNIQUE constraint: `UNIQUE(content_hash, category, path)` — this
  is the idempotency mechanism for `remember`/`store`: re-storing
  the same content under the same category and path selects back the
  existing row's id instead of inserting a duplicate.
- No other explicit indexes are declared on this table.

Content encoding (`_content_payload` in `muninn/core.py`):

- String content: stored verbatim, `content_is_json = 0`, hash =
  `sha256(("s:" + content).encode()).hexdigest()`.
- Non-string content: stored as `json.dumps(content, sort_keys=True)`,
  `content_is_json = 1`, hash =
  `sha256(("j:" + text).encode()).hexdigest()`. Non-JSON-serializable
  content raises `MuninnValidationError`. `content=None` is rejected
  by `remember` before this.
- On read (`_row_to_node`), JSON content is `json.loads`-ed back to
  the original value.

### 1.3 `activation_log` — CONTRACTUAL (BUILD_NOTES §1.2)

Append-only log of activations. One row per activation event.

| Column | Type | Constraints / default |
|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `memory_id` | INTEGER | NOT NULL. The activated id — need not be a node in `nodes` (cross-store ids are legal) |
| `activated_at` | TEXT | NOT NULL. ISO-8601 UTC |
| `emotional_valence` | REAL | NOT NULL DEFAULT 0.0 |
| `source` | TEXT | NOT NULL DEFAULT `'api'`. Free-form provenance string; `activate`/`activate_batch` take it as a parameter, and `retrieve(touch=True)` logs with source `"retrieve:touch"` |

Keys and indexes:

- PRIMARY KEY: `id`.
- Index: `idx_activation_memory ON activation_log(memory_id)`.

Contract notes (BUILD_NOTES §1.2): Bifröst inserts
`(memory_id, activated_at, emotional_valence, source)` by column
name; Hermes' Slice 87 probe requires this table to exist; Bifröst
also reads `SELECT COUNT(*) as cnt FROM activation_log WHERE
memory_id = ?` through `HebbianMemory._get_conn()`. The log is a
log: `forget()` does **not** delete a forgotten id's log rows.

### 1.4 `hebbian_connections` — CONTRACTUAL (BUILD_NOTES §1.2)

Hebbian wiring. Each logical connection is **two directed rows**,
`(a, b)` and `(b, a)`, kept symmetric by the API (see
`docs/ARCHITECTURE.md` §4.3).

| Column | Type | Constraints / default |
|---|---|---|
| `memory_a_id` | INTEGER | NOT NULL. Source end of this directed row. Part of PK |
| `memory_b_id` | INTEGER | NOT NULL. Target end of this directed row. Part of PK |
| `strength` | REAL | NOT NULL DEFAULT 0.0. In [0, 1] by construction of the update rule |
| `co_activation_count` | INTEGER | NOT NULL DEFAULT 0. Inserted as 1 on first wiring, incremented per co-activation |
| `consolidated` | INTEGER | NOT NULL DEFAULT 0. 0/1 flag (exposed as `bool` in `get_associations`) |
| `created_at` | TEXT | NOT NULL. ISO-8601 UTC of first wiring |
| `last_coactivated_at` | TEXT | Nullable. ISO-8601 UTC of the most recent co-activation |

Keys and indexes:

- PRIMARY KEY: `(memory_a_id, memory_b_id)` — so lookups by
  `memory_a_id` (the bridge's directional boost query) use the PK.
- Index: `idx_conn_b ON hebbian_connections(memory_b_id)` — covers
  the reverse direction and the `OR memory_b_id = ?` deletes in
  `forget`/backpressure.

Contract columns (BUILD_NOTES §1.2): `memory_a_id`, `memory_b_id`,
`strength`, `co_activation_count` — Bifröst's boost query selects
exactly these.

### 1.5 `node_activation`

Per-id activation counters and confidence. One row per id that has
ever been activated (the id need not be a node in `nodes`).

| Column | Type | Constraints / default |
|---|---|---|
| `memory_id` | INTEGER | PRIMARY KEY |
| `total_activations` | INTEGER | NOT NULL DEFAULT 0. Inserted as 1 on first activation |
| `confidence` | REAL | NOT NULL DEFAULT 1.0. Restored toward 1.0 per activation; faded by `decay()` |
| `last_activated_at` | TEXT | Nullable. ISO-8601 UTC |

This table is a maintained cache of the log: the heal pass
reconciles `total_activations` against `COUNT(*)` in
`activation_log` per id, inserting missing rows (with
`confidence = 1.0` and `last_activated_at` = the log's
`MAX(activated_at)`) and correcting totals that disagree.

### 1.6 `deleted_nodes`

Tombstones for deliberately forgotten ids.

| Column | Type | Constraints |
|---|---|---|
| `memory_id` | INTEGER | PRIMARY KEY |
| `deleted_at` | TEXT | NOT NULL. ISO-8601 UTC |

Written by `forget()` (even when nothing existed — the tombstone is
the standing record of deliberate forgetting) and by backpressure
pruning. Read by the heal pass, which prunes any edge touching a
tombstoned id. Deleted by activation paths: logging an activation
for an id, or associating it, removes its tombstone (the caller's
world says the id lives again).

---

## 2. Huginn local backend — SQLite tables

Source: `SCHEMA_SQL` in `huginn/src/huginn/local_backend.py`,
applied idempotently at backend construction by `open_store` in
`huginn/src/huginn/_db.py`. The backend object is built lazily, on
the `HuginnMemory` object's first operation.

Default file: `~/.hermes/memory/huginn_local.db`
(`HuginnConfig.local_db_path`; `~` expanded by
`resolved_local_path()`).

As in Muninn: no `FOREIGN KEY` clauses are declared; discipline is
maintained by the backend code and its heal pass.

### 2.1 `meta`

Identical shape to Muninn's `meta`: `key TEXT PRIMARY KEY`,
`value TEXT NOT NULL`. The code writes `schema_version = "1"`
(`SCHEMA_VERSION` in `huginn/_db.py`) at every open.

### 2.2 `documents`

One row per stored document (memory).

| Column | Type | Constraints / default |
|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `content` | TEXT | NOT NULL. Always a plain string (Huginn validates content as a non-empty string at the facade) |
| `content_hash` | TEXT | NOT NULL. `sha256(f"{category}\x00{content}".encode()).hexdigest()` |
| `category` | TEXT | NOT NULL DEFAULT `'general'` |
| `importance` | INTEGER | NOT NULL DEFAULT 5. Validated to 1–10 at the facade |
| `tags` | TEXT | NOT NULL DEFAULT `'[]'`. JSON array of strings (stored as given — no lowercasing/truncation, unlike Muninn) |
| `emotional_valence` | REAL | NOT NULL DEFAULT 0.0. Validated to [−1, 1] at the facade |
| `created_at` | TEXT | NOT NULL. ISO-8601 UTC |
| `updated_at` | TEXT | NOT NULL. ISO-8601 UTC |

Keys and indexes:

- PRIMARY KEY: `id` (AUTOINCREMENT). An upsert may also insert an
  explicit caller-supplied `memory_id` as the `id`.
- UNIQUE constraint: `UNIQUE(content_hash, category)` — the
  idempotency mechanism: the same content in the same category is
  the same document. (Note: unlike Muninn's unique key, `path`
  plays no part — Huginn documents have no path.)
- No other explicit indexes are declared on this table.

There is no `access_count` and no per-document confidence in this
schema — Huginn keeps no activation state.

### 2.3 `doc_terms` — the inverted index

One row per (document, distinct term) in the document.

| Column | Type | Constraints |
|---|---|---|
| `doc_id` | INTEGER | NOT NULL. Part of PK |
| `term` | TEXT | NOT NULL. A token as produced by `tokenize()` (lowercase, stopwords and 1-char tokens removed). Part of PK |
| `tf` | INTEGER | NOT NULL. Raw term frequency (count of the term in the document) |

Keys and indexes:

- PRIMARY KEY: `(doc_id, term)`.
- Index: `idx_terms_term ON doc_terms(term)` — term postings:
  candidate documents for a query are found with
  `SELECT DISTINCT doc_id FROM doc_terms WHERE term IN (…)`.

### 2.4 `corpus_stats`

Corpus-level document frequencies, maintained incrementally on
upsert/delete and recounted by the heal pass.

| Column | Type | Constraints |
|---|---|---|
| `term` | TEXT | PRIMARY KEY |
| `doc_freq` | INTEGER | NOT NULL. Number of documents containing the term |

Rows whose `doc_freq` would drop to ≤ 0 are deleted during
de-indexing, so every row present has `doc_freq >= 1`.

### 2.5 `doc_vectors`

Per-document dense vectors, used only in embedder modes
(`embedder="hashing"` or `"sentence-transformers"`). In the default
`embedder="tfidf"` mode no code path writes this table and it stays
empty.

| Column | Type | Constraints |
|---|---|---|
| `doc_id` | INTEGER | PRIMARY KEY |
| `vector` | TEXT | NOT NULL. JSON array of floats (`json.dumps(vector)`), length = the embedder's dimension |

A replaced document's vector row is deleted and re-inserted on
upsert; `delete` removes the row; the heal pass prunes rows whose
document no longer exists.

---

## 3. Huginn Qdrant backend — collection, point, and payload

Source: `huginn/src/huginn/qdrant_backend.py`. This backend has no
local file: all state lives in the Qdrant server. Status against a
live server: **NOT PROVEN** (proven only against a fake client — see
§10).

### 3.1 Collection

- Name: `HuginnConfig.collection_name`, default `huginn_memories`.
- Ensured lazily on first use: `get_collection(name)`; on any
  exception, `create_collection` with
  `vectors_config = VectorParams(size=<embedder dimension>,
  distance=Distance.COSINE)`.
- Vector size is the embedder's `dim`: for the hashing embedder,
  `HuginnConfig.vector_dim` (default 384); for
  sentence-transformers, the model's own embedding dimension.

### 3.2 Point

Each memory is one Qdrant point (`models.PointStruct`):

| Field | Value |
|---|---|
| `id` | Integer point id (see identity below) |
| `vector` | `list[float]` — the embedder's vector for the document's content |
| `payload` | Dict, shape in §3.3 |

Point id identity:

- If the caller passed `memory_id`, the point id is `int(memory_id)`.
- Otherwise the id is derived deterministically from the content
  hash: `_derived_id(content_hash) =
  int.from_bytes(bytes.fromhex(content_hash[:16]), "big")` — i.e.
  the first 8 bytes of the SHA-256 digest, big-endian. Re-upserting
  the same content in the same category therefore targets the same
  point (idempotent, like the local store).
- The content hash is the same formula as the local backend:
  `sha256(f"{category}\x00{content}".encode()).hexdigest()`.

### 3.3 Payload

The payload dict written on every upsert has exactly these keys:

| Key | Type | Notes |
|---|---|---|
| `content` | str | The document text |
| `category` | str | |
| `importance` | int | 1–10 (validated at the facade) |
| `tags` | list[str] | Copied with `list(tags)` |
| `emotional_valence` | float | [−1, 1] (validated at the facade) |
| `content_hash` | str | Hex SHA-256 as above |

There are no timestamps, no score, and no id inside the payload —
the id is the point id, and the score is a property of a search
result, not of the stored point. On read (`_point_to_doc`), missing
payload keys default to `content=""`, `category=""`,
`importance=5`, `tags=[]`, `emotional_valence=0.0`.

### 3.4 Search filters

`category` and `min_importance` become a Qdrant `Filter(must=[…])`:

- `category` given → `FieldCondition(key="category",
  match=MatchValue(value=category))`.
- `min_importance > 1` → `FieldCondition(key="importance",
  range=Range(gte=min_importance))`.
- Neither → filter is `None` (unfiltered search).

---

## 4. On-disk file layout

Applies to each SQLite store independently (Muninn's file and
Huginn's local file). The Qdrant backend has no on-disk layout on
the client side.

For a store at path `<db>` (e.g. `…/muninn_hebbian.db`):

| File | What it is |
|---|---|
| `<db>` | The SQLite database file itself |
| `<db>-wal` | WAL sidecar (write-ahead log), present while the store is open / after unclean shutdown. Path computed as `str(db_path) + "-wal"` |
| `<db>-shm` | WAL shared-memory sidecar. Path computed as `str(db_path) + "-shm"` |
| `<db>.bak-1` | Newest rolling backup |
| `<db>.bak-2` … `<db>.bak-N` | Older rolling backups, `N` = `backup_keep` (default 3 in both configs; `backup_keep=0` disables backups) |
| `<db>.bak-tmp` | Transient snapshot file used during `take_backup`: the new snapshot is written here, verified with `quick_check`, and only then moved into `.bak-1` (rotating older generations down and deleting generation `keep + 1`). A failed backup removes the temp file and leaves existing generations untouched |

Backup and restore facts (both `_db.py` files):

- Backups are made through SQLite's backup API
  (`src.backup(dst)`) from the live store file.
- On open with `auto_backup` on, a backup is refreshed only if the
  store existed before the open and its mtime is newer than
  `.bak-1`'s mtime (or `.bak-1` does not exist).
- Restore on corruption copies the newest verifying backup over
  `<db>` with `shutil.copyfile`, deleting `-wal`/`-shm` sidecars
  both before and after the copy.
- The parent directory of `<db>` is created on open
  (`mkdir(parents=True, exist_ok=True)`).

Connection pragmas set on every store connection (`_connect` in
both `_db.py` files): `busy_timeout = <config>` (default 5000),
`journal_mode = WAL`, `synchronous = FULL`, `foreign_keys = ON`.
Connections use `sqlite3.Row` as row factory and
`check_same_thread=False`, with
`timeout = busy_timeout_ms / 1000.0` seconds.

---

## 5. In-memory structures

### 5.1 `MemoryNode` (muninn `core.py`)

A `@dataclass` — one memory node. Fields, in declaration order:

| Field | Type | Default |
|---|---|---|
| `id` | int | (required) |
| `content` | Any | (required). A string, or the JSON-decoded value for JSON content |
| `path` | str | `""` |
| `memory_type` | str | `"fact"` |
| `importance` | int | 5 |
| `emotional_valence` | float | 0.0 |
| `tags` | List[str] | `[]` (factory) |
| `metadata` | Dict[str, Any] | `{}` (factory) |
| `access_count` | int | 0 |
| `created_at` | datetime | now, UTC (factory) |
| `updated_at` | datetime | now, UTC (factory) |

Plus:

- Property `category` → alias returning `memory_type` (Bifröst-era
  vocabulary). Note the mapping to storage: the dataclass field
  `memory_type` is the `nodes.category` column.
- `to_dict()` returns a dict with exactly these keys:
  `id`, `content`, `path`, `memory_type`, `category` (same value as
  `memory_type`), `importance`, `emotional_valence`, `tags` (a list
  copy), `metadata` (a dict copy), `access_count`, `created_at`
  (ISO string), `updated_at` (ISO string).
- `from_dict(data)` classmethod: inverse of `to_dict`; accepts
  `memory_type` or falls back to `category` (default `"fact"`),
  parses ISO timestamp strings back to datetimes.
- Note the default mismatch, which is in the code: the dataclass
  defaults `memory_type` to `"fact"`, while `remember()`'s
  `category` parameter and the `nodes.category` column both default
  to `'general'`. Nodes read back from the store carry whatever the
  column holds.

### 5.2 `RetrievalResult` (huginn `core.py`)

A `@dataclass` — the result of one Huginn flight. Fields, in
declaration order:

| Field | Type | Default |
|---|---|---|
| `query` | str | (required). The query exactly as passed to `fly()` (not the truncated internal copy) |
| `results` | List[Dict[str, Any]] | (required). Search result dicts (§7.2), possibly compressed (§5.4) |
| `relevance_scores` | List[float] | (required). `[float(r.get("score", 0.0)) for r in results]`, parallel to `results` |
| `source_realm` | str | (required). `"huginn:<backend kind>"` — `huginn:local`, `huginn:qdrant`, or `huginn:unresolved` if no backend was built |
| `retrieval_time` | float | (required). Seconds, measured with `time.time()` around the search |
| `compressed` | bool | (required). Echoes `fly()`'s `compress` argument |
| `error` | Optional[str] | None. Set to the `HuginnError`'s message when the flight's search failed; the flight then has empty `results` |
| `timestamp` | datetime | now, UTC (factory) |

### 5.3 Flight history (huginn `core.py`)

`HuginnMemory._flight_history: List[RetrievalResult]` — every
`fly()` appends its flight. Cap logic, verbatim behaviour:

```python
self._flight_history.append(flight)
if len(self._flight_history) > 100:
    self._flight_history = self._flight_history[-50:]
```

So the history holds at most 100 flights; the moment it would
exceed 100 it is cut to the most recent 50. `multi_hop_retrieve`
flights are appended too (each hop calls `fly`). The history is
per-object and in-memory only — nothing about flights is persisted.

### 5.4 Result compression (huginn `core.py`)

`_compress_result` (applied by `fly` when `compress=True`, the
default) transforms each result dict value-wise: strings longer
than 200 characters become `value[:200] + "..."`; lists longer than
5 entries become `value[:5]`; everything else passes through
unchanged. Keys are never added or removed.

### 5.5 Sparse TF-IDF structures (huginn `text.py` + local backend)

All sparse vectors are plain dicts:

| Structure | Shape | Meaning |
|---|---|---|
| Token list | `list[str]` | Output of `tokenize(text)`: `[^\W_]+` matches over the lowercased text, Unicode-aware, with stopwords and tokens of length ≤ 1 removed |
| Term counts | `dict[str, int]` | `term_counts(tokens)`: term → raw count. This is what is stored per document in `doc_terms` and used for queries |
| Document-frequency map | `dict[str, int]` | term → `doc_freq`, loaded in one batched query from `corpus_stats` during search |
| Sparse TF-IDF vector | `dict[str, float]` | `sparse_tfidf(counts, df, total_docs)`: term → `(count / total_terms) * idf(df, total_docs)` |

Formulas (verbatim from `text.py`):

- `idf(doc_freq, total_docs) = log(1.0 + (total_docs − doc_freq +
  0.5) / (doc_freq + 0.5))`, and 0.0 when `total_docs <= 0`. A term
  absent from the df map is looked up as `df.get(term, 0)`.
- `cosine(a, b)` over sparse dicts: dot product over the smaller
  dict's terms divided by both L2 norms; 0.0 for empty inputs,
  non-positive dot, or zero norms; clamped to at most 1.0.

`STOPWORDS` is a `frozenset` of 54 words, kept verbatim from the
ancestor (the full list is in `text.py`; it includes the question
words `when`, `where`, `why`, `how` — which is why `analyze_query`'s
`key_terms` and the tokenizer treat them differently: `key_terms`
checks membership in the same set).

### 5.6 Dense vectors and embedders (huginn `text.py`)

The `Embedder` protocol: attributes `name: str` and `dim: int`, and
`embed(text) -> list[float]`.

**`HashingEmbedder`** (`name = "hashing"`, `dim` from config,
default 384):

- Starts from `[0.0] * dim`.
- For each token (same `tokenize` as above): `digest =
  sha256(token.encode("utf-8")).digest()`; bucket =
  `int.from_bytes(digest[:4], "little") % dim`; sign = +1.0 if
  `digest[4]` is even else −1.0; `vector[bucket] += sign`.
- L2-normalizes if the norm is > 0. Same text → same vector, on any
  machine.
- Stored in the local backend as JSON text in `doc_vectors.vector`;
  sent to Qdrant as the point vector.

**`SentenceTransformerEmbedder`** (`name = "sentence-transformers"`):

- Wraps `SentenceTransformer(model)` (default model
  `all-MiniLM-L6-v2`); `dim` is the model's own
  `get_sentence_embedding_dimension()`.
- `embed` returns `[float(v) for v in model.encode([text],
  normalize_embeddings=True)[0]]` — already normalized by the model
  call.
- Construction raises `HuginnConfigurationError` when the
  `sentence_transformers` package is not installed. This path is
  **NOT PROVEN** (the extra was not installed in the build
  environment; see §10).

`dense_cosine(a, b)` over `Sequence[float]`: dot / (norms), 0.0 for
empty inputs or zero norms, clamped to [0.0, 1.0].

### 5.7 Store-object state (both packages)

`HebbianMemory` instance state: `config`, `_conn` (the shared
`sqlite3.Connection`), `_db_path` (a `Path`), `_lock`
(`threading.RLock`), `_closed` (bool), `open_report` (an
`OpenReport`, §5.8), `recovered_from_backup` (bool, copied from the
report), `last_heal_report` (dict, §7.1). Class attribute
`MAX_QUERY_RESULTS = 1000` (the bound applied to `retrieve`'s
`top_k`).

`HuginnMemory` instance state: `config`, `_lock`, `_backend`
(`LocalBackend | QdrantBackend | None` — None until first use),
`_embedder`, `_embedder_name` (str | None — the effective embedder
name reported by `health()`), `_fallback_reason` (str | None),
`_closed` (bool), `_flight_history` (§5.3). Module constants:
`MAX_RESULTS_CAP = 50` (bound for `fly`'s `max_results`),
`MAX_QUERY_CHARS = 1000` (queries are truncated to this in
`analyze_query` and `fly`).

`LocalBackend` instance state: `config`, `_embedder` (or None),
`_lock`, `_closed`, `_db_path`, `_conn`, `open_report`,
`recovered_from_backup`, `last_heal_report`. Class attribute
`kind = "local"`.

`QdrantBackend` instance state: `config`, `_embedder`, `_lock`,
`_client` (None until first use), `_models` (the
`qdrant_client.models` module, resolved at client creation),
`_collection_ready` (bool), `_closed` (bool). Class attribute
`kind = "qdrant"`. There is no `open_report` or heal report on this
backend — it has no local store to heal.

### 5.8 `OpenReport` (both `_db.py` files)

A `@dataclass` describing what happened while opening a store.
Identical fields in both packages:

| Field | Type | Default |
|---|---|---|
| `recovered_from_backup` | bool | False |
| `restored_backup` | str \| None | None. Path of the backup file that was restored |
| `backup_taken` | bool | False. True when the open refreshed the rolling backup |
| `integrity` | str | `"ok"` |

Fidelity note: in the current code `open_store` sets
`recovered_from_backup`, `restored_backup`, and `backup_taken`, but
never assigns `integrity` — it keeps its default `"ok"` even on a
recovery path. Live integrity is reported by `health()` (which runs
its own `PRAGMA quick_check`), not by this field.

---

## 6. Numeric bounds applied to arguments

These are bounds the code applies to *limit/count* arguments (not
clamping of stored caller data — stored values are validated and
raise instead, see §9):

| Place | Bound |
|---|---|
| Muninn `get_associations(limit)` | clamped to [1, 10000] |
| Muninn `retrieve(top_k)` | clamped to [1, `MAX_QUERY_RESULTS` = 1000] |
| Muninn `dump(limit)` | clamped to [1, 500] |
| Muninn `spread_activation(depth)` | clamped to [0, 10] |
| Muninn `spread_activation(limit)` | `max(1, limit)` applied after ranking |
| Huginn facade `search(limit)` | clamped to [1, 1000] |
| Huginn `fly(max_results)` | clamped to [1, `MAX_RESULTS_CAP` = 50] |
| Huginn `multi_hop_retrieve(hop_count)` | clamped to [1, 5] |
| Huginn `semantic_search(top_k)` | clamped to [1, len(documents)] |
| `analyze_query` / `fly` query text | truncated to `MAX_QUERY_CHARS` = 1000 chars |
| Muninn tags on write | each tag stripped, lowercased, truncated to 64 chars; empty tags dropped |

---

## 7. Muninn — exact return shapes of public methods

Class `HebbianMemory` (all inherited by the `Muninn` facade).
"Pure read" / "WRITE" follow the pure-reads law (see
`docs/ARCHITECTURE.md` §4.6).

### 7.1 Activation and wiring

**`activate(memory_id, *, emotional_valence=0.0, source="api") ->
int`** — WRITE. Returns the id's new total activation count (the
`total_activations` value in `node_activation` after this
activation).

**`activate_batch(memory_ids, *, emotional_valence=0.0,
source="api") -> dict`** — WRITE. Ids are deduplicated, preserving
first-seen order. Returns exactly:

| Key | Type | Meaning |
|---|---|---|
| `activated` | int | Number of unique ids activated |
| `pairs_wired` | int | Number of unordered pairs, `C(len(ids), 2)` |
| `connections_created` | int | Pairs for which at least one directed row was newly created by this batch |
| `connections_strengthened` | int | `pairs_wired − connections_created` |

**`associate(memory_a, memory_b, *, strength=None, delta=None) ->
float`** — WRITE. Returns the pair's new strength (the `(a, b)`
directed row's `strength` after the write; 0.0 if no row exists,
which cannot happen after a successful call).

**`get_associations(memory_id, min_strength=0.0, limit=100) ->
list[dict]`** — pure read. Ordered by `strength DESC,
co_activation_count DESC` (contractual ordering). Each dict has
exactly:

| Key | Type | Source column |
|---|---|---|
| `memory_id` | int | `memory_b_id` (the other end) |
| `strength` | float | `strength` |
| `co_activation_count` | int | `co_activation_count` |
| `consolidated` | bool | `consolidated` (0/1 → bool) |
| `last_coactivated_at` | str \| None | `last_coactivated_at` |

**`activation_count(memory_id) -> int`** — pure read.
`COUNT(*)` of the id's `activation_log` rows.

**`spread_activation(seed_ids, *, depth=2, attenuation=0.5,
min_strength=0.0, limit=1000) -> dict[int, float]`** — pure read.
Keys are memory ids, values activation levels (seeds 1.0); the dict
is in strongest-first iteration order.

### 7.2 Node API

**`remember(content, *, category="general", path="",
importance=5, tags=None, emotional_valence=0.0, metadata=None) ->
int`** — WRITE. The node's integer id (existing id on an
idempotent re-store).

**`store(content, path="", memory_type="fact", importance=5,
tags=None, metadata=None, *, emotional_valence=0.0) -> int`** —
WRITE. Ancestor-shaped alias of `remember` with
`category=memory_type`. Note its own default `memory_type="fact"`.

**`get_node(memory_id) -> MemoryNode | None`** — pure read.

**`retrieve(query=None, path=None, tags=None, memory_type=None,
top_k=5, *, category=None, touch=False) -> list[MemoryNode]`** —
pure read unless `touch=True` (then it also activates each returned
node, with source `"retrieve:touch"`). `category` overrides
`memory_type` when both are given. Sorting: importance DESC, then
`updated_at` DESC (via sort key `(importance, updated_at)`
reversed). `query` is a case-insensitive substring match over
content (over the JSON dump for non-string content), applied in
Python, not in SQL.

**`get_by_path(path) -> list[MemoryNode]`** — pure read. Nodes at
exactly `path`, ordered `importance DESC, updated_at DESC`.

**`get_children(parent_path) -> dict[str, list[MemoryNode]]`** —
pure read. Keys are full paths strictly under `parent_path`
(`path LIKE '<parent_path>/%'`), values the nodes at each path,
ordered by path then `importance DESC`.

**`update(node_id, content=None, **fields) -> bool`** — WRITE.
False when no such node. Allowed field names: `importance`,
`emotional_valence`, `tags`, `metadata`, `path`, `memory_type`,
`category`; anything else raises `MuninnValidationError`. Changing
content onto an existing (content_hash, category, path) triple
raises `MuninnValidationError` (converted from the SQLite
`IntegrityError`).

**`forget(memory_id) -> bool`** — WRITE. True when a node row or
any wiring was removed; the tombstone is written regardless.
**`delete(node_id) -> bool`** — alias of `forget`.
**`move(node_id, new_path) -> bool`** — WRITE; `update(node_id,
path=new_path)`.

**`get_tree_structure() -> dict`** — pure read. A nested dict built
by splitting each path on `/`: each path segment is a key whose
value is a dict; the leaf dict for a path carries `"_nodes": int`
(the node count at that exact path). Paths with no segments (the
empty path) contribute no keys.

**`dump(limit=50) -> dict`** — pure read. Exactly:

| Key | Type | Meaning |
|---|---|---|
| `stats` | dict | The `stats()` dict (§7.4) |
| `nodes` | list[dict] | `MemoryNode.to_dict()` dicts (§5.1) for the highest-importance nodes, ordered `importance DESC, updated_at DESC` |

### 7.3 Maintenance

**`heal_structure() -> dict`** — WRITE. The heal report, also stored
on the object as `last_heal_report` (and produced once at
construction). Exactly:

| Key | Type | Meaning |
|---|---|---|
| `self_edges_pruned` | int | Rows deleted where `memory_a_id = memory_b_id` |
| `dangling_edges_pruned` | int | Rows deleted for touching a tombstoned id |
| `pairs_repaired` | int | Reverse rows inserted + disagreeing pairs reconciled |
| `counters_fixed` | int | `node_activation` rows inserted or corrected against the log |
| `fixes` | int | Sum of the four counters above |

**`decay(days=1.0) -> dict`** — WRITE. Exactly:

| Key | Type | Meaning |
|---|---|---|
| `days` | float | The `days` argument, as float |
| `edge_factor` | float | `0.5 ** (days / decay_half_life_days)` |
| `confidence_factor` | float | `0.5 ** (days / confidence_half_life_days)` |
| `edges_decayed` | int | Rows whose strength was multiplied (rowcount of the strength UPDATE — every connection row) |
| `edges_pruned` | int | Rows deleted for falling below `prune_threshold` |
| `confidences_decayed` | int | `node_activation` rows whose confidence was multiplied |

(An intermediate step also un-marks `consolidated` on edges below
the consolidation threshold; its rowcount is not in the report.)

**`consolidate(threshold=None) -> dict`** — WRITE. Exactly:

| Key | Type | Meaning |
|---|---|---|
| `threshold` | float | The threshold used (default: config's 0.8) |
| `newly_consolidated` | int | Edges newly marked `consolidated = 1` |
| `unmarked` | int | Edges newly un-marked (`consolidated = 0`) for being below threshold |
| `total_consolidated` | int | Total rows with `consolidated = 1` after the pass |
| `heal` | dict | The heal report dict (§7.3 above), from the heal pass that runs as part of consolidation |

### 7.4 Health and stats

**`health() -> dict`** — pure read. Exactly:

| Key | Type | Meaning |
|---|---|---|
| `status` | str | `"healthy"` if the store's `PRAGMA quick_check` returns `"ok"`, else `"degraded"` |
| `db_path` | str | Store path |
| `integrity` | str | The `quick_check` result string (`"ok"`, another string, or `"failed"` on a SQLite error) |
| `recovered_from_backup` | bool | Whether this object's open restored from a backup |
| `nodes` | int | `COUNT(*)` of `nodes` |
| `connections` | int | `COUNT(*)` of `hebbian_connections` (directed rows — two per logical pair) |
| `activations` | int | `COUNT(*)` of `activation_log` |
| `schema_version` | str | Always `"1"` |

**`stats() -> dict`** — pure read (**`get_stats()`** is an
alias returning the same shape). Exactly:

| Key | Type | Meaning |
|---|---|---|
| `total_nodes` | int | `COUNT(*)` of `nodes` |
| `total_connections` | int | `COUNT(*)` of `hebbian_connections` (directed rows) |
| `total_activations` | int | `COUNT(*)` of `activation_log` |
| `consolidated_connections` | int | Rows with `consolidated = 1` |
| `strongest_connection` | float | `MAX(strength)`, or 0.0 when there are no connections |
| `categories` | dict[str, int] | Node count per `category` |
| `db_path` | str | Store path |

### 7.5 Lifecycle

**`backup() -> str | None`** — commits, then takes a rolling
backup; returns the newest backup's path as a string, or None when
backups are disabled (`backup_keep = 0`) or the backup failed.
**`close() -> None`** — idempotent. **`_get_conn() ->
sqlite3.Connection`** — the shared connection (contractual seam,
§1.3); raises `MuninnStorageError` when closed.

### 7.6 The `Muninn` facade constructor

`Muninn(data_path=None, *, config=None, **overrides)`: with no
config and a `data_path`, a directory path becomes
`<data_path>/muninn_hebbian.db` and a path whose suffix is `.db` is
used as the file itself; with neither, the default `MuninnConfig`
applies. All methods are inherited unchanged.

---

## 8. Huginn — exact return shapes of public methods

### 8.1 Facade: `HuginnMemory`

**`upsert_memory(content, category="general", importance=5,
tags=None, emotional_valence=0.0, *, memory_id=None) -> int`** —
WRITE. The stored memory's id (backend-assigned, caller-pinned, or
the existing id on an idempotent re-upsert; on Qdrant without
`memory_id`, the derived id of §3.2).

**`search(query_text, limit=10, category=None, min_importance=1) ->
list[dict]`** — pure read. A blank/whitespace query returns `[]`
(not an error). Each dict has exactly the keys of §8.3 **with**
`score`. There is no `reinforce` parameter (see §10).

**`get(memory_id) -> dict | None`** — pure read. The dict of §8.3
**without** `score`.

**`delete(memory_id) -> bool`** — WRITE. True when something was
removed.

**`health() -> dict`** — pure read; never raises for backend
trouble. Three shapes:

1. Backend reached: the backend's health dict (§8.4) plus two keys
   added by the facade — `embedder` (the effective embedder name:
   `"tfidf"`, `"hashing"`, or `"sentence-transformers"`; note a
   Qdrant backend with `embedder="tfidf"` configured reports
   `"hashing"`) and `backend_configured` (the config's `backend`
   string). When auto mode fell back, the facade also overrides
   `status` to `"degraded"` and adds `fallback_reason` (a string,
   `"qdrant unavailable: <error>"`).
2. Backend raising a `HuginnError` (e.g. explicit `backend="qdrant"`
   unreachable): exactly `{status: "unhealthy",
   backend_configured: <config backend>, error: <message>,
   error_type: <exception class name>}`.

**`stats() -> dict`** — returns exactly what `health()` returns
(the facade's `stats` is `health` under another name; Bifröst calls
`health()` for this).

**`close() -> None`** — idempotent; closes the backend if one was
built.

### 8.2 Facade: ancestor flight API

**`analyze_query(query) -> dict`** — pure read (also a module-level
function in `huginn.core`, exported at package top level). Exactly:

| Key | Type | Meaning |
|---|---|---|
| `query_type` | str | `"factual"` by default. The checks are a single `if`/`elif` chain over substrings of the lowercased query, so the **first** matching branch wins, in this order: `"explanatory"` if it contains `why`/`how`/`explain`; else `"search"` for `find`/`search`/`where`; else `"enumeration"` for `list`/`all`/`show`; else `"comparison"` for `compare`/`difference`/`vs` |
| `key_terms` | list[str] | Whitespace-split lowercased words not in `STOPWORDS` and longer than 2 chars |
| `strategy` | str | `"multi_hop"` (comparison), `"broad"` (enumeration), `"focused"` (more than 3 key terms), else `"standard"` |
| `recommended_hops` | int | 2 for comparison, else 1 |
| `word_count` | int | Number of whitespace-split words in the (truncated) query |

**`fly(query, max_results=5, compress=True) -> RetrievalResult`** —
pure read over the store (appends to the in-memory flight history,
§5.3). Field values are specified in §5.2.

**`multi_hop_retrieve(initial_query, hop_count=2,
max_results_per_hop=3) -> list[RetrievalResult]`** — pure read over
the store. One flight per hop, up to the bounded hop count; the
next hop's query is `f"{initial_query} {' '.join(concepts[:3])}"`
where concepts come from `_extract_concepts`: lowercased alphabetic
words longer than 4 chars from result contents, deduplicated,
sorted, capped at 10 (of which the first 3 are used).

**`get_flight_stats() -> dict`** — pure read. When no flights have
been made, exactly `{"total_flights": 0}`. Otherwise exactly:

| Key | Type | Meaning |
|---|---|---|
| `total_flights` | int | Flights in the (capped) history |
| `total_results_retrieved` | int | Sum of `len(f.results)` |
| `total_flight_time` | float | Sum of `retrieval_time` |
| `avg_flight_time` | float | `total_flight_time / total_flights` |
| `avg_results_per_flight` | float | `total_results_retrieved / total_flights` |
| `realm_visits` | dict[str, int] | Count of flights per `source_realm` |

**`semantic_search(query, documents, top_k=3) ->
list[tuple[int, float]]`** — module-level function (exported at
package top level; not a method). `(document index, score)` pairs,
best first, positive scores only; `[]` for an empty document list.

### 8.3 The Huginn document dict

Produced identically by both backends (`LocalBackend._row_to_doc`,
`QdrantBackend._point_to_doc`):

| Key | Type | Present |
|---|---|---|
| `id` | int | Always |
| `content` | str | Always |
| `category` | str | Always |
| `importance` | int | Always |
| `tags` | list[str] | Always (a list; JSON-decoded locally, payload-copied on Qdrant) |
| `emotional_valence` | float | Always |
| `score` | float | Only when a score is supplied: always in `search` results, never in `get` results |

Search results are ordered best-first (descending score). Local
TF-IDF and embedder searches return only documents scoring > 0.0;
Qdrant search returns whatever the server returns for the query,
each point mapped with `score = getattr(point, "score", 0.0)`.

### 8.4 Backend-level shapes

**`LocalBackend.health() -> dict`** — exactly:

| Key | Type | Meaning |
|---|---|---|
| `status` | str | `"healthy"` if `quick_check` is `"ok"`, else `"degraded"` |
| `backend` | str | `"local"` |
| `db_path` | str | Local store path |
| `integrity` | str | `quick_check` result string, or `"failed"` |
| `recovered_from_backup` | bool | Whether this backend's open restored from a backup |
| `documents` | int | `COUNT(*)` of `documents` |
| `vocabulary` | int | `COUNT(*)` of `corpus_stats` (distinct indexed terms) |

**`LocalBackend.heal() -> dict`** — WRITE (backend-level; also run
once at construction, kept as `last_heal_report`). Exactly:

| Key | Type | Meaning |
|---|---|---|
| `orphan_terms_pruned` | int | `doc_terms` rows deleted whose document no longer exists |
| `orphan_vectors_pruned` | int | `doc_vectors` rows deleted whose document no longer exists |
| `doc_freq_fixed` | int | Terms whose `corpus_stats` entry was inserted, corrected, or deleted to match a recount from `doc_terms` |

Unlike Muninn's heal report, there is no `fixes` total key.

**`LocalBackend.count() -> int`** — number of documents.
**`LocalBackend.get/delete/upsert/search`** — same shapes as the
facade's corresponding methods (§8.1, §8.3); `upsert` takes
keyword-only `category`, `importance`, `tags`, `emotional_valence`,
`memory_id`.

**`QdrantBackend.health() -> dict`** — exactly:

| Key | Type | Meaning |
|---|---|---|
| `status` | str | `"healthy"` (reaching this dict means `ping()` and `count()` succeeded) |
| `backend` | str | `"qdrant"` |
| `qdrant_url` | str | Configured server URL |
| `collection` | str | Collection name |
| `documents` | int | `count()` of the collection |

**`QdrantBackend.count() -> int`** — the collection's point count.
**`QdrantBackend.ping() -> None`** — returns None on success;
raises `HuginnBackendError` on server failure,
`HuginnConfigurationError` when the client package is missing.
**`QdrantBackend.get/delete/upsert/search`** — same shapes as the
facade's; server failures raise `HuginnBackendError`.

---

## 9. Error hierarchies

### 9.1 Muninn (`muninn/src/muninn/errors.py`)

```
Exception
└── MuninnError                     — base for every deliberate Muninn error
    ├── MuninnValidationError       — also subclasses ValueError
    ├── MuninnConfigurationError    — also subclasses ValueError
    └── MuninnStorageError
```

| Class | Raised for |
|---|---|
| `MuninnValidationError` | Caller supplied an invalid argument, raised **before** any write: non-int or negative `memory_id`; `importance` not an int in [1, 10]; `emotional_valence` not a number in [−1, 1]; `None` or non-JSON-serializable content; non-JSON-serializable metadata; `activate_batch` given a non-list; `associate` with `a == b`, with both `strength` and `delta`, with `strength` outside [0, 1], or with `delta` outside (0, 1]; `get_associations` `min_strength` outside [0, 1]; `spread_activation` `attenuation` outside (0, 1]; `decay` `days` not a number ≥ 0; `consolidate` `threshold` outside (0, 1]; `update` with unknown field names; `update` that would duplicate an existing (content, category, path) node |
| `MuninnConfigurationError` | A `MuninnConfig` value out of range at construction: empty/non-string `db_path`; `learning_rate` outside (0, 1]; either half-life ≤ 0; `prune_threshold` outside [0, 1); `consolidation_threshold` outside (0, 1]; negative `busy_timeout_ms` or `backup_keep`; `max_nodes` < 1 |
| `MuninnStorageError` | The store could not be opened, read, written, or healed: corrupt main store with no verifying rolling backup (refuses to start empty); schema preparation failure on open (wrapping the `sqlite3.Error`); any method called on a closed `HebbianMemory` (via `_get_conn`) |

Because the validation and configuration errors also subclass
`ValueError`, a caller's `except ValueError` catches them; a
caller's `except MuninnError` catches everything Muninn raises
deliberately. Raw `sqlite3.Error`s from ordinary operations are not
re-wrapped by the core (the two wrapped cases are open-time schema
preparation and `update`'s integrity conversion, §7.2).

### 9.2 Huginn (`huginn/src/huginn/errors.py`)

```
Exception
└── HuginnError                     — base for every deliberate Huginn error
    ├── HuginnValidationError       — also subclasses ValueError
    ├── HuginnConfigurationError    — also subclasses ValueError
    ├── HuginnStorageError
    └── HuginnBackendError
```

| Class | Raised for |
|---|---|
| `HuginnValidationError` | Invalid caller argument, before any write: empty/non-string upsert content; `importance` not an int in [1, 10]; `emotional_valence` outside [−1, 1]; non-int or negative `memory_id`; non-string `query_text`; non-int `min_importance`; and, from the local backend, the explicit-id/content clash on upsert (requested `memory_id` free but the content already lives at another id) |
| `HuginnConfigurationError` | A `HuginnConfig` value illegal at construction: `backend` not in `("auto", "local", "qdrant")`; `embedder` not in `("tfidf", "hashing", "sentence-transformers")`; empty `qdrant_url`, `local_db_path`, or `collection_name`; `vector_dim` < 8; `qdrant_timeout` ≤ 0; negative `busy_timeout_ms` or `backup_keep`. Also: a configured optional dependency is missing — `backend="qdrant"` without `qdrant-client` installed, or `embedder="sentence-transformers"` without `sentence-transformers` installed; and an unknown embedder name reaching `_make_embedder` |
| `HuginnStorageError` | The local store could not be opened/prepared, or was used after close: corrupt local store with no verifying rolling backup; schema preparation failure on open (wrapping `sqlite3.Error`); operations on a closed `LocalBackend` |
| `HuginnBackendError` | The selected backend failed at operation time: explicit (or probed) Qdrant server unreachable in `ping()`; Qdrant collection creation failure; Qdrant upsert/delete/retrieve/search/count failures (each wraps the client exception and names the operation); any operation on a closed `HuginnMemory` or closed `QdrantBackend` |

Designed non-raising paths, so they are not errors: in
`backend="auto"`, any Qdrant probe failure selects the local backend
instead of raising (the reason is recorded in `health()`); the
facade `health()` converts a `HuginnError` into the `"unhealthy"`
dict of §8.1; `fly()` converts a `HuginnError` from its search into
an empty `RetrievalResult` with `error` set.

Backup failures in both packages are also non-raising:
`take_backup` logs at ERROR level and returns None, leaving prior
generations intact.

---

## 10. Provenance, known disagreements, and NOT PROVEN items

Disagreements between `BUILD_NOTES_2026-10-30.md` and the code —
code wins; this document follows the code:

1. **Huginn search reinforce parameter.** BUILD_NOTES §1.4 lists a
   `search(..., reinforce=True)` reinforcing variant; §3.2 first
   writes `search(..., reinforce=False)` and then corrects itself
   ("the parameter does not exist"). The code has no such parameter
   on the facade or on either backend, and Huginn has no
   reinforcing read at all.
2. **Huginn local embedder-mode search.** BUILD_NOTES §3.2
   describes it as "reranking lexical candidates by vector cosine".
   The code (`LocalBackend._search_vectors_locked`) linearly scans
   **all** stored vectors in `doc_vectors` and scores each by dense
   cosine; no lexical candidate set is produced first.
3. **Shared error-hierarchy summary.** BUILD_NOTES §3 lists a
   `…BackendError` among both packages' hierarchies. Muninn has
   none; only Huginn defines `HuginnBackendError` (§9).

NOT PROVEN (from BUILD_NOTES §5; stated wherever relevant above):

- **Live Qdrant server round-trip — NOT PROVEN.** No server exists
  on the build VM. §3's point/payload/filter shapes are the shapes
  the code constructs and the shapes a fake in-`sys.modules` client
  was exercised against — not shapes verified against a real
  Qdrant server.
- **Sentence-transformers embedder path — NOT PROVEN.** The
  `embeddings` extra was not installed in the build environment, so
  no vector in §5.6's second embedder was ever produced there; the
  hashing embedder path **is** proven end-to-end.
- **Performance on unloaded hardware — NOT PROVEN.** The only
  benchmark numbers that exist are BUILD_NOTES §4's, measured on a
  loaded VM (twelve campaign keepers running; Python 3.12.3,
  SQLite 3.45.1) and labelled indicative there. No performance
  figure is stated anywhere in this document.
