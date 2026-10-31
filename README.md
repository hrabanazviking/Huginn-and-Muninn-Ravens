# Huginn and Muninn — the Ravens

Two small Python packages that give a program a memory and a way to
think about it.

In the old stories, Odin has two ravens. **Huginn** is Thought: he
flies out over the world and returns with what is relevant.
**Muninn** is Memory: he keeps what happened, and what belongs
together. These packages are those two ravens, built as software:

- **Muninn** (`muninn/`) — *memory and association.* Memory nodes,
  an activation log, and Hebbian wiring: memories that are used
  together grow connected, unused ones decay, strong ones
  consolidate. One SQLite file. Stdlib only.
- **Huginn** (`huginn/`) — *thought and retrieval.* Ask a question,
  get the most relevant memories back, scored. Runs on a fully
  capable local store with zero infrastructure, or on Qdrant when a
  server is genuinely there. Stdlib-only core.

Each package installs and works **on its own**. Together — as the
Bifröst memory bridge composes them — they are the memory fabric of
a persistent agent. They never depend on each other; composition is
the caller's job, which keeps each one usable in any project.

## Why they exist

Bifröst, the composite memory provider, was written against two
sibling packages — a `huginn` and a `muninn` — that were never kept
as auditable code. Its write paths (consolidation, decay,
reinforcement, ingestion) could not be enabled, because nobody could
say exactly what those packages would do.

So the ravens were rebuilt from the ancestors (the NorseSagaEngine
ravens and the Yggdrasil Cognitive Architecture design), true to
what they were always supposed to be: robust, self-healing,
error-correcting, threaded, crash-proof, and efficient — modular
parts meant to be useful across many projects. The full build
record, including the contract that was extracted from Bifröst's
own source, is in
[docs/BUILD_NOTES_2026-10-30.md](docs/BUILD_NOTES_2026-10-30.md).

## Quickstart

Both packages need Python ≥ 3.11. From a clone of this repo:

```bash
pip install ./muninn
pip install ./huginn            # local backend, zero infrastructure
pip install './huginn[qdrant]'  # optional: + Qdrant support
pip install './huginn[embeddings]'  # optional: + neural embeddings
```

### Muninn alone — remember, wire, recall

```python
from muninn import HebbianMemory
from muninn.config import MuninnConfig

mem = HebbianMemory(MuninnConfig(db_path="./memory/muninn_hebbian.db"))

a = mem.remember("The hall door sticks in winter", category="household", importance=6)
b = mem.remember("Oil the hinges before the first frost", category="household", importance=5)

mem.activate_batch([a, b])              # they were thought of together: wire them
print(mem.get_associations(a))          # strongest first -> b is there
print(mem.spread_activation([a]))       # {a: 1.0, b: ...}
mem.decay(days=30.0)                    # unused state fades, and says by how much
mem.close()
```

### Huginn alone — store, ask, receive

```python
from huginn import HuginnMemory

h = HuginnMemory(config=None)           # works with no server anywhere
h.upsert_memory(content="The hall door sticks in winter",
                category="household", importance=6)
h.upsert_memory(content="Oil the hinges before the first frost",
                category="household", importance=5)

for hit in h.search(query_text="door winter problem", limit=5):
    print(hit["score"], hit["content"])
print(h.health())                       # names its backend, honestly
h.close()
```

With no Qdrant server running, `backend="auto"` falls back to the
local store and *says so* — `health()` reports `status: "degraded"`
with the reason. A missing server never crashes the caller. Ask for
`backend="qdrant"` explicitly and a missing server is a loud, typed
error instead. That is the deal: degrade honestly or fail loudly,
never fake success.

### Both together

Muninn answers *"what belongs with this?"*; Huginn answers *"what
matches this question?"*. Bifröst merges the two (plus Mímir's
verbatim store) into one composite memory. See
[docs/INTEGRATION.md](docs/INTEGRATION.md) for worked examples,
including the Bifröst binding.

