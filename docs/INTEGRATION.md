# Integration — using the ravens in other projects

How to install Muninn and Huginn into your own project, what to
expect from their versions, and three worked wirings: a generic app
memory layer, the Bifröst binding these packages were built against,
and adopter notes for Hermes and other projects in the same house.

Plain version first: the two packages are independent. Each installs
on its own, opens only its own SQLite file, and never imports the
other. Composition — asking Muninn *what belongs with this?* and
Huginn *what matches this question?* and merging the answers — is
always the host app's job.

- Muninn (`muninn/`): Hebbian associative memory — nodes, an
  activation log, co-activation wiring, decay, consolidation.
- Huginn (`huginn/`): semantic retrieval — upsert memories, search
  them back scored. Local SQLite TF-IDF store by default; Qdrant
  when a server is genuinely there.

Both: version **1.0.0**, MIT, **Python >= 3.11**, stdlib-only cores.
Repo: https://github.com/hrabanazviking/Huginn-and-Muninn-Ravens —
the packages live in the repo-root subdirectories `muninn/` and
`huginn/`, each with its own `pyproject.toml`.

---

## 1. Install routes

### From a clone

```bash
git clone https://github.com/hrabanazviking/Huginn-and-Muninn-Ravens
cd Huginn-and-Muninn-Ravens

pip install ./muninn                     # Muninn alone
pip install ./huginn                     # Huginn, local backend, zero infrastructure
pip install './huginn[qdrant]'           # + Qdrant support (qdrant-client>=1.9,<2)
pip install './huginn[embeddings]'       # + neural embeddings (sentence-transformers>=2.2,<6)
```

Editable installs, for development against a checkout:

```bash
pip install -e ./muninn
pip install -e ./huginn
```

Muninn has no runtime dependencies and no extras that change its
behaviour (only a `dev` extra: `pytest>=7,<10`). Huginn's core is
likewise dependency-free; the two extras above are the only optional
dependencies in either package.

### Straight from git (pip VCS form)

Each package installs directly from the repo by subdirectory:

```bash
pip install "muninn @ git+https://github.com/hrabanazviking/Huginn-and-Muninn-Ravens#subdirectory=muninn"
pip install "huginn @ git+https://github.com/hrabanazviking/Huginn-and-Muninn-Ravens#subdirectory=huginn"
```

With a Huginn extra, the extra goes on the package name, before the
`@`:

```bash
pip install "huginn[qdrant] @ git+https://github.com/hrabanazviking/Huginn-and-Muninn-Ravens#subdirectory=huginn"
pip install "huginn[embeddings] @ git+https://github.com/hrabanazviking/Huginn-and-Muninn-Ravens#subdirectory=huginn"
```

Pinning to a specific commit or tag works the usual pip way, by
appending `@<ref>` to the repository URL (before the
`#subdirectory=` fragment).

### First smoke test

```python
from muninn import HebbianMemory
from muninn.config import MuninnConfig

mem = HebbianMemory(MuninnConfig(db_path="./data/muninn_hebbian.db"))
print(mem.health())   # {"status": "healthy", ...}
mem.close()

from huginn import HuginnMemory

h = HuginnMemory(config=None)           # works with no server anywhere
print(h.health())     # names its backend honestly ("degraded" + local
                      # fallback reason when no Qdrant answered)
h.close()
```

Importing either package constructs nothing and opens no file.
`HuginnMemory` construction is also lazy — its backend is built on
first use. `HebbianMemory` construction does open its store (and
only its store).

## 2. Versioning expectations

- **Both packages are at 1.0.0 and version independently.** Either
  one may move without the other; they share no code and no
  dependency. Pin them separately in your requirements.
- **The shared store schema is contractual.** Muninn's store file is
  read *directly* by other codebases (see §4 and §5), so these are
  contract, not implementation detail:
  - table `activation_log` with columns `memory_id`, `activated_at`,
    `emotional_valence`, `source`;
  - table `hebbian_connections` with columns `memory_a_id`,
    `memory_b_id`, `strength`, `co_activation_count` (plus
    `consolidated`, `created_at`, `last_coactivated_at` in the
    actual schema), stored as directed rows in **both** directions,
    kept symmetric by the API;
  - memory ids are **integers**.
- **Schema changes only with a `schema_version` bump.** The Muninn
  store's `meta` table carries `schema_version = "1"`
  (`SCHEMA_VERSION` in `muninn/_db.py`, also reported by
  `HebbianMemory.health()`). Huginn's local store carries the same
  stamp in its own `meta` table. A future change to the contractual
  tables/columns will arrive together with a bump of that value —
  adopters reading the tables directly should check it.
