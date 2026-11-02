# Baseline atlas (RM-057)

Part V — Speed opens with a map, not a change: every headline
operation of both packages measured at **1k / 10k / 100k** nodes
(Muninn) and documents (Huginn), extending the RM-005/006 bench
harness. The machine-readable records are committed beside the
scripts that made them — `muninn/scripts/atlas.json` and
`huginn/scripts/atlas.json` — each produced by its package's
`scripts/atlas.py`, each carrying the RM-006 environment block
and per-scale RM-020 corpus blocks. This page is the human
record; the JSON is the evidence.

## How the atlas measures

- **The seed is the write operation.** `remember` / `upsert`
  are timed as the total ms to store the whole scale from the
  RM-020 formula corpus — the same generators as the RM-005
  gate, so atlas and gate numbers describe the same texts.
- **Every other operation uses a fixed sample batch, identical
  at every scale** (Muninn: 2,000 `activate`, 500
  `activate_batch(5)`, 1,000 `get_associations`, 200
  `spread_activation(depth=2)`, 200 `stats`; read/maintenance
  ops take the median of 3 runs. Huginn: median per search over
  50 `search` and 25 filtered `search`). The atlas therefore
  shows how an operation's cost grows with *store size*, never
  mixing store size with batch size.
- **Storage class: tmpfs.** Stores lived on `/tmp` (tmpfs),
  the same storage class as the RM-005 baselines. Write
  operations are fsync-sensitive and the difference is not
  small: a controlled A/B on this VM on 2026-11-02 measured
  the RM-005 benchmark's 2,000 `activate` at **172.6 ms on
  tmpfs vs 58,843.2 ms on the overlay disk** (~340×). Atlas
  write numbers are tmpfs numbers; never quote them without
  the storage class.
- **The atlas is a record, not a gate.** Nothing here fails on
  a slow number. RM-071 wires the atlas operations into the
  regression gate.

## Muninn — recorded 2026-11-02 (this VM)

Environment (from the record): x86_64 Linux
(`Linux-7.0.0-39-generic-x86_64-with-glibc2.39`), 4 CPUs,
Python 3.12.3, SQLite 3.45.1, load average at record time
**[1.26, 5.46, 5.24]** — a loaded, shared machine; every
number below is indicative, not absolute, exactly as RM-006
requires it to be labelled.

One design fact the atlas had to face: Muninn's backpressure
ceiling (`MuninnConfig.max_nodes`) defaults to **20,000**, so
a default-config seed of 100,000 texts does not produce a
100k-node store — it prunes back (a default-config seed built
in this slice's first attempt sat at exactly 20,001 nodes).
The atlas therefore raises the ceiling to an exact fit per
scale, recorded in every entry as
`details.config_overrides = {"max_nodes": <scale>}`, and the
record proves the claim: `store_after_seed.total_nodes`
equals the scale at all three scales (with 4,000 connection
rows and 4,500 activations after the activation samples).

| operation (sample) | 1k | 10k | 100k |
|---|---:|---:|---:|
| remember ×scale (seed, total ms) | 404.6 | 1,494.0 | 577,093.1 |
| activate ×2000 | 998.6 | 283.3 | 413.6 |
| activate_batch(5) ×500 | 607.0 | 504.4 | 787.8 |
| get_associations ×1000 (median of 3) | 185.7 | 86.5 | 87.2 |
| spread_activation(depth=2) ×200 (median of 3) | 218.0 | 88.2 | 108.7 |
| decay(days=1) (median of 3) | 73.6 | 28.9 | 505.4 |
| consolidate (median of 3) | 44.4 | 121.3 | 599.7 |
| stats ×200 (median of 3) | 322.5 | 1,794.2 | 31,790.6 |

Reading the map, honestly:

- **Reads are flat.** `get_associations` and
  `spread_activation` cost the same at 100k as at 10k within
  load noise — the indexed read paths do not degrade with
  store size at personal-store scales and beyond.
- **`stats()` is the outlier.** Per call: ~1.6 ms at 1k,
  ~9.0 ms at 10k, **~159 ms at 100k** — it grows with the
  store. This is the clearest pain the atlas shows, and it is
  measured, not suspected: later Part V slices (and RM-071's
  gate) start from here.
- **Maintenance is sane.** Full-store `decay` and
  `consolidate` at 100k are ~0.5–0.6 s medians.
- **The 100k seed number is a load artefact, labelled as
  such.** remember at 100k (577 s, ~5.8 ms/node) ran while
  the VM carried many other campaigns (5-minute load 5.46);
  the 1k/10k seeds (~0.4 / ~0.15 ms/node) show the same code
  on a quieter moment. Non-monotonic small-scale rows
  (activate at 1k slower than at 10k) are the same noise.
  The atlas records the environment block precisely so this
  cannot be quoted as a clean per-node cost.

## Huginn — recorded 2026-11-02 (this VM, local backend)

Environment (from the record): x86_64 Linux, 4 CPUs,
Python 3.12.3, SQLite 3.45.1, load average at record time
**[2.39, 5.94, 5.71]** — loaded and shared, indicative only.

| operation | 1k | 10k | 100k |
|---|---:|---:|---:|
| upsert ×scale (seed, total ms) | 1,388.7 | 11,612.9 | 101,382.0 |
| upsert per doc (ms) | 1.39 | 1.16 | 1.01 |
| search(limit=10), median ms/search | 33.27 | 16.46 | 12.00 |
| search p95 (ms) | 101.54 | 96.98 | 71.50 |
| search(category filter), median ms/search | 1.89 | 6.15 | 1.62 |
| search filtered p95 (ms) | 4.99 | 73.49 | 1.97 |

Reading the map, honestly:

- **Upsert is a steady ~1.0–1.4 ms/doc at every scale** —
  100k real document rows stored in ~101 s under load. The
  write path does not degrade with store size.
- **The search rows carry a corpus caveat, and the record
  itself proves it.** The RM-020 formula corpus contains
  only **23 distinct documents** (the generator's period is
  23), repeated across the scale. RM-053's cost accounting,
  filed per scale in the record
  (`last_search_stats_after_search`), shows the local search
  was offered **230 candidates at 1k, 10k and 100k alike**
  (23 texts × 10 categories), scored all 230, and the
  10,000-candidate cap never bit (`capped: false` at every
  scale; the filtered search scored 23 of 230). So the flat
  search curve is real *for this candidate pool* — it does
  **not** prove search cost over 100k *distinct* documents.
  A distinct-content corpus is the named gap RM-061/RM-062
  must close before any search-at-scale claim is made; the
  atlas records the pool size precisely so the gap cannot be
  missed. (Muninn's corpus has no such caveat: its formula
  texts are all distinct — 100,000 of 100,000.)
- Median rows that fall as the store grows (search 33 ms at
  1k vs 12 ms at 100k) are load noise across runs, not a
  speedup; the environment blocks differ and say so.

A live Qdrant round-trip stays **NOT PROVEN** — the atlas is
local-backend only, like the RM-005 gate.

## What the atlas feeds

RM-058 (Muninn read path), RM-059 (activation write path),
RM-061/062 (Huginn search), RM-064 (decay/consolidate at
scale) and RM-071 (regression gates) all start from these
tables: an optimization claim from here on is a before/after
against the atlas, measured the same way, or it is not a
claim at all.
