# Bulk remember (RM-060)

Part V's ingest slice. Storing memories one `remember` call
at a time pays the full per-call cost N times: validate +
hash, one transaction (one commit), and one backpressure
head-count per node. `HebbianMemory.remember_many(items)`
is the batch API the roadmap names — item dicts carrying
`remember`'s arguments by name — built so the batch costs
what the batch should: **one preparation pass, one
transaction, backpressure applied once**. The gate script
is `muninn/scripts/bulk_remember.py`; the record committed
from the after tree's third run is
`muninn/scripts/bulk_remember.json`.

## The contract (and where it deliberately differs from a loop)

- **One preparation pass.** Every item is validated,
  serialized and content-hashed exactly once, *before* the
  transaction opens. The preparation is `remember`'s own —
  extracted into `_prepare_remember`, which both roads call
  — and the insert is likewise shared
  (`_insert_prepared_locked`), so batch and loop semantics
  cannot drift. RM-060 adds no new SQL shape: the RM-040
  audit total is unchanged at 98 sites.
- **One transaction.** All inserts land or none do. An
  invalid item anywhere, or a hash collision (RM-047)
  against the store or *within* the batch, rolls the whole
  batch back. This is deliberately stricter than a loop,
  whose earlier calls stay stored when a later one fails —
  a batch caller retries the batch whole, or not at all.
- **One timestamp.** The batch is stamped with a single
  `_tick()` reading — the `activate_batch` discipline: one
  ingest, one moment.
- **Backpressure applied once.** The `max_nodes` check runs
  once, after the commit, over the batch's final count
  (a loop runs it after every new node).
- **Per-item idempotency is `remember`'s.** An item whose
  content already lives under its category+path returns
  that node's id (first write wins, differing fields
  ignored); a duplicate inside the batch returns the id its
  first occurrence created. The result list always has
  exactly one id per input item, in input order.
- **Item shape is closed.** `content` is required; the
  only other keys are `category`, `path`, `importance`,
  `tags`, `emotional_valence`, `metadata`, with
  `remember`'s defaults. A non-dict item, an unknown key,
  or a missing `content` key is a typed refusal before any
  write (four new RM-018-pinned messages).

## Gate numbers — the loop vs the batch (10,000 nodes)

Same script, same machine; each row is one full script run
(itself the median of 3 ingests per road, fresh store per
ingest, RM-020 corpus, category `bench`, tmpfs stores).
Both roads' stores were verified logically identical —
same ids in order, same per-node fields excluding
timestamps — inside every run, before any timing was
recorded.

| run | `remember` loop | `remember_many` | speedup |
|---|---|---|---|
| 1 | 2,079.9 ms | 677.7 ms | 3.07× |
| 2 | 1,603.2 ms | 603.9 ms | 2.65× |
| 3 (committed record) | 1,028.6 ms | 367.4 ms | 2.80× |
| **median of the three runs** | **1,603.2 ms** | **603.9 ms** | **2.65×** |

**Honesty about the timing rows:** the VM was shared and
loaded throughout (1-minute load averages 3.6–4.6 across
the runs), so the absolute milliseconds are indicative —
the loop's own time swung 2× between runs. What does not
swing is the shape of the win, and it is pinned by tests,
not timings: one COMMIT for the whole ingest instead of
one per node, one backpressure head-count instead of one
per node, one `_tick()` instead of one per node. Every run
showed the batch faster by 2.65×–3.07×; the slice claims
the median, 2.65×, on this machine and storage class. On
real disk (where each loop commit is an fsync under
`synchronous=FULL`) the gap can only widen; that road is
not measured here and is not claimed.

## What the tests pin

`muninn/tests/test_bulk_remember.py` (17 tests): full
field fidelity of stored items (string + JSON content);
logical parity with the loop road on a 40-item mixed batch
(ids, stats, every node field) plus the one-timestamp
stamp; empty batch as a no-op; in-batch duplicates and
store hits (first write wins); the `Muninn` facade; the
transaction shape by trace callback (exactly one COMMIT
and one backpressure count for 50 nodes; two COMMITs when
backpressure prunes); backpressure victims exactly the
stated lowest-value order; atomic refusals (invalid item
mid-batch, oversize item, container/item shape guards);
the forced-hash collision rolling back the whole batch
with the pre-existing node untouched; a disk-full batch
surfacing as the typed `remember_many` storage error with
nothing stored; an encrypted store round-trip + idempotent
hit through the keyed tag; the RM-044 log discipline on the
batch path; and the gate script's small-run shape + the
committed record. The RM-013 matrix gains row M-30
(`remember_many` is idempotent; a failed batch is always
safe to re-issue whole).

## Honest limits

- The batch is one transaction, so a 10k-node ingest holds
  one write transaction open for its whole duration —
  other writers wait on the busy timeout, exactly as they
  would behind any long write. Callers with latency
  neighbours should batch in chunks; each chunk is its
  own atomic unit.
- Preparation holds every item's serialized form in memory
  before the transaction opens — O(batch), the price of
  validating everything before writing anything.
- AUTOINCREMENT sequence behaviour is the loop's own,
  unchanged: an idempotent hit (either road) may consume a
  sequence value without creating a row, so ids after
  retries are not guaranteed dense. No caller may read
  meaning into id gaps; none could before this slice.
