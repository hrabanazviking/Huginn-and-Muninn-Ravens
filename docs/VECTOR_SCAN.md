# Huginn vector scan (RM-062)

Part V's second Huginn slice. The roadmap's words: *the
embedder-mode scan is linear over stored vectors; add an
optional in-store prefilter (category/importance pushed into
SQL — partly true today) and measure honestly at 100k docs;
if linear still wins at personal-store scale, record that
and stop.*

This slice builds the prefilter, measures both roads at
10,000 and 100,000 documents, and records the verdict the
measurements support. The gate script is
`huginn/scripts/vector_scan.py`; the record committed from
the after tree's full run is
`huginn/scripts/vector_scan.json`.

## What the old road actually paid

Before this slice, `_search_vectors_locked`:

1. fetched **every** stored vector's text out of SQLite
   (`SELECT doc_id, vector FROM doc_vectors` — at the
   shipped 384 dimensions each vector is ~4.8 KB of JSON
   text, so the gate's 100k-document store — 477.5 MB on
   disk, the great bulk of it vector text — moved its
   whole vector table per search before anything was
   scored);
2. sorted the rows and applied the RM-053 candidate cap
   in Python;
3. fetched the capped candidates' document rows with the
   category/importance filter applied in SQL (the "partly
   true today" — the filter was already in SQL for the
   *documents*, it just ran after the vector transfer);
4. decoded and scored only the survivors.

So a category search that scored one tenth of the store
still transferred **all** of the store's vectors, and a
capped search transferred the vectors of documents the cap
had already excluded.

## The prefilter

All three cuts now happen in SQL, in the RM-053 order —
the candidate cap **before** the filter, lowest ids first:

1. the candidate total is a `COUNT(*)` over `doc_vectors`,
   not a fetch;
2. the capped candidate ids are selected in the store
   (`ORDER BY doc_id LIMIT <cap>`, the cap bound as a
   value);
3. the documents fetch (`_candidate_docs_locked`, unchanged)
   applies `category` / `importance >=` in SQL;
4. only the surviving documents' vectors are fetched, by
   id (`WHERE doc_id IN (...)`, every id bound).

The prefilter engages exactly when a search carries a
filter or the cap bites; it needs no new config and no
opt-in flag, because it changes no result: the survivors
are scored by the same linear dense-cosine scan in Python,
results and the RM-053 `last_search_stats` accounting are
bit-for-bit the old road's (parity-proven below). The
RM-040 SQL audit gained the new shapes as pinned forms
(site total 57 → 59). No public signature, table, column
or index changed.

## Gate corpora and method

Same script, run unchanged on the pre-slice (RM-061) and
post-slice trees, one full run per tree (each run is itself
the median of 5 timed searches per query on the api corpus
and 3 per query on the scale corpus, and **verifies result
parity against a brute-force reference inside the run
before quoting any timing** — the reference streams the
store's raw tables, decodes every stored vector once, and
applies the cap and filters in its own code; a mismatch
raises and no run recorded one). Stores on tmpfs;
`embedder="hashing"` at the shipped `vector_dim=384`
throughout; local backend only.

- **api corpus** — 10,000 documents of the RM-061
  distinct-document corpus, seeded through the public
  `upsert_memory` API (categories `cat{i % 10}`, importance
  `(i % 10) + 1`), under the shipped default
  `max_search_candidates=10000`. Store: 74,694,656 bytes.
- **scale corpus** — 100,000 genuinely distinct documents
  (the RM-061 formula plus a per-index `marker{i}` token),
  seeded by **direct construction**: a real open creates
  the store, then the `documents` + `doc_vectors` rows are
  inserted in one transaction with the upsert road's own
  content-hash function and the hashing embedder's vectors;
  the term index is intentionally empty (the vector road
  never reads it; a TF-IDF search on this store would find
  nothing). Seeding through the public API at this scale
  costs ~6 ms/document of per-call commit and term
  indexing — work this slice does not measure; the search
  under measurement runs entirely through the public API
  on a real store file. Opened with
  `max_search_candidates=200000`, a recorded override:
  the shipped 10,000 ceiling caps any scan at 10k
  candidates by design (RM-053), and the roadmap asks for
  the scan itself at 100k. Store: 477,544,448 bytes.

The fixed workload on each corpus: one query
(`term100 term200 term37`, limit 10) unfiltered, with
`category="cat3"` (one tenth of the store), and with
`min_importance=9` (two tenths).

## Gate numbers — before / after

One full run per tree (each the median of the searches
above; environment blocks in both records — 1-minute loads
6.1 / 8.0 / 7.1 before, 5.1 / 7.9 / 7.7 after):

