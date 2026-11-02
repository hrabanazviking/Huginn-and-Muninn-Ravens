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

## RM-020 — Reproducible benchmark corpus

- **Class:** BENCH
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** Both benchmark corpora are now versioned and
  hashed. The corpora were already formula-generated (muninn
  `corpus_text(i)`; huginn `doc_text(i)` over its fixed word
  list, its fixed search queries part of the corpus
  definition) — this slice names and pins that fact:
  `CORPUS_VERSION = 1` in both `scripts/benchmark.py`, a
  corpus block (`version`, `count`, SHA-256 of the stored
  texts, UTF-8 + newline-terminated, in order) carried in
  every record's `details.corpus` and printed beside the
  environment block, and a gate that refuses cross-corpus
  comparisons with a corpus-mismatch failure whatever the
  timings say (a pre-RM-020 baseline with no corpus block
  draws a printed note and a timing-only comparison).
  Default-workload (5,000) hashes: muninn
  `ffe8065f0eb8040e32cff2dc924ceaf752385aac0b9c7830d8efba448ee141d1`,
  huginn
  `3693044ba5a6490d5174b31bb86577d338be59f56b9496a05f623a864a06143f`.
  Both committed baselines gained their corpus blocks
  without re-timing — the generators' output is
  byte-identical to what the RM-005 baseline runs stored, so
  those timings stand. Record: `docs/BENCHMARKS.md`
  (Reproducible corpus section). Pinned by new
  `tests/test_benchmark_corpus.py` in both packages
  (4 tests each: determinism, honest hash recomputation,
  committed-baseline block, and the real script recording
  the same hash in printed + JSON output across two runs).
  Corpus-gate behaviour proven live on 2026-11-01 by the
  RM-020 wait-and-run record
  (`~/workspace/.verify-tmp/rm020_verify.log`): tiny-workload
  runs against the committed baselines fail with exactly the
  corpus-mismatch message for both packages (muninn
  n=20 `b674585d…` vs baseline n=5000 `ffe8065f…`; huginn
  n=20 `241e92a1…` vs baseline `3693044b…`). Verification
  history, honestly: the slice was built in the
  ~07:05–07:50 EST keeper tick but could not be banked then
  — the VM's Python write gate was closed (the RM-015
  pattern) — so a wait-and-run script probed until the gate
  opened (probe 57, 2026-11-01T12:56:34Z) and ran the gate
  proofs + both full suites; its first suite pass showed
  2 failed / 115 passed (muninn) and 2 failed / 91 passed
  (huginn), and a re-run in the banking tick proved both
  failures per package were exactly this slice-log entry
  missing (the EXPECTED pin extended in the build, the
  entry appended at banking, as in every prior slice).
  With the entry appended, full suites green in the
  RM-019 venv (non-editable installs as recorded there):
  muninn **117 passed** (113+4), huginn **93 passed**
  (89+4); ruff + mypy floors clean (rm014 venv; mypy
  muninn 5 files, huginn 8 files). No package source,
  public API, or schema change (scripts + baselines +
  tests + docs only; RM-003 freeze + RM-004 snapshot
  green), so no Bifröst re-verification required.
  Founding tree sync note from RM-005 stands and now
  extends to the corpus-versioned benchmark scripts +
  baselines (scripts only, no package code).

## RM-021 — Clock-free decay

- **Class:** UNIT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** Plain `decay(days)` is unchanged and stays
  clock-free — computed from the explicit `days` argument
  only, never reading the clock, its RM-003 signature and
  report untouched. The optional wall-clock mode is new and
  opt-in: `HebbianMemory.decay_wall_clock()` derives `days`
  from the marker `decay_last_run_at` in the store's `meta`
  table (an ISO-8601 UTC reading from `muninn.core._now`,
  the RM-012 seam). Record: `docs/WALL_CLOCK_DECAY.md`.
  Edge behaviour, all deliberate and all tested: the first
  call arms the marker and decays 0 days (enabling the mode
  never mass-fades a store); a forward clock jump decays
  the elapsed days and advances the marker; a backward jump
  decays 0 days and the marker does not move backward, so a
  later healthy reading cannot re-decay the same span; a
  corrupt or timezone-naive marker is re-armed and reported
  (`marker_reset`) instead of raising. The report is
  `decay()`'s report plus `mode` / `elapsed_days` /
  `last_run_at` / `run_at` / `first_run` / `marker_reset` /
  `marker_advanced`. Proven by new
  `tests/test_wall_clock_decay.py` (6 tests, clock patched
  at the `_now` seam: arming + exact-strength no-fade,
  +30-day jump halving a 0.8 edge to 0.4 at the default
  30-day half-life, backward jump + held marker + exact
  1-day follow-on, corrupt-marker reset, marker surviving
  a reopen at +10 days, and plain `decay()` leaving the
  marker absent). The method is classified in the RM-013
  idempotency matrix as row **M-29 (R)** with its own test
  (`test_idempotency.py`: a repeat at the same clock reading
  decays exactly 0 further days). The RM-019 golden API
  surface gained the two `decay_wall_clock` lines (facade
  included) in this commit — an addition, the only surface
  change; no signature, config, schema, or error-message
  change (RM-003 / RM-004 / RM-018 pins all green), and no
  new typed-error site was introduced. Public API changed
  (additively), so the **Bifröst contract re-verification
  was run before banking**: fresh venv
  (`ravens-rm021-bifrost-venv`), bifrost at b66e98cc — its
  own suites **25 passed**; BifrostBridge smoke PASS (store
  mimir_id+huginn_id; merged search proven on both source
  paths — huginn for the stored phrase, mimir for a seeded
  row; recall grew the Muninn activation log exactly +1;
  decay/consolidate reports; `decay_wall_clock()` callable
  through the bridge's muninn and arming at 0 days; stats
  over all three backends; both raven health dicts carry
  `sqlite_version` 3.45.1 through the bridge; huginn
  degraded via auto-fallback to local — qdrant-client not
  installed in the venv, the founding condition; live
  Qdrant still NOT PROVEN; double close safe). Full suites
  green in a fresh venv (`ravens-rm021-venv`, non-editable
  installs): muninn **124 passed** (117+6 wall-clock
  +1 idempotency), huginn **93 passed** (no huginn code
  change; slice-log EXPECTED pin only); ruff + mypy floors
  clean (rm014 venv; mypy muninn 5 files, huginn 8 files).
  Founding tree (`~/workspace/ravens`) NEEDS A SYNC for the
  new `decay_wall_clock()` method (extends the
  RM-008/RM-011/RM-012/RM-016/RM-017 sync note).

## RM-022 — Store-format stability promise

- **Class:** UNIT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** New `docs/FORMAT_STABILITY.md`: every file,
  table and key of both stores named with its contract class
  and the migration promise attached to it, reviewed
  line-by-line against the code (`_db.py` + schema SQL in
  both packages, `qdrant_backend.py`, the RM-004 goldens).
  Contents: the file family (main store, SQLite-owned
  `-wal`/`-shm` sidecars, `.bak-N` rolling generations —
  complete store files restorable with no conversion — and
  the transient `.bak-tmp`); the WAL + `synchronous=FULL`
  durability contract and the restore-or-refuse open
  behaviour; Muninn's tables with `activation_log` +
  `hebbian_connections` marked **shared schema — law**
  (Part X schema-version slices + migration proof +
  Bifröst re-verification only), the rest contractual;
  Huginn's local tables likewise; the `meta` registry
  (`schema_version` in both stores, `decay_last_run_at`
  Muninn-only since RM-021) with the additive-only /
  never-redefine / unknown-keys-ignored rules; the
  integer-id and UTC-ISO-8601 value promises; the Qdrant
  construction (collection `huginn_memories`, COSINE,
  embedder-sized vectors, integer point ids) stated as
  construction, **not** live proof — a live Qdrant
  round-trip is still NOT PROVEN. Honest centre of the
  document: `schema_version` ("1" in both stores) is today
  *recorded* on every open, **not yet gated on** — there
  is no migration registry yet; a format change today
  ships only under the golden-snapshot + re-verification
  discipline the slices have used, and the document defers
  governing authority to RM-132's registry (and RM-082's
  foreign-schema behaviour) when they land. Acceptance
  ("doc reviewed against code") is pinned by new
  `tests/test_format_stability.py` in both packages
  (2 tests each, RM-007 skip-outside-checkout pattern):
  every table + index in each package's RM-004 golden must
  be named in the document, along with the meta keys, the
  `.bak-` shape and the collection name — a schema element
  added without a promise update fails the suites. Full
  suites green in the RM-021 venv: muninn **126 passed**
  (124+2), huginn **95 passed** (93+2); ruff floor clean.
  No package code, public API, or schema change (RM-003 /
  RM-004 pins green), so no Bifröst re-verification
  required. Founding tree needs no sync for this slice
  (docs + tests only); the package-source sync note
  stands.

## RM-023 — Shutdown cleanliness

- **Class:** UNIT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** Record: `docs/SHUTDOWN_CLEANLINESS.md`.
  `close()` in both packages was already clean — this slice
  proves it and pins it, per the roadmap's acceptance, with
  new `tests/test_shutdown_cleanliness.py` in both packages
  (3 tests each): writes, then `close()`, then the `-wal`
  sidecar is absent or zero bytes (the final checkpoint
  completed; no half-written tail); a reopen performs zero
  recovery — muninn `recovered_from_backup is False` +
  health integrity ok + node/edge data intact, huginn
  health carries the same two facts + search still finds
  the stored documents; after the second close a raw
  `PRAGMA wal_checkpoint(TRUNCATE)` returns `busy == 0`
  with 0 log pages; double `close()` is a no-op and a
  later reopen is still recovery-free; and a
  thread-baseline test proves close leaves no lingering
  threads (neither package spawns workers — locks only).
  Full suites green in the RM-021 venv: muninn
  **129 passed** (126+3), huginn **98 passed** (95+3);
  ruff floor clean. No package code, public API, or
  schema change (RM-003 / RM-004 pins green), so no
  Bifröst re-verification required. Founding tree needs
  no sync for this slice (tests + docs only); the
  package-source sync note stands.

## RM-024 — Part gate (Part II complete)

- **Class:** UNIT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** `docs/PART_II_EVIDENCE.md` — the Part II
  evidence bundle: the four named evidence kinds filed
  (determinism RM-011, the 50-pair flake record RM-014,
  the 24-hour soak RM-015, the per-version matrix RM-007),
  a one-line acceptance + banking counts check-off for
  every slice RM-011–RM-024, the part's three Bifröst
  contract re-verifications (RM-016, RM-017, RM-021 — each
  fresh-venv, bifrost suites 25 passed, bridge smoke
  PASS), the floors standing at the gate (ruff/mypy clean
  at every banking, coverage floor 88, schema + contract
  freezes green throughout; no schema changed in Part II
  and the only surface change was RM-021's additive
  method), the honesty ledger carried forward unchanged
  (live Qdrant NOT PROVEN, sentence-transformers NOT
  PROVEN, GitHub-hosted CI NOT PROVEN), and the debts
  named (founding-tree sync owed; `schema_version`
  recorded-not-gated until RM-132 / RM-082). The bundle is
  pinned by new `tests/test_part_ii_gate.py` in both
  packages (2 tests each): it must name every Part II
  slice and file all four evidence kinds. Full suites
  green in the RM-021 venv: muninn **131 passed**
  (129+2), huginn **100 passed** (98+2); ruff floor clean.
  No package code, public API, or schema change, so no
  Bifröst re-verification required for the gate itself.
  **Part II (Stability) is complete with this slice** —
  14 of 14 slices banked. The road continues at Part III
  — Robustness (RM-025–RM-038).

## RM-025 — Input fuzzing, muninn

- **Class:** UNIT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** Record: `docs/INPUT_FUZZING_MUNINN.md`.
  Property-style fuzz over every Muninn validator (ids,
  valence, importance, paths, tags, metadata, and the numeric
  parameters), stdlib-only with recorded seeds 20261031,
  20261101, 42, pinned by new `muninn/tests/test_input_fuzz.py`
  (10 tests): every generated input either succeeds or raises
  a typed `MuninnError`, and every rejected write leaves the
  store's stats byte-identical (no partial write). Acceptance
  proven by negation: against the pre-fix code the suite
  failed 8 of 10 tests. Ten defects found and fixed in-slice:
  oversized ids overflowing SQLite untyped (ceiling now
  2⁶³−1 in `_check_memory_id`); a failed `activate_batch`
  leaving a pending partial write; `associate` validating
  `delta` only after its first tombstone write (both numbers
  now validated before any SQL); bare `float()`/`int()`
  TypeErrors across strength/delta/attenuation/min_strength/
  threshold/limit/depth/top_k; `decay(NaN)` corrupting
  confidences via an untyped IntegrityError (days must now be
  finite); non-iterable and bare-string tags crashing or
  exploding into characters (list/tuple only now); `update`'s
  uncaught metadata serializability failure; `MuninnConfig`
  raising untyped on non-convertible fields and accepting NaN
  half-lives; `spread_activation` seed/min_strength tightening.
  RM-018 golden extended in this commit (38 templates, 31
  cases; moved validators keep their exact messages). Full
  suites green in a fresh venv: muninn **141 passed**
  (131+10), huginn **100 passed** (no huginn change beyond
  this log pin); ruff + mypy floors clean. Validation
  behaviour tightened (no signature or schema change), so
  the Bifröst contract re-verification was run before
  banking — fresh venv, bifrost at b66e98cc, its suites
  25 passed, bridge smoke PASS (see CAMPAIGN_STATE.md).
  Founding tree NEEDS A SYNC for the validator hardening
  (extends the standing package-source sync note).

## RM-026 — Input fuzzing, huginn

- **Class:** UNIT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** Record: `docs/INPUT_FUZZING_HUGINN.md`.
  Property-style fuzz over every Huginn validator (content,
  category, importance, valence, tags, memory ids, the search
  arguments, and every query-text entry point), stdlib-only
  with recorded seeds 20261031, 20261101, 42, pinned by new
  `huginn/tests/test_input_fuzz.py` (10 tests): every
  generated input either succeeds or raises a typed
  `HuginnError`, every rejected write leaves the document
  count byte-identical, and huge / unicode-edge / NUL-bearing
  content and queries round-trip and search exactly.
  Acceptance proven by negation: against the pre-fix code the
  suite failed 8 of 10 tests (importance/valence and the
  huge/unicode/NUL corpora already passed). Nine defects
  found and fixed in-slice: oversized ids overflowing SQLite
  untyped (ceiling now 2⁶³−1 in `_check_memory_id`, the
  RM-025 fix mirrored); `search(limit=…)` bare `int()`
  errors and silent float truncation (one typed count
  checker now serves limit / top_k / max_results /
  hop_count / max_results_per_hop); a huge `min_importance`
  overflowing at SQL bind time (same ceiling); categories
  unvalidated on both paths (write-side `str()` coercion
  silently storing `"123"`/`"None"`, read-side lists dying
  as untyped SQLite `ProgrammingError`) — one checker now
  guards both; tags crashing on non-iterables and bare
  strings exploding into character tags (list/tuple only);
  the flight paths crashing with `AttributeError` on
  non-string queries (`fly` now validates inside its error
  envelope and returns an error flight); `analyze_query`
  sharing the crash and silently analysing None;
  `semantic_search` trusting query / documents / top_k
  entirely; and `HuginnConfig`'s numeric fields raising
  untyped on non-convertible values with a NaN
  `qdrant_timeout` passing (never-raising coercion helpers,
  messages unchanged), plus first-time type validation for
  `st_model` and `qdrant_api_key`. RM-018 golden extended
  deliberately in this commit (44 templates, 41 cases; the
  moved validators keep their exact messages). Full suites
  green in a fresh venv: muninn **141 passed** (no muninn
  code change; slice-log EXPECTED pin only), huginn
  **110 passed** (100+10); ruff + mypy floors clean.
  Validation behaviour tightened (no signature or schema
  change), so the Bifröst contract re-verification was run
  before banking — fresh venv, bifrost at b66e98cc, its
  suites 25 passed, bridge smoke PASS (see
  CAMPAIGN_STATE.md). Founding tree NEEDS A SYNC for the
  validator hardening (extends the standing package-source
  sync note).

## RM-027 — Oversize content policy