- What is *not* contractual: the remaining tables (`nodes`,
  `node_activation`, `deleted_nodes` in Muninn; `documents`,
  `doc_terms`, `corpus_stats`, `doc_vectors` in Huginn), result
  fields beyond the documented ones, and anything in modules whose
  names start with an underscore. `HebbianMemory._get_conn()` is the
  one underscore member that is contractual in practice, because
  Bifröst already depends on it (see §4).

## 3. Worked example (a): a generic app memory layer

The standard composition: Huginn holds the searchable text, Muninn
holds *what was thought of together*. One id space serves both —
here, the ids Muninn's `remember()` hands out are passed to Huginn
as `memory_id=`, so a search hit's id is directly usable for
association lookups. (Bifröst aligns ids the same way.)

```python
from muninn import HebbianMemory
from muninn.config import MuninnConfig
from huginn import HuginnMemory, HuginnConfig

DATA = "./data"   # the host app's data directory

muninn = HebbianMemory(MuninnConfig(db_path=f"{DATA}/muninn_hebbian.db"))
huginn = HuginnMemory(HuginnConfig(
    backend="local",                       # zero infrastructure;
    local_db_path=f"{DATA}/huginn_local.db",  # "auto" also works and
))                                         # falls back to this file

def learn(text: str, *, category: str = "general", importance: int = 5) -> int:
    """Store one memory in both ravens. WRITE (both stores)."""
    mid = muninn.remember(text, category=category, importance=importance)
    huginn.upsert_memory(content=text, category=category,
                         importance=importance, memory_id=mid)
    return mid

def recall(query: str, *, reinforce_top: int = 3) -> list[dict]:
    """Answer a question: retrieval, then association, then learning.

    The search itself is a pure read. Reinforcement is a separate,
    named write — the app decides whether recalling should also
    strengthen, and says so in its own code.
    """
    hits = huginn.search(query_text=query, limit=10)          # READ
    if not hits:
        return []
    # Widen the top hit with what memory associates with it.
    top = hits[0]
    neighbours = muninn.get_associations(top["id"], min_strength=0.2)  # READ
    # The app used these together — record that, by name. WRITE.
    used = [top["id"]] + [n["memory_id"] for n in neighbours[:2]]
    if len(used) > 1:
        muninn.activate_batch(used[:reinforce_top])
    else:
        muninn.activate(used[0])
    return hits

def nightly_maintenance() -> None:
    """Fade what is unused, consolidate what is strong. WRITE."""
    print(muninn.decay(days=1.0))
    print(muninn.consolidate())

a = learn("The hall door sticks in winter", category="household", importance=6)
b = learn("Oil the hinges before the first frost", category="household", importance=5)
muninn.activate_batch([a, b])        # they were learned together: wire them

for hit in recall("door winter problem"):
    print(hit["score"], hit["content"])

print(muninn.health(), huginn.health())
muninn.close()
huginn.close()
```

Wiring rules this example follows, and yours should too:

- **Keep the two stores separate** — two files, two objects. Neither
  package ever opens the other's file.
- **Reads are pure, so they are safe on hot paths.** `search`,
  `get_associations`, `spread_activation`, `get_node`, `retrieve`
  (default), `health`, and `stats` never write. They are proven pure
  by table-snapshot tests (see `docs/RELIABILITY.md` §8).
- **Writes are named.** If recalling should strengthen memory, call
  `activate` / `activate_batch` yourself, as above. The only
  reinforcing read anywhere is Muninn's `retrieve(..., touch=True)`,
  and it is opt-in.
- **Close what you open.** Both `close()` methods are idempotent,
  and both classes work as context managers.

## 4. Worked example (b): the Bifröst binding

Bifröst is the composite memory provider these packages were built
to serve: **hrabanazviking/bifrost**, pinned at commit
`b66e98cc8a79d4dede22ba11d68a1a5ecd22ebd6` (**v1.0.0**). The
contract below was extracted from its source in full
(`src/bifrost/core.py`, `src/bifrost/config.py`,
`src/bifrost/bridges/memory_bridge.py`, `tests/test_bifrost.py`,
`tests/test_hebbian_guard.py`) and is recorded in
`docs/BUILD_NOTES_2026-10-30.md` §1. If you write a bridge of your
own, this is the exact call surface to mirror.

### 4.1 The exact calls Bifröst makes

Muninn:

