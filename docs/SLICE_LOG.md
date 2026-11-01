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

## RM-015 — Long-run soak

- **Class:** BENCH
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** Harness `scripts/soak.py` (committed with this
  slice) cycled a mixed workload over both packages —
  muninn remember / activate_batch / retrieve with decay +
  consolidate maintenance, huginn upsert / search, fixed
  500-text corpus, local backend, no network — sampling RSS
  and store bytes every 60 s. The record spans
  **2026-10-31T10:47:56Z → 2026-11-01T10:54:18Z (24 h 06 m)**:
  1,043 samples, 39 segments, **174,523 cycles** summed
  (last-cycle-per-segment), **70 errors** summed — all
  `muninn.decay:OperationalError` in five earlier segments,
  each cluster paired in the log with `backup failed: disk
  I/O error` under the VM's extreme-load / write-gate
  episodes (environment class, cause not proven); every other
  operation error-free for the full span and the final segment
  clean (1,862 cycles, 0 errors). Growth verdict, published in
  full in `docs/SOAK.md`: RSS bounded (max 39.33 MB in hour 0,
  final 22.18 MB); huginn store flat (4.84–4.96 MB throughout);
  muninn store linear in work at a constant ~239–254 KiB per
  1,000 cycles from hour 4 on (428 KiB in hours 0–4 including
  the initial fill) — proportional to operations, not an
  accelerating leak. The process was torn down externally 38
  times (two proven VM reboots; the rest the RM-014 silent
  pattern, causes not proven) and resumed each time against
  the same workdir/out by the keeper; every segment_start
  shows both stores reopening with their existing data. One
  resume was held a tick while a sustained probe proved the
  write gate closed (0/60), then resumed on a fully green
  probe (60/60). Durable record copy:
  `rm015_soak_samples.jsonl` in the goal's hidden files. No
  package code, API, or schema change (RM-003 freeze + RM-004
  snapshot green), so no Bifröst re-verification required.
  Suites: muninn **99 passed**, huginn **75 passed**.

## RM-016 — Version-pinning of the sqlite runtime

- **Class:** UNIT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** `health()` now carries `sqlite_version`
  (`sqlite3.sqlite_version`, read from the runtime, never
  hard-coded) in muninn's `HebbianMemory.health()` and
  huginn's local backend `health()` (facade passes it
  through). Record + the minimum WAL-safe version are
  documented in `docs/SQLITE_RUNTIME.md`: minimum **3.7.0**
  (the release that introduced the WAL journal mode both
  stores use); runtime measured at banking 3.45.1 (this VM,
  Python 3.12.3), unchanged since RM-001. The Qdrant
  backend's health carries no `sqlite_version` (it runs no
  SQLite) and the facade's failing-backend early return
  claims none — both stated in the doc. Proven by new
  `tests/test_sqlite_version.py` in both packages (3 tests
  each): value equals the runtime's own, parses at or above
  the 3.7.0 floor, and the read is pure (stats/health
  unchanged across repeats). RM-003 health goldens updated
  deliberately in this same commit (+`sqlite_version` in
  both key sets). Because this slice changes a public API
  result, the **Bifröst contract re-verification was run
  before banking** (fresh venv `ravens-rm016-bifrost-venv`;
  hrabanazviking/bifrost at b66e98cc): Bifröst's own suites
  **25 passed** (matching the founding record), and a
  BifrostBridge smoke passed end-to-end — store returns
  mimir_id + huginn_id, search merges 2 results, recall
  grows the Muninn activation log by exactly 1, decay +
  consolidate return their reports, stats aggregates all
  three backends, double close safe — with both raven
  health dicts carrying `sqlite_version` 3.45.1 through the
  bridge (huginn degraded via auto-fallback to local, the
  founding venv condition: qdrant-client not installed).
  Full suites green in a fresh venv (`ravens-rm016-venv`,
  non-editable installs): muninn **102 passed** (99+3),
  huginn **78 passed** (75+3); ruff + mypy floors clean
  (mypy muninn 5 files, huginn 8 files, no issues). Founding
  tree (`~/workspace/ravens`) NEEDS A SYNC for the two
  health() additions (extends the RM-008/RM-011/RM-012 sync
  note).

## RM-017 — Config immutability

