# Benchmarks & the regression gate (RM-005)

Both packages ship a benchmark harness that doubles as a
regression gate:

- `muninn/scripts/benchmark.py` — headline ops: `remember`,
  `activate`, `activate_batch`, `get_associations`,
  `spread_activation`, `decay`, `consolidate`, `stats`
  (workload: 5,000 nodes, 20,000 activations, 2,000 batches).
- `huginn/scripts/benchmark.py` — headline ops: `upsert`,
  `search`, `search_filtered` (workload: 5,000 docs, local
  backend only; a live Qdrant round-trip stays **NOT PROVEN**).

## Running it

```sh
python scripts/benchmark.py                    # measure + gate against baseline.json
python scripts/benchmark.py --no-check         # measure only
python scripts/benchmark.py --output run.json  # also write the JSON record
python scripts/benchmark.py --update-baseline  # re-record baseline.json from this run
python scripts/benchmark.py --threshold 0.10   # stricter gate for this run
```

## The gate

Each script compares the run's headline timings with the
recorded baseline in `scripts/baseline.json` (same directory).
**Default threshold: a run fails (exit 1) if any headline
operation is more than 25% slower than its baseline.** A headline
operation missing from either side also fails — a silent gap
never passes. `--update-baseline` is a deliberate act: re-baseline
only when a change is understood, never to silence a regression
you have not read.

## Honesty labelling (machine + load)

Every record — the printed summary, the `--output` JSON and the
committed baseline — carries an **environment block**: machine
architecture, OS/platform, CPU count, load average at record
time, Python version, SQLite version, and the UTC timestamp.
Numbers measured on a loaded machine are indicative, not
absolutes, and must never be quoted without that block.
(RM-006: the printed output now carries the full block, field
by field, and `tests/test_benchmark_environment.py` in both
packages runs the real script end-to-end and asserts the block
is present in both the printed and JSON output, with versions
matching the running interpreter.)

That warning is earned, not decorative. On the recording VM
(4 CPUs, many campaigns running), two consecutive muninn gate
runs minutes apart on 2026-10-31 swung widely as the 1-minute
load average rose from 3.24 (baseline run) to 6.60 (check run):
`decay` +365%, `stats` +106%, `spread_activation` +75% — the
gate correctly failed that run. A FAIL under load is a signal
to re-run on a quieter machine before calling anything a
regression, exactly as the founding BUILD_NOTES labelled its
numbers "indicative, not promises".

## Recorded baselines (2026-10-31, this VM)

Environment (both): x86_64 Linux, 4 CPUs, Python 3.12.3,
SQLite 3.45.1; muninn recorded at load_avg [3.24, 6.35, 7.16],
huginn at [4.36, 6.49, 7.20]. Full records:
`muninn/scripts/baseline.json`, `huginn/scripts/baseline.json`.

**muninn** (median total ms for the labelled batch):

| operation | baseline ms |
|---|---:|
| remember ×5000 | 423.1 |
| activate ×20000 | 1454.7 |
| activate_batch(5) ×2000 | 977.0 |
| get_associations ×5000 | 216.5 |
| spread_activation ×1000 | 287.0 |
| decay | 16.4 |
| consolidate | 69.3 |
| stats ×1000 | 1936.9 |

**huginn, local backend** (upsert: total ms; search: median ms/search):

| operation | baseline ms |
|---|---:|
| upsert ×5000 docs | 4594.1 |
| search (limit 10) | 13.47 |
| search (category filter) | 1.62 |

The gate logic itself (threshold comparison, missing-operation
failures, baseline/environment shape) is pinned by deterministic
unit tests — `tests/test_benchmark_gate.py` in both packages —
so the unit suites never depend on wall-clock timing.

## Baseline atlas (RM-057)

Part V opens with `scripts/atlas.py` in both packages: the
headline operations above measured at 1k / 10k / 100k nodes
and documents, the seed itself as the write operation and
fixed sample batches for the rest, environment block attached,
records committed as `scripts/atlas.json` beside each script.
The human record — tables, the tmpfs storage-class warning,
Muninn's exact-fit `max_nodes` override, and what the map
shows (`stats()` is the outlier) — lives in `docs/ATLAS.md`.
The atlas is a record, not a gate; RM-071 wires its
operations into this gate.

## Muninn read path (RM-058)

`muninn/scripts/read_path.py` profiles `get_associations`
and `spread_activation` at 100k edges (a 5,000-node ring
graph with 100,000 directed rows, plus a 10,000-spoke hub
graph), records the `get_associations` query plan, and
serves as the before/after gate for the read-path changes:
the covering index `idx_conn_a_strength` and spread's
batched frontier queries. Record committed as
`muninn/scripts/read_path.json`; the human record — profile,
changes, median-of-three before/after table, and honest
limits — lives in `docs/READ_PATH.md`.

## Muninn activation write path (RM-059)

