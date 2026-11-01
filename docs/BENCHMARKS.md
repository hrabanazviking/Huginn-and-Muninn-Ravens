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
