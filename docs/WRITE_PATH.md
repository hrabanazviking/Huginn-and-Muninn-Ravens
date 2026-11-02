# Muninn activation write path (RM-059)

Part V's write-side slice. `activate` is Muninn's hottest
write — every reinforcement, every `activate_batch`, and
every `retrieve(..., touch=True)` passes through the one
helper, `_log_activation_locked`. The roadmap's charge:
batch its counter/log/node updates into the fewest
statements that keep the semantics, proven by the
count-exact tests. The gate script is
`muninn/scripts/write_path.py`, run unchanged on the
pre- and post-slice trees; the record committed from the
after tree's third run is `muninn/scripts/write_path.json`.

## What one activation did before

Five data statements per call (counted by trace callback
over the store's own connection, attestation off):

1. `INSERT` the `activation_log` row;
2. `INSERT … ON CONFLICT` the `node_activation` counter
   (confidence restored by the bounded formula);
3. `UPDATE nodes` — access count + `updated_at`;
4. `DELETE` the id's `deleted_nodes` tombstone;
5. `SELECT total_activations` — a re-read of the counter
   the upsert in step 2 had just written, solely to return
   it to the caller.

With attestation on, the chain advance added a meta read
plus an `executemany` of the two head rows (head, count).

## The changes (two, both in Muninn)

1. **The counter upsert returns its total.** On SQLite
   3.35+ the upsert carries `RETURNING total_activations`,
   so statement 5 disappears: **four statements per
   activation** — [INSERT, INSERT, UPDATE, DELETE]. Four
   is the floor without a schema or trigger change: four
   distinct tables change (log, counter, node, tombstone)
   and each is its own statement. Older runtimes — the
   documented WAL floor is 3.7.0, far below 3.35 — keep
   the upsert + re-read road behind the
   `muninn.core._RETURNING_OK` version check; the
   semantics (and every count) are identical, only the
   statement count differs, and the fallback road is
   test-pinned with the flag forced off.
2. **The attestation head write is one statement.** The
   two meta rows (head, count) now land via a single
   `INSERT OR REPLACE … VALUES (?, ?), (?, ?)` instead of
   an executemany of two — same rows, same transaction,
   one execution.

No public API, signature, return shape, table, column or
index changed. The RM-040 audit gained one pinned site
(the fallback road's upsert is a second constant form of
the counter write; total 97 → 98).

## Gate numbers — before / after

Same script, same machine; each cell is the **median of
three full script runs** per tree (each run itself a
median of 3 over its sample batch). Stores on tmpfs.

| operation (sample) | before | after |
|---|---|---|
| statements per `activate()` | **5** | **4** |
| activate same id ×2000 | 215.8 ms | 205.9 ms |
| activate distinct ids ×2000 | 256.7 ms | 213.3 ms |
| activate_batch(5) ×400 | 394.4 ms | 211.9 ms |
| retrieve(touch=True) ×200 | 11,791.6 ms | 8,300.9 ms |

**Honesty about the timing rows:** the statement count is
this slice's hard gate — it is exact, machine-independent
(on the RETURNING road), and pinned by tests. The timings
are indicative only, and this tick they are also
load-confounded: the before runs measured at 1-minute load
averages of 8.6–9.5, the after runs at 0.9–5.9, on a shared
VM running many campaigns. Every timing moved in the
expected direction and none is quoted as a multiplier;
the claim this slice banks on is 5 → 4 statements (a 20%
cut in per-activation SQL executions, and one fewer
round-trip through the counter's index on every
activation, on every caller of the helper — including
the RM-035 bulk road's per-id attestation advance and
`retrieve(touch=True)`).

## What the tests pin

`muninn/tests/test_write_path.py` (10 tests): the executed
statement count + shapes per `activate()` on both roads;
the attested head write as exactly one meta statement and
the chain verifying `ok` on a fresh open; count-exact
semantics against raw SQL ground truth — sequential
totals returned per id, log/counter/access counts equal
after mixed activation of live nodes, a forgotten id
(tombstone cleared, counting continues) and a
never-remembered id; the confidence formula bit-for-bit
(1.0 on first activation, `c + lr·(1 − c)` after a decay);
small-batch `activate_batch` pair/count reports;
`retrieve(touch=True)` counts; the gate script's small-run
shape and the committed record.

## Honest limits

- The remaining per-activation cost is four indexed
  writes plus a commit (fsync-bound on real disks; the
  gate's stores are tmpfs, the RM-005 storage class).
- `retrieve(touch=True)`'s measured cost is dominated by
  the retrieval scan, not the activation helper — this
  slice does not claim to have sped the scan up.
- The fallback road means a deployment on SQLite < 3.35
  sees no statement reduction. That is the price of the
  3.7.0 WAL floor recorded in `docs/SQLITE_RUNTIME.md`;
  raising that floor is a version-policy decision, not a
  speed slice's to take silently.
