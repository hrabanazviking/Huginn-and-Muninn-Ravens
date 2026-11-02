# Reliability — durability, threading, self-healing

How the two ravens keep data safe, and exactly what proves it.

Plain version first: both packages store everything in one SQLite
file per store, opened in WAL mode with full sync, so a process
killed mid-write loses at most the transaction that never committed.
Every open checks the store's integrity; a corrupt store is restored
from its own newest *verified* rolling backup, loudly, and if no
backup verifies, opening raises a typed error instead of starting
empty over lost data. Structural drift is repaired on every open and
the repairs are counted in a report. Every read API is a pure read,
proven by tests that snapshot the store's write-tables before and
after. One named exception exists in the whole design — Muninn's
`retrieve(..., touch=True)` — and it carries its nature in its name.

Everything below is traced to the code
(`muninn/src/muninn/_db.py`, `muninn/src/muninn/core.py`,
`huginn/src/huginn/_db.py`, `huginn/src/huginn/local_backend.py`)
and to the test suites, principally
`muninn/tests/test_robustness.py`, `muninn/tests/test_semantics.py`,
`huginn/tests/test_robustness.py`, and
`huginn/tests/test_local_backend.py`. The verification record is
`docs/BUILD_NOTES_2026-10-30.md` §5.

The storage discipline is implemented **per package** (small,
deliberate duplication in each package's `_db.py`) because each
package must install and run independently — neither depends on the
other.

---

## 1. Durability: the SQLite settings

Each package's `_db.py` has a `_connect()` that opens the store's
one connection with exactly these pragmas:

```sql
PRAGMA busy_timeout = <config busy_timeout_ms>   -- default 5000
PRAGMA journal_mode = WAL
PRAGMA synchronous = FULL
PRAGMA foreign_keys = ON
```

The Python-level timeout is set the same way
(`timeout=busy_timeout_ms / 1000.0` seconds).

What each one buys:

- **WAL** — writes go to a write-ahead log; readers are not blocked
  by the writer, and committed frames survive a process kill.
- **`synchronous=FULL`** — every commit is synced to disk before it
  reports success. This is the setting that makes "committed means
  committed" true across a `kill -9` or a power cut, at the cost of
  commit speed.
- **`busy_timeout`** — a locked store is awaited up to the timeout
  (default 5000 ms) instead of failing instantly with
  "database is locked".
- **`foreign_keys=ON`** — set for discipline; note honestly that the
  schemas declare no `FOREIGN KEY` constraints, so the pragma is
  belt-and-braces, not load-bearing.

Schema is applied idempotently on open (`CREATE TABLE IF NOT
EXISTS …`), and the `meta` table is stamped with
`schema_version = "1"` (the `SCHEMA_VERSION` constant in each
`_db.py`).

## 2. Threading model

- **One shared connection per store object**, opened with
  `check_same_thread=False`. The comment in `_connect()` states the
  reasoning plainly: the connection is used from many threads and
  serialized by the owner's lock — *that serialization is the
  safety*, and the flag is what permits it.
- **A `threading.RLock` per object** serializes every public method:
  - `HebbianMemory` holds one RLock; every public method runs under
    it, and internal helpers (`_log_activation_locked`,
    `_wire_pair_locked`, `_heal_locked`) assume the caller holds it.
  - `LocalBackend` and `QdrantBackend` each hold their own RLock.
  - `HuginnMemory` holds an RLock used for lazy backend construction
    (double-checked: `_ensure_backend()` re-tests under the lock),
    for `close()`, and for flight-history bookkeeping.
- Honest boundary: `HuginnMemory`'s facade methods delegate to the
  backend, and it is the **backend's** lock that serializes the
  backend's own operations. The facade adds no second store lock
  around `upsert` / `search` / `get` / `delete` calls.
- **Concurrent openers are supported** (RM-037): several objects —
  in one process or across processes — may hold the same store
  file. Each object's lock still protects only its own threads;
  across objects, ordinary reads and writes are serialized by
  SQLite's own locking plus `busy_timeout` (RM-031), and the
  open-time duties (creation, probe, restore, backup-on-open,
  heal) plus every backup are serialized per store file by the
  coordination lock in each package's `_db.py` (in-process RLock
  + `flock` on the sibling `.open-lock` file). Defined and
  pinned in `docs/CONCURRENT_OPENERS.md` and
  `tests/test_concurrent_openers.py` in both packages: exact
  counts across objects and processes, a fresh-store creation
  race, a corrupt-store restore race, and close independence.

