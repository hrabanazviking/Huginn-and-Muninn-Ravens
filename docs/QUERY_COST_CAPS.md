# Query Cost Caps — RM-053

*Security, slice fourteen: denial-of-service bounds.*

Threat **TH-13** in `docs/THREAT_MODEL.md`: expensive reads
consume unbounded CPU/time. Input *sizes* were already
bounded (RM-027 ceilings, RM-035's memory-bounded batch
road, RM-036's depth bound), and the two expensive reads
named by the threat — Muninn's `spread_activation` and
Huginn's local search — already bound their *output*
(`limit` / `top_k`). What they did not bound was the
*work*: the candidate set a single call would examine on
its way to that output. A hub node with tens of thousands
of edges, a dense graph, or a corpus where every document
shares the query term made one call examine all of it.
This slice adds the explicit candidate-set caps, with
visibility when a cap bites.

## The defined behaviour

### Muninn — `MuninnConfig.max_spread_candidates` (default 100000)

A **candidate** is one neighbour row (one directed edge)
considered during the expansion. One `spread_activation`
call examines **at most** `max_spread_candidates`
candidates, whatever the graph's shape:

* Frontier nodes are expanded in id order and each node's
  neighbours are considered in id order, so *which*
  candidates fit under the ceiling is deterministic —
  repeated calls on an unchanged store return identical
  results, capped or not.
* When the ceiling is reached, the expansion stops. The
  call returns the activations it has (seeds included) —
  a partial result, honestly reported (below), never an
  error: a capped spread is a bounded answer, not a
  failure.
* Below the ceiling nothing changes: the aggregation is
  order-independent (each node keeps the strongest value
  any path gives it), so the result is exactly the
  unbounded walk's.

### Huginn — `HuginnConfig.max_search_candidates` (default 10000)

A **candidate** is one document the index offers for a
query: on the TF-IDF road, a document containing at least
one query term; on the vector road, a document in the
vector table. One local search **scores at most**
`max_search_candidates` candidates:

* Candidates are considered in document-id order; when
  more exist than the ceiling, the lowest-id candidates
  are scored and the rest are not considered by that
  call. Which documents those are is deterministic.
* The cap applies **before** the category / importance
  filter — exactly where the unbounded candidate fetch
  sat — so a caller's filter cannot widen the work, and
  a filtered search can honestly score zero candidates
  while the cap bit (the record says so; see below).
* On the vector road, only surviving candidates' vectors
  are decoded at all, so a capped search does not pay the
  uncapped decode cost either. Since RM-062 they are also
  the only vectors *fetched*: the cap and the
  category/importance filter are applied in SQL before any
  vector leaves the store (the in-store prefilter —
  `docs/VECTOR_SCAN.md`).
* The Qdrant backend is out of scope: there is no local
  candidate set; the server owns its query cost.

Both ceilings are validated at construction (`>= 1`,
typed configuration error) like the other ceilings.

## Visibility when a cap bites

The roadmap's words: *typed/stat visibility*. The stat
half is a per-call record with the same four fields in
both packages:

| Field | Meaning |
|---|---|
| `candidates_total` (Huginn) / `candidates_examined` (Muninn) | How many candidates existed (Huginn) / were examined (Muninn) |
| `candidates_scored` (Huginn) | How many candidates were actually scored |
| `cap` | The ceiling in force for the call |
| `capped` | True when the ceiling bit |

Huginn's record carries one further field since RM-061:
`candidates_pruned` — TF-IDF candidates the posting-list
bound proved could not reach the result limit, excused
from full scoring with results unchanged (always 0 on
the vector road, which does not prune). See
`docs/CANDIDATE_PRUNING.md`.

Muninn's record is `HebbianMemory.last_spread_activation_stats`
(with `nodes_returned` in place of `candidates_scored`);
Huginn's is the facade property
`HuginnMemory.last_search_stats`, which returns a copy
and never constructs the backend to be read (lazy
construction is contractual; before the first search, and
on the Qdrant backend, it reports the zero record
carrying the configured cap).

**Why a dedicated accessor and not a `stats()` /
`health()` field:** those snapshots are pinned *pure* —
the read-purity invariant (RM-009's matrix) requires a
read to leave them unchanged, and the slice's first draft
failed exactly that pin. Per-call accounting therefore
lives beside the snapshots, never inside them; the new
suites pin that a capped spread and a capped search each
leave `stats()` / `health()` byte-identical. A bite is
also logged at WARNING with counts only — never content
(the RM-044 discipline).

**The honest cost of a cap:** a capped result is
*partial in a stated direction* — Muninn's walk stops
mid-expansion (later frontier nodes, in id order, are
unreached), and Huginn scores the lowest-id candidates
(a bias toward older documents when the cap bites).
Neither is hidden: `capped` is True and the counts say
how much was left unexamined. A caller who cannot accept
partial results raises the ceiling in config; a caller
protecting a latency budget lowers it.

Out of scope, honestly: Muninn's `retrieve` scans the
rows its category/path filter selects and filters
further in Python — a scan bounded by the store's node
count, which `max_nodes` backpressure already caps, with
its output bounded by `top_k`; this slice adds no second
ceiling there. Per-call *wall-clock* deadlines are
likewise not promised: the caps bound work units
(candidates examined/scored), from which time follows on
any given machine, but no millisecond guarantee is made.

## How it is proven

Pinned by `tests/test_query_cost_caps.py` in both
packages (muninn 7 tests, huginn 8):

- **The bound (BENCH acceptance):** a fully connected
  25-node synthetic graph — the worst case for spreading,
  every node one hop from every other — with the ceiling
  at 200: `candidates_examined` is exactly 200 and
  `capped` is True. A 12-document corpus sharing one term
  with the ceiling at 5: `candidates_total` 12,
  `candidates_scored` 5.
- **Determinism at the bite:** repeated capped calls
  return identical results; the Muninn star graph yields
  exactly the seed plus the first ten neighbours in id
  order; a cap of 1 examines exactly one candidate.
- **No change below the ceiling:** the ancestor spread
  values (1.0 / 0.5 / 0.25 chain) and full-corpus search
  results are unchanged, with `capped` False and the true
  candidate counts recorded.
- **Defined edges:** the cap-before-filter search
  (candidates scored 0, `capped` True, empty result);
  the vector road's cap; a no-candidate search recording
  an honest zero; construction validation (the RM-018
  goldens gained the two new configuration cases).
- **Purity:** capped calls leave `stats()` / `health()`
  snapshots unchanged; Huginn's property is lazy and
  returns a copy.