| corpus | query | before (ms) | after (ms) |
|---|---|---|---|
| api (10k) | unfiltered | 12,299.3 | 6,233.0 |
| api (10k) | category (1/10) | 2,337.0 | 982.5 |
| api (10k) | importance (2/10) | 3,586.7 | 1,704.8 |
| scale (100k) | unfiltered | 101,700.6 | 124,250.4 |
| scale (100k) | category (1/10) | 9,255.2 | 20,908.3 |
| scale (100k) | importance (2/10) | 16,361.6 | 32,315.4 |

A controlled back-to-back pair on the *same* seeded
stores (the gate stores, re-opened by both trees in
immediate succession, `max_search_candidates=200000` on
both corpora) leaned the other way at both scales:

| corpus | query | before (ms) | after (ms) |
|---|---|---|---|
| api (10k) | unfiltered | 13,934.4 | 16,790.2 |
| api (10k) | category (1/10) | 1,196.5 | 2,165.7 |
| api (10k) | importance (2/10) | 3,011.0 | 4,387.2 |
| scale (100k) | unfiltered | 157,713.2 | 106,831.6 |
| scale (100k) | category (1/10) | 14,982.4 | 11,487.3 |
| scale (100k) | importance (2/10) | 28,596.6 | 21,853.7 |

The pair ran while the shared VM's load rose steeply
under concurrent campaign suites (1-minute load ~9 at the
pair's start, ~16 by its end), so neither table is a
clean measurement: the two methods disagree at both
scales, in opposite directions. What the numbers do
support, honestly: no wall-clock regression or win is
*proven* either way at either scale — the searches are
dominated by decoding and scoring the survivors in
Python, next to which even the old road's full-table
text transfer (477 MB at the 100k scale) is a minority
cost on a warm tmpfs store.

## The verdict the roadmap asked for

**The linear scan stands.** At personal-store scale the
roadmap's condition is met: nothing measured here makes
an approximate-nearest-neighbour index worth its
complexity, its approximate answers, or a new dependency
— the survivors are scored by the same exact linear
dense-cosine scan as before, and this slice builds no
index and adds no approximation.

The prefilter is kept anyway, on the load-independent
evidence: it removes the one *unbounded* cost in the old
road. A filtered or capped search no longer transfers
every stored vector's text out of SQLite — its vector
transfer is proportional to its survivors (proven by the
statement-shape pin, not by a stopwatch), and excluded
vectors are never fetched and (as since RM-053) never
decoded. At the 100k scale that is the difference
between moving a 477 MB store's whole vector table per
search and moving one tenth or two tenths of it — a
memory and bandwidth bound that matters exactly when a
store outgrows the cache, whether or not a warm-cache
stopwatch on a loaded VM can see it today. Results and
the RM-053 accounting are bit-for-bit the old road's.

## Exactness evidence

- `tests/test_vector_scan.py` (7 tests, huginn only):
  parity against a brute-force reference computed from
  the raw tables on a randomized corpus across limits,
  category filters, importance floors and their
  combination; the prefilter's statement shape, captured
  by SQLite trace callback (no full-table vector fetch,
  the cap as a SQL `LIMIT`, the only vector fetch by
  surviving id); RM-053's cap-before-filter order
  preserved on the vector road; vectors of filtered-out
  and capped-out documents never decoded (their stored
  text corrupted to non-JSON, the searches still answer
  exactly); an RM-049 encrypted store searches
  identically to a plain one, stats included; gate-script
  shape + a small end-to-end run; the committed record's
  shape.
- The gate script re-proves parity inside every run on
  both corpora before recording timings (see above).
- **3 failed / 4 passed** (`test_prefilter_statement_shape`,
  the gate-script shape test and the committed-record test
  fail — the old tree has no prefilter, no script and no
  record; the parity and encrypted-store tests pass on
  both trees, exactness being a property of both roads);
  `test_sql_injection.py` **2 failed** (the new pinned
  template and the 57 → 59 site total); slice-log pins
  **2 failed** per package.

## Honest limits

- The survivors' scoring is still a Python linear scan —
  that is this slice's recorded verdict, not an oversight:
  no approximate-nearest-neighbour index is built, and at
  archive scale (hundreds of thousands of documents and
  up) the honest road remains the Qdrant backend.
- The 100k corpus is constructed, not upserted (method
  above, stated in the record's `seed` field): its
  documents and vectors are the upsert road's shapes, but
  the seed itself proves nothing about ingest cost at
  100k — RM-057/RM-060 territory, not this slice's.
- Wall-clock rows come from a shared, heavily loaded VM
  and are indicative only (environment blocks in both
  records); the load-independent evidence is the parity
  proof and the statement-shape pin: after this slice, a
  filtered search's vector transfer is proportional to
  the survivors, not to the store.
- A live Qdrant round-trip and the
  sentence-transformers path stay **NOT PROVEN** —
  untouched by this slice except that the local road they
  share the facade with got the prefilter.