Race tests (exact totals, not "no crash"):

- Muninn, 8 threads × (50 `activate` + 50 `activate_batch`): every
  per-id activation count is exactly 100, id 200 is exactly 400,
  all 8 pair rows exist with `co_activation_count` exactly 50
  (`test_concurrent_threads_no_lost_writes`).
- Muninn, 10 threads racing `remember()` of identical content:
  all get the same id; exactly 1 node exists.
- Huginn local, 6 threads × 25 upserts each interleaved with
  searches: no errors; exactly 150 documents at the end
  (`test_concurrent_upserts_and_searches`).

## 3. Transactions: all-or-nothing per API call

Writes inside one API call are grouped and committed **once**, at
the end of the call:

- `HebbianMemory.activate` — log row + counter update + node
  access-count bump, one commit.
- `HebbianMemory.activate_batch` — every activation and every pair
  wiring, one commit. A torn batch is impossible: the kill-9 test
  below shows the three ids' counts always agree exactly.
- `HebbianMemory.associate`, `remember`/`store`, `update`,
  `forget`/`delete`, `decay`, `consolidate`, and the heal pass —
  one commit each. (`update` explicitly rolls back when its write
  would violate the content-uniqueness index, then raises.)
- `LocalBackend.upsert` — document row + de-indexing + indexing +
  vector replacement, one commit. `LocalBackend.delete` likewise.

SQLite's own transaction handling does the rest: statements before
the commit are one transaction, so a crash or kill before the
commit leaves none of them, and after the commit leaves all of them
(WAL + FULL sync).

Two sequencing notes, straight from the code:

- `decay()` and `consolidate()` first commit any pending state,
  then take their pre-maintenance rolling backup (when
  `auto_backup` is on), then do the maintenance writes and commit.
- `HebbianMemory.backup()` commits pending state before snapshotting,
  so the snapshot includes everything the object has accepted.

## 4. Crash-proof, proven: the kill-9 subprocess tests

Both packages carry a subprocess test with the same design:

1. A child process (`sys.executable -c <script>`) opens the store
   and writes in an infinite loop. After each committed write it
   rewrites a separate *progress file* with the count of committed
   batches.
2. The parent waits until the progress file shows enough commits —
   **at least 30 batches** for Muninn (`activate_batch([1, 2, 3])`),
   **at least 25 upserts** for Huginn local (each upsert a distinct
   document) — with a 60-second deadline.
3. The parent then `proc.kill()`s the child — SIGKILL, no cleanup,
   mid-flight — and reopens the store in-process.

What is asserted on reopen:

- **Muninn** (`test_kill9_mid_write_no_corruption_no_lost_commits`):
  `health()["integrity"] == "ok"`; the per-id activation counts of
  ids 1, 2, 3 **tie exactly** (a torn batch would break the tie);
  the common count is `>=` the last committed count the parent saw;
  connections exist.
- **Huginn** (`test_kill9_mid_write`):
  `health()["integrity"] == "ok"`; `health()["documents"] >=` the
  committed count; a search still returns results.

Recorded results (`BUILD_NOTES_2026-10-30.md` §5): the suites that
contain these tests passed in full — muninn **36 passed, 0 failed**,
huginn **27 passed, 0 failed** — and §5's summary of the kill-9
coverage reads: "kill-9 subprocess (≥30 committed batches, per-id
log counts tie exactly, integrity ok)". In other words: at least 30
committed Muninn batches survive a SIGKILL with per-id activation
counts tying exactly and integrity `ok` on reopen, and the Huginn
test likewise passes at its ≥25-upsert threshold.

## 5. Rolling backups

- Backups live beside the store as `<db file name>.bak-1`,
  `.bak-2`, … up to `backup_keep` generations (**default 3** in
  both configs; `0` disables backups entirely).
- A backup is made through **SQLite's own backup API**
  (`src.backup(dst)`) from a verified-healthy store — never a raw
  file copy of a possibly-mid-write database.
- **Rotation happens only after the new snapshot verifies:** the
  snapshot is written to `<name>.bak-tmp`, probed with
  `PRAGMA quick_check`; only if it passes are generations shifted
  down (`bak-1 → bak-2`, …) and the temp file moved into place. A
  failed backup logs at ERROR level, deletes the temp file, returns
  `None`, and leaves every older generation untouched.