- **Class:** UNIT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** `MuninnConfig` and `HuginnConfig` are now
  `@dataclass(frozen=True)`: validated once at construction,
  then immutable — assigning to any field raises
  `dataclasses.FrozenInstanceError`, so a caller holding the
  config it handed in cannot change a live store's behaviour
  mid-flight (or smuggle in an unvalidated combination; the
  validators run only at construction). Record:
  `docs/CONFIG_IMMUTABILITY.md`. The road to a variant is
  `dataclasses.replace`, which re-runs full validation; the
  constructors' `**overrides` already took that road (via
  `replace`) and are now pinned to leave the caller's config
  untouched. Proven by new `tests/test_config_immutability.py`
  in both packages (5 tests each): assignment attempts on
  representative fields raise; a mutation attempt against a
  live store leaves behaviour at the validated values
  (Muninn's first wiring still starts at exactly the
  configured learning rate 0.1 after an attempted 1.0; a live
  Huginn local store's backend cannot be flipped to
  `qdrant`); `replace` builds a distinct re-validated config
  (out-of-range replacements raise the typed configuration
  errors); constructor overrides do not mutate the caller's
  config. Acceptance also proven by negation: the same test
  files run against a scratch copy with the freeze removed
  fail exactly the two mutation tests per package (2 failed /
  3 passed each) — the pin catches a regression. Because
  freezing changes public-surface behaviour (construction
  shapes, fields and defaults are unchanged — RM-003 freeze
  green), the **Bifröst contract re-verification was run
  before banking**: fresh venv (`ravens-rm017-bifrost-venv`),
  bifrost at b66e98cc — its own suites **25 passed**;
  BifrostBridge smoke PASS (store mimir_id+huginn_id; search
  2 merged results; recall grew the Muninn activation log
  exactly +1; decay/consolidate reports; stats over all three
  backends; both raven health dicts carry `sqlite_version`
  3.45.1 through the bridge; double close safe; huginn
  degraded via auto-fallback to local — qdrant-client not
  installed in the venv, the founding condition; live Qdrant
  still NOT PROVEN). Full suites green in a fresh venv
  (non-editable installs): muninn **107 passed** (102+5),
  huginn **83 passed** (78+5); ruff + mypy floors clean
  (mypy muninn 5 files, huginn 8 files, no issues; one B010
  on the new tests' `setattr` fixed in-slice to the direct
  assignment the floor prescribes). Founding tree
  (`~/workspace/ravens`) NEEDS A SYNC for the frozen configs
  (extends the RM-008/RM-011/RM-012/RM-016 sync note).

## RM-018 — Stable error messages

- **Class:** UNIT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** Error strings treated as API, pinned two ways
  in new `tests/test_error_messages.py` +
  `tests/golden_error_messages.txt` per package (record:
  `docs/ERROR_MESSAGES.md`). Behavioural pin: every
  deterministically triggerable typed error raised with
  fixed inputs and its exact message compared to the golden
  — muninn **31 cases**, huginn **33 cases** (Qdrant
  translations produced against a fake client raising
  `RuntimeError("boom")`; no live server, live Qdrant still
  NOT PROVEN). Template pin: every `raise <Typed>Error(...)`
  site re-extracted from the source AST (f-string values
  normalised to `{}`) and the multiset compared to the
  golden — muninn **33 sites**, huginn **36 sites** (35
  distinct; the no-row-id guard stands at two insert paths).
  The template pin is the only cover for the sites no
  deterministic trigger can reach (per package: the
  schema-preparation failure; the RM-008 no-row-id guards) —
  named in the doc, not silently skipped. Acceptance proven
  by negation on a scratch copy: rewording muninn's
  `"strength must be in [0, 1]"` fails the template test,
  rewording huginn's `"query_text must be a string"` fails
  the template test, and altering one muninn CASE line in
  the golden fails the behavioural test (muninn 2 failed /
  1 passed, huginn 1 failed / 2 passed on the drifted
  copies; the copies were discarded). Full suites green in
  a fresh venv (`ravens-rm018-venv`, non-editable installs):
  muninn **110 passed** (107+3), huginn **86 passed**
  (83+3); ruff + mypy floors clean (rm014 venv: mypy muninn
  5 files, huginn 8 files, no issues). No package code,
  public API, or schema change (RM-003 freeze + RM-004
  snapshot green), so no Bifröst re-verification required.
  Founding tree needs no sync for this slice (tests + docs
  only); the RM-008/RM-011/RM-012/RM-016/RM-017
  package-source sync note stands.

## RM-019 — API surface freeze test

- **Class:** UNIT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** The whole public surface of both packages is
  now snapshotted in `tests/golden_api_surface.txt` per
  package, enforced by new `tests/test_api_surface.py`
  (record: `docs/API_SURFACE.md`). Snapshot contents: every
  `__all__` name; every exported class with its direct bases
  (error hierarchy + the `Muninn` facade's inheritance
  pinned); every public method of every exported class —
  inherited methods included — in the RM-003
  (name, kind, default) shape; every dataclass field of the
  exported dataclasses with declared type and default;
  properties, public class attributes, huginn's exported
  module functions, and the presence of `__version__`.
  Muninn golden **101 lines**, huginn golden **57 lines**.
  Semantics per the roadmap: additions allowed, removals /
  renames / signature changes fail. Acceptance proven by
  negation on scratch copies of the installed packages
  (discarded): renaming muninn `stats` fails the freeze
  test (1 failed / 2 passed); changing `decay`'s default
  1.0 → 2.0 fails it (1 failed / 2 passed); dropping
  `semantic_search` from huginn's `__all__` fails it
  (2 failed / 1 passed); adding a new public method to
  `HebbianMemory` passes (3 passed). A companion test pins
  that the freeze inventory and `__all__` agree exactly, so
  a new export cannot slip in unlisted. Full suites green
  in a fresh venv (`ravens-rm019-venv`, non-editable
  installs): muninn **113 passed** (110+3), huginn
  **89 passed** (86+3); ruff + mypy floors clean. No
  package code, public API, or schema change (RM-003
  freeze + RM-004 snapshot green), so no Bifröst
  re-verification required. Founding tree needs no sync
  for this slice (tests + docs only); the
  RM-008/RM-011/RM-012/RM-016/RM-017 package-source sync
  note stands.