`muninn/scripts/write_path.py` profiles `activate` (same
id and distinct ids), small-batch `activate_batch` and
`retrieve(..., touch=True)`, and counts the SQL statements
one `activate()` executes — the slice's hard gate: **5 → 4
statements** (the counter upsert now returns its total via
`RETURNING` on SQLite 3.35+; the attestation head write is
one combined statement). Record committed as
`muninn/scripts/write_path.json`; the human record —
statement anatomy, changes, median-of-three before/after
table with its load-confounding disclosure, and honest
limits — lives in `docs/WRITE_PATH.md`.

## Muninn maintenance at scale (RM-064)

`muninn/scripts/maintenance_scale.py` builds the RM-058
uniform store (5,000 nodes, **100,000 directed edges**) and
runs `decay` and `consolidate` in the RM-064 chunked road
(committed chunks of `maintenance_chunk_size` rows,
per-chunk atomicity stated in the reports, optional
progress callback) and in a single-chunk road, verifying
every run's final tables row-for-row against an
independent old-road reference before quoting timings.
Record committed as `muninn/scripts/maintenance_scale.json`;
the human record — chunk design, the per-chunk boundary,
before/after medians with the honest reading (chunking
costs ~25% wall-clock at this scale; what it buys is
bounded transactions and progress, not speed) — lives in
`docs/MAINTENANCE_SCALE.md`.

## Muninn bulk remember (RM-060)

`muninn/scripts/bulk_remember.py` ingests 10,000 distinct
nodes (the RM-020 corpus) into a fresh store by the
`remember` loop and by the new `remember_many` batch API —
one preparation pass, one transaction, backpressure
applied once — verifying both roads built logically
identical stores before quoting any timing. Record
committed as `muninn/scripts/bulk_remember.json`; the
human record — the batch contract, the median-of-three
before/after table (loop 1,603.2 ms → batch 603.9 ms,
2.65×, load-disclosed), and honest limits — lives in
`docs/BULK_REMEMBER.md`.

## Huginn candidate generation (RM-061)

`huginn/scripts/candidate_pruning.py` seeds the RM-020
benchmark corpus and a 10,000-document distinct corpus
and measures the fixed local searches, verifying result
parity against a brute-force reference inside every run
before quoting timings. Posting-list pruning is exact:
on the benchmark corpus it scores **128 of 230
candidates** (102 pruned); on the flat distinct corpus
the bound prunes **0** and the new road costs ~1.5× the
old there — both halves, the bound's idf-floor weakness
and its measured mechanism, are recorded in
`docs/CANDIDATE_PRUNING.md`. Record committed as
`huginn/scripts/candidate_pruning.json`.

## Huginn vector scan (RM-062)

`huginn/scripts/vector_scan.py` seeds 10,000 documents
through the public API and a constructed 100,000-document
store and measures the fixed embedder-mode searches on the
pre- and post-slice trees, verifying result parity against
a brute-force reference inside every run before quoting
timings. The in-store prefilter pushes the RM-053
candidate cap and the category/importance filter into SQL
before any vector is fetched — a filtered or capped
search's vector transfer is now proportional to its
survivors, statement-shape-pinned — while the survivors
are still scored by the same linear dense-cosine scan.
Wall-clock rows on the shared VM were load-confounded in
both directions and are recorded as indicative only; the
verdict and the numbers live in `docs/VECTOR_SCAN.md`.
Record committed as `huginn/scripts/vector_scan.json`.

## Reproducible corpus (RM-020)

The corpora are synthetic and formula-generated — muninn's
`corpus_text(i)` ("benchmark memory *i* about topic *i* mod 50")
and huginn's `doc_text(i)` over its fixed word list — pure
functions of the index with no randomness anywhere, so every
run on every machine stores byte-identical texts. Both are
versioned (`CORPUS_VERSION = 1` in each script; huginn's fixed
search queries are part of its corpus definition).

Every benchmark record now carries a corpus block in
`details.corpus` — version, count, and the SHA-256 of the
stored texts (each UTF-8 encoded, newline-terminated, in
order) — and the printed output shows it beside the
environment block. Default-workload (5,000) hashes:

- muninn: `ffe8065f0eb8040e32cff2dc924ceaf752385aac0b9c7830d8efba448ee141d1`
- huginn: `3693044ba5a6490d5174b31bb86577d338be59f56b9496a05f623a864a06143f`

The gate now also compares corpora: a run whose corpus block
differs from the baseline's fails with a corpus-mismatch
message, whatever the timings say — BENCH comparisons only
ever compare like with like. A baseline with no corpus block
(predating RM-020) draws a printed note and a timing-only
comparison. The committed baselines gained their corpus
blocks without re-timing: the generators' output is
byte-identical to what the RM-005 runs stored, so those
timings stand. Pinned by `tests/test_benchmark_corpus.py` in
both packages (determinism, honest hash recomputation,
baseline block, and the real script recording the same hash
in printed + JSON output across two runs).