- When backups are taken:
  - **On open, when changed:** `open_store()` compares the store's
    mtime from before opening against the newest backup's mtime;
    only a stale (or missing) newest backup is refreshed. Reopening
    an unchanged store does not churn generations. This requires
    `auto_backup=True` (default), an already-existing store, and
    `backup_keep > 0`.
  - **Before maintenance (Muninn only):** `decay()` and
    `consolidate()` snapshot first, when `auto_backup` is on.
  - **On demand (Muninn only):** `HebbianMemory.backup()` takes one
    now and returns its path. Huginn's local backend exposes no
    equivalent public call in the source; its backups happen on
    open.
- `test_backup_generations_roll` (Muninn, `backup_keep=2`): three
  explicit backups leave exactly `.bak-1` and `.bak-2` and no
  `.bak-3`.

## 6. Corruption recovery on open

The open sequence in each `_db.py`'s `open_store()`:

1. If the store file already exists, it is probed: opened and
   checked with `PRAGMA quick_check`. A probe that throws (not a
   database at all, unreadable header) counts as unhealthy, same as
   a failed check.
2. If unhealthy, the failure is logged at **ERROR** level and the
   newest backup that **itself passes `quick_check`** is restored:
   generations are tried in order `bak-1 … bak-keep`, corrupt
   generations are skipped (each skip also logged at ERROR). The
   WAL sidecars (`<db>-wal`, `<db>-shm`) are removed before and
   after the copy, so no stale WAL frames can be replayed over the
   restored file. The recovery is logged at ERROR level again
   ("RECOVERED store … from backup …").
3. The recovery is surfaced, not hidden:
   - Muninn: `HebbianMemory.recovered_from_backup` is `True`,
     `open_report.recovered_from_backup` / `open_report.restored_backup`
     name what happened, and `health()` includes
     `"recovered_from_backup": True`.
   - Huginn local: `LocalBackend.recovered_from_backup` /
     `open_report` likewise, and `LocalBackend.health()` — hence
     `HuginnMemory.health()` — includes `"recovered_from_backup"`.
4. **If no backup verifies, opening raises the typed StorageError**
   (`MuninnStorageError` / `HuginnStorageError`) with the message
   that the store "is corrupt and no rolling backup verified;
   refusing to start empty over lost memory". There is no road on
   which a corrupt store silently becomes an empty store.

The recovery tests overwrite the main file's header with garbage
(`b"GARBAGE-NOT-A-DATABASE" * 16`) after ensuring a backup exists,
then assert: an ERROR-level log was emitted (Muninn test, via
`caplog` on the `muninn.store` logger), `recovered_from_backup` is
set, health is `"healthy"`, and the data written before the
corruption is still there. The no-backup tests
(`backup_keep=0`, file full of junk) assert the typed StorageError
is raised instead.

One lazy-construction nuance (Huginn): because `HuginnMemory`
builds its backend on first use, a corrupt local store surfaces on
the first operation, not at construction — the Huginn
corruption-without-backup test asserts the raise on
`upsert_memory(...)`. And after `close()`, Muninn operations raise
`MuninnStorageError` (tested); `close()` itself stays idempotent.

## 7. Heal-on-open: structural self-repair

After the integrity/recovery step, every open runs a heal pass.
The pass returns a **report dict counting every fix**; a non-empty
fix count is logged (WARNING level in both cores). Muninn keeps the
report on `last_heal_report`; the local Huginn backend keeps it on
its own `last_heal_report`, and `LocalBackend.heal()` re-runs the
pass on demand.

### Muninn heal (`_heal_locked`, also `heal_structure()`)

Report keys: `self_edges_pruned`, `dangling_edges_pruned`,
`pairs_repaired`, `counters_fixed`, plus `fixes` (their sum).

1. **Self-edges pruned** — every `hebbian_connections` row with
   `memory_a_id = memory_b_id` is deleted.
2. **Dangling edges to tombstoned ids pruned** — rows touching any
   id in `deleted_nodes` are deleted. `forget()`/`delete()` writes
   the tombstone (even when nothing existed), precisely so this
   step can recognize a *deliberately forgotten* id. Edges to ids
   that were never nodes here and never forgotten are **legal by
   design** — Muninn ids are often another store's row ids — and
   are not pruned.
3. **Asymmetric pair repair** — connections are stored as directed
   rows in both directions; for each row, if the reverse row is
   missing it is inserted as a copy; if the two directions disagree
   on strength / count, both are reconciled to the stronger
   strength and the larger count (`consolidated` takes the `min`).