- **Class:** UNIT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** Record: `docs/OVERSIZE_POLICY.md`. Explicit,
  configurable ceilings replace unbounded acceptance:
  `MuninnConfig.max_content_bytes` (default 1048576 = 1 MiB)
  and `max_metadata_bytes` (default 65536 = 64 KiB);
  `HuginnConfig.max_content_bytes` (default 1048576 — Huginn
  memories carry no caller metadata, so no metadata ceiling
  there). Sizes are UTF-8 bytes of what the store holds
  (stored content text — raw string or its JSON
  serialization; metadata's serialized JSON). Above a
  ceiling the write is refused with the typed validation
  error (`content size {} bytes exceeds max_content_bytes
  ({} bytes)` and the metadata twin) before any write;
  Muninn enforces on `remember` and on `update` (content and
  metadata), Huginn in the facade before any backend is
  touched, so the policy holds on local and Qdrant alike.
  Ceilings are validated at config construction (`>= 1`,
  typed configuration error; `dataclasses.replace`
  re-validates). Pinned by new `tests/test_oversize_policy.py`
  in both packages (muninn 8 tests, huginn 5): boundary tests
  below / at / above each ceiling, UTF-8 byte counting
  (5 × `é` = 10 bytes), JSON content measured as serialized
  text, refused writes leaving counts unchanged and the
  store functional. Negation: the new suites fail in full
  against the pre-RM-027 installed packages (muninn 8
  failed, huginn 5 failed). RM-018 goldens extended
  deliberately (muninn 35 cases / 42 templates, huginn 43
  cases / 46 templates) and the RM-019 API-surface goldens
  gained the new config fields. Full suites green in a
  fresh venv (`ravens-rm027-venv`, non-editable installs):
  muninn **149 passed**, huginn **115 passed**; ruff +
  mypy floors clean. Public config surface changed
  additively, so the **Bifröst contract re-verification was
  run before banking** — fresh venv
  (`ravens-rm027-bifrost-venv`), bifrost at b66e98cc, its
  suites **25 passed**, BifrostBridge smoke PASS (store
  mimir_id+huginn_id; search 2 merged results; recall grew
  the Muninn activation log exactly +1; decay/consolidate
  reports; `decay_wall_clock()` through the bridge armed at
  0 days; stats over all three backends; both raven health
  dicts carry `sqlite_version` 3.45.1; huginn degraded via
  auto-fallback to local — live Qdrant still NOT PROVEN;
  double close safe; evidence
  `~/workspace/.verify-tmp/rm027_bifrost.log`). Founding
  tree NEEDS A SYNC for the config fields + enforcement
  (extends the standing package-source sync note).
## RM-028 — Pathological paths

- **Class:** UNIT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** Muninn node paths now have defined behaviour,
  recorded in `docs/PATHOLOGICAL_PATHS.md` and pinned by new
  `tests/test_pathological_paths.py` (12 tests). One
  normaliser serves every entry point (`remember` / `store` /
  `update` / `move` writes; `retrieve` / `get_by_path` /
  `get_children` reads): split on `/`, empty and `.` segments
  drop, `..` climbs one level and clamps at the store root,
  segments re-join with single `/`s and the root is `""` — so
  every spelling of one logical path is the same path, and a
  `remember` retry under another spelling hits the idempotent
  identity instead of forking a node. Only `/` separates:
  backslash and unicode look-alikes (U+FF0F and kin) are
  ordinary segment characters. Prefix reads escape `\` / `%` /
  `_` with `ESCAPE '\'` — a LIKE-wildcard segment names
  exactly itself (previously `get_children("a_b")` also
  matched `aXb`). `get_children("")` now returns every pathed
  node grouped by path (previously a prefix no stored path
  could match, always `{}`). Bounds on the normalised path:
  string-only (non-strings are typed
  `MuninnValidationError` before any write), at most 64
  segments and 2048 UTF-8 bytes. Negation: the new suite
  failed 11 of 12 against the pre-RM-028 installed packages
  (RM-027 venv; the one pass is verbatim backslash/unicode
  storage, which already held). RM-018 goldens extended
  deliberately (38 cases / 41 templates). Full suites green
  in a fresh venv (`ravens-rm028-venv`, non-editable
  installs): muninn **161 passed**, huginn **115 passed**; ruff +
  mypy floors clean. Validation behaviour tightened (no
  signature or schema change; RM-003/RM-004 pins green), so
  the Bifröst contract re-verification was run before
  banking: fresh venv (`ravens-rm028-bifrost-venv`),
  bifrost at b66e98cc — its own suites **25 passed**;
  BifrostBridge smoke PASS (store mimir_id+huginn_id;
  search 1 merged result; recall grew the Muninn activation
  log exactly +1; decay/consolidate reports;
  `decay_wall_clock()` through the bridge armed at 0 days;
  stats over all three backends; both raven health dicts
  carry `sqlite_version` 3.45.1; huginn degraded via
  auto-fallback to local — live Qdrant still NOT PROVEN;
  double close safe; evidence
  `~/workspace/.verify-tmp/rm028_bifrost.log`). Founding
  tree NEEDS A SYNC for the path normaliser (extends the
  standing package-source sync note). Huginn has no node
  paths — this slice is Muninn-only by design.
## RM-029 — Disk-full behaviour

- **Class:** FAULT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** Writes against a full filesystem now surface as
  typed storage errors with the store still openable and
  consistent afterwards, recorded in `docs/DISK_FULL.md` and
  pinned by new `tests/test_disk_full.py` in both packages
  (muninn 3 tests, huginn 2). Every public write runs behind a
  write guard (`_storage_write` in `muninn/core.py` — remember/
  store, update/move, forget/delete, activate, activate_batch,
  associate, retrieve(touch=True), heal_structure, decay,
  decay_wall_clock, consolidate, backup; and in
  `huginn/local_backend.py` — upsert, delete, heal; the Qdrant
  backend already raises `HuginnBackendError`). On a storage
  failure the guard rolls the failed call's transaction back —
  no partial write survives and nothing leaks into a later
  commit (proven for Muninn's 300-node activate_batch and for
  Huginn's replace-by-id upsert, which de-indexes before it
  writes) — and raises `MuninnStorageError` /
  `HuginnStorageError` with the shape `… write failed during
  {operation}: {sqlite message}`. Before this slice the same
  fault escaped as a raw `sqlite3.OperationalError`. The fault
  is injected with the real engine: `PRAGMA max_page_count`
  clamped to the store's current page count yields SQLite's own
  SQLITE_FULL (`database or disk is full`) — the same error a
  full filesystem produces; no genuinely-full-device claim is
  made. Negation: all 5 new tests fail against the pre-RM-029
  installed packages (RM-028 venv). RM-018 goldens extended
  deliberately (muninn 39 cases / 42 templates, huginn 44
  cases / 45 templates). Full suites green in a fresh venv
  (`ravens-rm029-venv`, non-editable installs): muninn
  **164 passed** (161+3), huginn **117 passed** (115+2);
  ruff + mypy floors clean.
  Error behaviour of writes changed (no signature or schema
  change; RM-003/RM-004 pins green), so the Bifröst contract
  re-verification was run before banking: fresh venv
  (`ravens-rm029-bifrost-venv`), bifrost at b66e98cc — its own
  suites **25 passed**; BifrostBridge smoke PASS (store
  mimir_id=2 huginn_id=5; search 2 merged results; recall
  grew the Muninn activation log exactly +1; decay/
  consolidate reports; `decay_wall_clock()` through the
  bridge armed at 0 days; stats over all three backends;
  both raven health dicts carry `sqlite_version` 3.45.1;
  huginn degraded via auto-fallback to local — live Qdrant
  still NOT PROVEN; double close safe; evidence
  `~/workspace/.verify-tmp/rm029_bifrost.log`).
  Founding tree NEEDS A SYNC for the write guards (extends the
  RM-008/RM-011/RM-012/RM-016/RM-017/RM-025/RM-026/RM-027/
  RM-028 sync note).

## RM-030 — Read-only filesystem

- **Class:** FAULT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** Opening a store whose location is read-only now
  fails loudly and immediately with the typed storage error,
  recorded in `docs/READONLY_FILESYSTEM.md` and pinned by new
  `tests/test_readonly_filesystem.py` in both packages (muninn
  4 tests, huginn 3). There is no read-only mode: a store is
  opened for writing or not at all. The refusal happens in a
  pre-flight at the head of `open_store` in each package's
  `_db.py`, before any connection — a location is read-only
  when the store file or the directory that must hold it (the
  parent, or the nearest existing ancestor of a not-yet-created
  parent) carries no write permission bit at all, or when this
  process cannot write there; every later open stage (parent
  creation, integrity probe, connection, schema preparation)
  also translates a read-only failure (`EROFS`/`EACCES`/`EPERM`,
  SQLite's read-only wordings) into the same typed error, so a
  read-only open never takes the corruption/restore road and
  never escapes raw. The one message shape per package —
  `{package} store {path} is read-only and cannot be opened
  for writing` — is pinned by the RM-018 goldens (new CASE in
  both packages; the template stands six times per package,
  once per raise site, and the main connection's new wrapper
  added a second "could not be prepared" template line).
  Pinned behaviours: refusal in under 5 s despite a 60 s busy
  timeout; the store file's SHA-256 unchanged and no backup
  taken or restored; a clean zero-recovery reopen once
  unmarked; a new store in a read-only directory refused and
  never created; Huginn's facade `health()` reporting the
  refusal as `unhealthy` with `HuginnStorageError` named.
  Negation: all 7 new tests fail against the pre-RM-030
  installed packages (RM-029 venv) — as a privileged process
  the old code simply opened the marked stores and wrote to
  them; no read-only behaviour was defined at all. In-slice
  repair of a discovered pre-existing defect: the RM-008 mypy
  floor did not reproduce at HEAD under the CI invocation
  (`python -m mypy src/muninn` from the package directory,
  rm014-venv tools) — RM-029's `_storage_write` decorator
  returned `Any`, so `warn_return_any` fired in four alias
  methods in `muninn/core.py` (the same 4 errors on a clean
  HEAD worktree, proven before the fix). The decorator in
  both packages now preserves the wrapped method's return
  type via a `TypeVar` (behaviour unchanged; the RM-029
  suites stay green), and both floors pass as CI runs them:
  ruff **All checks passed!**, mypy **Success: no issues
  found** (muninn 5 files, huginn 8 files). Full
  suites green in a fresh venv (`ravens-rm030-venv`,
  non-editable installs): muninn **168 passed** (164+4),
  huginn **120 passed** (117+3); ruff + mypy floors clean.
  Error behaviour of open changed (no signature or schema
  change; RM-003/RM-004 pins green), so the **Bifröst
  contract re-verification was run before banking**: fresh
  venv (`ravens-rm030-bifrost-venv`), bifrost at b66e98cc —
  its own suites **25 passed**; BifrostBridge smoke PASS
  (store mimir_id+huginn_id; search 2 merged results; recall
  grew the Muninn activation log exactly +1; decay/consolidate
  reports; `decay_wall_clock()` through the bridge armed at
  0 days; stats over all three backends; both raven health
  dicts carry `sqlite_version` 3.45.1; huginn degraded via
  auto-fallback to local — live Qdrant still NOT PROVEN;
  double close safe; evidence
  `~/workspace/.verify-tmp/rm030_bifrost.log`). Founding tree
  NEEDS A SYNC for the read-only pre-flight + open-stage
  translations (extends the RM-008/RM-011/RM-012/RM-016/
  RM-017/RM-025/RM-026/RM-027/RM-028/RM-029 sync note).

## RM-031 — Locked-store contention

- **Class:** UNIT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** Locked-store contention now has a defined,
  pinned behaviour, recorded in `docs/LOCKED_STORE.md` and
  pinned by new `tests/test_locked_store.py` in both packages
  (muninn 5 tests, huginn 6). Before this slice the busy
  timeout was honoured but the expiry failure was undefined:
  an open reported the generic preparation failure
  (`could not be prepared: database is locked`), a write
  echoed SQLite's wording through the RM-029 guard, and a
  locked failure at the open's integrity-probe stage fell
  into the corruption bucket and took the backup-restore
  road. Now every stage of the open in each package's
  `_db.py` (probe connect, probe quick_check, main connect,
  schema preparation) classifies a locked failure —
  `database is locked` / `database table is locked` /
  `database is busy` wordings or the SQLITE_BUSY /
  SQLITE_LOCKED codes — and raises the one contention
  message, `{package} store {path} is locked by another
  process (busy timeout {ms} ms expired)`; the RM-029 write
  guards in `muninn/core.py` and `huginn/local_backend.py`
  likewise raise `{package} write failed during {operation}:
  store is locked by another process (busy timeout expired)`
  after rolling the failed call back. The lock holder in the
  acceptance tests is a real second process (a subprocess
  holding a raw `sqlite3` `BEGIN EXCLUSIVE` transaction):
  opens and writes wait out the configured timeout (≥1.2 s
  at 1500 ms), succeed when the holder releases inside it
  (0.8 s hold vs 8000 ms), fail fast at a zero timeout, store
  nothing when refused, and work again on the same object
  after release; a locked open leaves the store's SHA-256
  unchanged, creates no backup generation, and never says
  "corrupt"; pure reads (Muninn stats / get_node / retrieve,
  Huginn get / search) proceed against the WAL snapshot
  mid-contention; Huginn's facade `health()` reports the
  locked open as `unhealthy` naming `HuginnStorageError`.
  RM-018 goldens extended deliberately (muninn 42 cases /
  55 templates, huginn 47 cases / 58 templates — the locked
  open template stands four times per package, once per open
  stage, the probe's quick_check stage added a seventh
  read-only site, and each write guard gained its locked
  raise); guides + API reference updated. Negation: against
  the pre-RM-031 installed packages (RM-030 venv) the new
  suites fail exactly on the contention messages — muninn
  3 failed / 2 passed, huginn 4 failed / 2 passed — the
  passes being the behaviours that already held (release
  inside the timeout, WAL reads) and are now pinned. Full
  suites green in a fresh venv (`ravens-rm031-venv`,
  non-editable installs): muninn **173 passed** (168+5),
  huginn **126 passed** (120+6); ruff + mypy floors clean
  (rm014 venv; mypy muninn 5 files, huginn 8 files).
  Open/write error behaviour changed (no signature or
  schema change; RM-003/RM-004 pins green), so the
  **Bifröst contract re-verification was run before
  banking**: fresh venv (`ravens-rm031-bifrost-venv`),
  bifrost at b66e98cc — its own suites **25 passed**;
  BifrostBridge smoke PASS (store mimir_id=2 huginn_id=5;
  search 2 merged results; recall grew the Muninn
  activation log exactly +1; decay/consolidate reports;
  `decay_wall_clock()` through the bridge armed at 0 days;
  stats over all three backends; both raven health dicts
  carry `sqlite_version` 3.45.1; huginn degraded via
  auto-fallback to local — live Qdrant still NOT PROVEN;
  double close safe; evidence
  `~/workspace/.verify-tmp/rm031_bifrost.log`). Founding
  tree NEEDS A SYNC for the locked classification + the
  write guards' contention shape (extends the
  RM-008/RM-011/RM-012/RM-016/RM-017/RM-025/RM-026/
  RM-027/RM-028/RM-029/RM-030 sync note).

## RM-032 — Partial-file states

- **Class:** FAULT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** Partial file states now have defined, pinned
  open behaviour in both packages, recorded in
  `docs/PARTIAL_FILE_STATES.md` and pinned by new
  `tests/test_partial_file_states.py` (muninn 10 tests,
  huginn 10). Pre-fix probes (RM-031 venv) measured the
  undefined states: a main store truncated to zero bytes
  opened as a silently empty store — even with a verified
  `.bak-1` beside it, which the empty store then rotated
  into the chain on later opens; a non-empty WAL without
  its main file was silently discarded by a fresh start;
  and a `.bak-tmp` left by a killed backup lingered until
  some later backup overwrote it. Defined now, in each
  package's `_db.py` `open_store` (after the RM-030
  pre-flight): a zero-length main file takes the corruption
  road before any connection (restore the newest verified
  generation, else the existing typed corrupt refusal, the
  truncated file left untouched); a non-empty WAL without
  its main file restores a verified backup (sidecars
  consumed by the restore) or raises the new typed refusal
  `… store {path} has a write-ahead log but no main file
  and no rolling backup verified; refusing to start empty
  over lost memory` — on refusal no main file is created
  and the WAL stands; an empty/absent WAL is not evidence
  and a missing main without one is an ordinary new store;
  and a leftover `.bak-tmp` is removed on open and never
  read — proven adversarially: a complete valid store copy
  at the temp path beside a corrupt main gets the refusal,
  not a resurrection, and when a generation and a valid
  temp coexist the restore provably comes from the
  generation. WAL-missing and garbage-WAL opens were
  already sound (checkpointed data intact, no recovery)
  and are now pinned. RM-018 goldens extended deliberately
  (muninn 43 cases / 60 template lines, huginn 48 cases /
  61 template lines, counted from the golden files — one
  new partial-state CASE + TEMPLATE in each; the RM-031
  record's template figures in CAMPAIGN_STATE.md do not
  match a line count of its goldens, a pre-existing record
  discrepancy noted here, not rewritten); guides + API
  reference + format-stability doc updated. Negation: the new suites fail 7 / pass 3 per
  package against the pre-RM-032 installed packages
  (RM-031 venv) — the passes are the already-held
  behaviours. Full suites green in a fresh venv
  (`ravens-rm032-venv`, non-editable installs): muninn
  **183 passed** (173+10), huginn **136 passed** (126+10);
  ruff + mypy floors clean (rm014 venv; mypy muninn 5
  files, huginn 8 files). One first full-suite run showed
  a single muninn golden-test failure during a VM
  Python-write-gate closure (the RM-015/RM-020 environment
  pattern; Python tempfile creation was refused machine-
  wide minutes later, then probed open 5/5); the disk-
  logged re-run in the open window is the 183 above
  (logs `~/workspace/.verify-tmp/rm032/`). The same test
  later failed in a burst of huginn runs inside the same
  window and passed 8/8 consecutive loop runs (plus 4/4
  per-case debug runs and an exact manual per-case capture
  match) once it closed — environment class, never
  reproduced outside the window; no code changed for it. Open error
  behaviour changed (no signature or schema change;
  RM-003/RM-004 pins green), so the **Bifröst contract
  re-verification was run before banking**: fresh venv
  (`ravens-rm032-bifrost-venv`), bifrost at b66e98cc —
  its own suites **25 passed**; BifrostBridge smoke PASS
  (store mimir_id=2 huginn_id=5; search 2 merged results;
  recall grew the Muninn activation log exactly +1;
  decay/consolidate reports; `decay_wall_clock()` through
  the bridge armed at 0 days; stats over all three
  backends; both raven health dicts carry `sqlite_version`
  3.45.1; huginn degraded via auto-fallback to local —
  live Qdrant still NOT PROVEN; double close safe;
  evidence `~/workspace/.verify-tmp/rm032_bifrost.log`).
  Founding tree NEEDS A SYNC for the partial-state open
  handling (extends the RM-008/RM-011/RM-012/RM-016/
  RM-017/RM-025/RM-026/RM-027/RM-028/RM-029/RM-030/RM-031
  sync note).

## RM-033 — Non-database files

