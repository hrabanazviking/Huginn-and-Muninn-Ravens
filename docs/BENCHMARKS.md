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
