# Backup Cost — RM-065

Roadmap RM-065: *backup-on-open and pre-maintenance
snapshots measured at 100k scale; add incremental or
copy-on-write strategies only if the numbers demand
it.* This record is the measurement, the verdict, and
the reasoning. Gate scripts:
`muninn/scripts/backup_cost.py` and
`huginn/scripts/backup_cost.py`; committed records at
`muninn/scripts/backup_cost.json` (recorded
2026-11-03T00:06:49Z, 1-minute load 6.16) and
`huginn/scripts/backup_cost.json` (recorded
2026-11-03T00:06:58Z, load 5.90). Stores on tmpfs;
timings under multi-campaign load are indicative —
the load-independent facts are the byte counts, the
per-megabyte rate both packages agree on, the
took-backup flags, and the table comparisons.

## What a snapshot is

A rolling backup (`take_backup` in each package's
`_db.py`, twin machinery) is a **full copy**: SQLite's
backup API copies the whole store to `.bak-tmp`, the
snapshot inherits the store's permissions (RM-043),
it must pass `quick_check`, and only then do the
generations rotate (RM-037). There is no incremental
element today. The three roads that pay for one:

1. **Backup-on-open** — only when the store changed
   since the newest backup (mtime staleness, judged in
   `open_store`); an unchanged store pays nothing.
2. **Pre-maintenance** — Muninn's `decay` /
   `consolidate` (and `decay_wall_clock` through them)
   take one unconditionally when `auto_backup` is on:
   the snapshot is the recovery point for the pass
   that follows.
3. **Explicit** — the public `backup()` call.

## Muninn at 100k edges

Seed: the RM-058 uniform store — 5,000 nodes,
100,000 directed edges, 50 confidences,
19,972,096 bytes — built once via the public API and
byte-copied fresh for every measurement.

| Measurement | Result |
|---|---|
| Snapshot (median of 3) | **94.7 ms** (93.4 / 94.7 / 101.5), 19,972,096 bytes, quick_check + edge count verified on every run |
| Snapshot rate | **4.74 ms/MB** |
| Open, unchanged (median of 3) | 545.0 ms; took a backup **0 of 3** (backup hash stood still) |
| Open, changed (median of 3) | 591.3 ms; took a backup **3 of 3** |
| Open backup share | +46.3 ms — the snapshot is a minority of an open's prepare/heal cost at this scale, and the share reads under it |
| `decay(10d)` backup share | +91.1 ms (medians 733.2 with vs 642.1 without) — one snapshot, as expected |
| `consolidate()` backup share | +120.4 ms (831.1 vs 710.6) — one snapshot, as expected |

## Huginn at 100k documents

Seed: 100,000 documents by direct construction
(documents rows only — term index and `doc_vectors`
intentionally empty, as in RM-062's scale corpus;
backup cost is byte-proportional, so the rate is the
carrier), 46,391,296 bytes.

| Measurement | Result |
|---|---|
| Snapshot (median of 3) | **196.8 ms** (133.7 / 196.8 / 197.2), quick_check + document count verified |
| Snapshot rate | **4.24 ms/MB** |
| Open, unchanged (median of 3) | 196.8 ms; took a backup **0 of 3** |
| Open, changed (median of 3) | 313.1 ms; took a backup **3 of 3** |
| Open backup share | **+116.3 ms** — the snapshot's order, as expected |

The two packages' rates agree (4.74 vs 4.24 ms/MB):
a snapshot costs what its bytes cost, in either
package, at either gate's scale. Projected by the
rate, a snapshot of RM-062's 477,544,448-byte Huginn
vector store would cost ~2.0–2.3 s — the one scale in
the records where a snapshot is seconds, not
milliseconds.

## The double pay — proven, bounded, named

The gate's `double_pay` case: a store changes, is
opened (the open takes a backup), and `decay` runs
immediately, with no write in between. The decay's
pre-maintenance snapshot was compared row-for-row
(nodes, edges, confidences) against the open's
backup: **identical**. That second snapshot bought
nothing — the recovery point it exists to create
already existed. Its cost is one snapshot: ~95 ms at
the 100k-edge Muninn store, ~2.0–2.3 s projected at
the 477 MB vector-store scale.

It is also narrow: any write between the open and
the maintenance pass makes the snapshot non-redundant
again, and ordinary operation writes constantly
(recall with `touch=True`, activations, remembers).
The window is *open → maintain, untouched*.

## Verdict: no strategy built — NOT demanded

**The numbers do NOT demand an incremental or
copy-on-write strategy at personal-store scale, and
none is built.** The full snapshot is 95–197 ms at
every store size the gates build; it is paid at most
once per open-that-changed and once per maintenance
pass; and the machinery it would replace is the
durability core pinned by RM-037 (coordination),
RM-043 (permissions), RM-049 (encryption composition)
and RM-051 (secure-forget purge across generations).
A page-incremental scheme (SQLite's paged backup
against a persistent base) or a reflink copy-on-write
scheme would redesign generation rotation itself —
a large, risky change to buy back a tenth of a
second in the common case. That trade fails the
roadmap's own test: *only if the numbers demand it*.

Named trigger for reopening: if stores at the
~500 MB scale become routine (the projected ~2.2 s
snapshot), or if the open → maintain pattern becomes
a hot road, the double pay is the first thing to
kill, and the sound design is recorded here so it is
not reinvented unsoundly:

- **Never skip on main-file mtime alone.** In WAL
  mode, committed writes can sit in the `-wal` file
  while the main file's mtime stands still; a backup
  taken through a fresh connection sees them, but an
  mtime comparison does not. (The open road's
  existing check is safe because it runs after
  open-time recovery has folded any leftover WAL.)
- The sound skip: `wal_checkpoint(TRUNCATE)` first
  (folds every committed frame into the main file,
  moving its mtime iff anything was folded), *then*
  the mtime comparison against the newest backup —
  skip the snapshot only when the checkpoint folded
  nothing and a backup exists. Anything less is a
  durability bug wearing a speed costume.

## What this slice changed

No package code, no public API, no schema, no SQL —
so no Bifröst re-verification is required (the
RM-057 pattern). New: the two gate scripts + their
committed records, `tests/test_backup_cost.py` in
both packages (muninn 4, huginn 4: gate shape, a
small run's behaviour incl. the took-backup flags,
committed-record shape, this record's verdict pin),
the BENCHMARKS pointer, and the slice-log entry.
Live Qdrant + sentence-transformers stay NOT PROVEN.