4. **Activation-counter reconciliation** — `node_activation` totals
   are recomputed from `activation_log` per id: a missing counter
   row is inserted (with the log's count and latest timestamp,
   confidence 1.0), a drifted total is corrected.

`consolidate()` also runs this pass as part of itself.

The heal test (`test_heal_repairs_damage`) inserts damage behind
Muninn's back with raw SQL — a self-edge, an edge to a tombstoned
id, a one-directional edge, and a counter set to 999 — and asserts
the report counts each class and the store reads correctly after.

### Huginn local heal (`_heal_locked`, also `heal()`)

Report keys: `orphan_terms_pruned`, `orphan_vectors_pruned`,
`doc_freq_fixed`.

1. **Orphan `doc_terms` pruned** — term postings whose `doc_id` no
   longer exists in `documents` are deleted.
2. **Orphan `doc_vectors` pruned** — stored vectors whose `doc_id`
   no longer exists are deleted.
3. **`corpus_stats` doc_freq recount** — expected frequencies are
   recomputed by counting `doc_terms` per term; every term whose
   stored `doc_freq` differs is corrected (inserted, updated, or
   deleted when it should not exist at all), and each corrected
   term counts once in `doc_freq_fixed`.

The heal test (`test_heal_repairs_index_drift`) sets a term's
`doc_freq` to 999 and inserts a posting for document 99999 behind
the backend's back; `heal()` reports both fixes and the recounted
frequency reads 1 afterwards.

There is no heal for the Qdrant backend — there is no local index
to drift; the server owns its state.

## 8. The pure-reads law

Every read API is a pure read: it must not change any write-bearing
table. This is **proven, not promised**, by table-snapshot tests:

- Muninn `test_reads_are_pure`: a helper snapshots, through a
  *separate* connection, the `activation_log` count, all
  `hebbian_connections` rows (ids, strength, count), the `nodes`
  count, and all `node_activation` counters. Then it calls
  `get_associations` (twice), `activation_count`,
  `spread_activation`, `get_node`, `retrieve` (by query and by
  path), `get_by_path`, `get_children`, `get_tree_structure`,
  `health`, `stats`, and `dump` — and asserts the snapshot is
  byte-for-byte identical afterwards.
- Huginn `test_search_is_pure_read`: snapshots the `documents`
  count, all `doc_terms` rows, and all `corpus_stats` rows; calls
  `search`, `get`, `fly`, and `health`; asserts identity.

**The one exception, named:** Muninn's
`retrieve(..., touch=True)` is the **only** reinforcing read in
either package. It is explicit and opt-in — the default
`touch=False` is pure — and its test asserts the pure call changes
nothing and the `touch=True` call adds **exactly one** activation
log row for the returned node.

**Huginn has none.** `HuginnMemory.search` has no `reinforce`
parameter in the code (see the note in §10); `search`, `get`,
`fly`, `multi_hop_retrieve`, `health`, and `stats` never write to
the store. (`fly` does append to the object's *in-memory* flight
history — process memory, not the store.)

Reinforcement is a named write or it does not happen: `activate`,
`activate_batch`, `associate`, and `retrieve(touch=True)` in
Muninn. Nothing else strengthens anything.

## 9. Typed errors are the error-correcting surface

Callers correct errors by catching types, not by parsing messages
or inspecting half-written state:

- Muninn: `MuninnError` → `MuninnValidationError` (also a
  `ValueError`), `MuninnConfigurationError` (also a `ValueError`),
  `MuninnStorageError`.
- Huginn: `HuginnError` → `HuginnValidationError` (also a
  `ValueError`), `HuginnConfigurationError` (also a `ValueError`),
  `HuginnStorageError`, `HuginnBackendError`.

The rules that make this a correction surface rather than decoration:

- **Validation before any write.** Id types (bools explicitly
  rejected as ids), importance in `[1, 10]`, valence in `[-1, 1]`,
  strengths and rates in their ranges, non-empty string content,
  string queries, config ranges at construction — all checked
  before the store is touched. The validation tests assert that
  after a battery of invalid calls, the store still contains zero
  activations / zero nodes / zero documents.
- **No silent clamping of caller data.** Ranges that are caller
  data (importance, valence, strength) raise; only result-shaping
  parameters are clamped (`limit`, `top_k`, `depth`, hop counts) —
  and those clamps are documented per method in the API reference.
- **Storage and backend failures are typed too:** corruption with
  no valid backup → `…StorageError`; explicit Qdrant unreachable →
  `HuginnBackendError`; a missing optional dependency →
  `HuginnConfigurationError`; operations on a closed Muninn object
  → `MuninnStorageError`.