## The reliability story, in brief

- **Crash-proof.** SQLite in WAL mode with `synchronous=FULL`.
  Kill the process mid-write and you lose at most the transaction
  that never committed. This is not a claim — both packages carry
  subprocess kill tests that prove it.
- **Self-healing.** Every open checks integrity. A corrupt store is
  restored from its own newest *verified* rolling backup, loudly.
  Structural drift (broken wiring in Muninn, index drift in
  Huginn's local store) is repaired on open and reported.
- **No silent data loss, ever.** If a store is corrupt and no
  backup verifies, opening raises a typed error. The ravens never
  quietly start empty over lost memory.
- **Honest reads.** Every read API is a pure read — proven by tests
  that snapshot the store before and after. The one reinforcing
  read (Muninn's `retrieve(..., touch=True)`) carries its nature in
  its name. Huginn has none: reinforcement is Muninn's job.
- **Threaded.** One shared connection per store, serialized
  internally; safe under concurrent use, proven by race tests with
  exact final counts.
- **Typed errors.** Validation happens before any write, and every
  failure leaves as a typed exception. Libraries should not fake
  success; callers decide policy.

The long version is [docs/RELIABILITY.md](docs/RELIABILITY.md).

## Honesty ledger

Proven (2026-10-30, from the test runners and a live Bifröst run):

- muninn: **36/36 tests passed**. huginn: **27/27 tests passed**.
- Bifröst (`hrabanazviking/bifrost` @ `b66e98cc`, v1.0.0): its own
  suites pass **25/25** against these packages, and an end-to-end
  run through `BifrostBridge` — store, search, recall, reinforce,
  decay, consolidate, health, stats — passed.

**NOT PROVEN**, stated plainly:

- A live Qdrant **server** round-trip. No server was available on
  the build machine; the Qdrant backend is proven against a
  faithful fake client (round trip, filters, derived ids, error
  roads), not a real server.
- The `sentence-transformers` embedder path. The extra was not
  installed during verification; the deterministic hashing
  embedder path *is* proven end-to-end.
- Performance on unloaded hardware. The benchmark numbers in the
  build notes were measured on a heavily loaded machine and are
  indicative only.

Scoring honesty, too: Huginn's local default score is TF-IDF
cosine — *lexical* semantics (weighted word overlap), genuinely
useful, and labelled as what it is. It is not neural embedding
similarity, and nothing here pretends otherwise.

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — how the two packages are designed and how they compose
- [docs/MUNINN_GUIDE.md](docs/MUNINN_GUIDE.md) — Muninn concepts, usage, configuration, failure behaviour
- [docs/HUGINN_GUIDE.md](docs/HUGINN_GUIDE.md) — Huginn concepts, backends, usage, configuration
- [docs/DATA_STRUCTURES.md](docs/DATA_STRUCTURES.md) — every table, file, record shape, and error type
- [docs/API_REFERENCE.md](docs/API_REFERENCE.md) — the complete public API of both packages
- [docs/RELIABILITY.md](docs/RELIABILITY.md) — durability, threading, self-healing, and the pure-reads law
- [docs/INTEGRATION.md](docs/INTEGRATION.md) — using the ravens in other projects
- [docs/BUILD_NOTES_2026-10-30.md](docs/BUILD_NOTES_2026-10-30.md) — the build record: contract, fidelity, benchmarks, verification
- [RAVENS_ROADMAP_2026-10-31.md](RAVENS_ROADMAP_2026-10-31.md) — the road ahead

Each package also carries its own `INTERFACE.md` (the short-form
contract) beside its code.

## Repo layout

```
muninn/     the Memory Raven — package, tests, benchmark script
huginn/     the Thought Raven — package, tests, benchmark script
docs/       guides, architecture, data structures, reliability, integration
```

## Licence

MIT — see [LICENSE](LICENSE). Copyright (c) 2026 Volmarr Wyrd.