| Call | What Bifröst relies on |
|---|---|
| `from muninn import HebbianMemory` | Exported at package top level. |
| `from muninn.config import MuninnConfig` | Module `muninn.config`, class `MuninnConfig`. |
| `MuninnConfig(db_path=<str>)` | Dataclass, `db_path` keyword; may contain `~`. |
| `HebbianMemory(config)` | Positional config. |
| `muninn.activate(memory_id)` / `activate(id, emotional_valence=float)` | Logs one activation (a WRITE, by name). |
| `muninn.activate_batch(ids, emotional_valence=float)` | Logs each activation **and** wires all pairs. |
| `muninn.get_associations(memory_id, min_strength=float)` | List of dicts, each with `"strength"`; Bifröst takes `[0]` as the boost, so the list is sorted by strength **descending**. |
| `muninn._get_conn()` | Returns a `sqlite3.Connection` (Row factory). Bifröst runs raw SQL `SELECT COUNT(*) as cnt FROM activation_log WHERE memory_id = ?` on it and reads `row["cnt"]`. |
| `muninn.decay(days=float)` | Returns a dict. |
| `muninn.consolidate()` | Returns a dict. |
| `muninn.health()` | Dict containing `"status": "healthy"` when well. |
| `muninn.stats()` | Dict containing `"total_activations"` and `"total_connections"` (the hebbian-guard tests check these keys). |
| `muninn.close()` | Idempotent (the bridge double-close is tested). |

Huginn:

| Call | What Bifröst relies on |
|---|---|
| `from huginn import HuginnMemory` | Exported at package top level. |
| `HuginnMemory(config=None)` | Must work with **no config and no Qdrant server** — Bifröst never passes its `qdrant_url`; the defaults land on a working local backend. |
| `huginn.upsert_memory(content=, category=, importance=, tags=, emotional_valence=)` | Returns the stored vector id (`int`). |
| `huginn.search(query_text=, limit=, category=None, min_importance=int)` | List of dicts with keys `id`, `content`, `category`, `importance`, `tags` (a list), `emotional_valence`, `score`. |
| `huginn.health()` | Dict containing `"status"`. |
| `huginn.close()` | Optional for Bifröst (it checks `hasattr`); provided, and idempotent. |

And the schema contract of §2 is part of this binding: Bifröst's
own memory class inserts into `activation_log` by column name and
runs its boost query over `hebbian_connections`
(`memory_a_id`, `memory_b_id`, `strength`, `co_activation_count`),
directionally — which is why connections are stored as directed
rows in both directions.

What Bifröst's *own* `search()` / `recall()` do on top of this —
including their write-on-read reinforcement behaviour — is
Bifröst's documented design choice, implemented by calling the
named write APIs above. No write is hidden inside the ravens.

### 4.2 Verification result (BUILD_NOTES §5)

Verified 2026-10-30 / 2026-10-31 in a fresh venv
(`pip install -e muninn -e huginn` plus Bifröst from the pinned
clone):

- **Bifröst's own test suites: 25 passed, 0 failed**
  (`tests/test_bifrost.py` + `tests/test_hebbian_guard.py`; the
  guard scenarios run against the real Muninn).
- **End-to-end through the `BifrostBridge` public API: PASS** —
  `_ensure_muninn()` / `_ensure_huginn()` construct the real
  classes; `store()` returns both `mimir_id` and `huginn_id`;
  `search()` merges Huginn-sourced results with composite scores;
  `recall()` grows the Muninn activation log by exactly 1; with
  fixtures past the guard threshold, a 2-result search wires
  connections 0 → 2 (both directions stored); `decay()` and
  `consolidate()` return proper reports through the bridge;
  `health()` shows Mímir healthy, Muninn healthy, and Huginn
  **degraded** — auto mode fell back to local because
  `qdrant-client` was not installed in that venv, with the reason
  stated; `stats()` aggregates all three; double `close()` is safe.
- Qdrant-client-present roads (client installed into the verify
  venv afterwards): `backend="auto"` against a dead URL falls back
  to local with `fallback_reason` recorded; `backend="qdrant"`
  against a dead URL raises `HuginnBackendError`.

**NOT PROVEN, stated plainly:**

- A live Qdrant **server** round-trip. No server existed on the
  verification machine; the Qdrant backend is proven against a
  faithful fake client (round trip, filters, derived ids, error
  roads), not a real server.
- The `sentence-transformers` embedder path (the extra was not
  installed during verification). The hashing-embedder path *is*
  proven end-to-end.
- One observed Bifröst-side behaviour, not a raven defect: memories
  added via `bridge.store()` are not visible to Mímir FTS search
  until an FTS rebuild, because Bifröst's schema has no FTS sync
  triggers. Huginn covers those memories immediately.

