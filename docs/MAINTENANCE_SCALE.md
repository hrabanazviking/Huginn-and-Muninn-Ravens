# RM-064 — Decay/consolidate at scale: chunked maintenance

**Class:** BENCH
**Slices:** RM-064 (Part V — Speed)

Muninn's two maintenance passes, `decay` and `consolidate`,
were full-store UPDATEs: one transaction that touched every
edge row (and, for decay, every confidence row) in the
store. At personal-store scale that is fast — the gate
below measures ~0.35 s at 100,000 edges — but the
transaction is as large as the store, a long run reports
nothing until it ends, and a crash anywhere in it rolls
the whole pass back to zero. RM-064 chunks both passes.

## What changed

- One new config field, Muninn only: `maintenance_chunk_size`
  (`int`, default `1000`, validated `>= 1` — a typed
  `MuninnConfigurationError` otherwise). Huginn has no
  decay/consolidate pass and gains nothing in this slice
  beyond the slice-log pin.
- `decay(days, progress=None)` walks the edge table in
  rowid order in chunks of at most `maintenance_chunk_size`
  rows — fade, unmark and prune applied to the chunk, then
  **committed** — then walks `node_activation` the same
  way for confidences.
- `consolidate(threshold=None, progress=None)` walks the
  edge table in chunks the same way (mark, then unmark,
  per chunk, committed per chunk); the heal pass that
  follows commits as it always did.
- The per-row maths is the old road's, applied chunk by
  chunk in row order, so **the final store state is
  exactly the pre-RM-064 full-store result at any chunk
  size** — proven by parity tests against a raw-table
  reference at chunk sizes 1, 2, 7 and 1000, and inside
  the gate script at 100,000 edges.
- Decay and consolidate touch edges and `node_activation`
  only — never node rows — so the RM-063 warm cache owes
  them no invalidation.

## Atomicity — per chunk, stated plainly

The atomicity is **per chunk**: every chunk is fully
applied or fully rolled back, never half a chunk. An
interrupted run (a crash, a failure, a progress callback
raising) leaves the store at a chunk boundary — committed
chunks applied, the rest untouched — and the store is
consistent and re-runnable from there (decay and
consolidate are both safe to re-run). The reports state
this in every return dict:

```python
{"chunks": int,          # chunks committed by this call
 "chunk_size": int,      # the configured ceiling
 "atomicity": "per_chunk"}
```

This is a deliberate change from the pre-RM-064
all-or-nothing-across-the-whole-store transaction, made
because the roadmap asks for exactly it: bounded
transactions and a usable progress signal on long
maintenance, with the boundary stated in the report
rather than implied.

## Progress reporting

`progress` is an optional callable taking one event dict,
called **after each committed chunk**:

```python
{"operation": "decay" | "consolidate",
 "phase": "edges" | "confidences",   # decay has both; consolidate: edges
 "chunk": int,        # 1-based within the phase
 "processed": int,    # rows of this phase committed so far
 "total": int}        # rows in the phase when the run started
```

A callback exception propagates and stops the run at the
last committed chunk boundary — the boundary semantics
above are exactly what a stopped run leaves behind.

## The gate — 100,000 edges

`muninn/scripts/maintenance_scale.py` builds the RM-058
uniform store (5,000 nodes, ring lattice, 100,000 directed
edge rows, 50 activation confidences), snapshots the raw
tables, and runs decay (10 days) and consolidate in the
chunked road (chunk 1000) and in a single-chunk road
(chunk larger than the store — the pre-RM-064 shape).
Every run's final tables are compared row-for-row
against an independent old-road reference computed from
the raw snapshot, and chunked vs single-chunk finals are
compared against each other; timings are quoted only for
runs whose parity held. Record committed at
`muninn/scripts/maintenance_scale.json` (after tree,
2026-11-02T23:19:40Z, 1-minute load 1.29).

| Operation | Before (RM-063 tree) | After (chunk 1000) | After (single chunk) |
|---|---|---|---|
| decay 10d, median of 3 | 351.0 ms | 441.1 ms | 576.8 ms (one run) |
| consolidate, median of 3 | 379.9 ms | 462.3 ms | 551.6 ms (one run) |

(Before record run the same evening, load 0.88: decay
351.0 / 345.0–420.9 ms, consolidate 379.9 ms; chunked
decay ran 101 chunks — 100 edge chunks + 1 confidence
chunk — consolidate 100 chunks. `edges_pruned` was 0 at
gate scale: the seeded strengths (0.1–0.9) decayed by
10 days stay above the 0.01 prune threshold; pruning
parity is pinned by the unit tests, not the gate.)

**Honest reading:** chunking is *slower* per run at this
scale — roughly a quarter more wall-clock on these
medians, the price of ~100 commits instead of one — and
no speed win is claimed. What the slice buys is what the
roadmap asked for: transactions bounded at
`maintenance_chunk_size` rows no matter how large the
store grows, a live progress signal, and a crash boundary
at most one chunk behind the work done. At 100k edges the
old full-store pass was already sub-second, so the cost
is small in absolute terms (~90 ms); the single-chunk
road remains available to any caller who wants the old
shape (set `maintenance_chunk_size` above the store's
edge count).

## Acceptance (BENCH)

- 100k-edge gate run with parity verified inside every
  run (above).
- `tests/test_maintenance_chunks.py` (15 items): field
  default + typed validation; report chunking fields;
  decay parity against the raw-table reference at chunk
  sizes 1 / 2 / 7 / 1000; exact progress sequences;
  callback failure leaves the store at a chunk boundary
  and re-runnable; a mid-chunk statement failure (a
  RAISE(ABORT) trigger) rolls its chunk back whole while
  earlier chunks stay committed; consolidate parity,
  progress and heal composition; the callback boundary
  for consolidate; `decay_wall_clock` carrying the chunk
  fields; empty-store zero-chunk runs; this record; the
  gate script + committed record shape.

## Honesty ledger

- Live Qdrant round-trip: NOT PROVEN (unchanged; Muninn
  maintenance issues no Qdrant traffic).
- Sentence-transformers path: NOT PROVEN (unchanged).
- Timings are single-machine medians under the recorded
  load, indicative only — the load-independent results
  are the parities and the chunk counts.