- **No fake success.** Nothing swallows an exception into a
  success-shaped result. The two designed exceptions are explicit:
  `backend="auto"` answers a missing Qdrant with the local backend
  and says so in `health()`; `fly()` returns a flight with `error`
  set instead of raising (the ancestor's contract), and the error
  string is right there in the result.

## 10. Idempotency — what is safe to retry

| Operation | Idempotent? | Why |
|---|---|---|
| `remember` / `store` (Muninn) | Yes | Content-hash unique index on `(content_hash, category, path)`; a repeat returns the existing id. Proven under a 10-thread race. |
| `upsert_memory` (Huginn) | Yes | Same content in the same category is the same memory on both backends (unique key locally; deterministic derived point id on Qdrant). A repeat replaces fields and re-indexes instead of duplicating. |
| `close()` (both, and both backends) | Yes | Second and later calls are no-ops (Bifröst double-closes; tested). |
| `decay()` / `consolidate()` (Muninn) | Safe to re-run | Deterministic functions of current state; a second `consolidate()` reports `newly_consolidated == 0`. (Re-running `decay(days)` naturally fades further — it is re-runnable, not a no-op.) |
| `heal_structure()` / `heal()` | Yes | Repairs drift; on a healthy store every count is 0. |
| `backup()` (Muninn) | Yes | Takes a fresh snapshot; rotation is verify-first. |
| `activate` / `activate_batch` (Muninn) | **No — intentionally** | An activation is an event. Logging it twice is two events, and the counts must say so. Callers who need exactly-once semantics must dedupe at their own layer. |
| `associate` (Muninn) | No | Each call counts a co-activation (`co_activation_count += 1`), even the `strength=` form. |

## 11. Benchmarks (indicative only)

From `BUILD_NOTES_2026-10-30.md` §4 — measured 2026-10-30 on the
build VM **while it was loaded** (twelve campaign keepers running;
Python 3.12.3, SQLite 3.45.1). The notes themselves label these
numbers "indicative, not promises". Scripts:
`muninn/scripts/benchmark.py`, `huginn/scripts/benchmark.py`.

Muninn (5,000 nodes seeded; 812 connection rows, 30,000 activations
after seeding):

| Operation | Result |
|---|---|
| `remember()` × 5,000 | 986 ms total (0.20 ms/node, incl. WAL FULL commit each) |
| `activate()` × 20,000 | 2,821 ms total (0.14 ms/call) |
| `activate_batch(5 ids)` × 2,000 | 1,275 ms total (0.64 ms/batch; wires 20 pairs per batch) |
| `get_associations()` × 5,000 | 371 ms (0.07 ms/read) |
| `spread_activation(depth=2)` × 1,000 | 375 ms (0.37 ms/call) |
| `decay(days=1)` full store | 193 ms (incl. pre-maintenance backup snapshot) |
| `consolidate()` full store | 99 ms (incl. backup snapshot) |
| `stats()` | 1.1 ms |

Huginn, local TF-IDF backend (5,000 documents; the synthetic corpus
uses a 22-word vocabulary, so every query term matches most
documents — a worst case for candidate-set size):

| Operation | Result |
|---|---|
| `upsert_memory()` × 5,000 | 4,113 ms total (0.82 ms/doc incl. indexing) |
| `search(limit=10)` | median 16.5 ms, p95 80.9 ms |
| `search(limit=10, category=…)` | median 1.7 ms, p95 55.9 ms |

## 12. Known honesty notes

- **Code vs build notes, Huginn `search`:** §1.4 and §3.2 of the
  BUILD_NOTES mention a `search(..., reinforce=...)` shape. **The
  code has no such parameter** — `HuginnMemory.search(query_text,
  limit, category, min_importance)` only — and §3.2 itself ends by
  recording that "the parameter does not exist". The code wins:
  Huginn search is a pure read, full stop.
- The Huginn kill-9 test's commit threshold in code is **25**
  upserts; the "≥30 committed batches" figure in the BUILD_NOTES
  §5 summary sentence belongs to the Muninn test. Both tests pass
  as written in the tree.
- Live Qdrant **server** behaviour is *not* part of the proven
  reliability story: the Qdrant backend is proven against a fake
  client in `huginn/tests/test_qdrant_fake.py`, not a real server
  (BUILD_NOTES §5, NOT PROVEN). Everything in this document about
  WAL, backups, healing, and kill-9 concerns the SQLite stores.