## 5. Adopter notes: Hermes

What the build record states about Hermes (recorded in
`docs/BUILD_NOTES_2026-10-30.md` §1; nothing beyond it is claimed
here):

- Hermes' `plugins/volmarr-core/memory_fabric.py` **consumes the
  contract surface** — the same Muninn/Huginn calls catalogued in
  §4 — including a read-only probe from its Slice 87 work.
- **Default paths** (the packages' own defaults, which match the
  Hermes layout):
  - Muninn: `~/.hermes/memory/muninn_hebbian.db`
    (`MuninnConfig.db_path` default).
  - Huginn local: `~/.hermes/memory/huginn_local.db`
    (`HuginnConfig.local_db_path` default).
  With those defaults, plain `HebbianMemory()` / `HuginnMemory()`
  land in the Hermes memory directory with no path configuration.
- **The Slice 87 probe** reads Muninn's store **directly**: it
  requires the tables `activation_log` and `hebbian_connections`
  to exist in the store file. That is one of the two reasons those
  tables are contractual (§2) — any Hermes-side tooling that reads
  the file the same way should likewise stick to the contractual
  columns and check `meta.schema_version` (`"1"`).

Practical notes for the Hermes wiring:

- Construct each memory object **lazily and separately** — one
  object per store, each opening only its own file — matching how
  the packages are tested to behave.
- Because every read is pure, Hermes can call `search`,
  `get_associations`, `health`, and `stats` on hot paths without
  side effects; reinforcement stays in the named writes
  (`activate`, `activate_batch`).

## 6. Adopter notes: Ember / Rúnmál / ThoughtForge

These are wiring guidance only — this document does not describe
those projects' internals, and adopters should map the pattern of
§3 onto their own data layout:

- **Construct with explicit db paths under the host app's data
  dir.** Do not rely on the `~/.hermes/...` defaults outside
  Hermes; pass `MuninnConfig(db_path="<app data>/muninn_hebbian.db")`
  and `HuginnConfig(backend="local",
  local_db_path="<app data>/huginn_local.db")` (or
  `backend="auto"` if the app may run near a Qdrant server and a
  silent, reported fallback to local is acceptable).
- **Keep the two stores separate.** Two files, two objects, no
  shared connections. If the app needs one id space across both,
  mint the id in one place and pass it along — `remember()`'s
  returned id into `upsert_memory(..., memory_id=...)`, as in §3.
- **Reads are pure, so they are safe on hot paths** — render loops,
  request handlers, and other read-heavy code may call `search`,
  `get_associations`, `spread_activation`, `retrieve`, `health`,
  and `stats` freely; they cannot mutate memory state.
- **Writes are named.** Anything that should change memory says so:
  `remember`/`store`, `upsert_memory`, `activate`,
  `activate_batch`, `associate`, `update`, `forget`/`delete`,
  `move`, `decay`, `consolidate`, `heal_structure`. Put
  `decay()` / `consolidate()` on the app's own maintenance cadence
  (a nightly job, an idle hook), not on a read path.
- **Catch the typed errors at the app boundary** —
  `MuninnValidationError` / `HuginnValidationError` for bad caller
  input, `…StorageError` for store trouble,
  `HuginnBackendError` / `HuginnConfigurationError` for backend and
  setup trouble — and let the app decide policy. The libraries
  never fake success, so the app never has to guess.
- **Threading:** one object per store is safe to share across the
  app's threads (each object serializes itself internally). A
  second object onto the same store file — in the same process or
  another one — is also supported (RM-037): committed writes are
  visible across objects at once, SQLite serializes ordinary
  reads and writes, and the packages' coordination lock
  serializes the open-time duties and backups. See
  `docs/CONCURRENT_OPENERS.md` for the full definition and its
  limits.
- **Backups come along for free:** each store keeps rolling,
  verified backups beside its file (`backup_keep`, default 3) and
  self-heals on open. The app's own backup story should treat the
  `.db` file plus its `.bak-N` generations as one unit — and never
  copy a live `.db` without its `-wal` sidecar and call that a
  backup; use `HebbianMemory.backup()` (Muninn) or a quiet moment
  (Huginn) instead.

---

*Companion documents: `docs/API_REFERENCE.md` (every public class,
function, and method, with signatures) and `docs/RELIABILITY.md`
(durability, threading, self-healing, and the pure-reads law, each
traced to code and tests). The build record is
`docs/BUILD_NOTES_2026-10-30.md`.*
