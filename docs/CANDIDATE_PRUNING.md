# Huginn candidate generation (RM-061)

Part V's Huginn search slice. The local TF-IDF search used
to fetch **every** candidate's full term set and score it.
This slice narrows the candidates from the query terms'
posting lists first — **posting-list pruning** — and fully
scores only the candidates the bound cannot excuse. The
roadmap's acceptance is a recall test proving **result
parity on the benchmark corpus**: the pruned search must
return the unpruned search's results. That parity is the
slice's hard gate, and it holds everywhere it was tested.
The timing story is more mixed, and this record states it
exactly as measured — including the corpus where pruning
prunes nothing and the new road is the slower one.

The gate script is `huginn/scripts/candidate_pruning.py`;
the record committed from the after tree's third run is
`huginn/scripts/candidate_pruning.json`.

## How the pruning works

For each candidate that survives the RM-053 cap and the
category/importance filter, the query terms' posting lists
alone determine:

- the **dot product** with the query — exact, because a
  cosine numerator only ever involves shared terms;
- a **lower bound on the full vector norm**: the
  posting-only sub-vector's norm, plus the least the
  remaining terms can contribute. Every remaining token
  sits on a term whose idf is at least the corpus minimum
  (the most frequent term's idf), integer term frequencies
  give `sum(tf^2) >= sum(tf)` over the remaining terms,
  and the candidate's total token count comes from one
  aggregate query (`SUM(tf) GROUP BY doc_id`).

So `dot / (|query| * norm bound)` is a true **upper bound**
on the candidate's cosine score (cosine is scale-invariant
per document, so the bound is computed on raw `tf*idf`
weights; the TF normalizer's per-document total cancels).
Candidates are fully scored best-bound-first in batches of
128; once `limit` exact scores stand, a remaining candidate
whose bound — carried with a `(1 + 1e-9)` safety factor —
cannot beat, or tie-and-outrank by the RM-011 doc-id
tie-break, the current limit-th score is **pruned**: its
full term set is never fetched. Pruning is therefore
exact, not approximate: no candidate that could reach the
result list is ever excused.

The per-call accounting in `last_search_stats` gains one
field, `candidates_pruned` (the vector road always records
0; it does not prune). No public signature, table, column
or index changed; the RM-040 SQL audit gained the new
shapes as pinned templates (site total 53 → 57).

## Where the bound is weak — measured, not guessed

The norm bound is only as strong as the corpus-minimum
idf, and **one corpus-wide term collapses it**: the floor
is the idf of the single most frequent term, so a term
that appears in most documents drags the floor toward
zero and the remaining-terms contribution toward nothing.
Both gate corpora contain such a term, and the bound's
strength then depends on how much of a document's norm
its query terms already carry:

- **Benchmark corpus** (the RM-020 corpus; 5,000 texts
  dedupe to **230 stored documents** — 23 distinct texts
  × 10 categories): the most frequent term (`raven`)
  sits in 230 of 230 documents, so the floor is ≈ 0.002.
  Pruning still narrows decisively — **230 candidates →
  128 scored, 102 pruned** on every after run — because
  the documents are short: the posting-only sub-norm is
  already most of each document's norm, so the bound
  stays discriminative where it matters.
- **Distinct corpus** (10,000 distinct synthetic
  documents, 20–79 tokens each over a 1,024-term
  vocabulary; built for this slice because RM-057 could
  only measure the benchmark corpus's 23 distinct
  documents): one formula term (`term766`) lands in
  6,990 of 10,000 documents, putting the floor at idf
  0.358 against query-term idfs of ~3.1–3.7, and the
  documents are long. On a 3,000-document diagnostic
  store the sampled mid-ranked candidate's bound norm
  was **3.85 against a true norm of 17.54**; the median
  candidate bound was **0.437 against a limit-th true
  score of 0.162** — every candidate's bound clears the
  threshold, so **nothing is pruned** (0 of 1,129 / 853 /
  1,168 candidates on the gate queries) and the bound
  pass (posting read + totals aggregate + bound walk)
  is pure overhead there. The corpus's true scores are
  not the obstacle — only 33 of 322 diagnostic candidates
  score within 0.8× of the limit-th score — the bound
  is. A tighter bound needs per-term information the
  posting lists alone do not carry; that is a different
  algorithm (WAND-family), not this slice's to invent.

## Gate numbers — before / after

Same script, run unchanged on the pre-slice (RM-060) and
post-slice trees, three full runs per tree; each run is
itself the median of 15 timed searches per query, and
**verifies result parity against a brute-force reference
inside the run before quoting any timing** (a mismatch
raises; no run recorded a mismatch). Stores on tmpfs.
The shared VM was heavily loaded throughout (1-minute
load averages 1.9–14.4 across the nine after-side runs
alone, with ~14 campaigns sharing the box), so the
millisecond rows are **indicative only** — the scored /
pruned counts, which do not depend on load, are the
durable evidence.

| corpus (median of 3 runs) | before | after (final, batch 128) |
|---|---:|---:|
| benchmark search | 44.38 ms | 102.63 ms |
| distinct search | 689.62 ms | 1,082.46 ms |

Run by run — before: benchmark 21.2 / 44.4 / 46.1 ms,
distinct 679.9 / 890.6 / 689.6 ms. After (batch 128):
benchmark 59.4 / 102.6 / 111.4 ms, distinct 1,223.0 /
919.4 / 1,082.5 ms. An interim after set at the first
draft's batch of 64 (benchmark 21.0 / 41.2 / 59.3 ms,
scored 64 of 230; distinct 1,096.8 / 918.2 / 1,066.3 ms)
ran *before* the final set while the box's load was
still climbing, which is why the batch-128 benchmark
median must not be read as a regression either: the
three sets' load bands overlap too widely to separate
code cost from contention at the benchmark scale.