- **Class:** UNIT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** Non-database shapes at the store path now
  have defined, pinned behaviour in both packages, recorded
  in `docs/NON_DATABASE_FILES.md` and pinned by new
  `tests/test_non_database_files.py` (muninn 8 tests,
  huginn 8). Pre-fix probes (RM-032 venv) measured the
  undefined shapes: a directory at the store path with a
  verified backup beside it took the corruption road and
  the restore's file copy raised a raw `IsADirectoryError`
  out of `open_store` — a traceback, not a typed error;
  a directory without a backup was misreported as a corrupt
  store; text and empty files already took the corruption
  road (typed refusal, or restore from a verified backup)
  and are now pinned as a class. Defined now, in each
  package's `_db.py` `open_store`: a shape pre-flight
  (`_check_store_path_shape`) runs before every other open
  step — a directory raises the typed refusal `… store
  {path} is a directory, not a database file; refusing to
  open` (the directory and its contents stand untouched,
  the backup beside it neither consumed nor rotated, and a
  directory is never deleted or replaced to make room for
  a restore; Huginn's facade reports the refusal as an
  `unhealthy` `health()` dict), and any other non-regular
  file raises `… store {path} is not a regular file;
  refusing to open` before any open is attempted on it;
  a text file (long or short) and an empty file take the
  corruption road — restore a verified backup, else the
  typed corrupt refusal, the refused file left
  byte-identical with no sidecars created. RM-018 goldens
  extended deliberately (muninn 45 cases / 62 template
  lines, huginn 50 cases / 63 template lines, counted from
  the golden files — two new CASEs + TEMPLATEs per package:
  `directory_store`, `nonfile_store`). Negation: the new
  suites fail 3 / pass 5 per package against the pre-RM-033
  installed packages (RM-032 venv) — the failures are
  exactly the new shape behaviours, the passes the
  already-held text/empty behaviours. Full suites green in
  a fresh venv (`ravens-rm033-venv`, non-editable
  installs): muninn **191 passed** (183+8)**, huginn
  **144 passed** (136+8)**; ruff + mypy floors clean (rm014 venv;
  mypy muninn 5 files, huginn 8 files). Open error
  behaviour changed (no signature or schema change;
  RM-003/RM-004 pins green), so the **Bifröst contract
  re-verification was run before banking**: fresh venv
  (`ravens-rm033-bifrost-venv`), bifrost at b66e98cc —
  its own suites **25 passed**; BifrostBridge smoke
  PASS (store mimir_id=2 huginn_id=5; search 2 merged
  results; recall grew the Muninn activation log exactly
  +1; decay/consolidate reports; `decay_wall_clock()`
  through the bridge armed at 0 days; stats over all three
  backends; both raven health dicts carry `sqlite_version`
  3.45.1; huginn degraded via auto-fallback to local —
  live Qdrant still NOT PROVEN; double close safe;
  evidence `~/workspace/.verify-tmp/rm033_bifrost.log`).
Discovered-bug fix in this slice (test harness, no package code): the RM-031 golden-case lock holder in `tests/test_error_messages.py` was kept alive only by an incidental reference cycle; when the cyclic GC collected it before the locked cases ran, its connection closed, the lock rolled back, and `locked_open` / `locked_remember` (huginn: `locked_upsert`) intermittently did not raise — diagnosed by per-case capture (first capture pass of a fresh process failed, later passes passed; a direct probe showed the lock held 4/4 after `_cases` returns, so collection timing was the race). `_cases` now returns the holder and the test holds a strong reference for the whole pass: per-case loop 6/6 clean per package, fresh processes included. Verification history, honestly: a first final muninn full run inside a machine-wide Python/SQLite write-gate closure (plain sqlite WAL creates then failing 5/5 in every directory, `tempfile` refused — the RM-015/RM-020 environment pattern, reproduced identically against the RM-032 packages) showed that one golden failure; the disk-logged re-runs outside the window, after the holder fix, are the green counts above (logs `~/workspace/.verify-tmp/rm033/`).   Founding tree NEEDS A SYNC for the shape pre-flight
  (extends the RM-008/RM-011/RM-012/RM-016/RM-017/RM-025/
  RM-026/RM-027/RM-028/RM-029/RM-030/RM-031/RM-032 sync
  note).

## RM-034 — Unicode & encoding gauntlet

- **Class:** UNIT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** Unicode behaviour now defined and pinned in
  both packages, recorded in `docs/UNICODE_GAUNTLET.md` and
  pinned by new `tests/test_unicode_gauntlet.py` (muninn 17
  tests, huginn 10). Pre-fix probes measured the undefined
  shapes: a lone surrogate (unpaired U+D800–U+DFFF) in Muninn
  string content, a path or a category escaped as a raw
  `UnicodeEncodeError` (hash/size `.encode()`, or the SQLite
  bind for category), while Muninn tags, metadata and
  JSON-valued content were silently stored as JSON
  `\udXXX` escapes and handed back unencodable; in Huginn,
  content died in the RM-027 size check, a category at the
  SQLite bind, a tag was silently stored, and a surrogate
  query silently searched for nothing. Defined now: one
  checker per package (`_check_no_lone_surrogates` in each
  `core.py`) refuses any text carrying a lone surrogate
  with the typed validation error `{field} must not
  contain lone surrogates`, before any write — Muninn
  checks content (recursively over JSON-shaped values),
  metadata (same recursive walk), tags, category, path
  (inside the RM-028 normaliser) and the `retrieve`
  filters; Huginn checks in the facade (content, category,
  tags, every query-shaped argument via `_check_query_text`,
  read-side categories, `semantic_search` documents), so
  the refusal holds on local and Qdrant alike, and a
  surrogate `fly` query comes home as an error flight
  naming the refusal. The welcome half is pinned verbatim:
  RTL (Arabic/Hebrew) and CJK content round-trips and
  searches, emoji ZWJ sequences round-trip byte-for-byte,
  combining marks are never normalised (decomposed and
  precomposed spellings are distinct memories), and
  astral-plane characters — single code points above
  U+FFFF, not lone surrogates — pass untouched; refused
  writes leave both stores' counts unchanged. Negation:
  the new suites fail against the pre-RM-034 code —
  muninn **12 failed / 5 passed**, huginn **6 failed /
  4 passed** (the passes are the welcome half, which
  already held). RM-018 goldens extended deliberately
  (muninn 47 cases / 63 templates, huginn 52 cases / 64
  templates, counted from the files — +2 CASEs +1 TEMPLATE
  each: the shared `{} must not contain lone surrogates`
  template). Full suites green in a fresh venv
  (`ravens-rm034-venv`, non-editable installs, final
  banking tree): muninn **208 passed** (191+17), huginn
  **154 passed** (144+10); ruff + mypy floors clean
  (rm014 venv; mypy muninn 5 files, huginn 8 files).
  Validation behaviour changed (no signature or schema
  change; RM-003/RM-004 pins green), so the **Bifröst
  contract re-verification was run before banking**:
  fresh venv (`ravens-rm034-bifrost-venv`), bifrost at
  b66e98cc — its own suites **25 passed**; BifrostBridge
  smoke PASS (store mimir_id=2 huginn_id=5; search 2
  merged results; recall grew the Muninn activation log
  exactly +1; decay/consolidate reports;
  `decay_wall_clock()` through the bridge armed at 0
  days; stats over all three backends; both raven health
  dicts carry `sqlite_version` 3.45.1; huginn degraded
  via auto-fallback to local — live Qdrant still NOT
  PROVEN; double close safe; evidence
  `~/workspace/.verify-tmp/rm034_bifrost.log`). Founding
  tree NEEDS A SYNC for the surrogate checkers (extends
  the RM-008/RM-011/RM-012/RM-016/RM-017/RM-025/RM-026/
  RM-027/RM-028/RM-029/RM-030/RM-031/RM-032/RM-033 sync
  note).

## RM-035 — Huge-batch atomicity

