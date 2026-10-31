# Slice Log — Huginn & Muninn Ravens Roadmap

The evidence record for every closed slice of
`RAVENS_ROADMAP_2026-10-31.md`. One entry per slice, appended
in the same commit that banks the slice, never edited after the
fact (a correction is a new note under the entry, dated).

## Entry convention

Each entry carries, in this order:

- **Slice** — the roadmap id and title (`## RM-NNN — Title`).
- **Class** — the honesty class of its proof (UNIT / FAULT /
  BENCH / LIVE / NOT PROVEN), per the roadmap's governing laws.
- **Commit** — the short hash of the banking commit. A slice's
  own entry is written inside its banking commit, so its hash
  is recorded as *this commit* and is recoverable exactly from
  `git log` and `CAMPAIGN_STATE.md`.
- **Evidence** — the counts and results, quoted from test
  runners and tool output only. Numbers are never estimated.

`CAMPAIGN_STATE.md` (repo root) is the working state; this log
is the permanent record. `tests/test_slice_log.py` in both
packages pins that every banked slice through the current part
has an entry here with its Class and Commit fields present.

---

## RM-001 — Repo-shipped baseline

- **Class:** UNIT
- **Commit:** abad7b5
- **Evidence:** Fresh venv, packages installed non-editable from
  this repo, suites run from a neutral cwd against the installed
  packages, twice consecutively: muninn **36 passed**, huginn
  **27 passed** — the roadmap's v1.0.0 acceptance exactly.

## RM-002 — Manual-only CI

- **Class:** UNIT (inspection)
- **Commit:** 63d96ed
- **Evidence:** `.github/workflows/ci.yml` trigger block verified
  by parsed-YAML inspection: `on` is exactly
  `{workflow_dispatch: null}` — no automatic trigger of any kind.
  Local suites re-run green: muninn 36, huginn 27. A
  GitHub-hosted run is NOT PROVEN (never dispatched).

## RM-003 — Contract freeze tests

- **Class:** UNIT
- **Commit:** 112e0ee
- **Evidence:** Golden signature + result-key tests added to both
  packages. Acceptance proven by deliberate drift: changing
  `activate`'s `emotional_valence` default in a scratch copy
  fails `test_golden_signatures`. Suites: muninn **39 passed**,
  huginn **29 passed**.

## RM-004 — Schema snapshot tests

- **Class:** UNIT
- **Commit:** 0e50b5b
- **Evidence:** Golden `sqlite_master` dumps pinned: muninn six
  tables + 2 indexes, huginn local five tables + 1 index. A
  scratch `CREATE TABLE drift_probe` makes the dump mismatch.
  Suites: muninn **41 passed**, huginn **31 passed**.

## RM-005 — Benchmark harness as a gate

- **Class:** BENCH
- **Commit:** 9c58d04
- **Evidence:** Both `scripts/benchmark.py` promoted to gates
  with committed baselines; >25% headline regression (or a
  missing headline op) exits 1. Gate behaviour proven by unit
  tests of the comparison, a real load-driven FAIL honestly
  recorded in `docs/BENCHMARKS.md`, and a controlled pass against
  an inflated baseline. Suites: muninn **49 passed**, huginn
  **39 passed**.

## RM-006 — Loaded-machine honesty in benchmarks

- **Class:** UNIT (output) / BENCH (harness)
- **Commit:** f98585f
- **Evidence:** Benchmark output (printed + JSON) now carries the
  full environment block field by field, asserted end-to-end
  against the running interpreter's real Python/SQLite versions.
  Suites: muninn **51 passed**, huginn **41 passed**.

## RM-007 — Test-matrix slice

- **Class:** UNIT
- **Commit:** de2dfa1
- **Evidence:** Manual CI matrix widened to Python 3.11 / 3.12 /
  3.13, pinned by tests (a scratch shrink to `["3.12"]` fails the
  pin). Local matrix run, fresh venv per version: muninn
  **54 passed** and huginn **44 passed** on all three versions.
  A GitHub-hosted matrix run is NOT PROVEN (never dispatched).

## RM-008 — Lint/type floor

- **Class:** UNIT
- **Commit:** 0bc193d
- **Evidence:** Ruff floor (E, W, F, I, UP, B, SIM, C4;
  line-length 100; py311) + mypy ratchet level 1 in both
  pyprojects; first run found 196 ruff + 9 mypy findings, all
  fixed in code, plus 10 pre-existing `noqa` removed by fixing.
  Clean run: ruff **All checks passed!**, mypy **Success: no
  issues found** (5 + 8 files). Suites: muninn **58 passed**,
  huginn **49 passed**. Full record: `docs/LINT_AND_TYPES.md`.

## RM-009 — Coverage floor

- **Class:** UNIT
- **Commit:** 506b2df
- **Evidence:** Line coverage measured: muninn **88.80%**
  (661 statements), huginn **88.79%** (883 statements);
  `fail_under = 88` enforced by `coverage report` in the manual
  CI and proven both directions (real reports pass; a scratch
  floor of 99 fails). Suites under coverage: muninn
  **61 passed**, huginn **52 passed**. Full report:
  `docs/COVERAGE.md`.

