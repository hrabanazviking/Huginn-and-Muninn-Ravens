# Muninn — interface

Hebbian associative memory in one SQLite store. Odin's memory raven:
nodes, activation, co-activation wiring, decay, consolidation —
self-healing and crash-proof. Stdlib only. Python ≥ 3.11.

## Install

```bash
pip install ./muninn          # or: pip install -e ./muninn
```

## The contract surface (Bifröst-compatible)

```python
from muninn import HebbianMemory
from muninn.config import MuninnConfig

mem = HebbianMemory(MuninnConfig(db_path="~/.hermes/memory/muninn_hebbian.db"))
mem.activate(memory_id)                        # log one activation (WRITE)
mem.activate_batch([id1, id2], emotional_valence=0.0)   # activate + wire pairs (WRITE)
mem.get_associations(memory_id, min_strength=0.0)       # [{memory_id, strength, ...}] strongest first (READ)
mem.decay(days=1.0)                            # fade + prune (WRITE) -> dict
mem.consolidate()                              # mark strong edges consolidated (WRITE) -> dict
mem.health()                                   # {"status": "healthy", ...} (READ)
mem.stats()                                    # {"total_activations", "total_connections", ...} (READ)
mem.close()                                    # idempotent
```

Store schema shared with Bifröst/Hermes by contract: tables
`activation_log (memory_id, activated_at, emotional_valence, source)`
and `hebbian_connections (memory_a_id, memory_b_id, strength,
co_activation_count, …)`. Connections are stored as directed rows in
**both** directions, kept symmetric by the API. Memory ids are
integers (Mímir row ids in Bifröst deployments).

## Node API (ancestor semantics)

`remember(content, *, category, path, importance=1..10, tags,
emotional_valence=-1..1, metadata) -> int` — idempotent by content
hash. `remember_many(items) -> list[int]` is its batch form
(RM-060): item dicts carrying the same arguments by name, one
preparation pass, one transaction (a bad item or collision
rolls the whole batch back), one timestamp, backpressure
applied once; per-item idempotency unchanged. `store(...)` is
the ancestor-shaped alias (`memory_type` =
category). Also: `get_node`, `retrieve(query, path, tags, memory_type,
top_k, touch=False)`, `get_by_path`, `get_children`, `update`, `move`,
`delete`/`forget`, `get_tree_structure`, `dump`, and `Muninn` — an
ancestor-shaped facade constructed with a data directory.

`retrieve` is a **pure read** by default. `touch=True` is the one
explicitly named reinforcing read: it also activates what it returns.

## Semantics

- **Activation**: appends one `activation_log` row, increments the
  id's counter, and restores its confidence toward 1.0
  (`conf ← conf + rate·(1 − conf)`).
- **Wiring**: co-activation strengthens each pair both directions by
  the bounded rule `s ← 1 − (1 − s)(1 − rate)` (default rate 0.1);
  strengths live in [0, 1]. `associate(a, b, strength=|delta=)` wires
  manually.
- **Decay**: strengths × `0.5^(days/30)` by default, confidences ×
  `0.5^(days/90)`; edges under the prune threshold (0.01) are deleted
  and counted in the returned dict.
- **Consolidation**: edges ≥ threshold (default 0.8) are marked
  consolidated; the heal pass runs as part of it. Content is never
  rewritten.
- **Spread**: `spread_activation(seed_ids, depth, attenuation)` —
  pure-read BFS returning `{id: activation}`.

## Failure behaviour

- Invalid arguments raise `MuninnValidationError` **before** any write.
- Storage failures raise `MuninnStorageError`. A corrupt main store is
  restored from the newest verified rolling backup (`<db>.bak-N`,
  created via SQLite's backup API) and logged loudly;
  `mem.recovered_from_backup` and `health()` report it. If no backup
  verifies, opening raises — Muninn never silently starts empty over
  lost memory.
- Durability: WAL + `synchronous=FULL`; a `kill -9` loses at most the
  uncommitted transaction. Batch writes are single transactions.
- Self-healing: on open and on demand (`heal_structure()`), self-edges
  and edges to forgotten ids are pruned, asymmetric pairs repaired,
  and activation counters reconciled with the log. The report dict
  counts every fix. Edges to ids never registered as nodes are legal
  (cross-store ids) and are *not* pruned.
- Threading: one shared connection, all methods serialized by an
  internal lock; safe under concurrent use (proven by race tests).
  Concurrent openers — several objects on one store file, in one
  process or across processes — are supported (RM-037,
  `docs/CONCURRENT_OPENERS.md`).
- `activate` is an event and is intentionally **not** idempotent;
  `remember`/`store`, `close`, `decay`, `consolidate` are safe to
  retry/re-run.

Errors: `MuninnError` → `MuninnValidationError`,
`MuninnConfigurationError`, `MuninnStorageError`.