- **Class:** BENCH
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** `activate_batch` gained a bulk road at ≥64
  unique ids (`_activate_batch_bulk_locked` in
  `muninn/src/muninn/core.py`): the same single transaction
  and the same writes restated set-at-a-time — activations
  as `executemany` over generators, wiring as one
  `INSERT … SELECT` over a TEMP staging table self-joined
  on `<>`, `pairs_wired` arithmetic, `connections_created`
  subtracting pairs already wired in both directions (a
  one-direction drift counts as created and is repaired,
  exactly the per-pair loop's rule), and the secondary
  index `idx_conn_b` dropped and recreated inside the same
  transaction (a rollback restores it; the RM-004/RM-022
  schema pins pass unchanged). Below 64 unique ids the
  original per-pair loop runs unchanged. Record:
  `docs/HUGE_BATCH_ATOMICITY.md`; bench harness
  `muninn/scripts/huge_batch_bench.py`. Pinned by new
  `tests/test_huge_batch_atomicity.py` (7 tests): exact
  counts at 800 ids, de-duplication, exact repeat
  strengthening, pre-wired + one-direction-drift repair,
  loop/bulk agreement across the threshold, disk-full
  rollback at bulk scale including index restoration, and
  a subprocess memory pin (16× the pairs move peak RSS by
  <40 MB). Bench proof: the pre-RM-035 loop probed at
  500 ids in 16.90 s; the bulk road runs the same 500 in
  **0.64 s**, and the full 10k batch — 49,995,000
  unordered pairs, 99,990,000 directed rows — completed
  in **1629.6 s** at peak RSS **47.5 MB** with all eight
  bench checks passed (record
  `~/workspace/.verify-tmp/rm035/bench10k.json`, recorded
  2026-11-01T22:42:34Z under load_avg [11.23, 8.76,
  7.77]; store 12,232,638,464 bytes after the batch).
  Full suites green in the RM-035 venv (non-editable
  installs, TMPDIR on the workspace disk; an earlier run
  through the full /tmp failed en masse — environment
  class, superseded): muninn **215 passed** (208+7),
  huginn **154 passed**; re-run on the final banking tree
  in the banking tick, counts in `CAMPAIGN_STATE.md`.
  Ruff + mypy floors clean. No signature or schema change
  (RM-003/RM-004 pins green; behaviour at bulk scale is
  new, so) the **Bifröst contract re-verification was
  run before banking**: fresh venv
  (`ravens-rm035-bifrost-venv`), bifrost at b66e98cc —
  its own suites **25 passed**; BifrostBridge smoke PASS
  (store mimir_id=2 huginn_id=6; search 1 merged result;
  recall grew the Muninn activation log exactly +1;
  decay/consolidate reports; `decay_wall_clock()`
  through the bridge armed at 0 days; stats over all
  three backends; both raven health dicts carry
  `sqlite_version` 3.45.1; huginn degraded via
  auto-fallback to local — live Qdrant still NOT
  PROVEN; double close safe; evidence
  `~/workspace/.verify-tmp/rm035/bifrost_smoke.log`).
  Founding tree NEEDS A SYNC for the bulk
  `activate_batch` road (extends the RM-008/RM-011/
  RM-012/RM-016/RM-017/RM-025/RM-026/RM-027/RM-028/
  RM-029/RM-030/RM-031/RM-032/RM-033/RM-034 sync note).
  Huginn has no batch operation — this slice is
  Muninn-only.

## RM-036 — Adversarial tags/metadata

- **Class:** UNIT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** The annotation payload's *shape* is bounded
  now, in both ravens. Probed first against the RM-035
  packages: Muninn metadata or JSON-shaped content nested
  5,000 containers deep escaped `remember` as a raw
  `RecursionError` (inside the recursive RM-034 surrogate
  walk or `json.dumps` itself, before the RM-027 size check
  ran); a 200,000-entry tags list was accepted by both
  ravens unbounded; a Huginn tag element nested 50,000 deep
  escaped `upsert_memory` as a raw `RecursionError` from
  the `repr` of the facade's `str()` coercion. Defined now
  (record `docs/ADVERSARIAL_TAGS_METADATA.md`): one
  iterative depth bound (`_check_structure_depth`,
  `_MAX_STRUCTURE_DEPTH = 100` containers — explicit stack,
  path-scoped id set, so the check cannot overflow the
  stack it guards) over Muninn's JSON-shaped content,
  metadata (`remember` + `update`) and every tag element
  (`remember`, `update`, `retrieve` filter), and over
  Huginn's tag elements in the facade — deeper is the typed
  refusal `{field} nesting depth exceeds maximum of 100`
  before any write. The walker does not descend into a
  container already on its path, so self-referential
  content/metadata keep their established typed
  serializability refusals and a circular tag element still
  renders through `repr`'s ellipsis; shared (DAG)
  substructures are walked per occurrence and stored as
  before. The RM-027 ceilings are applied uniformly to the
  one payload they had not reached: the cleaned tags list,
  measured as its stored JSON form in UTF-8 bytes, must fit
  Muninn's `max_metadata_bytes` / Huginn's
  `max_content_bytes` — `tags size {n} bytes exceeds
  max_metadata_bytes ({c} bytes)` and its Huginn twin,
  before any write, on both write paths. Pinned by new
  `tests/test_adversarial_tags_metadata.py` (muninn 16,
  huginn 7): at-bound shapes stored verbatim, above-bound
  and thousands-deep refused typed with counts unchanged,
  circular/DAG behaviour preserved, tags at the ceiling
  stored and above it refused with the measured size, a
  200,000-tag flood refused under the default ceilings.
  Negation against the pre-RM-036 packages: muninn
  **9 failed / 7 passed**, huginn **3 failed / 4 passed**
  (disk logs `~/workspace/.verify-tmp/rm036/
  muninn_negation.log`, `huginn_negation.log`; the
  failures are exactly the new behaviours, the passes
  exactly the behaviours the slice preserves. Tallies
  corrected the same evening — the first-recorded 10/6
  and 5/2 came from a crossed runtime delivery matching
  neither session's disk log).
  RM-018 goldens extended deliberately (muninn 50 cases /
  65 templates, huginn 54 cases / 66 templates, counted
  from the files — +3 CASEs +2 TEMPLATEs muninn, +2 +2
  huginn). Full suites green in a fresh venv
  (`ravens-rm036-venv`, non-editable installs, TMPDIR on
  the workspace disk): muninn **231 passed** (215+16),
  huginn **161 passed** (154+7); ruff + mypy floors clean
  (rm014 venv; mypy muninn 5 files, huginn 8 files).
  Validation behaviour changed (no signature or schema
  change; RM-003/RM-004 pins green), so the **Bifröst
  contract re-verification was run before banking**: fresh
  venv (`ravens-rm036-bifrost-venv`), bifrost at b66e98cc
  — its own suites **25 passed**; BifrostBridge smoke PASS
  (store mimir_id=2 huginn_id=6; search 1 merged result;
  recall grew the Muninn activation log exactly +1;
  decay/consolidate reports; `decay_wall_clock()` through
  the bridge armed at 0 days; stats over all three
  backends; both raven health dicts carry `sqlite_version`
  3.45.1; huginn degraded via auto-fallback to local —
  live Qdrant still NOT PROVEN; double close safe;
  evidence `~/workspace/.verify-tmp/rm036/bifrost_smoke.log`).
  Founding tree NEEDS A SYNC for the depth bound and the
  tags ceiling (extends the RM-008/RM-011/RM-012/RM-016/
  RM-017/RM-025/RM-026/RM-027/RM-028/RM-029/RM-030/RM-031/
  RM-032/RM-033/RM-034/RM-035 sync note).

## RM-037 — Concurrent openers

- **Class:** UNIT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** Concurrent openers are now **defined as
  supported** and made true (record
  `docs/CONCURRENT_OPENERS.md`). Two or more objects — same
  process or cross-process — may hold one SQLite store at
  once in both packages: committed writes are visible across
  objects at once and never lose each other (SQLite
  serializes ordinary reads/writes, WAL + busy timeout,
  RM-031), closing one object leaves the others working,
  and the duties that cannot interleave — creation,
  integrity probe, restore, backup-on-open, heal, and every
  rolling backup — are serialized per store file by a new
  coordination lock in each package's `_db.py`
  (`store_coordination_lock`: a process-wide re-entrant lock
  per path plus an `flock` on the sibling
  `<db_path>.open-lock` file; the RM-033/RM-030 pre-flights
  still run first, unlocked, so a refused open creates
  nothing). Negation against the RM-036 packages (disk logs
  `~/workspace/.verify-tmp/rm037/muninn_negation.log`,
  `huginn_negation.log`): muninn **3 failed / 5 passed**,
  huginn **1 failed / 7 passed** — the failures are the
  three real races the slice closes (threaded fresh-store
  creation read as corruption in muninn; concurrent
  `backup()` colliding on `.bak-tmp`, failing with disk
  I/O errors and returning `None`; openers restoring a
  corrupt store over each other in both packages), the
  passes exactly the behaviours preserved (cross-visibility,
  exact interleaved and cross-process write totals, close
  independence; huginn's creation race passed pre-slice in
  the recorded run — timing luck through the lazy facade,
  stated in the record doc). Two test-side corrections
  during the build (a wired pair is two directed rows; a
  worker id collided with the seed document's id) — the
  packages were right, the tests were wrong. Pinned by new
  `tests/test_concurrent_openers.py` (muninn 8, huginn 8):
  cross-visibility and exact totals, six-thread fresh-store
  creation race, two-process exact writes, concurrent
  backups verified by `quick_check`, stale-store
  backup-on-open race, corrupt-store restore race, close
  independence. Targeted suites green twice on the final
  tree in a fresh venv (`ravens-rm037-venv`, non-editable
  installs, TMPDIR on the workspace disk). Honest limits,
  documented in the record: the RM-012 timestamp guard is
  per object (cross-object timestamps may repeat or invert
  by microseconds); a foreign raw-SQLite writer gets
  SQLite's locking but not the coordination lock; live
  Qdrant stays NOT PROVEN. No signature or schema change
  (RM-003/RM-004 pins green; `<db_path>.open-lock` added to
  the FORMAT_STABILITY file family as a transient non-store
  file), but open/backup behaviour changed, so the
  **Bifröst contract re-verification was run before
  banking** — counts in `CAMPAIGN_STATE.md`. Full-suite and
  floor counts are recorded in `CAMPAIGN_STATE.md` with this
  entry. Founding tree NEEDS A SYNC for the coordination
  lock (extends the RM-008/RM-011/RM-012/RM-016/RM-017/
  RM-025/RM-026/RM-027/RM-028/RM-029/RM-030/RM-031/RM-032/
  RM-033/RM-034/RM-035/RM-036 sync note).
  Amendment recorded with this slice: the RM-033
  text-file refusal tests in both packages now expect the
  zero-byte `.open-lock` neighbour (the corruption road
  runs under the coordination lock; the RM-033 pre-flight
  refusals — directory, non-regular, read-only — still
  create nothing), and `docs/NON_DATABASE_FILES.md` states
  it. The first final-tree muninn run caught exactly this
  (238 passed / 1 failed on the old assertion) before the
  amendment; the re-run counts stand in CAMPAIGN_STATE.md.

## RM-038 — Part gate (Part III complete)

- **Class:** UNIT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** `docs/PART_III_EVIDENCE.md` — the Part III
  evidence bundle: every FAULT result filed (RM-029
  disk-full, RM-030 read-only filesystem, RM-032
  partial-file states — typed errors, exact rollback, the
  store openable and consistent afterwards in each case),
  the rest of the robustness evidence indexed (both fuzz
  suites with their nineteen in-slice defect fixes, the
  oversize / pathological-path / adversarial-shape
  ceilings, locked-store contention and concurrent
  openers defined as supported, non-database files and
  the unicode gauntlet, and RM-035's BENCH result — 10k
  ids, 49,995,000 pairs / 99,990,000 directed rows in
  1629.6 s at peak RSS 47.5 MB, all eight bench checks
  passed), a one-line acceptance + banking counts
  check-off for every slice RM-025–RM-038, the part's
  thirteen Bifröst contract re-verifications (RM-025
  through RM-037 — each fresh-venv, bifrost suites 25
  passed, bridge smoke PASS), the floors standing at the
  gate (ruff/mypy clean at every banking, coverage floor
  88, schema + contract freezes green throughout; no
  schema changed in Part III), the honesty ledger carried
  forward unchanged (live Qdrant NOT PROVEN,
  sentence-transformers NOT PROVEN, GitHub-hosted CI NOT
  PROVEN), and the debts named (founding-tree sync owed
  for all Part III package sources; `schema_version`
  recorded-not-gated until RM-082 / RM-132; the per-object
  timestamp guard's cross-object limit under concurrent
  openers, stated in the RM-037 record). The bundle is
  pinned by new `tests/test_part_iii_gate.py` in both
  packages (2 tests each): it must name every Part III
  slice and file every FAULT result. Full suites green in
  a fresh venv (`ravens-rm038-venv`, non-editable
  installs, TMPDIR on the workspace disk): muninn
  **241 passed** (239+2), huginn **171 passed** (169+2);
  ruff floor clean. No package code, public API, or schema
  change, so no Bifröst re-verification required for the
  gate itself. **Part III (Robustness) is complete with
  this slice** — 14 of 14 slices banked. The road
  continues at Part IV — Security (RM-039–RM-056).

## RM-039 — Threat model

- **Class:** UNIT (inspection)
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** `docs/THREAT_MODEL.md` — the Part IV
  foundation, reviewed against both codebases at the
  Part III gate (HEAD `78acff3`): ten assets (AS-01–AS-10:
  memory content, wiring, the activation log, retrieval
  indexes, the store file family, tombstones + `meta`,
  the Qdrant API key, diagnostics, availability, content
  identity), the roadmap's four actors (AC-1 buggy caller,
  AC-2 hostile input source, AC-3 local file attacker,
  AC-4 network attacker against Qdrant — plus the two
  named sub-cases: compromised optional dependency,
  hostile co-tenant process), seven trust boundaries
  (TB-1 caller↔API through TB-7 cross-store readers of
  the shared tables), a twenty-one-threat register
  (TH-01–TH-21) with each threat's state today —
  Controlled / Partial / Open / Accepted — and eight
  explicit non-goals (NG-1–NG-8: no defence against the
  host process itself, no authn/authz, no platform
  protection, no content-truth judgement, and kin).
  Findings stated plainly, from inventories taken over
  the sources in this slice: every SQL value is bound
  (the interpolated sites are enumerated — `int()`-cast
  PRAGMA, `update()`'s allow-listed column names,
  `len()`-built placeholders, the static schema script),
  no `chmod` exists in either package (TH-03), the
  Qdrant default is plaintext localhost HTTP with no TLS
  requirement (TH-06), stores and backups are plaintext
  (TH-09), raw-SQL tampering is undetectable today
  (TH-10), and `forget`/`delete` leave WAL frames,
  backup generations and (Muninn, by design) the
  activation log holding forgotten content (TH-11).
  The citation rule binds every later Part IV slice:
  RM-040–RM-056 are each mapped to the threats they own,
  and a slice that finds an unnamed threat amends the
  model in its own commit. Pinned by new
  `tests/test_threat_model.py` in both packages (2 tests
  each: the model names the four actors + core assets,
  and maps every slice RM-040–RM-056 with its non-goals
  and honesty ledger present). Negation: a scratch copy
  of the model with the RM-047 lines removed fails the
  mapping test (1 failed / 1 passed). Suites green in
  a fresh venv (`ravens-rm039-venv`, non-editable
  installs): huginn **173 passed** (171+2) in one full
  run on the final tree (TMPDIR on the workspace disk);
  muninn **243 passed** (241+2) assembled per-file —
  all 38 test files green in this tick (per-file logs
  in `~/workspace/.verify-tmp/rm039/chunks/`), because
  the home filesystem's quota kept closing mid-run
  under ~14 concurrent campaigns: repeated EDQUOT
  (Errno 122), and SQLite `SIGBUS` crashes in
  heavy-write tests while the quota was shut
  (`test_huge_batch_atomicity` passes in 7.1 s with
  TMPDIR on the then-free `/tmp` — the crash follows
  the quota, not the code; root cause proven to the
  Errno-122 line in the pytest internal-error log).
  Writes reopened after this keeper deleted five of
  this campaign's own spent per-slice venvs and the
  shared pip/uv download caches (~2.5G, regenerable;
  model and rattler caches untouched). On the road, the
  first full muninn run (load average ~12) also failed
  exactly `test_wall_clock_decay.py::test_corrupt_
  marker_is_rearmed_and_reported` (1 failed / 242
  passed); that file passes alone (6 passed) and in
  its chunk run — recorded, environment class (the
  RM-001 pattern). ruff + mypy floors clean (rm014
  venv; mypy muninn 5 files, huginn 8 files).
  No package code, public API, or schema change (docs +
  tests only), so no Bifröst re-verification required.
  Founding tree needs no sync for this slice; the
  Part II/III package-source sync note stands.

## RM-040 — SQL-injection audit

- **Class:** UNIT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** `docs/SQL_INJECTION_AUDIT.md` — TH-01
  closed for the SQLite surfaces. Every `execute` /
  `executemany` / `executescript` site in both `src/`
  trees inventoried from the AST on the RM-039 head and
  classified. Audit table:

  | Package | Sites | Constant SQL | Interpolated / variable (the complete set) |
  |---|---|---|---|
  | Muninn | 81 (`_db.py` 8, `core.py` 73) | 76 — every caller value bound as `?`; the rest value-free (static PRAGMAs, counts, heal, batch temp-table/index DDL) | `PRAGMA busy_timeout={int(busy_timeout_ms)}` (int-cast config; PRAGMAs cannot bind); `UPDATE nodes SET {assignments}` in `update()` — keys only from literal assignments behind the closed field allow-list, values bound; `executescript(schema_sql)` = static `SCHEMA_SQL`; `execute(sql)` ×2 — the timestamp seed loop (tuple of constants) and `retrieve` (constant base + constant fragments, category/path/LIKE pattern all bound, LIKE pattern escaped) |
  | Huginn | 42 (`_db.py` 8, `local_backend.py` 34) | 36 — every caller value bound as `?`; the rest value-free | `PRAGMA busy_timeout={int(...)}` as Muninn; three `IN ({placeholders})` f-strings built from `len()` only, every element bound; `executescript(schema_sql)` = static `SCHEMA_SQL`; `execute(sql, params)` in `_candidate_docs_locked` (the `IN` f-string base + constant filter fragments, values bound) |

  No other shape exists: no `%`-formatting, no string
  concatenation and no `.format()` builds SQL in either
  package (the one scripts-side SQL user,
  `huge_batch_bench.py`, is 4 constant sites, values
  bound). Proven by the hostile battery in new
  `tests/test_sql_injection.py` in both packages
  (muninn 9 tests, huginn 7 tests): 12 / 11 hostile
  contents (quotes, `'; DROP TABLE …; --`, `DELETE …
  WHERE 1=1`, `UNION SELECT`, comment markers, backslash
  escapes, newline-split payloads, curly-quote/fullwidth
  look-alikes, RTL-override prefix) stored and retrieved
  verbatim with every table intact; hostile category /
  tags / metadata / path values round-trip verbatim;
  injection as a filter matches nothing (`' OR '1'='1`
  is a literal, never a tautology); Muninn's LIKE path
  filter treats `%` literally; a hostile `update()` value
  is stored verbatim while a hostile field *name* is a
  typed refusal; Huginn's placeholders exercised at
  50-term width. The same files pin the audit itself
  (site totals, exact f-string template sets, exact
  variable-site names/counts, and every SQL-shaped
  f-string anywhere in each source tree), so a new SQL
  shape fails the suite until the audit is re-run.
  Negation: a scratch tree with an injected f-string
  site in Muninn fails both audit tests (2 failed / 7
  passed); a scratch tree with a concatenation site in
  Huginn fails its classification test (1 failed / 6
  passed); the battery passes on both scratch trees.
  Full suites green in a fresh venv
  (`ravens-rm040-venv`, non-editable installs, TMPDIR on
  the workspace disk): muninn **252 passed** (243+9),
  huginn **180 passed** (173+7); ruff + mypy floors
  clean (rm014 venv; mypy muninn 5 files, huginn 8
  files). No package code, public API, or schema change
  (docs + tests only), so no Bifröst re-verification
  required. Founding tree needs no sync for this slice;
  the Part II/III package-source sync note stands.
  TH-01's register state is re-checked at the RM-056
  part gate, per the threat model's rule.

## RM-041 — Path safety

- **Class:** UNIT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** Record: `docs/PATH_SAFETY.md` — TH-02's
  opt-in strict mode. Both configs gain
  `strict_path_safety: bool = False` (additive, at the end
  of each dataclass; like `auto_backup` a plain boolean
  flag). Default off is the recorded behaviour and is
  pinned as such: paths are `~`-expanded, never
  symlink-resolved, parent permissions unchecked. With
  the flag on, a new pre-flight (`_check_path_safety` in
  each package's `_db.py`, running with the RM-030/RM-033
  pre-flights at the head of `open_store` — before the
  RM-037 coordination lock, so a refused open creates
  nothing, not even the `.open-lock` file — and again
  inside the locked open) refuses two shapes with the
  package's typed storage error: (1) the store path
  itself, or any parent directory component of its
  absolute path, is a symlink (every existing component
  judged by `is_symlink`/`lstat`, never followed); (2)
  the store's immediate parent directory is
  world-writable (`mode & 0o002`). Scoping stated in the
  record: only the immediate parent is judged
  world-writable (system ancestors such as `/tmp` are
  world-writable by design), and a not-yet-existing
  parent is created under the process umask and judged
  from the next open. Strict mode refuses; it never
  resolves or redirects the caller's path. The check
  covers the restore road too, since a restore writes to
  the same path inside the same open. Huginn's flag
  applies to the local backend only (Qdrant has no local
  file). Pinned by new `tests/test_path_safety.py` in
  both packages (9 tests each: three default-mode pins —
  symlinked file, symlinked parent, `0o777` parent all
  open and work as before; six strict-mode tests —
  symlink file/parent/ancestor refused with the exact
  message and nothing created, world-writable parent
  refused then working at `0o755`, normal store +
  reopen, missing-parent creation). Negation against
  the RM-040 installed packages: 6 failed / 3 passed per
  package — the passes are exactly the preserved
  default-mode behaviours. RM-018 goldens extended
  deliberately in both packages (muninn 52 cases / 67
  templates, huginn 56 cases / 68 templates — the two
  new raise sites in each `_db.py` plus their CASE
  triggers; the goldens' stale header counts were
  corrected to the true totals in this commit). RM-019
  API-surface goldens gained the field + the updated
  config `__init__` lines. Public config surface changed
  additively, so the **Bifröst contract re-verification
  was run before banking**: fresh venv
  (`ravens-rm041-bifrost-venv`), bifrost at b66e98cc —
  its own suites **25 passed**; BifrostBridge smoke PASS
  (store mimir_id+huginn_id; search 1 merged result;
  recall grew the Muninn activation log exactly +1;
  decay/consolidate reports; `decay_wall_clock()` armed
  at 0 days; stats over all three backends; both raven
  health dicts carry `sqlite_version` 3.45.1 through the
  bridge; huginn degraded via auto-fallback to local —
  qdrant-client not installed in the venv, the founding
  condition; live Qdrant still NOT PROVEN; double close
  safe; evidence `~/workspace/.verify-tmp/rm041/`).
  Full suites green in a fresh venv (`ravens-rm041-venv`,
  non-editable installs, TMPDIR on `/var/tmp`): muninn
  **261 passed** (252+9), huginn **189 passed** (180+9);
  ruff + mypy floors clean (rm014 venv; mypy muninn 5
  files, huginn 8 files). Founding tree
  (`~/workspace/ravens`) NEEDS A SYNC for the new config
  field + the `_db.py` pre-flight (extends the standing
  package-source sync note). TH-02's register state is
  re-checked at the RM-056 part gate, per the threat
  model's rule.

## RM-042 — File permissions

- **Class:** UNIT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** Record: `docs/FILE_PERMISSIONS.md` —
  TH-03's creation side. In each package's `_db.py`, an
  open that creates the store file (fresh store, or a
  store restored onto a path that did not exist — the
  RM-032 orphaned-WAL road) now sets it owner-only
  (`0o600`, new `_secure_new_store_files` /
  `_chmod_owner_only`, best-effort: a refused chmod is
  logged, never raised — "where the OS allows") once the
  schema is applied, together with its `-wal` / `-shm`
  sidecars. `created_by_this_open` is captured before
  the restore logic runs, so the restore-onto-missing
  case is covered and an existing file is never
  re-permissioned. An existing looser file is instead
  reported by `health()`: new additive field
  `file_permissions_warning` (new
  `store_permissions_warning` helper in `_db.py`, one
  `stat`, pure read — `health()` stays pure) is `None`
  when the store file has no `0o077` bits, else the
  string `store file permissions {mode:04o} are looser
  than owner-only 0600; group or other local accounts
  can access the store file` naming the actual mode.
  Huginn's field lives on the local backend's `health()`
  and is carried through the facade; the Qdrant backend
  has no local file and carries no field. Rolling
  backups are explicitly out of scope — they are
  RM-043. Pinned by new `tests/test_file_permissions.py`
  in both packages (7 tests each, POSIX-only: new file
  exactly `0o600` after store + close and under umask
  `0`; open sidecars `0o600`; new-store warning `None`;
  an existing `0o644` file reopens working, stays
  `0o644`, and warns naming `0644`/`0600`; `0o640`
  warns naming `0640`; an existing `0o600` file reopens
  without warning). Negation against the RM-041
  installed packages: **7 failed / 0 passed** per
  package (both the behaviour and the health field are
  absent there). RM-019 contract-freeze health key sets
  in both packages gained `file_permissions_warning`
  deliberately. Public `health()` surface changed
  additively, so the **Bifröst contract re-verification
  was run before banking**: fresh venv
  (`ravens-rm042-bifrost-venv`, on `/var/tmp` — see the
  environment note below), bifrost at b66e98cc — its
  own suites **25 passed**; BifrostBridge smoke PASS
  (store mimir_id+huginn_id; search 1 merged result;
  recall grew the Muninn activation log exactly +1;
  decay/consolidate reports; `decay_wall_clock()` armed
  at 0 days; stats over all three backends; both raven
  health dicts carry `sqlite_version` 3.45.1 through
  the bridge; huginn on the local backend; live Qdrant
  still NOT PROVEN; double close safe; evidence
  `~/workspace/.verify-tmp/rm042/`). Full suites green
  in a fresh venv (`ravens-rm042-venv`, on `/var/tmp`,
  non-editable installs, TMPDIR on `/var/tmp`):
  muninn **268 passed** (261+7), huginn **196 passed**
  (189+7); ruff + mypy floors clean (fresh
  tool venv on `/var/tmp`, ruff `--no-cache` and mypy
  cache redirected — see below; mypy muninn 5 files,
  huginn 8 files). Founding tree
  (`~/workspace/ravens`) NEEDS A SYNC for the `_db.py`
  helpers + the `health()` field (extends the standing
  package-source sync note). TH-03's backup side is
  RM-043; the register state is re-checked at the
  RM-056 part gate, per the threat model's rule.
  Environment, honestly: the home quota (EDQUOT) closed
  repeatedly during this tick and was still closed at
  banking time; this keeper deleted this campaign's own
  spent scratch (~146 MB: the RM-041 suite venv, spent
  after the negation evidence was captured, and the
  RM-014 tool venv), built every RM-042 venv on
  `/var/tmp`, redirected TMPDIR, the mypy cache and the
  Bifrost smoke's HOME there (the smoke's one in-home
  failure — Huginn's default store under `~/.hermes`
  refused by the quota, so the bridge omitted
  `huginn_id` — was diagnosed as that environment
  class, not a package defect; with HOME on `/var/tmp`
  the smoke passes in full).

## RM-043 — Backup confidentiality

- **Class:** UNIT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** Record: `docs/BACKUP_CONFIDENTIALITY.md` —
  TH-04. A rolling backup is a full copy of memory, but
  the snapshot was created by SQLite under the process
  umask, so an owner-only (RM-042) store's backup could
  land at `0o644` or worse. In each package's
  `_take_backup_unlocked`, the snapshot (`.bak-tmp`) is
  now chmodded to the store file's own mode the moment
  it is written and closed — before verification and
  rotation — via the new `_inherit_store_permissions`
  helper (best-effort: a refused chmod is logged, never
  raised). Every backup road goes through that one
  function (explicit `backup()`, auto-backup on open,
  maintenance backups). Inheritance is exact in both
  directions: a `0o600` store's backups are `0o600`
  under any umask (umask `0` included); a deliberately
  loosened store's backups inherit exactly that mode
  (inheritance, not a forced mode); a rotated generation
  keeps the mode it was taken with. Pinned by new
  `tests/test_backup_confidentiality.py` (muninn 5
  tests, huginn 4, POSIX-only; huginn exercised through
  the auto-backup-on-open road and `huginn._db`'s
  `take_backup`). Negation against the RM-042 installed
  packages: muninn **4 failed / 1 passed**, huginn
  **4 failed / 0 passed** — the one muninn pass is the
  backup-on-open road at `0o640`, where SQLite's Unix
  VFS already copied the store's mode on its own; the
  slice makes inheritance explicit and universal
  instead of road-dependent. No public API or schema
  changed, so no Bifröst re-verification was required
  (the RM-040 precedent). Full suites green in a fresh
  venv (`ravens-rm043-venv`, on `/var/tmp`,
  non-editable installs from `/var/tmp` package copies,
  TMPDIR + PYTHONDONTWRITEBYTECODE on `/var/tmp`):
  muninn **273 passed** (268+5), huginn **200 passed**
  (196+4); ruff + mypy floors clean (rm042
  tool venv; mypy muninn 5 files, huginn 8 files).
  Founding tree (`~/workspace/ravens`) NEEDS A SYNC for
  the `_db.py` backup helper (extends the standing
  package-source sync note). TH-04 closed on top of
  RM-042's TH-03 creation side; the register state is
  re-checked at the RM-056 part gate, per the threat
  model's rule. Environment, honestly: the home quota
  (EDQUOT) stayed hostile all tick — see the RM-042
  entry; this slice's scratch, venvs and logs likewise
  lived on `/var/tmp`.

## RM-044 — Log redaction

- **Class:** UNIT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** Record: `docs/LOG_REDACTION.md` —
  TH-05. Before this slice the no-content-in-logs posture
  rested on the RM-039 inspection alone: every logger call
  site carried paths, counts, heal-count reports, the
  Qdrant URL and exception strings, but nothing scanned
  for a regression and no sanctioned road to content in
  logs existed. Both configs gain
  `debug_log_content: bool = False` (additive; a plain
  boolean flag like `auto_backup`). With the flag off, no
  log record at any level — DEBUG included — carries
  memory content. With it on, exactly the store and
  search paths emit content, at DEBUG level only: muninn
  `remember` (stored text + id) and `retrieve` (query +
  returned contents); huginn's facade `upsert_memory` and
  `search`, so the rule binds whichever backend serves
  the call. Content never appears at INFO or above, and
  the heal paths carry no content at any level even with
  the flag on (their reports are counts by design).
  Exception strings stay uncontrolled here by scoping:
  typed-error message hygiene is RM-054 (TH-14), the
  Qdrant key/transport side RM-045 (TH-06). Pinned by
  new `tests/test_log_redaction.py` in both packages
  (7 tests each; huginn on the local backend): default
  pinned off; flag-off log capture at DEBUG over the
  store, search and heal paths (heal warning really
  emitted, counts only) finds no secret content in any
  record; flag-on store/search emit the content only in
  DEBUG records; flag-on heal still emits none.
  Negation against the RM-043 installed packages:
  **4 failed / 3 passed** per package (the failures are
  the flag and every flag-on behaviour; the passes are
  the preserved default-off behaviours). RM-019
  API-surface goldens gained the field in both packages.
  Public config surface changed additively, so the
  **Bifröst contract re-verification was run before
  banking**: fresh venv (`ravens-rm044-bifrost-venv`,
  on `/var/tmp`), bifrost at b66e98cc — its own suites
  **25 passed**; BifrostBridge smoke PASS (store
  mimir_id+huginn_id; search 1 merged result; recall
  grew the Muninn activation log exactly +1;
  decay/consolidate reports; `decay_wall_clock()` armed
  at 0 days; stats over all three backends; both raven
  health dicts carry `sqlite_version` 3.45.1 through the
  bridge; huginn on the local backend; live Qdrant still
  NOT PROVEN; double close safe; evidence
  `~/workspace/.verify-tmp/rm044/`). Full suites green
  in a fresh venv (`ravens-rm044-venv`, on `/var/tmp`,
  non-editable installs, TMPDIR on `/var/tmp`) on the
  final banking tree: muninn **280 passed** (273+7),
  huginn **207 passed** (200+7); ruff + mypy floors
  clean (rm042 tool venv; mypy muninn 5 files, huginn
  8 files). Founding tree (`~/workspace/ravens`) NEEDS
  A SYNC for the config field + the gated DEBUG
  emissions (extends the standing package-source sync
  note). TH-05 closed by this slice; the register state
  is re-checked at the RM-056 part gate, per the threat
  model's rule.

## RM-045 — Qdrant transport safety

- **Class:** UNIT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** Record: `docs/QDRANT_TRANSPORT.md` —
  TH-06. HTTPS is now required by default for
  non-localhost Qdrant URLs: `HuginnConfig` validation
  refuses a non-http(s) scheme, a hostless URL, and plain
  `http` to a non-localhost host, with three static typed
  messages (four raise sites in `config.py`; the host
  message stands at two of them) that carry neither the
  API key nor the URL. Plain `http` stays accepted for
  loopback hosts (`localhost` / `*.localhost` /
  127.0.0.0/8 / `::1`, judged by `ipaddress` — lookalike
  hostnames such as `localhost.evil.example` are refused),
  so the recorded default `http://localhost:6333` works
  unchanged; the explicit opt-out is the new additive
  config flag `allow_insecure_http: bool = False` (a plain
  boolean flag like `auto_backup`). The API key's handling
  is audited and pinned: its one destination is the
  `QdrantClient` constructor (proven by a recording fake);
  it is excluded from the config's `repr`
  (`field(repr=False)`); and every client exception the
  Qdrant backend wraps — ping, collection creation,
  upsert, delete, retrieve, search, count — is scrubbed of
  the configured key (`***` placeholder) before the
  `HuginnBackendError` is raised, with the facade applying
  the same scrub to `auto`'s recorded fallback reason, its
  INFO log line, and `health()`'s unhealthy error string.
  Pinned by new `tests/test_qdrant_transport.py` (15
  tests, fake clients only — the roadmap's acceptance,
  error strings scanned for key material, is met by leaky
  fakes that embed the key in their exception text and are
  scanned on every road above). Negation against the
  RM-044 installed packages: **13 failed / 2 passed**
  (the passes are the preserved behaviours — loopback
  defaults already worked, and the constructor already
  received the key). The existing fake-client suite now
  opts in explicitly for its non-localhost fake hosts.
  RM-018 goldens extended deliberately (59 CASE, 72
  TEMPLATE sites / 60 distinct) and the RM-019
  API-surface golden gained the field. Public config
  surface changed additively, so the **Bifröst contract
  re-verification was run before banking**: fresh venv
  (`ravens-rm045-bifrost-venv`, on `/var/tmp`), bifrost
  at b66e98cc — its own suites **25 passed**;
  BifrostBridge smoke PASS (store mimir_id+huginn_id;
  search 1 merged result; recall grew the Muninn
  activation log exactly +1; decay/consolidate reports;
  `decay_wall_clock()` armed at 0 days; stats over all
  three backends; both raven health dicts carry
  `sqlite_version` 3.45.1 through the bridge; huginn on
  the local backend; live Qdrant still NOT PROVEN;
  double close safe; evidence
  `~/workspace/.verify-tmp/rm045/`). Full suites green in
  a fresh venv (`ravens-rm045-venv`, on `/var/tmp`,
  non-editable installs from `/var/tmp` package copies,
  TMPDIR on `/var/tmp`) on the final banking tree:
  muninn **280 passed** (no muninn code change; slice-log
  EXPECTED pin only), huginn **222 passed** (207+15);
  ruff + mypy floors clean (rm042 tool venv; mypy muninn
  5 files, huginn 8 files). Founding tree
  (`~/workspace/ravens`) NEEDS A SYNC for the config flag
  + transport validation, the backend scrubbing and the
  facade scrubs (extends the standing package-source sync
  note). TH-06 closed at the code level this slice
  reviews; a live Qdrant round-trip remains NOT PROVEN,
  and the register state is re-checked at the RM-056
  part gate, per the threat model's rule. Environment,
  honestly: the home quota (EDQUOT) closed repeatedly
  during this tick; this keeper freed this campaign's own
  spent pytest/bench scratch across its `rm0*` evidence
  dirs (all logs and scripts kept) and built every
  RM-045 venv on `/var/tmp`, installing from `/var/tmp`
  package copies after an in-tree pip build hit the
  quota writing egg-info.

## RM-046 — Qdrant payload hygiene

- **Class:** UNIT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** Record: `docs/QDRANT_PAYLOAD.md` —
  TH-07. Payload keys are now a pinned closed set on both
  roads. Write: `upsert`'s payload is one fixed dict —
  exactly the six `_PAYLOAD_KEYS` (`content`, `category`,
  `importance`, `tags`, `emotional_valence`,
  `content_hash`) — and caller content, category and tags
  enter as values only, so no caller input can add or
  overwrite a reserved key. Read: `_point_to_doc` (the one
  road from a server point to a caller document, for both
  `get` and `search`) now hygiene-checks every returned
  point — integer point id; a dict payload carrying every
  closed-set key; `content`/`category` strings;
  `importance` a non-bool int in [1, 10]; `tags` a list of
  strings; `emotional_valence` a finite non-bool number in
  [-1, 1]; `content_hash` equal to the SHA-256 of the
  returned content and category; a finite numeric score on
  search results — and raises `HuginnBackendError`
  (`Qdrant point {id} has a malformed payload`, or the
  id-less shape when the id itself is malformed) instead
  of the pre-slice coercions (`int("999")`, a tag string
  exploding into characters, foreign content trusted
  under any hash) or untyped `ValueError`s. The refusal
  names only the point id, never payload content; keys
  outside the closed set are dropped, as before. Pinned
  by new `tests/test_qdrant_payload.py` (14 tests, fake
  clients only, hostile points planted directly in the
  fake store as a co-tenant would): the closed set and
  the backend-computed hash on write, reserved-key-named
  tags / category staying values, payload-shaped content
  unable to forge the hash, the facade round-trip, the
  extra-key drop, a well-formed raw point returned, and
  the forged-hash (get + search), missing-key,
  wrong-type/range, non-dict-payload, malformed-id and
  forged-score refusals. Negation against the RM-045
  installed packages: **7 failed / 7 passed** (failures
  are exactly the new hygiene refusals; passes are the
  preserved write-side closed set, the extra-key drop,
  the well-formed point and the facade round-trip).
  RM-018 goldens extended deliberately (61 CASE, 74
  TEMPLATE sites / 62 distinct — the two new
  malformed-payload messages, with deterministic cases
  added in `test_error_messages.py`). No public API,
  config or schema change, so no RM-019 surface change;
  the **Bifröst contract re-verification was run before
  banking** as a precaution (fresh venv
  `ravens-rm046-bifrost-venv`, on `/var/tmp`), bifrost
  at b66e98cc — its own suites **25 passed**;
  BifrostBridge smoke PASS (store mimir_id+huginn_id;
  search 1 merged result; recall grew the Muninn
  activation log exactly +1; decay/consolidate reports;
  `decay_wall_clock()` armed at 0 days; stats over all
  three backends; both raven health dicts carry
  `sqlite_version` 3.45.1; huginn on the local backend;
  live Qdrant still NOT PROVEN; double close safe;
  evidence `/var/tmp/rm046-evidence/`). Full suites
  green in a fresh venv (`ravens-rm046-venv`, on
  `/var/tmp`, non-editable installs from `/var/tmp`
  package copies, TMPDIR on `/var/tmp`) on the final
  banking tree: muninn **280 passed** (no muninn code
  change; slice-log EXPECTED pin only), huginn **236
  passed** (222+14); ruff + mypy floors clean (rm042
  tool venv; mypy muninn 5 files, huginn 8 files).
  Founding tree (`~/workspace/ravens`) NEEDS A SYNC for
  the payload hygiene check (extends the standing
  package-source sync note). Discovery recorded for
  RM-047 (TH-08, which already owns the Qdrant id
  derivation): the derived point id is an unsigned
  64-bit value, so roughly half of derived ids exceed
  the facade's `memory_id` ceiling of 2⁶³−1 and such a
  memory cannot be fetched through `HuginnMemory.get`
  (it validates the id before the backend is reached);
  found while building this slice's facade test, which
  uses an explicit id like the RM-045 fake suite. TH-07
  closed at the code level this slice reviews; a live
  Qdrant round-trip remains NOT PROVEN, and the register
  state is re-checked at the RM-056 part gate, per the
  threat model's rule. Environment, honestly: the home
  quota (EDQUOT) closed repeatedly during this tick;
  this keeper freed this campaign's own regenerable
  scratch (the repo's build dirs and tool caches, the
  shared pip download cache) and built every RM-046
  venv on `/var/tmp` with its evidence there.

## RM-047 — Hash-collision honesty

- **Class:** UNIT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** Record: `docs/HASH_COLLISION.md` —
  TH-08. Content-hash identity is SHA-256 on all three
  store roads, and the collision assumption is now
  documented (natural collision implausible; the design
  does not stand on that alone). Every idempotent-store
  road gained the length+content double check: a hash hit
  is the same memory only after the stored content's
  length and exact content (and, in Muninn, its string vs
  JSON kind) are proven equal to the incoming values.
  Muninn `remember`'s INSERT-OR-IGNORE fallback, Huginn
  local `upsert`'s (hash, category) hit and its
  free-explicit-id discrimination, and Huginn Qdrant's
  derived-id upsert (the existing point retrieved and
  hygiene-checked first) all refuse a different memory
  under one hash with the one typed message —
  `content hash collision: a different memory already
  holds this content hash (id {id}); refusing to merge`
  (ValidationError on the local roads, BackendError on
  Qdrant; the existing memory/point untouched, the message
  naming only the id). Explicit-id replace (Huginn) and
  addressed `update` (Muninn) are not the idempotent path
  and keep their semantics. The Qdrant derivation also
  changed: derived ids are masked to 63 bits, fixing the
  RM-046 discovery that roughly half of derived ids
  exceeded the facade's `memory_id` ceiling of 2⁶³−1 and
  could never be fetched through `HuginnMemory.get`; the
  double check guards the truncated space that remains.
  Muninn's hash was extracted to `_content_hash` as the
  injection seam. Pinned by new
  `tests/test_hash_collision.py` in both packages
  (muninn 8 tests, huginn 12; forced collisions via the
  injected constant hash function — the roadmap's named
  acceptance method — different-length, same-length and
  kind collisions refused, true duplicates / different
  category / different path / explicit replaces
  preserved; planted-row and planted-point shapes refused
  without injection; derived-id ceiling proven with
  deterministically found over-ceiling contents, one
  round-tripping through the facade). Negation against
  the RM-046 installed packages: muninn **4 failed /
  4 passed**, huginn **7 failed / 5 passed** (failures
  are exactly the new refusals and the ceiling fix;
  passes are the preserved behaviours). RM-018 goldens
  extended deliberately (muninn 53 CASE / 68 TEMPLATE;
  huginn 63 CASE / 77 TEMPLATE, 64 distinct — the two
  collision cases per package planted with real hashes,
  plus a second `Qdrant upsert failed` template site for
  the pre-check's wrapped retrieve failure). No schema
  change. **Bifröst re-verification PASS** (fresh venv
  `ravens-rm047-bifrost-venv` on `/var/tmp`, bifrost at
  b66e98cc — its own suites **25 passed**; BifrostBridge
  smoke PASS, evidence `/var/tmp/rm047-evidence/`).
  Full suites green in the RM-047 fresh venv on the
  final banking tree (TMPDIR on `/var/tmp`, installs
  from `/var/tmp` copies): muninn **288 passed**
  (280+8), huginn **248 passed** (236+12); ruff +
  mypy floors clean (rm042 tool venv, mypy cache on
  `/var/tmp` after the home cache hit the quota and
  mypy died with an internal error on the stale cache —
  environment class, diagnosed; mypy muninn 5 files,
  huginn 8 files). Founding tree (`~/workspace/ravens`)
  NEEDS A SYNC for the double checks, the hash seam and
  the 63-bit derivation (extends the standing
  package-source sync note). TH-08 closed at the code
  level this slice reviews; a live Qdrant round-trip
  remains NOT PROVEN, and the register state is
  re-checked at the RM-056 part gate, per the threat
  model's rule. Environment, honestly: the home quota
  (EDQUOT) was full at this tick's start and repeatedly
  mid-tick; this keeper freed the shared chroma cache
  (~88 MB), the regenerated shared pip cache (~2.5 GB)
  and the shared rattler download cache (~2.8 GB), and
  built every RM-047 venv and evidence dir on
  `/var/tmp`.

## RM-048 — Store encryption, design

- **Class:** UNIT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** Decision record: `docs/STORE_ENCRYPTION.md`
  — TH-09. A design slice only: no package code, public
  API, or schema changed. The three roadmap candidates
  were judged against the campaign's two standing
  constraints (stdlib-first; the shared-schema law /
  TB-7). **SQLCipher rejected**: a compiled SQLite fork
  plus a binding that compiles against a system
  libsqlcipher a pip extra cannot express or bound —
  verified absent on the decision machine (no binary, no
  package, neither binding imports) — and whole-file
  encryption would break the TB-7 contract as practised
  (Bifröst-class readers open Muninn's file with stdlib
  `sqlite3`; the schema would survive, its readability
  would not), while replacing the stdlib store machinery
  every durability proof stands on. **Filesystem
  encryption adopted as standing deployment guidance,
  not the build**: zero code, hides structure while
  locked, but a library cannot provision or promise it
  (NG-3) and it cannot discharge RM-049's in-library
  mandate. **Decision: RM-049 builds application-level
  envelope encryption** — per-store random data key
  wrapped under a PBKDF2-HMAC-SHA256 KEK (stdlib), values
  sealed with AES-256-GCM from the one bounded extra
  (`cryptography>=42,<51`, lazy, flag-gated; the stdlib
  has no cipher and no hand-rolled AEAD is permitted),
  `enc:v1:` envelopes in the same `TEXT` columns (no
  schema change; RM-004 goldens unmoved), wrap + salt +
  key-check value as `meta` rows, open-time key proof
  before any write (wrong passphrase or a plain/flag-off
  open of a marked store refuses, typed, store
  untouched). Transform list: Muninn `nodes.content` /
  `metadata` / `tags`; Huginn `documents.content` /
  `tags`, `doc_terms.term` + `corpus_stats.term` keyed-
  HMAC (TF-IDF is equality-only, so scoring is
  bit-for-bit the plaintext computation), `doc_vectors.
  vector` (search already loads all vectors in-process);
  `content_hash` becomes a keyed lookup tag in both, so
  RM-047's double check compares decrypted content and
  idempotency is preserved. The contracted tables
  (`activation_log`, `hebbian_connections`) carry no
  content and stay plaintext-readable by direct readers.
  Honest limits recorded in the decision: structure,
  counts, timestamps, wiring and approximate lengths
  stay readable — the purchase is content
  confidentiality against AC-3 (stolen disk, copied
  backup; backups and WAL inherit ciphertext values
  through the backup API), not structure-hiding; the
  equality of two memories under one store's tag leaks;
  a lost passphrase is a lost store. The record also
  pins the honest reading of RM-049's "unreadable by
  plain sqlite3": every content-bearing value an
  envelope, no plaintext token in a raw dump. Pinned by
  new `tests/test_store_encryption_design.py` in both
  packages (2 tests each); negation: the decision line
  doctored in a scratch edit → 1 failed / 1 passed per
  package, record then restored byte-identical (sha256
  verified). SLICE_LOG EXPECTED pins extended to RM-048
  in both packages. No public API or schema change, so
  no Bifröst re-verification required (RM-039/RM-040
  precedent). Full suites green in the RM-048 fresh
  venv on the final banking tree (TMPDIR on `/var/tmp`,
  installs from `/var/tmp` copies): muninn **290
  passed** (288+2), huginn **250 passed** (248+2);
  ruff + mypy floors clean (rm042 tool venv; mypy muninn
  5 files, huginn 8 files). Founding tree needs no sync
  for this slice (docs + tests only; the standing
  package-source sync note from earlier slices stands).
  TH-09 stays Open until RM-049 lands the build; the
  register re-check is RM-056's, per the threat model's
  citation rule. The `cryptography` extra in the ravens'
  own venv, like a live Qdrant round-trip, remains NOT
  PROVEN until RM-049 installs and runs it.

## RM-049 — Store encryption, build

- **Class:** FAULT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** Build of the RM-048 decision (TH-09) in both
  packages. New `_crypto.py` per package: one random 32-byte
  per-store data key wrapped under a PBKDF2-HMAC-SHA256 KEK
  (stdlib; 600,000 iterations, per-store 16-byte salt), wrap +
  salt + iterations + AES-256-GCM key-check in the existing
  `meta` table (no schema change — RM-004 goldens unmoved);
  content values sealed AES-256-GCM from the one bounded
  extra `cryptography>=42,<51` (new `encryption` extra in
  both packages, lazily imported only with the flag on) as
  `enc:v1:` envelopes in the same TEXT columns with the
  table+column name as GCM associated data. Config (both,
  additive): `store_encryption: bool = False` +
  `encryption_passphrase` (repr=False; its absence with the
  flag on is a typed configuration error; a missing extra is
  the same, at open, never an import crash). Open-time key
  proof BEFORE any write, on a pure read-only probe: wrong
  passphrase and plain (flag-off) opens of a marked store
  refuse typed with the store byte-for-byte untouched
  (test-pinned); when the probe cannot read the file at all
  (corrupt main), the proof defers to the live connection
  after the restore road — a restored encrypted backup
  unlocks with the same passphrase. Transforms: Muninn
  `nodes.content`/`metadata`/`tags`; Huginn local
  `documents.content`/`tags`, `doc_vectors.vector`, and
  `doc_terms.term`/`corpus_stats.term` as keyed HMAC tags
  (TF-IDF is equality-only — encrypted search scores are
  bit-for-bit the plain store's, test-pinned); both
  `content_hash` columns become keyed lookup tags over the
  RM-047 hash inputs, and the RM-047 double check compares
  decrypted content. Contracted tables
  (`activation_log`/`hebbian_connections`) stay plaintext
  and plain-sqlite3-readable (test-pinned). Two build
  behaviours recorded in `docs/STORE_ENCRYPTION.md`'s build
  note: flag-on over an existing plain store holding
  memories/documents refuses typed (no half-encryption);
  Huginn's flag binds the local backend only. New
  `tests/test_store_encryption.py` (9 tests each package);
  negation against the RM-048 packages **8 failed / 1
  passed** per package (the pass: flag-off plaintext
  preserved). RM-018 goldens extended (+3 CASE / +7
  TEMPLATE lines per package — counts muninn 56 CASE / 79
  TEMPLATE, huginn 66 CASE / 88 TEMPLATE); RM-019 surface
  goldens gained the two config fields; RM-040 audit totals
  moved 81→84 (muninn) / 42→45 (huginn) for the probe's
  constant sites + the header insert, `count_sql` named.
  **Bifröst re-verification PASS** (fresh venv
  `ravens-rm049-bifrost-venv` on `/var/tmp`, bifrost at
  b66e98cc — its own suites **25 passed**; BifrostBridge
  store/search/recall/decay/consolidate smoke PASS,
  evidence `/var/tmp/rm049-evidence/`). Full suites green
  in the RM-049 fresh venv on the final banking tree
  (TMPDIR + installs on `/var/tmp`, extra installed):
  muninn **299 passed** (290+9), huginn **259 passed**
  (250+9); ruff + mypy floors clean (rm042 tool venv;
  mypy muninn 6 files, huginn 9 files). The `cryptography`
  extra is PROVEN in the ravens' own venv from this slice
  (50.0.2, installed via the extra and exercised end to
  end); live Qdrant and sentence-transformers stay NOT
  PROVEN. Suites from this slice run with the `encryption`
  extra installed (the RM-018 case capture builds an
  encrypted store when the extra is present). Founding
  tree NEEDS A SYNC for the whole encryption build
  (extends the standing package-source sync note).

## RM-050 — Integrity attestation

- **Class:** FAULT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** Optional HMAC chain over `activation_log`
  (TH-10), Muninn-only — `activation_log` exists only in
  Muninn; Huginn's copy of the slice work is this entry's
  slice-log pin. Record in `docs/INTEGRITY_ATTESTATION.md`.
  Config (additive): `integrity_attestation: bool = False`
  + `integrity_passphrase` (repr=False; missing passphrase
  with the flag on is a typed configuration error).
  **Stdlib only, no new dependency**: the chain key is
  PBKDF2-HMAC-SHA256 from the passphrase (600,000
  iterations, per-store 16-byte salt) and is never stored;
  each appended log row extends an HMAC-SHA256 chain
  (genesis over a domain constant ‖ salt; each link over
  head ‖ memory_id ‖ activated_at ‖ repr(valence) ‖
  source), and the store carries only salt / iterations /
  head / chained count as `meta` rows — no schema change,
  RM-004 goldens unmoved, the contracted table untouched.
  Every appending road chains in the row's own transaction
  (`activate`, both `activate_batch` roads including the
  RM-035 bulk road, `retrieve(touch=True)`), re-reading the
  stored head before each advance so a rolled-back
  transaction never leaves the in-memory chain ahead of
  the store. Verification on open recomputes the chain
  over the rows as they stand and *reports* the verdict —
  the store opens and serves; the result rides on
  `HebbianMemory.integrity_attestation_status` and
  `health()`'s new additive `integrity_attestation` field
  (`ok` / `tamper_detected` / `not_enabled`), with a
  failure logged at ERROR and the tampered rows left as
  found. A marked store opened without the flag refuses
  typed before any write (pre-open probe; the judgement
  defers to the live connection when the probe cannot
  read the file, and a restored backup is judged by its
  own header — test-pinned). Enabling the flag on an
  existing store bootstraps the chain over the rows as
  found. Honest limits in the record: a wrong passphrase
  is indistinguishable from tampering (both recompute to
  a different head — the keyless chain's honest shape);
  the chain covers `activation_log` only, not the whole
  store; detection, not prevention or attribution;
  cross-process concurrent writers can false-alarm, never
  silently pass. New `tests/test_integrity_attestation.py`
  (13 tests — the roadmap's raw-SQL tamper test plus
  inserted/deleted-row, rewritten-head, wrong-passphrase,
  plain-open refusal, bootstrap, both batch roads, touch,
  encryption composition, backup-restore); negation
  against the RM-049 packages **12 failed / 0 passed /
  1 skipped** (the skip: the encryption-compose test, the
  negation venv carries no `cryptography`). RM-018
  goldens extended (+2 CASE / +6 TEMPLATE lines — muninn
  58 CASE / 85 TEMPLATE); RM-019 surface golden gained
  the two config fields; RM-003 health key set gained the
  field; RM-040 audit total 84 → 89 (+5 constant sites).
  **Bifröst re-verification PASS** (fresh venv
  `ravens-rm050-bifrost-venv` on `/var/tmp`, bifrost at
  b66e98cc — its own suites **25 passed**; BifrostBridge
  store/search/recall/decay/consolidate smoke PASS,
  evidence `/var/tmp/rm050-evidence/`). Full suites green
  in the RM-050 fresh venv on the final banking tree
  (TMPDIR + installs on `/var/tmp`, encryption extra
  installed): muninn **312 passed** (299+13), huginn
  **259 passed** (slice-log pin only); ruff + mypy floors
  clean (fresh tool venv on `/var/tmp`; mypy muninn 7
  files — the new `_attest.py` — huginn 9 files). Live
  Qdrant and sentence-transformers stay NOT PROVEN.
  Founding tree NEEDS A SYNC for the attestation build
  (extends the standing package-source sync note).

## RM-051 — Forget is forgetting

- **Class:** FAULT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** Forget-is-forgetting (TH-11), record in
  `docs/SECURE_FORGET.md`. The audit, proven by forensic
  byte-search of the store's files: plain `forget` /
  `delete` remove the live rows only — the forgotten
  content persists in WAL frames not yet checkpointed, in
  freed pages of the main file (whether a checkpoint
  zeroes them is a build's `secure_delete` default, not a
  promise), and in every rolling `.bak-N` generation until
  rotation; Muninn's `activation_log` is kept by design
  (ids and timestamps, never content). Both guides now
  state that truth beside `forget` / `delete`. New public
  method **`secure_forget(memory_id) -> bool`** in both
  packages (Muninn `HebbianMemory` + the `Muninn` facade;
  Huginn facade + both backends): the same validation,
  row work and return value as `forget` / `delete`, then
  the purge — the delete runs under
  `PRAGMA secure_delete=ON` (the per-connection value
  found is restored on exit: `_db.secure_delete_enabled`),
  `wal_checkpoint(TRUNCATE)`, `VACUUM` (the store is
  rebuilt from live rows only), `wal_checkpoint(TRUNCATE)`
  again, and — under the RM-037 coordination lock — every
  `.bak-*` file is discarded and replaced by one fresh
  snapshot of the purged store when `backup_keep` allows
  (`_db.purge_forgotten_content`, twin helpers in both
  packages; the row work is shared with `forget` /
  `delete` via `_forget_rows_locked` /
  `_delete_rows_locked`, so the semantics cannot drift).
  The purge runs even when nothing live was removed, so
  it remediates an earlier plain forget's residue. Cost
  stated in the record doc and both guides: a full store
  rewrite (time + temporary space on the store's order,
  exclusive lock) and the loss of all older backup
  generations; the purge is not atomic across its stages
  (the row deletion commits first) and another opener
  holding an old snapshot can keep WAL frames alive or
  fail the rewrite typed — close other openers first.
  Huginn's Qdrant backend has no local files: its
  `secure_forget` is the server-side delete (pinned
  against a stub client), and what the server's own
  snapshots retain is the operator's domain. New
  `tests/test_secure_forget.py` (muninn 10, huginn 8):
  the before/after forensic pair (string findable in
  `.bak-1` after plain forget/delete; findable in **no**
  file — main, `-wal`, `-shm`, every generation — after
  secure_forget, open, closed and reopened, in both the
  WAL-resident and the already-checkpointed cases),
  three generations replaced by exactly one fresh one,
  `backup_keep=0` leaves none, missing-id purge,
  tombstone/wiring parity with `forget`, typed id
  validation, and RM-049 encryption composition.
  Negation against the RM-050 packages: muninn **8
  failed / 2 passed**, huginn **6 failed / 2 passed** —
  the passes are exactly the preserved behaviours (the
  plain-forget residue truth and the record doc's
  existence). One test bug found and fixed in-slice: the
  first Huginn draft asserted `search(SECRET) == []`,
  but hyphen tokenisation shares the `rm051` token with
  the keeper document — the assertion now searches the
  secret's distinctive token. RM-019 surface goldens
  gained the method in both packages; RM-040 audit pins
  updated for the purge machinery's eight new constant
  sites per package, all in `_db.py`, no values at all
  (Muninn 89 → 97, Huginn 45 → 53); RM-018 goldens
  unmoved (no new raise site — the `_storage_write`
  wrapper's); no schema change (RM-004 goldens unmoved).
  Public API changed additively, so the **Bifröst
  contract re-verification was run before banking**:
  fresh venv (`ravens-rm051-bifrost-venv` on `/var/tmp`),
  bifrost at b66e98cc — its own suites **25 passed**;
  BifrostBridge smoke PASS (store mimir_id=2
  huginn_id=6; search 1 merged result; recall grew the
  Muninn activation log exactly +1; decay/consolidate
  reports; `decay_wall_clock()` through the bridge armed
  at 0 days; stats over all three backends; both raven
  health dicts carry `sqlite_version` 3.45.1; huginn
  degraded via auto-fallback to local — live Qdrant
  still NOT PROVEN; double close safe; evidence
  `/var/tmp/rm051-evidence/`). Full suites green in the
  RM-051 fresh venv on the final banking tree (TMPDIR +
  installs on `/var/tmp`, encryption extra installed):
  muninn **322 passed** (312+10), huginn **267 passed**
  (259+8); ruff + mypy floors clean (rm050 tool venv;
  mypy muninn 7 files, huginn 9 files). No new
  dependency — stdlib + SQLite pragmas only. Live
  Qdrant and sentence-transformers stay NOT PROVEN.
  Founding tree NEEDS A SYNC for the `secure_forget`
  build (extends the standing package-source sync
  note). TH-11's register update remains RM-056's.

## RM-052 — Dependency hygiene

- **Class:** UNIT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** Dependency hygiene (TH-12), record in
  `docs/DEPENDENCY_HYGIENE.md`. The audit at this slice:
  both cores dependency-free; every declared requirement
  (build-system setuptools `>=68,<82`; cryptography
  `>=42,<51`; qdrant-client `>=1.9,<2`;
  sentence-transformers `>=2.2,<6`; dev pytest / ruff /
  mypy / coverage) carries a `>=floor,<ceiling` bound and
  no direct reference — now pinned by new
  `tests/test_dependency_hygiene.py` in both packages
  (7 tests each). Lockfile example added:
  `docs/examples/requirements-lock.example.txt`, the exact
  23-pin closure `pip freeze` resolved for
  `muninn[encryption]` + `huginn[encryption,qdrant]` on
  CPython 3.12.3 (2026-11-02), with its generation road and
  the embeddings/dev exclusions stated in its header and
  the record; tests pin its exact-pin shape and that its
  direct-extra pins satisfy the declared bounds. The
  manual CI gains a `dependency-scan` job (bounded
  `pip-audit>=2.7,<3`; scans the lockfile example and an
  installed runtime + dev environment; the workflow stays
  manual-only — parsed-YAML check: trigger is exactly
  `workflow_dispatch`, jobs `test` + `dependency-scan`).
  **Found and fixed in-slice:** the slice's own scan,
  actually run locally with pip-audit 2.10.1, flagged
  **PYSEC-2026-1845** in pytest 8.4.2 — the newest release
  the old dev bound `pytest>=7,<9` allowed; the fix
  (9.0.3) sat outside the ceiling. The runtime closure
  scanned clean in the same run. The dev bound is now
  `pytest>=7,<10` in both pyprojects and the CI install
  line (`docs/INTEGRATION.md` corrected to match); after
  upgrading the scan environment to pytest 9.2.0,
  pip-audit over the full environment and over the
  lockfile example both reported no known vulnerabilities,
  and a hygiene test pins that the bound reaches 9.0.3.
  Negation against the RM-051 tree: **5 failed / 2 passed**
  per package (the passes are the pre-existing truths —
  dependency-free cores and bounds already present).
  No package code, public API, or schema change, so no
  Bifröst re-verification required. Full suites green in
  the RM-052 fresh venv on the final banking tree
  (TMPDIR + installs on `/var/tmp`, encryption extra
  installed, pytest 9.2.0): muninn **329 passed**
  (322+7), huginn **274 passed** (267+7); ruff + mypy
  floors clean. A GitHub-hosted run of the new job stays
  NOT PROVEN (manual-only, never dispatched); live
  Qdrant and sentence-transformers stay NOT PROVEN.
  Founding tree needs no sync for this slice (no package
  source changed); the standing package-source sync note
  stands. TH-12's register update remains RM-056's.

## RM-053 — Denial-of-service bounds

- **Class:** BENCH
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** Query cost ceilings (TH-13), record in
  `docs/QUERY_COST_CAPS.md`. The two expensive reads the
  threat names bound their *output* before this slice but
  not their *work*. Now: Muninn gains
  `max_spread_candidates: int = 100000` — one
  `spread_activation` call examines at most that many
  candidate edges (neighbour rows), frontier nodes and
  neighbours considered in id order so the bite is
  deterministic; Huginn gains
  `max_search_candidates: int = 10000` — one local search
  scores at most that many candidate documents (lowest
  ids first, cap applied before the category/importance
  filter, exactly where the unbounded fetch sat; on the
  vector road only surviving candidates' vectors are
  decoded at all). Both ceilings are validated at
  construction (RM-018 goldens gained the two cases).
  When a cap bites the call returns its partial result —
  never an error — and the bite is visible: Muninn's
  `last_spread_activation_stats` attribute and Huginn's
  new `last_search_stats` facade property carry the
  counts (`candidates_examined` / `candidates_total`,
  `candidates_scored`, `cap`, `capped`), and a WARNING
  with counts only is logged. **Design correction made
  in-slice:** the first draft surfaced the record inside
  `stats()` / `health()` and failed Muninn's RM-009
  read-purity pin (`test_idempotency` M09) — those
  snapshots are pinned pure, so the accounting moved to
  the dedicated accessors and the new suites pin that
  capped calls leave both snapshots byte-identical.
  Below the ceilings, results are exactly the unbounded
  behaviour (ancestor spread values and full-corpus
  search pinned unchanged). Qdrant search is out of
  scope (the server owns its cost); Muninn `retrieve`'s
  scan is bounded by `max_nodes` and no second ceiling
  was added there — both stated in the record. New
  `tests/test_query_cost_caps.py` (muninn 7, huginn 8),
  including the BENCH acceptance: a fully connected
  25-node graph at ceiling 200 examines exactly 200
  candidates with `capped` True; a 12-document one-term
  corpus at ceiling 5 scores exactly 5 of 12.
  Negation against the RM-052 tree: muninn **7 failed /
  0 passed**, huginn **8 failed / 0 passed** (every test
  pins new behaviour). Public API changed additively
  (two config fields, one facade property; RM-019
  goldens updated), so the **Bifröst contract
  re-verification was run before banking**: fresh venv
  (`ravens-rm053-bifrost-venv` on `/var/tmp`), bifrost
  at b66e98cc — its own suites **25 passed**;
  BifrostBridge smoke PASS (store mimir_id+huginn_id;
  search 1 merged result; recall grew the Muninn
  activation log exactly +1; decay/consolidate reports;
  `decay_wall_clock()` armed at 0 days; stats over all
  three backends; both raven health dicts carry
  `sqlite_version` 3.45.1; huginn on local via
  auto-fallback — qdrant-client not installed in the
  venv, the founding condition; double close safe;
  evidence `/var/tmp/rm053-evidence/`). Full suites
  green in the RM-053 fresh venv on the final banking
  tree (TMPDIR + installs on `/var/tmp`, encryption
  extra installed): muninn **336 passed** (329+7),
  huginn **282 passed** (274+8); ruff check clean;
  mypy clean in the RM-052 deps-free tool venv (muninn
  7 files, huginn 9 files). No schema change (RM-004
  goldens unmoved); no new dependency. Live Qdrant and
  sentence-transformers stay NOT PROVEN. Founding tree
  NEEDS A SYNC for the two config fields, the spread
  walk, the local search caps and the facade property
  (extends the standing package-source sync note).
  TH-13's register update remains RM-056's.

## RM-054 — Error-message hygiene

- **Class:** UNIT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** Typed errors never carry file contents, keys
  or full paths beyond the store path the caller itself
  supplied (TH-14), record in
  `docs/ERROR_MESSAGE_HYGIENE.md`. The audit found fourteen
  wrap sites interpolating uncontrolled exception *text*:
  six SQLite sites (per package: the two
  `could not be prepared` branches in `_db.py` and the
  write guard's generic branch) and Huginn's eight Qdrant
  wraps, which since RM-045 carried client text with only
  the API key masked. The leak is real, not theoretical:
  SQLite generates some error text from the store file
  itself — a trigger's `RAISE(ABORT, '…')` message rode
  verbatim into the typed error on both the write and open
  roads in a probe against the RM-053 tree. The rule now:
  a typed message is built only from fixed text,
  package-computed values, the caller's own supplied
  store path / Qdrant URL / collection name, and the
  underlying exception's **class name** — never its text
  (`_error_kind` in both `_db.py` files; the Qdrant
  backend's `_scrub` seam kept, its contract changed).
  The full text remains available through the exception
  chain (`from exc` everywhere; the new suites pin the
  planted text in `__cause__`). The write guards also gain
  a classified disk-full branch (`_is_full_error`:
  SQLITE_FULL code 13 or the canonical wording) emitting
  the package's own fixed `database or disk is full`
  text, so RM-029's shape survives without echoing.
  Deliberate message changes, recorded per RM-018: the
  seven Qdrant CASE lines in Huginn's golden now end in
  the fake clients' class name (`RuntimeError`) instead
  of their wording; RM-045's transport tests assert
  absence of the whole client wording where they asserted
  the `***` mask (the facade still key-scrubs the error
  strings it reports — `health()`, fallback reason — as
  defence in depth, and those surfaces are scan-pinned
  too). RM-018's "cannot be triggered deterministically"
  note for `could not be prepared` is superseded: a store
  trigger aborting the prepare-time meta insert triggers
  it, and both that branch and the generic write-guard
  branch are CASE lines now (goldens 61 / 69 cases;
  template counts corrected to the true 87 / 90, one new
  fixed disk-full template each). New
  `tests/test_error_message_hygiene.py` (muninn 7,
  huginn 8): a combined planted leak (a stored memory's
  exact content, a foreign absolute path, the Qdrant key,
  both passphrases) placed in trigger text, client error
  text and wrong-passphrase attempts, scanned out of
  every typed message and Huginn's reported surfaces,
  plus an AST pin that no raise site interpolates an
  exception variable except through `_error_kind` /
  `_scrub`. Negation against the RM-053 tree: muninn
  **5 failed / 2 passed**, huginn **5 failed / 3 passed**
  (the passes are exactly the shapes already fixed text:
  disk-full, wrong-passphrase, Huginn's local fixed
  shapes). Scoping stated in the record: validation
  messages echoing a caller's own argument back to that
  caller stay (deliberate RM-018 API); untyped third-party
  raises are not typed errors. **Bifröst re-verification
  PASS** (fresh venv `ravens-rm054-bifrost-venv` on
  `/var/tmp`, bifrost at b66e98cc — its own suites
  **25 passed**; BifrostBridge smoke PASS, evidence
  `/var/tmp/rm054-evidence/`). Full suites green in the
  RM-054 fresh venv on the final banking tree (TMPDIR +
  installs on `/var/tmp`, encryption extra installed):
  muninn **343 passed** (336+7), huginn **290 passed**
  (282+8); ruff check clean; mypy clean in the RM-052
  deps-free tool venv (muninn 7 files, huginn 9 files).
  No schema change (RM-004 goldens unmoved); no public
  signature change (RM-019 goldens unmoved); no new
  dependency. Live Qdrant + sentence-transformers stay
  NOT PROVEN. Founding tree NEEDS A SYNC for the
  RM-054 build (extends the standing package-source sync
  note). TH-14's register update remains RM-056's.

## RM-055 — Secure defaults review

- **Class:** UNIT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** Every config default re-judged for safety
  (TH-15), record in `docs/SECURE_DEFAULTS.md`, with the
  judgements also recorded in both guides' config tables.
  All 38 fields (MuninnConfig 19, HuginnConfig 19) were
  judged in four classes — safe-off/safe-none,
  safety-positive on, bounded, compatibility-kept — and
  **no default changed**: every default that could leak
  content, weaken transport, execute or download is
  already off, loopback-confined, or opt-in; every default
  that is on is safety-positive (backups) or bounded
  (finite timeouts, validated ceilings); and the three
  compatibility-kept judgements are named plainly in the
  record — `strict_path_safety=False` in both packages
  (recorded behaviour; flipping it would refuse legitimate
  symlinked deployments at open; the opt-in is the
  locked-down road), Huginn's `backend="auto"` (the
  Bifröst no-config contract; the fallback is not silent —
  lazy loopback probe bounded by `qdrant_timeout`, reason
  and effective backend in `health()`; `backend="local"`
  never touches the network), and
  `store_encryption` / `integrity_attestation` off (each
  needs a passphrase a default must never invent; a marked
  store refuses unprotected opens, so opting in is
  complete). **Drift found and fixed in-slice
  (never-leave-a-bug):** `store_encryption` and
  `encryption_passphrase` were missing from both guides'
  config tables, and the `docs/API_REFERENCE.md` config
  listings had drifted behind RM-049/RM-050/RM-053 — the
  missing rows and listings are added, so a deployment can
  discover and judge every default from the guides. New
  `tests/test_secure_defaults.py` (muninn 7, huginn 8)
  pin the exact default of every field, the field set
  itself (a new field fails until reviewed here), the
  security flags' posture, the absence of any invented
  secret, the bounded waits/ceilings, Huginn's default
  transport posture (loopback http accepted, remote http
  refused at construction), and that the record and the
  guide name every field. Negation against the RM-054
  tree: muninn **2 failed / 5 passed**, huginn **2 failed
  / 6 passed** — the failures are exactly the record and
  guide pins; the passes are the defaults that were
  already reviewed-safe, which is the expected shape for a
  review that changes no default. No package source, public
  API, or schema change (docs + tests only), so no Bifröst
  re-verification required. Founding tree needs no sync
  for this slice; the standing package-source sync note
  stands. TH-15's register update remains RM-056's.
  Banking verification: see `CAMPAIGN_STATE.md`.

## RM-056 — Part gate

- **Class:** UNIT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** Part IV (Security) gate — TH-16 closed.
  Security evidence bundle filed at
  `docs/PART_IV_EVIDENCE.md`: every Part IV slice
  (RM-039–RM-056) checked off with its banking suites,
  every FAULT result filed (RM-049 store encryption
  build, RM-050 integrity attestation, RM-051
  secure forget — each with its record document,
  forensic/tamper acceptance and negation counts), the
  rest of the part's evidence grouped (injection and
  path safety, file and backup confidentiality,
  diagnostics hygiene, the Qdrant boundary, identity
  and at-rest, supply chain and cost, defaults), the
  Bifröst re-verifications inside the part (RM-041,
  RM-049, RM-050, RM-051, RM-053, RM-054 — six for six
  green; RM-046 also ran it as a precaution), the floors
  (ruff + mypy clean at every banking, coverage
  `fail_under = 88`, and **no schema changed in Part
  IV** — RM-049's envelopes live in the same TEXT
  columns, RM-050's chain header in `meta` rows, the
  contracted tables exactly as frozen), the honesty
  ledger carried forward unchanged (live Qdrant
  round-trip, sentence-transformers path and
  GitHub-hosted CI all **NOT PROVEN**; the `cryptography`
  extra proven from RM-049), and the debts named
  (founding-tree sync owed for every Part IV
  package-source change on top of the Part II/III debt;
  `schema_version` recorded-not-gated until RM-082 /
  RM-132; Part IV's opt-in posture itself recorded, not
  hidden). **Threat model updated with what the part
  actually built**, per the RM-039 citation rule:
  `docs/THREAT_MODEL.md` carries an RM-056 banner, every
  register State cell updated to its post-Part-IV
  position (Controlled: TH-01, TH-03, TH-04, TH-05,
  TH-08, TH-11, TH-12, TH-13, TH-14, TH-15, TH-16 at
  this gate; Partial by stated design: TH-02, TH-06,
  TH-07, TH-09, TH-10, TH-19; Accepted unchanged:
  TH-20, TH-21; Controlled unchanged: TH-17, TH-18),
  and a full RM-056 re-review section recording, threat
  by threat, the slice evidence each verdict stands on
  and the updated boundary notes for TB-2/TB-5/TB-6; no
  threat was found that RM-039 did not name and no
  register entry was deleted; the RM-039 text is
  otherwise preserved as the record the part was built
  against. Pinned by new `tests/test_part_iv_gate.py`
  in both packages (3 tests each: the bundle names every
  Part IV slice, files every FAULT result and carries
  the honesty ledger, and the threat model carries the
  gate re-review and updated register); both
  `test_slice_log.py` EXPECTED pins extended to RM-056
  in this commit. Negation: the gate tests run against
  a scratch tree whose bundle omits a slice name and a
  FAULT marker fail on exactly those pins (recorded in
  `CAMPAIGN_STATE.md`). No package code, public API, or
  schema change (docs + tests only), so no Bifröst
  re-verification required for the gate itself.
  Founding tree needs no NEW sync for this slice (docs +
  tests only); the Part IV package-source sync note
  stands. **Part IV (Security) is complete with this
  slice** — 18 of 18 slices banked. The road continues
  at Part V — Speed (RM-057–RM-072).
  Banking verification: see `CAMPAIGN_STATE.md`.

## RM-057 — Baseline atlas

- **Class:** BENCH
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** Part V — Speed opens with a map, not a
  change. New `scripts/atlas.py` in both packages extends
  the RM-005/006 harness to **1k / 10k / 100k** nodes
  (Muninn) and documents (Huginn) for every headline
  operation, reusing the RM-020 corpus generators and the
  RM-006 environment block unchanged. The seed is the write
  operation (total ms for the whole scale); every other
  operation uses fixed sample batches identical at every
  scale (Muninn: 2,000 activate, 500 activate_batch(5),
  1,000 get_associations, 200 spread_activation(depth=2),
  200 stats, read/maintenance medians of 3; Huginn: median
  per search over 50 search / 25 filtered), so the tables
  show cost growth with store size only. Records committed
  as `muninn/scripts/atlas.json` and
  `huginn/scripts/atlas.json`; human record with both
  tables and readings in `docs/ATLAS.md`; pointer section
  added to `docs/BENCHMARKS.md`. The atlas is a record,
  not a gate (RM-071 wires the gate). Findings, all from
  the records: Muninn reads are flat to 100k
  (get_associations ×1000: 185.7 / 86.5 / 87.2 ms;
  spread ×200: 218.0 / 88.2 / 108.7 ms) while **stats() is
  the outlier** (×200: 322.5 / 1,794.2 / 31,790.6 ms —
  ~1.6 / ~9.0 / ~159 ms per call); decay and consolidate
  at 100k are ~0.5–0.6 s medians; Huginn upsert is a
  steady ~1.0–1.4 ms/doc at every scale (100k docs in
  101,382.0 ms) — and the search rows carry a proven
  corpus caveat: the RM-020 Huginn corpus holds only
  **23 distinct documents**, so RM-053's filed accounting
  shows a 230-candidate pool at every scale, cap never
  biting; search cost over 100k *distinct* documents is
  therefore NOT measured here and is named as the gap
  RM-061/RM-062 must close (Muninn's corpus is fully
  distinct, 100,000 of 100,000). Two design facts faced
  squarely: Muninn's atlas raises the backpressure
  ceiling (`max_nodes`, default 20,000) to an exact fit
  per scale, recorded as `config_overrides` in every
  entry — a default-config seed provably stalls at
  20,001 nodes, so without the override the 100k row
  would be false; and the stores lived on **tmpfs**, the
  RM-005 storage class, with the fsync warning measured
  in a controlled A/B in this slice (2,000 activate:
  172.6 ms tmpfs vs 58,843.2 ms overlay disk, ~340×).
  Environment blocks in both records (Muninn recorded
  2026-11-02T13:33:00Z at load [1.26, 5.46, 5.24]; Huginn
  2026-11-02T13:40:22Z at load [2.39, 5.94, 5.71]; both
  x86_64, 4 CPUs, Python 3.12.3, SQLite 3.45.1) — loaded
  machine, numbers indicative: the 100k Muninn seed
  (577,093.1 ms) is labelled a load artefact in the
  record's reading. Pinned by new
  `tests/test_benchmark_atlas.py` in both packages
  (5 tests each: scales are exactly 1k/10k/100k, headline
  ops match the gate contract, sample batches are fixed,
  a tiny-scale real run covers every op with honest
  corpus hashes and — Muninn — exact node counts and the
  named override, and the committed record covers all
  scales and ops); both `test_slice_log.py` EXPECTED
  pins extended to RM-057 in this commit. Negation
  against the RM-056 tree (new tests + extended pins on
  the archived tree): **7 failed / 0 passed per package**
  (5 atlas + 2 slice-log), failures exactly on the
  missing atlas files and the missing RM-057 entry.
  Slice-internal repairs, recorded not hidden: the first
  Muninn run used the default ceiling and its 100k row
  was discarded unrecorded once the prune was proven;
  the first Huginn run crashed on a property called as a
  method (`last_search_stats` is RM-053's facade
  property) — fixed in the script and re-run; the
  Huginn record was then re-run once more so the
  unfiltered search's cost accounting is filed beside
  the filtered one's. No package source, public API, or
  schema change (scripts + records + tests + docs
  only), so no Bifröst re-verification required.
  Founding tree needs no sync for this slice (no package
  source change); the standing Part II–IV sync note
  stands. Live Qdrant + sentence-transformers stay
  NOT PROVEN.
  Banking verification: see `CAMPAIGN_STATE.md`.

## RM-058 — Muninn read path

- **Class:** BENCH
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** The atlas (RM-057) showed Muninn reads flat
  to 100k *nodes* — on a store with only ~4,000 connection
  rows. This slice profiles `get_associations` and
  `spread_activation` at **100k edges** with a new gate
  script, `muninn/scripts/read_path.py` (deterministic
  graphs: a 5,000-node ring with 100,000 directed rows,
  degree 20; and a hub with 10,000 spokes, 20,000 directed
  rows), run unchanged on the pre- and post-slice trees,
  three full runs per tree, medians reported. The profile
  found the pain exactly at the hub: `get_associations`
  with the default limit cost ~10 ms/call (plan: PK-index
  search + `USE TEMP B-TREE FOR ORDER BY` — all 10,000 hub
  rows fetched and sorted to return 100), and depth-2
  `spread_activation` from the hub issued one query per
  frontier node (10,001 queries) plus a redundant Python
  re-sort of rows the PK index already orders. Two changes,
  nothing else: (1) covering index `idx_conn_a_strength`
  on `hebbian_connections (memory_a_id, strength DESC,
  co_activation_count DESC, memory_b_id ASC, consolidated,
  last_coactivated_at)` — the first four keys are the
  query's filter + ordering, the last two are trailing
  keys carrying the remaining selected columns (this
  machine's SQLite build rejects `INCLUDE` outright,
  probed directly on 3.45.1; trailing keys do the job).
  No table or column changed; the schema script creates
  the index on every open, so pre-RM-058 stores gain it on
  their next open (test-pinned). (2) `spread_activation`
  reads each depth level in chunks of 500 frontier ids
  (`IN (...)` bound parameters, `ORDER BY memory_a_id,
  memory_b_id`) — exactly the old walk's candidate order,
  so results and the RM-053 cap's bite point are
  bit-for-bit preserved (parity pinned against an
  independent reference walk in the new tests, including
  a cap bite inside the second chunk); the new SQL shape
  is a pinned template in the RM-040 audit (site total
  unchanged — one constant site became the template).
  Gate numbers (median of 3 runs per tree, sample totals,
  tmpfs, loaded VM): hub `get_associations` limit=100 ×20
  **207.2 → 3.1 ms (~67×)**; hub limit=10000 ×20
  1,870.9 → 1,091.4 ms (~1.7×); hub spread depth2
  **208.3 → 95.3 ms (~2.2×)**; hub spread depth1 71.1 →
  76.9 ms (no win claimed — one query either way, Python
  row loop dominates); uniform reads flat (get ×200
  10.7 → 7.2 ms, spread depth2 ×50 96.0 → 90.0 ms,
  depth3 ×20 99.6 → 96.2 ms). After plan: `SEARCH ...
  USING COVERING INDEX idx_conn_a_strength`, no temp
  b-tree. Record committed at `muninn/scripts/read_path.json`;
  human record in `docs/READ_PATH.md`; pointers in
  `docs/BENCHMARKS.md`; `docs/FORMAT_STABILITY.md` names
  the new index beside the other golden indexes. New
  `tests/test_read_path.py` (10 tests, muninn only);
  both `test_slice_log.py` EXPECTED pins extended to
  RM-058. Negation against the RM-057 tree: muninn
  **12 failed / 13 passed** (failures exactly on the
  script/record/index/plan/audit-template/golden/format/
  slice-log pins; the parity and limit semantics tests
  pass on both trees, as they must), huginn **2 failed /
  0 passed** (slice-log pins). **Bifröst re-verification
  PASS** (schema gained an index: fresh venv, bifrost at
  b66e98cc — its own suites **25 passed**; BifrostBridge
  store/search/recall/decay/consolidate smoke PASS).
  Full suites green in the RM-058 fresh venv on the final
  banking tree (non-editable installs, encryption +
  qdrant extras, cryptography 50.0.2, qdrant-client
  1.20.0, pytest 9.2.0): muninn **368 passed** (358+10),
  huginn **306 passed** (slice-log pin only); ruff check
  clean (both packages, whole tree); mypy clean in a
  deps-free tool venv per package (muninn 7 files,
  huginn 9 files). Honest limits recorded in
  `docs/READ_PATH.md`: the remaining hub costs are Python
  (10k result dicts, the depth-1 row loop), and the index
  is one more index maintained on connection writes —
  RM-059/RM-060 measure write costs with it in place.
  Founding tree NEEDS A SYNC for the index + batched
  spread build (extends the standing package-source sync
  note). Live Qdrant + sentence-transformers stay
  NOT PROVEN.
  Banking verification: see `CAMPAIGN_STATE.md`.

## RM-059 — Activation write path

- **Class:** BENCH + UNIT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** `activate`'s one helper,
  `_log_activation_locked` (behind `activate`, the
  small-batch road of `activate_batch`, and
  `retrieve(..., touch=True)`), ran **five data statements
  per activation** — log INSERT, counter upsert, node
  UPDATE, tombstone DELETE, and a SELECT re-reading the
  counter total the upsert had just written. New gate
  script `muninn/scripts/write_path.py` profiles activate
  (same id / distinct ids), `activate_batch(5)` and
  `retrieve(touch=True)` on a 2,000-node store and counts
  the executed statements per `activate()` by trace
  callback; run unchanged on both trees, three full runs
  per tree, medians reported. Two changes, nothing else:
  (1) the counter upsert now carries `RETURNING
  total_activations` on SQLite 3.35+, folding the re-read
  into the write — **four statements per activation**
  [INSERT, INSERT, UPDATE, DELETE], which is the floor
  without a schema or trigger change (four distinct
  tables change). Older runtimes (the documented WAL
  floor is 3.7.0) keep the upsert + re-read road behind
  the `muninn.core._RETURNING_OK` version check —
  semantics identical, fallback test-pinned with the
  flag forced off. (2) The RM-050 attestation head write
  (two meta rows, head + count) is one combined
  `INSERT OR REPLACE … VALUES (?, ?), (?, ?)` instead of
  an executemany of two — same rows, same transaction.
  Gate (medians of 3, tmpfs): statements **5 → 4**;
  activate same id ×2000 215.8 → 205.9 ms; distinct
  ×2000 256.7 → 213.3 ms; batch(5) ×400 394.4 → 211.9 ms;
  retrieve(touch) ×200 11,791.6 → 8,300.9 ms — timings
  recorded as indicative only, honestly load-confounded
  (before runs at 1-minute load 8.6–9.5, after runs at
  0.9–5.9 on the shared VM); the statement count is the
  hard gate. Record at `muninn/scripts/write_path.json`
  (after tree's third run, recorded
  2026-11-02T15:19:39Z, load [5.93, 4.73, 4.78]); human
  record `docs/WRITE_PATH.md`; BENCHMARKS.md pointer.
  New `tests/test_write_path.py` (10, muninn only):
  statement counts + shapes on both roads, the attested
  head as one meta statement with the chain verifying on
  reopen, count-exact semantics against raw-SQL ground
  truth (sequential totals; log/counter/access equality
  across live, forgotten and never-remembered ids;
  tombstone clearing; the confidence formula after a
  decay; small-batch pair reports; touch counts), the
  gate script's small-run shape and the committed
  record. RM-040 audit site total 97 → 98 (the fallback
  upsert is a second constant form); `test_slice_log.py`
  EXPECTED to RM-059 in both. Negation vs RM-058 tree:
  muninn **8 failed / 13 passed** (failures exactly on
  the new pins; the count-exact semantics pass on both
  trees, as they must), huginn **2 failed / 0 passed**.
  No public API, signature, return shape, table, column
  or index changed, so no Bifröst re-verification is
  required by the standing rule; one was run anyway as a
  precaution — see `CAMPAIGN_STATE.md`. Full suites and
  floors: see `CAMPAIGN_STATE.md`. Founding tree NEEDS
  A SYNC for the RETURNING upsert + combined head write
  (extends the standing package-source sync note). Live
  Qdrant + sentence-transformers stay NOT PROVEN.
  Banking verification: see `CAMPAIGN_STATE.md`.

## RM-060 — Bulk remember

- **Class:** BENCH
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** Muninn gains `remember_many(items) -> list[int]`:
  item dicts carrying `remember`'s arguments by name
  (`content` required; `category`, `path`, `importance`,
  `tags`, `emotional_valence`, `metadata` optional, same
  defaults), ids returned in input order. The batch
  contract, per the roadmap — **one transaction, one
  content-hash pass, backpressure applied once**: every
  item is prepared exactly once before the transaction
  opens (validation, serialization, the one hash), by
  `remember`'s own preparation extracted as
  `_prepare_remember` and shared by both roads, with the
  insert likewise shared (`_insert_prepared_locked`), so
  the roads cannot drift and the RM-040 audit total is
  unchanged at 98 sites (no new SQL shape). All inserts
  land or none do — an invalid item, or an RM-047 hash
  collision against the store or within the batch, rolls
  the whole batch back (deliberately stricter than a
  loop, whose earlier calls stay stored); the batch
  carries one `_tick()` timestamp (the `activate_batch`
  discipline); the `max_nodes` check runs once after the
  commit. Per-item idempotency is `remember`'s (first
  write wins; an in-batch duplicate shares its first
  occurrence's id). Item shape is closed: four new typed
  refusals (container, per-item dict, unknown key,
  missing `content`), pinned as RM-018 CASE + TEMPLATE
  lines (61 → 65 cases, 87 → 91 templates). Gate script
  `muninn/scripts/bulk_remember.py` ingests 10,000
  distinct RM-020-corpus nodes into a fresh store by the
  loop and by the batch, verifying both roads built
  logically identical stores (same ids in order, same
  per-node fields excluding timestamps) inside every run
  before quoting timings. Three full runs on the after
  tree (each the median of 3 ingests per road, tmpfs):
  loop 2,079.9 / 1,603.2 / 1,028.6 ms, batch 677.7 /
  603.9 / 367.4 ms — **medians of the runs: loop
  1,603.2 ms → batch 603.9 ms, 2.65×** (per-run speedups
  3.07× / 2.65× / 2.80×). Timings are indicative only:
  the shared VM's 1-minute load ran 3.6–4.6 and the
  loop's own time swung 2× between runs; the durable
  claim is the test-pinned shape — one COMMIT and one
  backpressure head-count per batch instead of one per
  node. Record at `muninn/scripts/bulk_remember.json`
  (third run, recorded 2026-11-02T15:52:31Z, load
  [4.58, 3.79, 4.25]); human record
  `docs/BULK_REMEMBER.md`; BENCHMARKS.md pointer. New
  `tests/test_bulk_remember.py` (17, muninn only):
  field fidelity, loop parity + one-timestamp stamp,
  empty-batch no-op, in-batch + store-hit idempotency,
  facade, transaction/backpressure statement counts by
  trace callback, exact backpressure victims, atomic
  refusals (invalid, oversize, shape guards), the
  forced-collision rollback, the disk-full typed road,
  the encrypted-store composition, the RM-044 log
  discipline, gate-script shape + committed record.
  RM-013 matrix gains row M-30 with its test; RM-019
  golden gained the two `remember_many` lines.
  Negation vs the RM-059 tree: `test_bulk_remember.py`
  **17 failed / 0 passed**; `test_idempotency.py`
  **1 failed / 30 passed** (M-30 only);
  `test_error_messages.py` **2 failed / 1 passed**;
  `test_api_surface.py` **1 failed / 2 passed**;
  `test_sql_injection.py` 9 passed (audit unchanged, as
  designed); slice-log pins **2 failed** per package.
  Public API grew additively, so the **Bifröst
  re-verification was run before banking** — see
  `CAMPAIGN_STATE.md`. Suites in the RM-060 fresh venv
  on the final banking tree (non-editable installs
  from a full-repo copy, encryption + qdrant extras,
  cryptography 50.0.2, qdrant-client 1.20.0, pytest
  9.2.0): huginn **306 passed** in one full run
  (slice-log pin only; its first attempt died at
  collection on an EDQUOT pycache creation and the
  green run used `PYTHONDONTWRITEBYTECODE=1` with
  TMPDIR on `/var/tmp`); muninn **396 passed**
  (378+18) **assembled per-file — all 57 test files
  green** — after two full-run attempts died with a
  fatal Bus error mid-suite (the first in `close()`
  during `test_contract_freeze`, the second in
  `activate` during `test_benchmark_atlas`; both
  files pass alone and in the assembly). The pattern
  is the RM-039 environment class: SQLite WAL `-shm`
  faults while the home quota is shut under the VM's
  multi-campaign write load, not a code failure.
  Ruff clean (whole tree); mypy clean in a deps-free
  tool venv (muninn 7 files, huginn 9 files).
  Founding tree NEEDS A SYNC for the `remember_many`
  build (extends the standing package-source sync
  note). Live Qdrant + sentence-transformers stay
  NOT PROVEN.

## RM-061 — Huginn candidate generation

- **Class:** BENCH + UNIT
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** Local TF-IDF search gains posting-list
  pruning. From the query terms' posting lists alone the
  backend computes each candidate's exact dot product and
  a lower bound on its full vector norm (posting sub-norm
  plus the least the remaining terms can contribute, from
  the corpus-minimum idf and the candidate's total token
  count via one `SUM(tf)` aggregate), giving a true upper
  bound on its cosine score. Candidates are fully scored
  best-bound-first in batches of 128; once `limit` exact
  scores stand, a remaining candidate whose bound (with a
  `(1 + 1e-9)` safety factor) cannot beat — or
  tie-and-outrank by the RM-011 id tie-break — the
  limit-th score is pruned without its term set ever
  being fetched. Pruning is EXACT: results are the
  unpruned search's results. `last_search_stats` gains
  `candidates_pruned` (always 0 on the vector road);
  RM-040 audit site total 53 → 57 (the posting read, the
  totals aggregate and the evolved per-batch shapes are
  pinned templates). Gate script
  `huginn/scripts/candidate_pruning.py` seeds the RM-020
  benchmark corpus (5,000 texts dedupe to 230 stored
  documents) and a new 10,000-document distinct corpus,
  verifies parity against a brute-force reference inside
  every run before quoting timings, three runs per tree.
  Structural result (load-independent): benchmark
  candidates **230 → 128 scored, 102 pruned** on every
  after run; distinct candidates **pruned 0** of
  1,129 / 853 / 1,168. Timings are indicative only and
  honestly load-confounded (1-minute loads 1.9–14.4
  across the nine runs on the shared VM): medians of
  three runs, benchmark 44.4 → 102.6 ms, distinct
  689.6 → 1,082.5 ms; an interim batch-64 after set at
  lower load read benchmark 41.2 ms (64 scored), and a
  controlled back-to-back pair on a 3,000-document
  distinct store (30 searches, median) measured
  **198.9 ms before → 301.1 ms after** — where the
  bound prunes nothing, the new road costs ~1.5×.
  The weakness is measured, not guessed: one
  corpus-wide term collapses the idf floor (benchmark
  `raven` in 230/230 documents, floor ≈ 0.002; distinct
  `term766` in 6,990/10,000, floor 0.358 against
  query-term idfs ~3.1–3.7), and on long documents the
  bound norm sits far under the true norm (sampled
  mid-ranked candidate 3.85 vs 17.54; median bound
  0.437 vs limit-th score 0.162), so no distinct
  candidate's bound ever clears the threshold. Batch
  size was raised 64 → 128 during the slice's own gate
  runs (halves the per-batch query overhead on the
  no-prune path; the benchmark corpus still spans two
  batches). Human record `docs/CANDIDATE_PRUNING.md`;
  BENCHMARKS.md pointer; QUERY_COST_CAPS.md stats table
  gained the `candidates_pruned` row. New
  `tests/test_candidate_pruning.py` (9, huginn only):
  raw-table-reference parity on the benchmark corpus
  (limits 10/3, category filter) and a randomized
  corpus (limits, category, importance floors),
  crafted strong/weak pruning + exactness, RM-053 cap
  composition, exact ties never pruned, vector road
  records 0, RM-049 encrypted store prunes identically,
  gate-script shape + small run, committed record
  shape. Negation vs the RM-060 tree:
  `test_candidate_pruning.py` **5 failed / 4 passed**
  (parities pass on both trees — exactness is a
  property of both roads), `test_query_cost_caps.py`
  **2 failed**, `test_sql_injection.py` **2 failed**,
  slice-log pins **2 failed** per package. Public API
  grew additively (one stats field), so the **Bifröst
  re-verification was run before banking** — see
  `CAMPAIGN_STATE.md`. Suites in the RM-061 fresh venv
  on the final banking tree: huginn **315 passed**,
  muninn **396 passed** (counts as banked; see
  CAMPAIGN_STATE.md for the run record). Ruff clean
  (whole tree); mypy clean in a deps-free tool venv
  (muninn 7 files, huginn 9 files). Founding tree
  NEEDS A SYNC for the RM-061 build (extends the
  standing package-source sync note). Live Qdrant +
  sentence-transformers stay NOT PROVEN.

## RM-062 — Huginn vector scan

- **Class:** BENCH
- **Commit:** this commit (hash in `CAMPAIGN_STATE.md` / `git log`)
- **Evidence:** The embedder-mode vector scan gains the
  in-store prefilter the roadmap asked for. The old road
  fetched EVERY stored vector's text out of SQLite
  (`SELECT doc_id, vector FROM doc_vectors` — at 384
  dimensions ~4.8 KB of JSON text per vector, so the
  gate's 100k-document store, 477,544,448 bytes, moved
  its whole vector table per search), sorted and capped
  in Python, and only then applied the
  category/importance filter to the document rows. All
  three cuts now happen in SQL, in the RM-053 order —
  cap BEFORE filter, lowest ids first: the candidate
  total is a `COUNT(*)`, the capped ids are selected in
  the store (`ORDER BY doc_id LIMIT ?`, cap bound), the
  documents fetch applies the filter in SQL as it
  already did, and only the surviving documents' vectors
  are fetched, by id (`WHERE doc_id IN (...)`, every id
  bound). The survivors are scored by the same linear
  dense-cosine scan in Python — no index, no
  approximation — and results and the RM-053
  `last_search_stats` accounting are bit-for-bit the
  old road's. RM-040 audit site total 57 → 59 (the old
  full-table fetch replaced by the COUNT, the capped-id
  select, and the pinned survivor-fetch template). Gate
  script `huginn/scripts/vector_scan.py` seeds 10,000
  documents through the public `upsert_memory` API
  (store 74,694,656 bytes) and a constructed
  100,000-document store (direct construction stated in
  the record; the term index is intentionally empty —
  the vector road never reads it), verifies result
  parity against a brute-force reference computed from
  the raw tables inside every run before quoting
  timings, one full run per tree. Gate medians: api
  unfiltered 12,299.3 → 6,233.0 ms, category
  2,337.0 → 982.5 ms, importance 3,586.7 → 1,704.8 ms;
  scale unfiltered 101,700.6 → 124,250.4 ms, category
  9,255.2 → 20,908.3 ms, importance
  16,361.6 → 32,315.4 ms. A controlled back-to-back
  pair on the same seeded stores leaned the other way
  at both scales (api unfiltered 13,934.4 → 16,790.2 ms,
  category 1,196.5 → 2,165.7 ms, importance
  3,011.0 → 4,387.2 ms; scale unfiltered
  157,713.2 → 106,831.6 ms, category
  14,982.4 → 11,487.3 ms, importance
  28,596.6 → 21,853.7 ms) while the VM's 1-minute load
  rose ~9 → ~16 under concurrent campaign suites — so
  **no wall-clock win or regression is claimed either
  way**: the searches are dominated by decoding and
  scoring the survivors, next to which even the old
  road's full-table transfer is a minority cost on a
  warm tmpfs store. **Verdict, as the roadmap directed:
  the linear scan stands at personal-store scale; no
  ANN index is built.** The prefilter is kept on the
  load-independent evidence — a filtered or capped
  search's vector transfer is now proportional to its
  survivors (statement-shape-pinned), and excluded
  vectors are never fetched or decoded. Record at
  `huginn/scripts/vector_scan.json` (after tree's run,
  recorded 2026-11-02T20:42:38Z, load [5.12, 7.91,
  7.72]); human record `docs/VECTOR_SCAN.md`;
  BENCHMARKS.md pointer; QUERY_COST_CAPS.md,
  HUGINN_GUIDE.md, ARCHITECTURE.md and API_REFERENCE.md
  gained the prefilter notes. New
  `tests/test_vector_scan.py` (7, huginn only):
  raw-table-reference parity across limits, category,
  importance and combined filters; the prefilter's
  statement shape by trace callback; RM-053
  cap-before-filter order on the vector road;
  filtered/capped-out vectors never decoded (stored
  text corrupted, searches still exact); RM-049
  encrypted store searches identically; gate-script
  shape + small run; committed record shape. Negation
  vs the RM-061 tree: `test_vector_scan.py` **3 failed
  / 4 passed** (parities pass on both trees),
  `test_sql_injection.py` **2 failed**, slice-log pins
  **2 failed** per package. No public signature, table,
  column or index changed, so no Bifröst
  re-verification was required by the standing rule;
  run anyway as a precaution (the RM-059 pattern) —
  see `CAMPAIGN_STATE.md`. Suites, ruff and mypy on
  the final banking tree are recorded in
  `CAMPAIGN_STATE.md`. Founding tree NEEDS A SYNC for
  the RM-062 build (extends the standing
  package-source sync note). Live Qdrant +
  sentence-transformers stay NOT PROVEN.
