# Muninn read path (RM-058)

Part V's first optimization slice, and it starts where the
RM-057 atlas left off: the atlas showed Muninn's reads flat
to 100k *nodes* — but its store carried only ~4,000
connection rows. This slice profiles `get_associations` and
`spread_activation` at **100k edges**, changes only what the
profile shows to be in pain, and files the before/after gate
numbers from one script (`muninn/scripts/read_path.py`) run
unchanged on the pre-slice and post-slice trees.

## The graphs

- **uniform** — 5,000 nodes, each associated with the next
  10 nodes on a ring (fixed strength formula): 50,000
  undirected pairs = **100,000 directed rows**, degree 20.
- **hub** — one hub associated with 10,000 spokes: 20,000
  directed rows, hub degree 10,000. Hubs are where read
  paths go to die.

## What the profile showed (before)

- `get_associations` on an ordinary node: flat and cheap
  (~0.05 ms/call at degree 20) — no pain, no change needed
  for the common case.
- `get_associations` on the hub with the default
  `limit=100`: **~10 ms/call**. The query plan said why:
  `SEARCH ... USING INDEX sqlite_autoindex (memory_a_id=?)`
  plus `USE TEMP B-TREE FOR ORDER BY` — the query fetched
  all 10,000 of the hub's rows and sorted them to return
  100.
- `spread_activation` depth 2 from the hub: **~200 ms**.
  It issued one SQL query per frontier node — 10,001
  queries for the hub's depth-2 walk — and re-sorted every
  node's rows in Python, rows the primary-key index already
  returns in id order.
- `spread_activation` depth 1 from the hub (~70 ms for
  10,000 examined edges) is a single query either way; its
  cost is the Python row loop, and this slice does not
  claim a win there (see the table).

## The changes (two, both in Muninn)

1. **Covering index `idx_conn_a_strength`** on
   `hebbian_connections (memory_a_id, strength DESC,
   co_activation_count DESC, memory_b_id ASC, consolidated,
   last_coactivated_at)`. The first four keys are exactly
   `get_associations`' filter + ordering; the last two are
   trailing keys carrying the remaining selected columns so
   the index covers the query (this machine's SQLite build
   rejects the `INCLUDE` clause outright — probed directly
   against SQLite 3.45.1, which reports the version that
   has supported `INCLUDE` since 3.31 — so trailing keys
   do the job instead). Tables, columns and the shared
   cross-store schema contract are unchanged. The index is
   created by the schema script on every open, so a store
   written before RM-058 gains it on its next open — that
   upgrade is test-pinned.
2. **Batched frontier reads in `spread_activation`**: one
   query per chunk of 500 frontier ids per depth level
   (`IN (...)` with bound parameters, `ORDER BY
   memory_a_id, memory_b_id`) instead of one query per
   node. The batched order is exactly the old walk's
   examination order — frontier ids ascending, neighbours
   ascending — so every result, including where the RM-053
   candidate cap bites and what `last_spread_activation_stats`
   reports, is bit-for-bit the old walk's. Chunked at 500
   so the bound-variable count stays under SQLite's legacy
   999 limit. The new SQL shape is a pinned template in the
   RM-040 audit (placeholders only; every id still travels
   as a bound parameter).

No public API, signature or return shape changed.

## Gate numbers — before / after

Same script, same machine, back-to-back runs; each cell is
the **median of three full script runs** per tree (each run
itself a median of 3 over its sample batch). Loads across
the six runs: 1-minute averages 1.5–3.2 on a shared,
loaded VM — indicative, not absolute. Stores on tmpfs.

| operation (sample) | before | after | |
|---|---:|---:|---:|
| uniform get_associations ×200 | 10.7 ms | 7.2 ms | flat (noise band) |
| uniform spread depth2 ×50 | 96.0 ms | 90.0 ms | flat |
| uniform spread depth3 ×20 | 99.6 ms | 96.2 ms | flat |
| hub get_associations limit=100 ×20 | 207.2 ms | 3.1 ms | **~67×** |
| hub get_associations limit=10000 ×20 | 1,870.9 ms | 1,091.4 ms | ~1.7× |
| hub spread depth1 ×1 | 71.1 ms | 76.9 ms | no win claimed |
| hub spread depth2 ×1 | 208.3 ms | 95.3 ms | **~2.2×** |

Query plan, before: `SEARCH hebbian_connections USING
INDEX sqlite_autoindex_hebbian_connections_1
(memory_a_id=?)` + `USE TEMP B-TREE FOR ORDER BY`.
After: `SEARCH hebbian_connections USING COVERING INDEX
idx_conn_a_strength (memory_a_id=? AND strength>?)` — no
temp b-tree.

The committed record (`muninn/scripts/read_path.json`) is
the after tree's third run (recorded 2026-11-02, load
[1.98, 2.89, 3.60] at record time); the before record and
all six runs stand in the slice's verification evidence.

## Honest limits

- The remaining hub costs are Python, not SQL: returning
  10,000 association dicts costs ~55 ms/call however they
  are fetched, and a depth-1 hub spread examines 10,000
  rows through one Python loop. Further wins there are
  pagination/laziness API questions, not index questions,
  and are not this slice's to invent.
- Ordinary-degree reads were already flat; the index costs
  one more index maintained on every connection write.
  That trade is recorded, not hidden: Part V's write-path
  slices (RM-059/RM-060) will measure write costs with
  this index in place.
- A live Qdrant round-trip and the sentence-transformers
  path stay **NOT PROVEN** — untouched by this slice.