## RM-010 — Slice-log discipline

- **Class:** UNIT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** This log exists with the convention above;
  RM-001–RM-009 backfilled from the real records in
  `CAMPAIGN_STATE.md` and `git log` only — every count, class
  and hash cross-checked against those two sources.
  `tests/test_slice_log.py` in both packages pins the entries'
  presence and shape. Suites: muninn **63 passed**, huginn
  **54 passed** (the RM-009 counts plus this slice's two pins
  each).

## RM-011 — Determinism audit

- **Class:** UNIT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** Full audit in `docs/DETERMINISM.md`: tie-breaks
  pinned in every ordered read (associations, spread activation,
  retrieve, search in both scoring paths, `semantic_search`),
  backpressure victim choice, and both heal passes' write order;
  content hashes, the hashing embedder, and float arithmetic
  proven already deterministic; Qdrant server ordering and
  wall-clock timestamps documented, not pinned. Acceptance:
  `tests/test_determinism.py` in both packages — one fixed
  workload on two fresh stores produces byte-identical logical
  dumps (every non-timestamp column of every table; the excluded
  timestamp columns are listed in the audit and in the tests),
  in-process and in child processes under `PYTHONHASHSEED` 0
  and 42. Suites: muninn **66 passed**, huginn **57 passed**.

## RM-012 — Timestamp discipline

- **Class:** UNIT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** Record in `docs/TIMESTAMPS.md`: one stored-
  timestamp helper per package (Muninn `core._now`, Huginn
  local `local_backend._now`; Qdrant stores none), all UTC
  ISO-8601. A monotonic guard (`_tick` in both stores) issues
  last-issued + 1µs whenever the wall clock stalls or runs
  backwards, seeded on open from the store's own stored
  maximum. Acceptance: `tests/test_timestamps.py` in both
  packages — format scan over every stored timestamp column,
  and clock-skew tests that patch the helper with a
  backwards-running clock: Muninn's activation log stays
  strictly increasing (including across a reopen), a Huginn
  document's `updated_at` never precedes its `created_at`,
  and a healthy clock's readings pass through untouched.
  Suites: muninn **70 passed**, huginn **60 passed**; ruff +
  mypy floors still clean.

## RM-013 — Idempotency matrix

- **Class:** UNIT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** The matrix in `docs/API_REFERENCE.md` Part 3:
  every public API row of both packages classified **I**
  (idempotent) / **R** (safely re-runnable) / **N**
  (intentionally not), with the repeat behaviour stated per
  row — 28 Muninn rows (M-01–M-28, the `Muninn` facade
  inheriting every row) and 15 Huginn rows (H-01–H-15, local
  backend; live Qdrant still NOT PROVEN, no Qdrant row claimed
  proven). Proven by `tests/test_idempotency.py` in both
  packages — exactly one test per row: muninn **29 tests**
  (28 rows + the facade-inheritance row M-01b), huginn
  **15 tests**. The N rows are proven to double-apply
  (`activate` / `activate_batch` / `associate` counts and
  strengths advance, `retrieve(touch=True)` reinforces again,
  Huginn flights append history while the store stays pure);
  every pure-read row's test also asserts the store's stats
  did not move. Notable semantics pinned, not changed: a
  Muninn `remember` retry with differing fields returns the
  same id with the first write winning, while a Huginn
  `upsert_memory` retry replaces in place under the same id;
  Muninn `decay` is R — `decay(1)` twice composes to
  `decay(2)` to float precision. No package code, API, or
  schema change (RM-003 freeze + RM-004 snapshot green), so
  no Bifröst re-verification required. Suites: muninn
  **99 passed**, huginn **75 passed**; ruff + mypy floors
  still clean.

## RM-014 — Flake quarantine

- **Class:** UNIT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** Harness `scripts/flake_quarantine.py` runs both
  suites back to back as pairs under 2 busy-loop load workers
  and records one JSON line per pair; a pair is green only when
  both suites exit 0, and the harness never retries — the first
  non-green pair would stop the sweep with its full output
  saved. No non-green pair ever occurred. The final record
  (`~/workspace/.verify-tmp/rm014/runs-resumed.jsonl`, durable
  copy in the goal's hidden files as
  `rm014_flake_record.jsonl`) holds **50 consecutive green
  pairs, runs 1–50**: muninn **99 passed** and huginn
  **75 passed** in every pair, 0 failed / 0 errors throughout.
  Honest interruption history (interruptions, not flakes —
  each is recorded in full in `CAMPAIGN_STATE.md`): the first
  attempt reached 15/50 before a VM reboot; the resumed record
  was then carried forward across five further external
  teardowns of the background sweep process (silent deaths and
  one runtime-reported SIGTERM, causes not proven) using the
  harness's `--start-run` resume, which keeps pair numbers so
  the file reads as one consecutive run; the final resume
  (pairs 31–50) completed in one stretch. No package code, API,
  or schema change (RM-003 freeze + RM-004 snapshot green), so
  no Bifröst re-verification required. Suites: muninn
  **99 passed**, huginn **75 passed**.
