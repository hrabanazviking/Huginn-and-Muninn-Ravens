# Huge-Batch Atomicity — RM-035

*One transaction, exact counts, memory bounded by the batch —
not by the square of the batch.*

`activate_batch` is the Hebbian operation: activate every unique
id once, then wire **every unordered pair**. The pair count grows
quadratically — a batch of 10,000 ids wires

    10,000 × 9,999 / 2 = 49,995,000 unordered pairs
                     = 99,990,000 directed connection rows.

## What v1.0.0 did (measured by probe)

The original implementation looped in Python over
`itertools.combinations(ids, 2)` and ran four SQL statements per
pair through `_wire_pair_locked` (plus four per id for the
activations). Probed on this machine (loaded VM, load ~13) with
ids 1..500 against the pre-RM-035 packages:

    500 ids → 124,750 pairs in 16.90 s

At that rate a 10k batch — 400× the pairs — is hours of wall time.
The semantics were never wrong; the road could not carry the load
the roadmap asks for.

## The defined behaviour

Two roads, one contract:

* **Below 64 unique ids** — the original per-pair loop, unchanged.
* **At or above 64 unique ids** — the bulk road
  (`_activate_batch_bulk_locked`): the same writes, restated
  set-at-a-time inside the same single transaction.

  * Activations are the four writes of `_log_activation_locked`
    issued as `executemany` over generators (activation log row,
    node-activation upsert with the same confidence rule, node
    access bump, tombstone delete).
  * `pairs_wired` is arithmetic: `n(n−1)/2`.
    `connections_created` subtracts the pairs already wired in
    **both** directions — the loop's exact rule, since
    `_wire_pair_locked` reports a pair created when *either*
    directed row was missing. A one-direction drift therefore
    counts as created on both roads, and the bulk insert repairs
    the missing direction fresh while strengthening the survivor.
  * The wiring is one `INSERT … SELECT` over a TEMP staging table
    self-joined on `<>`, with the same insert strength
    (`learning_rate`), the same bounded strengthening on conflict
    (`strength ← 1 − (1 − strength)(1 − learning_rate)`,
    `co_activation_count += 1`), and the same timestamps.
  * The secondary index `idx_conn_b` is dropped for the insert
    and recreated before commit, **inside the same transaction**.
    Maintaining it row-by-row turns the insert's sequential
    primary-key writes into random secondary-index writes — the
    measured bottleneck (a raw-SQL prototype at 1,000 ids:
    23.6 s with the index maintained, 4.0 s insert + 1.5 s
    reindex without). A rollback restores the dropped index with
    everything else, so the store never observably lacks it; the
    recreated index uses the exact `SCHEMA_SQL` statement, and the
    RM-004 / RM-022 schema pins pass unchanged.

**Memory-bounded** means Python-side: the only Python structure
is the caller's id list. Pairs are generated inside SQLite, never
materialised in Python — pinned by a subprocess test in which
16× the pairs (44,850 → 719,400) move peak RSS by less than
40 MB, and by the 10k bench's own peak-RSS figure below.

**Atomicity** is unchanged and pinned at bulk scale: against a
page-capped store (the RM-029 disk-full fault), a 400-id bulk
batch fails typed, leaves zero activations and zero connections,
and the rollback restores `idx_conn_b`; once space returns, the
same batch lands with exact counts.

## The 10k bench proof (BENCH)

`muninn/scripts/huge_batch_bench.py`, run once against the
banked tree in a fresh venv (`ravens-rm035-venv`, non-editable
install; Python 3.12.3, SQLite 3.45.1, this VM):

<!-- BENCH10K -->
Record (`~/workspace/.verify-tmp/rm035/bench10k.json`,
recorded 2026-11-01T22:42:34Z, load_avg [11.23, 8.76, 7.77]):

    10,000 ids → 49,995,000 unordered pairs
               = 99,990,000 directed connection rows
    wall time: 1629.6 s (~27.2 min) under that load
    peak RSS:  47.5 MB — Python-side memory stayed flat
               while ~50 M pairs were wired inside SQLite
    store size after the batch: 12,232,638,464 bytes
    all eight bench checks passed: report fields exact,
    directed rows exact, activation log exact,
    node-activation exact, sampled strength/count uniform.
<!-- /BENCH10K -->

The small end of the same bench, for scale: 500 ids in **0.64 s**
(the pre-RM-035 loop took 16.90 s for the same batch size on this
machine) — peak RSS 25.0 MB, all eight bench checks passed.

What a huge batch honestly costs is disk: the measured 10k run
above left a 12,232,638,464-byte store — ~122 bytes per directed
row (the row plus its two index entries). That is the shape of the
data — every pair is a real, queryable connection — not overhead
the slice can design away without breaking the schema law.

## Pinned by tests

`muninn/tests/test_huge_batch_atomicity.py` (7 tests): exact
counts at 800 ids against the store's own rows; de-duplication
before counting; a repeat batch strengthening exactly
(`connections_created` 0, every row at the twice-strengthened
strength with count 2); pre-wired pairs and one-direction drift
counted and repaired exactly; loop/bulk agreement across the
64-id threshold; disk-full rollback at bulk scale including
index restoration; and the subprocess memory-scaling pin above.
Huginn has no batch operation — this slice is Muninn-only.