What the timings do support, from a controlled pair: on
a 3,000-document distinct store, 30 back-to-back
searches of one fixed query measured **198.9 ms before
→ 301.1 ms after** (median; batch 128; the batch-64
draft measured 318.8 ms in the same seat). On a corpus
where the bound prunes nothing, the new road costs
roughly half again the old road's time — the totals
aggregate reads every candidate's rows a second time
and the bound walk is extra Python. Where the bound
does prune (benchmark-shaped stores: short documents,
clear winners), the saved per-document scoring pays
that back; today's contention does not let this record
quote a clean wall-clock win even there, and it does
not invent one.

**Batch size note:** survivors are fetched in batches of
128 (raised from the first draft's 64 during this
slice's own gate runs — every batch costs a term fetch
plus a doc_freq lookup, and halving the batch count
halves that overhead on the no-prune path, while the
benchmark corpus's 230 candidates still span two
batches so the gate record keeps showing the narrowing:
128 scored, 102 pruned).

## Exactness evidence

- `tests/test_candidate_pruning.py` (9 tests, huginn
  only): parity against a brute-force reference computed
  from the store's raw tables — on the benchmark corpus
  (fixed queries, limits 10 and 3, a category-filtered
  query), on a randomized 400-document corpus across
  limits, category filters and importance floors; the
  crafted strong/weak corpus (330 candidates: pruning
  prunes and stays exact); composition with the RM-053
  candidate cap; exact ties never pruned (100 identical
  documents all fully scored, lowest ids win); the
  vector road records `candidates_pruned == 0`; an
  RM-049 encrypted store prunes identically to a plain
  one (same pruned count); gate-script shape + a small
  end-to-end run; the committed record's shape.
- The gate script re-proves parity inside every run on
  both corpora before recording timings (see above).
- Negation against the RM-060 tree: the candidate-
  pruning suite **5 failed / 4 passed** (the parity
  tests pass on both trees — exactness is a property
  of both roads; the failures are exactly the new
  pins: pruning happens, ties/vector/encrypted stats,
  the committed record), `test_query_cost_caps.py`
  **2 failed** (the two exact-dict stats pins),
  `test_sql_injection.py` **2 failed** (the audit
  total + templates), slice-log pins **2 failed** per
  package.

## Honest limits

- The wall-clock outcome is corpus-dependent and, on
  today's contended box, not fully resolvable: pruning
  is a clear structural win where score separation
  exists and a measured ~1.5× cost on the flat
  distinct corpus where the bound cannot separate.
  Both halves are the record; neither is buried.
- The bound's known weakness — one corpus-wide term
  collapsing the idf floor — is measured above with
  its mechanism. Stores whose vocabulary has no such
  term, or whose documents are short, prune well;
  long-document stores with a near-universal term
  will see little narrowing until a WAND-family bound
  replaces this one. That replacement is future work,
  named here, not smuggled into this slice.
- A live Qdrant round-trip and the
  sentence-transformers path stay **NOT PROVEN** —
  untouched by this slice (the vector road's only
  change is recording `candidates_pruned: 0`).
