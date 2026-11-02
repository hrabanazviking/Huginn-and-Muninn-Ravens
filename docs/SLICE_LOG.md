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
