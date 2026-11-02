# CAMPAIGN STATE — Huginn & Muninn Ravens Roadmap

Roadmap: `RAVENS_ROADMAP_2026-10-31.md` (repo root)
Repo: hrabanazviking/Huginn-and-Muninn-Ravens
Working tree: `~/workspace/ravens-repo/` (own clone, never shared)
Keeper: ravens-roadmap-keeper (10-minute keeper, Volmarr's keeper law)

## Slice census (from the roadmap file itself, counted 2026-10-31)

Total: **212 slices (RM-001–RM-212), seventeen parts.**

| Part | Range | Count | Title |
|---|---|---|---|
| I | RM-001–RM-010 | 10 | Foundations & Gates |
| II | RM-011–RM-024 | 14 | Stability |
| III | RM-025–RM-038 | 14 | Robustness |
| IV | RM-039–RM-056 | 18 | Security |
| V | RM-057–RM-072 | 16 | Speed |
| VI | RM-073–RM-086 | 14 | Self-Healing |
| VII | RM-087–RM-098 | 12 | Error-Correcting |
| VIII | RM-099–RM-112 | 14 | Crash-Proof: Fault Injection & Chaos |
| IX | RM-113–RM-126 | 14 | Scalability |
| X | RM-127–RM-138 | 12 | Modularity |
| XI | RM-139–RM-150 | 12 | Multi-Threading & Async |
| XII | RM-151–RM-164 | 14 | Intelligent Functions |
| XIII | RM-165–RM-178 | 14 | Advanced Intelligence |
| XIV | RM-179–RM-190 | 12 | Adaptability |
| XV | RM-191–RM-198 | 8 | Interop |
| XVI | RM-199–RM-206 | 8 | Observability |
| XVII | RM-207–RM-212 | 6 | Proof Spine |

Check: 10+14+14+18+16+14+12+14+14+12+12+14+14+12+8+8+6 = 212.

## Status

- Banked: RM-001, RM-002, RM-003, RM-004, RM-005, RM-006, RM-007,
  RM-008, RM-009, RM-010. **Part I (Foundations & Gates) is
  complete** — all ten slices banked and pushed.
- Banked (Part II): RM-011, RM-012, RM-013, RM-014, RM-015,
  RM-016, RM-017, RM-018, RM-019, RM-020, RM-021, RM-022,
  RM-023, RM-024. **Part II (Stability) is complete** — all
  fourteen slices banked and pushed; evidence bundle in
  `docs/PART_II_EVIDENCE.md`.
- RM-015 (24-hour soak) BANKED 2026-11-01: record span
  2026-10-31T10:47:56Z → 2026-11-01T10:54:18Z (24 h 06 m),
  39 segments, 174,523 cycles, 70 errors (all
  `muninn.decay:OperationalError`, environment-paired,
  disclosed in docs/SOAK.md). Full growth curves in
  docs/SOAK.md; durable record copy in the goal hidden
  files (`rm015_soak_samples.jsonl`). The soak's 120-check
  watch log was condensed at banking — each check was
  recorded in this file as it happened and the outcomes
  stand in the slice log entry below.
- Banked (Part III): RM-025, RM-026, RM-027, RM-028, RM-029,
  RM-030, RM-031, RM-032, RM-033, RM-034, RM-035, RM-036,
  RM-037. Part III (Robustness) is under way — 13 of 14
  slices banked.
- Next: RM-038 in roadmap order (Part III — Part gate).
- **RM-037 BANKED 2026-11-01 (keeper tick ~18:46–20:35 EST):**
  concurrent openers defined as SUPPORTED and made true —
  a per-store coordination lock in both packages' `_db.py`
  (`store_coordination_lock`: process-wide RLock per path +
  `flock` on the sibling `<db_path>.open-lock` file)
  serializes the open-time duties (creation, probe, restore,
  backup-on-open, heal) and every rolling backup, while
  ordinary reads/writes stay serialized by SQLite itself
  (RM-031). The RM-033/RM-030 pre-flights still run first,
  unlocked. Negation against the RM-036 packages: muninn
  **3 failed / 5 passed**, huginn **1 failed / 7 passed**
  (the races: fresh-store creation read as corruption,
  concurrent `backup()` colliding on `.bak-tmp` and
  returning `None`, restore-over-restore in both). Full
  suites green in a fresh venv (`ravens-rm037-venv`,
  non-editable installs, TMPDIR on the workspace disk) on
  the final banking tree: muninn **239 passed** (231+8),
  huginn **169 passed** (161+8); ruff + mypy floors clean
  (rm014 venv; mypy muninn 5 files, huginn 8 files);
  **Bifröst re-verification PASS** (fresh venv
  `ravens-rm037-bifrost-venv`, bifrost at b66e98cc — its
  own suites **25 passed**; BifrostBridge smoke PASS,
  evidence `~/workspace/.verify-tmp/rm037/bifrost_smoke.log`).
  One amendment inside the slice: the RM-033 text-file
  refusal tests now expect the zero-byte `.open-lock`
  neighbour (first final muninn run: 238 passed / 1 failed
  on the old assertion, then amended and re-run green).
  Environment, honestly: this tick opened with the VM's
  Python write gate closed and the home quota then filled
  completely (EDQUOT on every write under `~`, device still
  showing 40G free — the aggregate of the concurrent
  campaigns); writes reopened after this keeper deleted 34
  of this campaign's own disposable per-slice venvs
  (~1.4G; the rm014 tool venv, the rm036 pair, and every
  rm0xx evidence dir were kept). All counts above are from
  this slice's own disk logs under
  `~/workspace/.verify-tmp/rm037/`.
- **RM-035 BANKED 2026-11-01 (keeper ticks ~17:04–18:20 EST):**
  the slice stood built but unbanked when the first tick
  opened (bulk `activate_batch` road in `muninn/core.py`,
  7 tests, bench script, `docs/HUGE_BATCH_ATOMICITY.md`,
  guide/API updates — all uncommitted). That tick verified:
  installed venv copy byte-identical to the tree; targeted
  suite 7 passed; FULL suites green with TMPDIR on the
  workspace disk (muninn **215 passed** (208+7), huginn
  **154 passed**); ruff + mypy floors clean; **Bifröst
  re-verification PASS** (fresh venv
  `ravens-rm035-bifrost-venv`, bifrost at b66e98cc — its
  own suites **25 passed**; BifrostBridge smoke PASS,
  evidence `~/workspace/.verify-tmp/rm035/bifrost_smoke.log`).
  An earlier full-suite run (21:27 UTC logs) failed en masse
  through /tmp — environment class, superseded by the
  TMPDIR-redirected green runs. The 10k bench (detached
  pid 12693, started 22:15 UTC) completed at 22:42:34 UTC:
  49,995,000 pairs / 99,990,000 directed rows in 1629.6 s,
  peak RSS 47.5 MB, all eight checks passed (record
  `~/workspace/.verify-tmp/rm035/bench10k.json`). The
  following keeper tick (~18:04 EST) found the work stopped
  with the bench done and finished the banking: BENCH10K
  placeholder filled from the record, SLICE_LOG entry
  appended + EXPECTED pins extended to RM-035 in both
  packages, both suites re-run green on the final tree
  (muninn **215 passed**, huginn **154 passed**; logs
  `~/workspace/.verify-tmp/rm035/muninn_final.log`,
  `huginn_final.log`), commit + push (hash in the slice
  log below). The bench's ~12 GB scratch workdir was
  deleted after its record was banked into the doc (a
  first final-suite attempt hit a disk-quota error on the
  log write with the scratch still in place; the record
  JSON is preserved and the scratch held nothing else).
- **RM-036 BANKED 2026-11-01 (keeper tick ~18:06 EST):**
  adversarial tags/metadata — one iterative depth bound
  (100 containers, `_check_structure_depth` in both
  packages' `core.py`) over Muninn's JSON-shaped content,
  metadata and tag elements and Huginn's tag elements, plus
  the RM-027 ceilings applied to the cleaned tags list
  (Muninn `max_metadata_bytes`, Huginn
  `max_content_bytes`). Pre-slice probes: metadata/content
  nested 5,000 deep escaped as raw `RecursionError`, a
  200,000-tag list was accepted unbounded, a 50,000-deep
  Huginn tag element escaped as `RecursionError`. Full
  suites green in a fresh venv (`ravens-rm036-venv`,
  non-editable installs, TMPDIR on the workspace disk):
  muninn **231 passed** (215+16), huginn **161 passed**
  (154+7); ruff + mypy floors clean; **Bifröst
  re-verification PASS** (fresh venv
  `ravens-rm036-bifrost-venv`, bifrost at b66e98cc — its
  own suites **25 passed**; BifrostBridge smoke PASS,
  evidence `~/workspace/.verify-tmp/rm036/bifrost_smoke.log`).
  Negation against the RM-035 packages (disk logs
  `~/workspace/.verify-tmp/rm036/muninn_negation.log`,
  `huginn_negation.log`): muninn 9 failed / 7 passed,
  huginn 3 failed / 4 passed (passes = the behaviours the
  slice preserves). Commit + push in the slice log
  entry below. CORRECTION (same evening): the tallies
  first recorded here (10/6, 5/2) came from a runtime
  delivery that matches neither negation session's disk
  log — the crossed-notification pattern of RM-028/RM-034;
  the disk-log counts above are authoritative and the
  SLICE_LOG entry is corrected with them.
- **RM-020 BANKED 2026-11-01 (keeper tick from ~07:56 EST):**
  the wait-and-run log (`~/workspace/.verify-tmp/
  rm020_verify.log`) shows the write gate OPEN at probe 57
  (2026-11-01T12:56:34Z) and both corpus-gate proofs failing
  exactly as designed (tiny n=20 runs vs the committed
  n=5000 baselines: corpus-mismatch GATE FAIL for both
  packages). Its first full-suite pass was 2 failed /
  115 passed (muninn) and 2 failed / 91 passed (huginn);
  a re-run in this tick proved both failures per package
  were exactly the missing RM-020 entry in
  `docs/SLICE_LOG.md` (EXPECTED pin extended in the build;
  entry appended at banking, as in every prior slice).
  With the entry appended, both full suites were re-run
  green before banking (counts in the slice log entry
  below). No bug was found in package or script code.

## Standing invariants (from ~/workspace/ravens/BUILD_NOTES.md)

- Reads stay pure; the only reinforcing read is the explicitly named
  `touch=True` (Muninn `retrieve`); Huginn has no reinforcing read.
- Lazy, separate construction: import constructs nothing, opens no file;
  each memory object opens only its own store.
- Shared cross-store schema law is contractual: Muninn
  `activation_log` / `hebbian_connections`, integer memory ids.
- Any slice changing a public API or the shared schema must re-run the
  Bifröst contract verification before banking (fresh venv;
  hrabanazviking/bifrost at b66e98cc; its own suites + BifrostBridge
  store/search/recall/decay/consolidate smoke) and record the result here.

## Honesty ledger

- Live Qdrant round-trip: NOT PROVEN (no live server run yet).
- Sentence-transformers path: NOT PROVEN (extra not run live yet).
- All counts in this file come from test runners / the tree only.

## Slice log

- **RM-001 — Repo-shipped baseline. BANKED 2026-10-31. Class: UNIT.**
  Fresh venv (`~/workspace/.verify-tmp/ravens-rm001b-venv`, Python 3.12.3,
  SQLite 3.45.1); `pip install ./muninn ./huginn` from this repo (non-editable;
  imports verified resolving to the venv's site-packages, not `src/`).
  Suites run from a neutral cwd against the installed packages:
  muninn **36 passed**, huginn **27 passed** — twice consecutively on the
  fresh venv (evidence: `~/workspace/.verify-tmp/rm001-evidence/suites.log`
  + `install.log`). Meets the roadmap acceptance (36/36, 27/27) exactly.
  Honest note: the very first combined run on the first venv failed broadly
  (18 failed/17 errors muninn, 19 failed huginn) under heavy machine load
  (load avg ~9.5, several other campaigns' suites running concurrently);
  every re-run — per-file, full suites on venv A, and both runs on fresh
  venv B — passed. Root cause not proven; recorded here so RM-014 (flake
  quarantine) inherits the observation. No code changed in this slice;
  the founding tree (`~/workspace/ravens`) needs no sync.
- **RM-002 — Manual-only CI. BANKED 2026-10-31. Class: UNIT (inspection).**
  `.github/workflows/ci.yml` added: installs `./muninn ./huginn` from the
  repo and runs both suites. Trigger block verified by parsed-YAML
  inspection: `on` is exactly `{workflow_dispatch: null}` — no push,
  pull_request, schedule, or any other automatic trigger (the words appear
  only in an explanatory comment). Local full suites re-run green after
  the change: muninn 36 passed, huginn 27 passed. The workflow itself has
  never been dispatched, so a GitHub-hosted run is NOT PROVEN — only the
  file and its triggers are proven. No package code changed; founding
  tree needs no sync.
- **RM-003 — Contract freeze tests. BANKED 2026-10-31. Class: UNIT.**
  Added `tests/test_contract_freeze.py` to both packages: golden
  (name, kind, default) signatures for every BUILD_NOTES §1 contract
  method, golden result-key sets (muninn stats/health/association/
  decay/consolidate; huginn search/health), and the MuninnConfig
  dataclass + keyword-`db_path` pin. Acceptance proven: a deliberate
  signature drift (scratch copy of the installed muninn with
  `activate`'s `emotional_valence` default changed 0.0→0.5) fails
  `test_golden_signatures` while the other freeze tests pass; the
  scratch copy was discarded, no repo code drifted. Full suites green:
  muninn **39 passed** (36+3), huginn **29 passed** (27+2). Side note
  (pre-existing, not introduced here): both packages share test-file
  basenames, so the suites must be run per package — a combined
  single-pytest invocation hits pytest's import-file-mismatch on the
  founding `test_contract.py` pair identically. No public API or
  schema change, so no Bifröst re-verification was required; founding
  tree needs no sync (test-only addition; a tests sync to the founding
  tree is optional and has not been done).
- **RM-004 — Schema snapshot tests. BANKED 2026-10-31. Class: UNIT.**
  Added `tests/test_schema_snapshot.py` + `tests/golden_schema.txt` to
  both packages: golden `sqlite_master` dumps (internal `sqlite_%`
  excluded, SQL whitespace-normalized) — muninn **six tables + 2
  indexes**, huginn local **five tables + 1 index**, matching the
  roadmap's counts. Acceptance proven: baseline dump equals the golden
  exactly, and a raw-SQL `CREATE TABLE drift_probe` on a scratch store
  makes the dump mismatch the golden (the test raises with a unified
  diff). Full suites green: muninn **41 passed** (39+2), huginn
  **31 passed** (29+2). No schema or API change — snapshots pin what
  exists — so no Bifröst re-verification required; founding tree needs
  no sync (test-only addition).
- **RM-005 — Benchmark harness as a gate. BANKED 2026-10-31. Class: BENCH.**
  Both `scripts/benchmark.py` promoted to repeatable gates: JSON
  record per run, committed baselines (`scripts/baseline.json` in
  both packages), default gate = exit 1 when any headline operation
  regresses >25% vs baseline (missing headline op on either side
  also fails); `--update-baseline` / `--no-check` / `--threshold`
  supported. Every record carries an environment block (machine,
  OS/platform, CPU count, load average, Python + SQLite versions,
  UTC timestamp) — numbers labelled with machine + load as the
  roadmap requires (this also lands the recording half of RM-006;
  RM-006 still owns its own output-level acceptance tests).
  Baselines recorded on this VM (4 CPUs, Python 3.12.3, SQLite
  3.45.1, loaded): muninn at load_avg [3.24, 6.35, 7.16] —
  remember 423.1 ms, activate 1454.7, activate_batch 977.0,
  get_associations 216.5, spread_activation 287.0, decay 16.4,
  consolidate 69.3, stats×1000 1936.9; huginn (local) at
  [4.36, 6.49, 7.20] — upsert×5000 4594.1 ms, search median
  13.47 ms, search_filtered 1.62 ms. Gate behaviour proven three
  ways: deterministic unit tests of `compare_to_baseline` in both
  packages (identical/+24% pass, +26% fails, threshold override,
  missing-op fails); a real check run minutes after baselining
  FAILED as load rose to 6.60 (decay +365%, stats +106%,
  spread_activation +75%, activate +45% — recorded honestly in
  docs/BENCHMARKS.md: under load a FAIL is a signal to re-run
  quieter, not proof of regression); a controlled pass run
  against a ×10-inflated copy of the baseline in
  ~/workspace/.verify-tmp/rm005/ exited 0 for both packages.
  Docs: new `docs/BENCHMARKS.md`. Full suites green: muninn
  **49 passed** (41+8), huginn **39 passed** (31+8). No public
  API or schema change, so no Bifröst re-verification required;
  founding tree needs a sync (benchmark scripts changed there
  are now behind this repo's gate versions — scripts-only, no
  package code change).
- **RM-006 — Loaded-machine honesty in benchmarks. BANKED 2026-10-31. Class: UNIT (output) / BENCH (harness).**
  The environment block landed with RM-005's harness; this slice
  makes the printed benchmark output carry the FULL block field by
  field (recorded_at, machine, system, platform, node, cpu_count,
  load_avg, python_version, sqlite_version — previously a one-line
  summary) and proves the acceptance end-to-end: new
  `tests/test_benchmark_environment.py` in both packages runs the
  real script as a subprocess at a tiny workload and asserts the
  block is present in both printed and JSON output, that the
  versions equal the running interpreter's real Python/SQLite
  versions (a canned block cannot pass), and that load_avg is a
  3-number list where provided. Full suites green: muninn
  **51 passed** (49+2), huginn **41 passed** (39+2). No public
  API or schema change, so no Bifröst re-verification required;
  founding tree sync note from RM-005 stands (scripts only).
- **RM-007 — Test-matrix slice. BANKED 2026-10-31. Class: UNIT.**
  Manual CI matrix widened from `["3.12"]` to
  `["3.11", "3.12", "3.13"]` (`fail-fast: false` already set, so
  failures stay named per version; trigger stays
  `workflow_dispatch` only). New `tests/test_ci_matrix.py` in both
  packages pins the matrix list, the fail-fast setting, and the
  manual-only trigger; it skips when run outside a repo checkout
  (the RM-001 neutral-cwd installed-package method). Acceptance
  proven two ways: (1) local matrix run, fresh venv per version,
  packages installed from this repo, suites run per package as CI
  runs them — Python 3.11.17: muninn **54 passed**, huginn
  **44 passed**; Python 3.12.3: muninn **54 passed**, huginn
  **44 passed**; Python 3.13.17: muninn **54 passed**, huginn
  **44 passed** (evidence:
  `~/workspace/.verify-tmp/rm007/matrix.log`). (2) A scratch copy
  with the matrix shrunk back to `["3.12"]` fails
  `test_ci_matrix_covers_all_supported_pythons` (1 failed,
  2 passed) — the pin catches drift. A GitHub-hosted matrix run
  is NOT PROVEN (the workflow has never been dispatched); the
  local per-version runs are the evidence. No package code, API,
  or schema change, so no Bifröst re-verification required;
  founding tree needs no sync (CI + tests only).
- **RM-008 — Lint/type floor. BANKED 2026-10-31. Class: UNIT.**
  Both packages now carry the floor in their own pyproject.toml:
  ruff (families E, W, F, I, UP, B, SIM, C4; line-length 100;
  target py311; scope src+tests+scripts) and mypy ratchet level 1
  (python 3.11; disallow_untyped_defs, disallow_incomplete_defs,
  check_untyped_defs, warn_return_any, no_implicit_optional,
  warn_unused_configs). Tools are dev-extra only, bounded
  `ruff>=0.6,<1`, `mypy>=1.11,<2` — no runtime dependency added.
  First run under the floor: **196 ruff findings + 9 mypy
  findings, all fixed in code, none suppressed** — annotation
  modernisation (typing.Dict/List/Optional → builtins/`|`,
  timezone.utc → datetime.UTC), import sorting, unused imports
  out; four `Any`-returning validators now return `int(value)`;
  three `int(cur.lastrowid)` sites now raise the package storage
  error loudly when an insert reports success without a row id;
  four try/except-pass close paths are `contextlib.suppress`;
  `zip()` gained explicit `strict=` (True in the qdrant fake;
  deliberate commented False in `dense_cosine`, whose stored
  vectors must never crash a pure read). Also removed **10
  pre-existing `noqa`** (7× E731 lambdas in the qdrant fake →
  `@staticmethod` factories; 3× E402 benchmark-script imports →
  moved into the single using function): grep now finds no
  `noqa` and no `# type: ignore` in either tree. The one mypy
  configuration exception is scoped and pinned: huginn overrides
  `ignore_missing_imports` for exactly `qdrant_client` +
  `sentence_transformers` (optional extras, lazily imported, not
  in the type env). Floor pinned by new `tests/
  test_lint_type_floor.py` in both packages (acceptance proven: a
  scratch copy with line-length lowered 100→88 and
  warn_return_any flipped off fails both pins, 2 failed / 1
  passed / 1 skipped); manual CI gained install + ruff + mypy
  steps (still workflow_dispatch only). Clean run recorded in
  docs/LINT_AND_TYPES.md (new): ruff 0.15.22 **All checks
  passed!**; mypy 1.20.2 **Success: no issues found** — muninn
  5 files, huginn 8 files. Full suites green (installed packages,
  venv, TMPDIR redirected — /tmp was 100% full this tick, which
  had caused two spurious muninn robustness failures in a first
  system-python run; both pass cleanly with TMPDIR on the
  workspace disk): muninn **58 passed** (54+4), huginn
  **49 passed** (44+5). No public API or schema change (RM-003
  freeze + RM-004 snapshot tests green), so no Bifröst
  re-verification required. A GitHub-hosted run of the new CI
  steps is NOT PROVEN (never dispatched). Founding tree
  (`~/workspace/ravens`) NEEDS A SYNC: package sources there are
  now behind this repo (annotation modernisation, the loud
  lastrowid guards, suppress rewrites — behaviour identical
  except the guard's loud error in a previously-TypeError path)
  plus both pyprojects (dev extras + floor config). Ratchet road
  named in docs/LINT_AND_TYPES.md: next mypy raise is
  warn_redundant_casts + strict_equality (a further set of
  findings measured on muninn this tick), then
  disallow_untyped_calls; ruff BLE/S/PLR families evaluated
  case-by-case later.
- **RM-009 — Coverage floor. BANKED 2026-10-31. Class: UNIT.**
  Line coverage measured with coverage.py 7.17.0 (suites importing
  from `src/`, per package): muninn **88.80%** (661 statements,
  74 missed), huginn **88.79%** (883 statements, 99 missed) —
  the v1.0.0 logic as it stands post-RM-008. Floors set at the
  measured level rounded down: `[tool.coverage.report]
  fail_under = 88` in both pyprojects, with
  `[tool.coverage.run] source_pkgs` naming each package.
  `coverage>=7,<8` added to both dev extras (dev-only, bounded).
  Enforcement proven both ways: the real reports exit 0
  (88.80 / 88.79 ≥ 88), and a scratch copy at `fail_under = 99`
  fails with "Coverage failure: total of 88.80 is less than
  fail-under=99.00"; the pin itself is proven by a scratch copy
  at 80 failing `test_coverage_floor_is_pinned`. New
  `tests/test_coverage_floor.py` in both packages (3 pins each);
  manual CI gained muninn + huginn coverage steps (still
  workflow_dispatch only). Committed report: docs/COVERAGE.md
  (verbatim tables + Missing columns + a read of what the missed
  lines are: config validation branches, _db healing paths, the
  NOT-PROVEN sentence-transformers body and live-Qdrant paths,
  and the RM-008 lastrowid guards — unreachable by construction,
  counted as missed, absorbed by the floor). Suites under
  coverage: muninn **61 passed** (58+3), huginn **52 passed**
  (49+3); ruff floor still clean. No package code, API, or
  schema change, so no Bifröst re-verification required;
  founding tree needs no NEW sync beyond RM-008's note
  (pyprojects there would need the coverage config too when the
  RM-008 sync happens). A GitHub-hosted run of the coverage
  steps is NOT PROVEN (never dispatched).
- **RM-010 — Slice-log discipline. BANKED 2026-10-31. Class: UNIT.**
  `docs/SLICE_LOG.md` created with the entry convention (Slice /
  Class / Commit / Evidence, appended in the banking commit,
  never edited after the fact). RM-001–RM-009 backfilled from
  real records only — counts and classes from the slice log
  above, commit hashes cross-checked against `git log`
  (abad7b5, 63d96ed, 112e0ee, 0e50b5b, 9c58d04, f98585f,
  de2dfa1, 0bc193d, 506b2df). New `tests/test_slice_log.py` in
  both packages pins that every banked slice RM-001–RM-010 has
  an entry carrying Class + Commit fields; later slices extend
  EXPECTED in the same commit they bank. Full suites green:
  muninn **63 passed** (61+2), huginn **54 passed** (52+2).
  No package code, API, or schema change, so no Bifröst
  re-verification required; founding tree needs no sync for
  this slice (docs + tests only). **Part I complete with this
  slice.**
- **RM-011 — Determinism audit. BANKED 2026-10-31. Class: UNIT.**
  Full audit in `docs/DETERMINISM.md`. PINNED in code: every
  ordered read whose sort key can tie now carries an explicit
  final tie-break (muninn `get_associations` +`memory_b_id ASC`;
  `spread_activation` key `(-activation, id)`; `retrieve`
  `(importance, updated_at, id)`; `get_by_path`/`get_children`/
  `dump` +`id ASC`; huginn TF-IDF + vector search key
  `(-score, doc_id)`; module `semantic_search` `(-score,
  index)`); muninn backpressure victim choice +`id ASC` (a tie
  could previously prune a different node per run); both heal
  passes' write order (muninn wiring read `ORDER BY a, b`;
  huginn corpus repair iterates `sorted(terms)` instead of a
  hash-seed-ordered set union). PROVEN already deterministic:
  content hashes (SHA-256 over sort_keys JSON / raw text — no
  float ever formatted into a hash input outside json's fixed
  repr), the hashing embedder, float sums (dict insertion order
  only, never sets). DOCUMENTED, not pinned: Qdrant server
  result order (live Qdrant still NOT PROVEN), wall-clock
  timestamp values, physical SQLite file bytes (acceptance is
  at the logical-dump level). Acceptance proven by new
  `tests/test_determinism.py` in both packages: one fixed
  workload on two fresh stores produces byte-identical logical
  dumps (every non-timestamp column of every table; excluded
  timestamp columns listed in the audit + the tests), in-process
  AND in child processes under PYTHONHASHSEED 0 and 42. Full
  suites green: muninn **66 passed** (63+3), huginn **57
  passed** (54+3); ruff + mypy floors still clean. No public
  API signature or schema change (RM-003 freeze + RM-004
  snapshot green; the contractual strength-DESC association
  order is preserved — only ties gained a rule), so no Bifröst
  re-verification required. Founding tree (`~/workspace/ravens`)
  NEEDS A SYNC: the tie-break pins are package-source changes
  there (extends the RM-008 sync note).
- **RM-012 — Timestamp discipline. BANKED 2026-10-31. Class: UNIT.**
  Record: `docs/TIMESTAMPS.md`. Both packages already drew every
  stored timestamp from one helper (muninn `core._now`, huginn
  local `local_backend._now`; the Qdrant backend stores no
  timestamps; the remaining `datetime.now` calls are in-memory
  only — MemoryNode defaults, RetrievalResult.timestamp) — this
  slice pins that fact in docs and adds the missing half: a
  monotonicity guard. New `_tick()` in both stores issues
  `_now()` when the clock is healthy and last-issued + 1µs
  when it stalls or runs backwards; on open the guard is
  seeded from the store's own stored maximum (muninn: max
  across activation_log / nodes / wiring / node_activation /
  tombstones; huginn: documents.updated_at), so a reopen after
  a clock rollback still issues strictly after stored history.
  All muninn stored-timestamp call sites (activate,
  activate_batch, associate, remember, retrieve-touch, update,
  forget, backpressure) and huginn's upsert now go through
  `_tick()`. Acceptance proven by new `tests/test_timestamps.py`
  in both packages: a format scan over every stored timestamp
  column (UTC, ISO-8601, `+00:00`), and clock-skew tests
  patching the helper with a backwards-running clock — muninn's
  activation log stays strictly increasing in row order,
  including across a reopen; huginn's `updated_at` never
  precedes `created_at`; a healthy clock's readings pass
  through untouched (one test expectation was corrected during
  the build: with a frozen clock the second issue is correctly
  +1µs, so the first log row sits past the frozen reading —
  the guard was right, the test was wrong). Full suites green:
  muninn **70 passed** (66+4), huginn **60 passed** (57+3);
  ruff + mypy floors still clean (one E501 + one B905 from the
  build fixed in-slice). No public API signature or schema
  change (RM-003 freeze + RM-004 snapshot green), so no
  Bifröst re-verification required. Founding tree NEEDS A
  SYNC for the `_tick` guard (package sources; extends the
  RM-008/RM-011 sync note).
- **RM-013 — Idempotency matrix. BANKED 2026-10-31. Class: UNIT.**
  Matrix in `docs/API_REFERENCE.md` Part 3 (new): every public
  API row of both packages classified **I** (idempotent) /
  **R** (safely re-runnable) / **N** (intentionally not), with
  the repeat behaviour + blind-retry guidance stated per row.
  Muninn: 28 rows M-01–M-28 (`HebbianMemory`; the `Muninn`
  facade inherits every row — proven by an extra facade test).
  Huginn: 15 rows H-01–H-15, proven on the local backend; the
  Qdrant backend mirrors the upsert identity and pure reads by
  construction, but a live Qdrant round-trip is still NOT
  PROVEN, so no Qdrant row is claimed proven. Proven by new
  `tests/test_idempotency.py` in both packages — exactly one
  test per row: muninn **29 tests**, huginn **15 tests**.
  N rows proven to double-apply: muninn `activate`,
  `activate_batch`, `associate` (explicit-strength form pins
  the strength value but `co_activation_count` still advances;
  the delta form's strength climbs), `retrieve(touch=True)`;
  huginn `fly` / `multi_hop_retrieve` (results repeat, the
  store never moves, but each flight appends one in-memory
  history record). R rows: construction/reopen in both
  packages, muninn `backup()` (rolling generations rotate,
  store unchanged), muninn `decay` — proven cumulative in the
  defined way: `decay(1)` twice composes to `decay(2)` to
  float precision (`pytest.approx`, rel 1e-12). Every
  pure-read row's test also asserts the store's stats did not
  move between repeats. Semantics pinned, not changed: a
  Muninn `remember` retry carrying different fields returns
  the same id and the FIRST write wins, while a Huginn
  `upsert_memory` retry replaces in place under the same id;
  removal rows (`forget`/`delete`) return True→False with
  state unmoved; `update`/`move` are I apart from the
  `updated_at` stamp (RM-012 `_tick`). One mid-build
  correction, test-side only: an early draft of the muninn
  row file briefly carried a `noqa` — removed in-slice before
  banking (the RM-008 floor forbids them); a separate
  long-line E501 was fixed by naming a helper. Full suites
  green in a fresh venv (`ravens-rm013-venv`, packages
  installed non-editable, imports resolving to site-packages,
  suites run from the checkout, TMPDIR redirected to the
  workspace disk): muninn **99 passed** (70+29), huginn
  **75 passed** (60+15); ruff + mypy floors still clean in
  both packages. No package code, public API, or schema
  change (RM-003 freeze + RM-004 snapshot green), so no
  Bifröst re-verification required. Founding tree needs no
  NEW sync for this slice (tests + docs only); the
  RM-008/RM-011/RM-012 package-source sync note stands.
- **RM-014 — Flake quarantine. BANKED 2026-10-31. Class: UNIT.**
  Acceptance met: **50 consecutive green runs recorded.**
  Harness `scripts/flake_quarantine.py` (committed with this
  slice) ran both suites back to back as pairs under 2
  busy-loop load workers, one JSON record line per pair, never
  retrying — a non-green pair stops the sweep with full output
  saved, and none ever occurred. Final record
  (`~/workspace/.verify-tmp/rm014/runs-resumed.jsonl`; durable
  copy in the goal hidden files as `rm014_flake_record.jsonl`):
  runs 1–50, every pair green, muninn **99 passed** / huginn
  **75 passed**, 0 failed / 0 errors throughout. The road to
  the record was interrupted repeatedly by the machine, never
  by a flake: first attempt 15/50 then a VM reboot (~07:18
  UTC); the resumed record was carried across five further
  external teardowns of the background sweep process (silent
  deaths at 15, 22→, 30 pairs and one runtime-reported SIGTERM
  during pair 23; causes not proven — OOM under concurrent
  campaigns plausible but NOT PROVEN) via the harness's
  `--start-run` resume, which keeps pair numbers so the file
  reads as one consecutive run; the final resume (pairs
  31–50, keeper-run 2026-10-31 ~10:17–10:32 UTC) completed in
  one stretch. Every interruption was recorded in this file
  as it happened, not hidden. No package code, public API, or
  schema change (RM-003 freeze + RM-004 snapshot green), so
  no Bifröst re-verification required. Founding tree needs no
  sync for this slice (harness + docs + slice-log test pin
  only); the RM-008/RM-011/RM-012 package-source sync note
  stands. Post-sweep, the harness was tidied to the lint
  floor (executable bit, explicit `check=False`,
  `datetime.UTC`) — behaviour unchanged, record unaffected;
  ruff + mypy floors re-verified clean at banking (mypy:
  muninn 5 files, huginn 8 files, no issues).
- **RM-015 — Long-run soak. BANKED 2026-11-01. Class: BENCH.**
  Acceptance met: **24-hour mixed-workload soak completed,
  growth curves published in `docs/SOAK.md`.** Harness
  `scripts/soak.py` (committed with this slice) cycled muninn
  remember / activate_batch / retrieve with decay +
  consolidate maintenance and huginn upsert / search over a
  fixed 500-text corpus (local backend, no network), sampling
  every 60 s. Final record read from the file itself: span
  **2026-10-31T10:47:56Z → 2026-11-01T10:54:18Z (24 h 06 m)**,
  1,043 samples, **39 segments**, **174,523 cycles** summed
  (last-cycle-per-segment), **70 errors** summed — all
  `muninn.decay:OperationalError`, in five earlier segments
  (7+41+3+9+10), each cluster paired in the soak log with
  `muninn: backup failed: disk I/O error` during the VM's
  extreme-load / write-gate episodes (environment class,
  cause not proven, never reproduced on a quiet machine);
  every other operation error-free across the whole span and
  the final segment clean (1,862 cycles, 0 errors). Growth
  verdict (full hourly table in docs/SOAK.md): RSS bounded —
  all-time max 39.33 MB in hour 0, final 22.18 MB; huginn
  store flat at 4.84–4.96 MB throughout; muninn store linear
  in work done at a constant rate (428 KiB/1,000 cycles in
  hours 0–4 including the initial corpus fill, then
  254/244/246/249/239 KiB per 1,000 cycles across hours
  4–24) — proportional to operations, not an accelerating
  leak; a plateau under a remember-heavy workload would need
  a retention policy, a design question for a later slice.
  Interruption history, honestly: the process was torn down
  externally 38 times (two proven VM reboots; the rest the
  RM-014 silent-teardown pattern, causes not proven) and the
  keeper resumed it each time against the same --workdir and
  --out; every segment_start shows both stores reopening
  with their existing data (38 clean heal/reopen cycles).
  One resume was held one tick while a sustained probe
  proved the write gate closed (0/60 writes landing), then
  resumed on the next tick's fully green probe (60/60). The
  keeper stopped the process after the sample at
  10:54:18 UTC crossed the 24 h span. Durable record copy:
  `rm015_soak_samples.jsonl` in the goal's hidden files
  (493,406 B, 1,043 lines). No package code, public API, or
  schema change (RM-003 freeze + RM-004 snapshot green), so
  no Bifröst re-verification required. Founding tree needs
  no sync for this slice (harness + docs + slice-log test
  pin only); the RM-008/RM-011/RM-012 package-source sync
  note stands. Full suites green at banking in the RM-013
  venv (packages as installed there; no package code has
  changed since): muninn **99 passed**, huginn **75 passed**;
  ruff + mypy floors clean (rm014 venv, per-package config:
  mypy muninn 5 files, huginn 8 files, no issues; the one
  BLE001 a root-level ruff run reports on soak.py's counted
  catch-all is outside the packages' floor select — the
  catch is the harness's error-counting design, stated in
  its comment).
- **RM-016 — Version-pinning of the sqlite runtime. BANKED
  2026-11-01. Class: UNIT.** Record: `docs/SQLITE_RUNTIME.md`.
  `health()` in both packages now carries `sqlite_version`
  (`sqlite3.sqlite_version`, read from the runtime): muninn
  `HebbianMemory.health()`; huginn local backend `health()`,
  passed through by the facade. Minimum WAL-safe version
  documented: **3.7.0** (WAL's introduction release; both
  stores open in WAL mode). Runtime at banking: 3.45.1
  (Python 3.12.3, this VM), unchanged since RM-001. Absent
  honestly where there is no SQLite: the Qdrant backend's
  health and the facade's failing-backend early return.
  Acceptance proven by new `tests/test_sqlite_version.py`
  in both packages (3 each): value equals the runtime's,
  parses ≥ (3,7,0), read is pure. RM-003 health goldens
  updated deliberately in the banking commit. Public API
  result changed (additive key), so the **Bifröst contract
  re-verification was run before banking**: fresh venv
  (`ravens-rm016-bifrost-venv`), bifrost at b66e98cc — its
  own suites **25 passed**; BifrostBridge smoke PASS
  (store mimir_id+huginn_id; search 2 merged results;
  recall grew the Muninn activation log exactly +1;
  decay/consolidate reports; stats over all three backends;
  double close safe) with both raven health dicts carrying
  `sqlite_version` 3.45.1 through the bridge (huginn
  degraded via auto-fallback to local — qdrant-client not
  installed in the venv, the founding condition; live
  Qdrant still NOT PROVEN). One smoke-script correction
  during the run (mine, not a package defect): recall takes
  the bridge's mimir id — there is no `muninn_id` key in
  the store result. Full suites green in a fresh venv
  (non-editable installs): muninn **102 passed** (99+3),
  huginn **78 passed** (75+3); ruff + mypy floors clean
  (mypy muninn 5 files, huginn 8 files). Founding tree
  NEEDS A SYNC for the health() additions (extends the
  RM-008/RM-011/RM-012 sync note).
- **RM-017 — Config immutability. BANKED 2026-11-01. Class: UNIT.**
  `MuninnConfig` and `HuginnConfig` are now
  `@dataclass(frozen=True)`: validated once at construction,
  then immutable — assigning to any field raises
  `dataclasses.FrozenInstanceError`, so a caller cannot change
  a live store's behaviour mid-flight or smuggle in an
  unvalidated combination (validators run only at
  construction). Record: `docs/CONFIG_IMMUTABILITY.md`. The
  road to a variant is `dataclasses.replace` (full
  re-validation); the constructors' `**overrides` already took
  that road and are now pinned to leave the caller's config
  untouched. Proven by new `tests/test_config_immutability.py`
  in both packages (5 tests each): representative-field
  assignment attempts raise; a mutation attempt against a live
  store leaves behaviour at the validated values (Muninn first
  wiring still starts at exactly lr 0.1 after an attempted 1.0;
  a live Huginn local backend cannot be flipped to `qdrant`);
  `replace` re-validates (typed configuration errors on
  out-of-range replacements); overrides never mutate the
  caller's config. Acceptance proven by negation: the same
  files against a scratch copy with the freeze removed fail
  exactly the two mutation tests per package (2 failed / 3
  passed each). Construction shapes, fields and defaults are
  unchanged (RM-003 freeze green), but freezing changes
  public-surface behaviour, so the **Bifröst contract
  re-verification was run before banking**: fresh venv
  (`ravens-rm017-bifrost-venv`), bifrost at b66e98cc — its own
  suites **25 passed**; BifrostBridge smoke PASS (store
  mimir_id+huginn_id; search 2 merged results; recall grew the
  Muninn activation log exactly +1; decay/consolidate reports;
  stats over all three backends; both raven health dicts carry
  `sqlite_version` 3.45.1 through the bridge; double close
  safe; huginn degraded via auto-fallback to local —
  qdrant-client not installed, the founding condition; live
  Qdrant still NOT PROVEN). Full suites green in a fresh venv
  (non-editable installs), re-run on the final banking tree
  after a service restart interrupted the first attempt:
  muninn **107 passed** (102+5), huginn **83 passed** (78+5);
  ruff + mypy floors clean (mypy muninn 5 files, huginn 8
  files; one B010 on the new tests fixed in-slice). Founding
  tree NEEDS A SYNC for the frozen configs (extends the
  RM-008/RM-011/RM-012/RM-016 sync note).
- **RM-018 — Stable error messages. BANKED 2026-11-01. Class: UNIT.**
  Record: `docs/ERROR_MESSAGES.md`. Error strings are now
  treated as API and pinned two ways by new
  `tests/test_error_messages.py` +
  `tests/golden_error_messages.txt` in both packages.
  Behavioural pin: every deterministically triggerable typed
  error raised with fixed inputs, exact message compared to
  the golden — muninn **31 cases**, huginn **33 cases**
  (Qdrant translations against a fake client raising
  `RuntimeError("boom")`; live Qdrant still NOT PROVEN).
  Template pin: every `raise <Typed>Error(...)` site
  re-extracted from the source AST (f-string values → `{}`)
  and the multiset compared to the golden — muninn **33
  sites**, huginn **36 sites** (35 distinct; the no-row-id
  guard stands at two insert paths). The template pin alone
  covers the sites no deterministic trigger can reach (per
  package the schema-preparation failure + the RM-008
  no-row-id guards) — named in the doc, not skipped.
  Acceptance proven by negation on a scratch copy (discarded):
  rewording muninn's "strength must be in [0, 1]" and
  huginn's "query_text must be a string" each fail the
  template test; altering one muninn CASE line in the golden
  fails the behavioural test (muninn 2 failed / 1 passed,
  huginn 1 failed / 2 passed on the drifted copies). Full
  suites green in a fresh venv (`ravens-rm018-venv`,
  non-editable installs): muninn **110 passed** (107+3),
  huginn **86 passed** (83+3); ruff + mypy floors clean
  (rm014 venv; mypy muninn 5 files, huginn 8 files). No
  package code, public API, or schema change (RM-003 freeze
  + RM-004 snapshot green), so no Bifröst re-verification
  required. Founding tree needs no sync for this slice
  (tests + docs only); the RM-008/RM-011/RM-012/RM-016/
  RM-017 package-source sync note stands.
- **RM-019 — API surface freeze test. BANKED 2026-11-01. Class: UNIT.**
  Record: `docs/API_SURFACE.md`. The whole public surface of
  both packages is now snapshotted in
  `tests/golden_api_surface.txt` per package, enforced by new
  `tests/test_api_surface.py`: every `__all__` name; every
  exported class with its direct bases (error hierarchy and
  the `Muninn` facade's inheritance from `HebbianMemory`
  pinned); every public method of every exported class —
  inherited methods included, so the facade keeps the whole
  ancestor surface — in the RM-003 (name, kind, default)
  shape; every dataclass field of the exported dataclasses
  (`MuninnConfig`, `MemoryNode`, `HuginnConfig`,
  `RetrievalResult`) with declared type and default;
  properties (`MemoryNode.category`), public class attributes
  (`MAX_QUERY_RESULTS`), huginn's exported module functions
  (`analyze_query`, `semantic_search`), and the presence of
  `__version__`. Builtin-inherited members are excluded as
  not package surface. Muninn golden **101 lines**, huginn
  golden **57 lines**. Semantics per the roadmap: additions
  allowed (a companion test pins that the freeze inventory
  and `__all__` agree exactly, so a new export cannot slip in
  unlisted), removals / renames / signature changes fail
  until a major-version slice updates the golden. Acceptance
  proven by negation on scratch copies of the installed
  packages (discarded): renaming muninn `stats` fails the
  freeze test (1 failed / 2 passed); changing `decay`'s
  default 1.0 → 2.0 fails it (1 failed / 2 passed); dropping
  `semantic_search` from huginn's `__all__` fails it
  (2 failed / 1 passed); adding a new public method to
  `HebbianMemory` passes (3 passed). Full suites green in a
  fresh venv (`ravens-rm019-venv`, non-editable installs):
  muninn **113 passed** (110+3), huginn **89 passed** (86+3);
  ruff + mypy floors clean (mypy muninn 5 files, huginn 8
  files). No package code, public API, or schema change
  (RM-003 freeze + RM-004 snapshot green), so no Bifröst
  re-verification required. Founding tree needs no sync for
  this slice (tests + docs only); the RM-008/RM-011/RM-012/
  RM-016/RM-017 package-source sync note stands.
- **RM-020 — Reproducible benchmark corpus. BANKED
  2026-11-01. Class: BENCH.** Record: `docs/BENCHMARKS.md`
  (Reproducible corpus section). Both benchmark scripts now
  carry `CORPUS_VERSION = 1` and a corpus block — version,
  count, SHA-256 of the stored texts (UTF-8,
  newline-terminated, in order) — in every record's
  `details.corpus` and in the printed output; the gate
  refuses cross-corpus comparisons with a corpus-mismatch
  failure whatever the timings say (a pre-RM-020 baseline
  with no block draws a printed note + timing-only
  comparison). The corpora were already formula-generated
  (muninn `corpus_text(i)`; huginn `doc_text(i)` over its
  fixed word list + fixed search queries) — this slice
  names, versions, and pins that fact. Default-workload
  (5,000) hashes: muninn `ffe8065f…141d1`, huginn
  `3693044b…43f`. Both committed baselines gained their
  corpus blocks without re-timing (generator output
  byte-identical to the RM-005 runs' stored texts).
  Pinned by new `tests/test_benchmark_corpus.py` in both
  packages (4 tests each: determinism, honest hash
  recomputation, committed-baseline block, real script
  recording the same hash in printed + JSON output across
  two runs). Corpus-gate behaviour proven live
  2026-11-01 by the wait-and-run record
  (`~/workspace/.verify-tmp/rm020_verify.log`): tiny runs
  vs the committed baselines fail with exactly the
  corpus-mismatch message for both packages. Verification
  history, honestly: built in the ~07:05–07:50 EST tick
  but unbankable then — the VM's Python write gate was
  closed (the RM-015 pattern) — so the wait-and-run probed
  until the gate opened (probe 57, 12:56:34Z) and ran the
  proofs + suites; its first suite pass (2 failed /
  115 passed muninn, 2 failed / 91 passed huginn) was
  proven in the banking tick to be exactly the missing
  `docs/SLICE_LOG.md` RM-020 entry in both packages.
  With the entry appended, full suites green in the
  RM-019 venv: muninn **117 passed** (113+4), huginn
  **93 passed** (89+4); ruff + mypy floors clean (rm014
  venv; mypy muninn 5 files, huginn 8 files). No package
  source, public API, or schema change (RM-003 freeze +
  RM-004 snapshot green), so no Bifröst re-verification
  required. Founding tree sync note from RM-005 stands
  and extends to the corpus-versioned benchmark scripts
  + baselines (scripts only, no package code).
- **RM-021 — Clock-free decay. BANKED 2026-11-01. Class: UNIT.**
  Record: `docs/WALL_CLOCK_DECAY.md`. Plain `decay(days)`
  unchanged and clock-free (explicit `days` only; RM-003
  signature + report untouched). New opt-in
  `decay_wall_clock()`: derives `days` from the
  `decay_last_run_at` marker in the store's `meta` table
  (ISO-8601 UTC from `muninn.core._now`). First call arms
  the marker and decays 0 days; forward jump decays the
  elapsed days and advances the marker; backward jump
  decays 0 days and the marker never moves backward (a
  later healthy reading cannot re-decay the same span);
  a corrupt or timezone-naive marker is re-armed and
  reported via `marker_reset`, never raised. Report =
  `decay()`'s plus mode / elapsed_days / last_run_at /
  run_at / first_run / marker_reset / marker_advanced.
  Proven by new `tests/test_wall_clock_decay.py` (6 tests
  at the `_now` seam) and classified in the RM-013 matrix
  as row M-29 (R) with its own idempotency test. RM-019
  golden surface gained the two `decay_wall_clock` lines
  in this commit — the only surface change, an addition;
  no signature, config, schema, or error-message change
  and no new typed-error site. Public API changed
  additively, so the **Bifröst contract re-verification
  was run before banking**: fresh venv
  (`ravens-rm021-bifrost-venv`), bifrost at b66e98cc —
  its own suites **25 passed**; BifrostBridge smoke PASS
  (store mimir_id+huginn_id; merged search proven on the
  huginn and mimir source paths; recall grew the Muninn
  activation log exactly +1; decay/consolidate reports;
  `decay_wall_clock()` through the bridge's muninn armed
  at 0 days; stats over all three backends; both raven
  health dicts carry `sqlite_version` 3.45.1; huginn
  degraded via auto-fallback to local — live Qdrant still
  NOT PROVEN; double close safe). Full suites green in a
  fresh venv (`ravens-rm021-venv`, non-editable installs):
  muninn **124 passed** (117+6+1), huginn **93 passed**
  (no huginn code change); ruff + mypy floors clean
  (rm014 venv; mypy muninn 5 files, huginn 8 files).
  Founding tree NEEDS A SYNC for `decay_wall_clock()`
  (extends the RM-008/RM-011/RM-012/RM-016/RM-017 sync
  note). Huginn has no decay of its own — this slice is
  Muninn-only by design.
- **RM-022 — Store-format stability promise. BANKED
  2026-11-01. Class: UNIT.** Record:
  `docs/FORMAT_STABILITY.md` — every file, table and key
  of both stores named with its contract class + the
  migration promise attached, reviewed against the code.
  Highlights: `.bak-N` generations are complete store
  files in the live format (restorable with no
  conversion); Muninn's `activation_log` +
  `hebbian_connections` are shared-schema law (Part X
  slices + migration proof + Bifröst re-verification
  only); the `meta` registry (`schema_version` both
  stores, `decay_last_run_at` Muninn-only) is additive-
  only, never redefined in place, unknown keys ignored;
  integer ids + UTC ISO-8601 timestamps are value-level
  promises; the Qdrant section promises construction
  only (collection `huginn_memories`, COSINE, integer
  point ids) — live Qdrant still NOT PROVEN. Stated
  honestly in the doc: `schema_version` ("1", both
  stores) is recorded on every open but **not yet gated
  on** — no migration registry exists yet; RM-132 builds
  it and RM-082 defines foreign-schema behaviour, and
  the doc defers governing authority to them. Acceptance
  pinned by new `tests/test_format_stability.py` in both
  packages (2 tests each): every golden table + index
  must be named in the doc, so a schema element shipped
  without a promise update fails. Full suites green in
  the RM-021 venv: muninn **126 passed** (124+2), huginn
  **95 passed** (93+2); ruff floor clean. No package
  code, API, or schema change, so no Bifröst
  re-verification required. Founding tree needs no sync
  (docs + tests only); the package-source sync note
  stands.
- **RM-023 — Shutdown cleanliness. BANKED 2026-11-01.
  Class: UNIT.** Record: `docs/SHUTDOWN_CLEANLINESS.md`.
  `close()` in both packages proven clean and pinned by
  new `tests/test_shutdown_cleanliness.py` (3 tests each):
  after writes + close, the `-wal` sidecar is absent or
  zero bytes; a reopen performs zero recovery
  (`recovered_from_backup is False`, health integrity ok,
  data/search intact); a raw `PRAGMA wal_checkpoint
  (TRUNCATE)` on the closed store returns busy 0 with
  0 log pages; double close is a no-op; no lingering
  threads after close (locks only, no workers in either
  package). Full suites green in the RM-021 venv: muninn
  **129 passed** (126+3), huginn **98 passed** (95+3);
  ruff floor clean. No package code, API, or schema
  change, so no Bifröst re-verification required.
  Founding tree needs no sync (tests + docs only); the
  package-source sync note stands.
- **RM-024 — Part gate. BANKED 2026-11-01. Class: UNIT.**
  `docs/PART_II_EVIDENCE.md` files the Part II evidence
  bundle: determinism (RM-011), the 50-pair flake record
  (RM-014), the 24-hour soak (RM-015) and the per-version
  matrix (RM-007); a check-off row per slice
  RM-011–RM-024 with banking counts; the part's three
  Bifröst re-verifications (RM-016/RM-017/RM-021, all
  green); floors standing; the honesty ledger unchanged
  (live Qdrant, sentence-transformers, GitHub-hosted CI
  all NOT PROVEN); debts named (founding-tree sync owed;
  `schema_version` recorded-not-gated until RM-132 /
  RM-082). Pinned by new `tests/test_part_ii_gate.py` in
  both packages (2 tests each). Full suites green in the
  RM-021 venv: muninn **131 passed** (129+2), huginn
  **100 passed** (98+2); ruff floor clean. No package
  code, API, or schema change, so no Bifröst
  re-verification required for the gate itself.
  **Part II (Stability) complete: 14/14 slices banked
  and pushed.** Next: Part III — Robustness, RM-025.
- **RM-025 — Input fuzzing, muninn. BANKED 2026-11-01.
  Class: UNIT.** Record: `docs/INPUT_FUZZING_MUNINN.md`.
  Stdlib-only property-style fuzz (seeds 20261031, 20261101,
  42) over every Muninn validator, pinned by new
  `tests/test_input_fuzz.py` (10 tests): every generated
  input either succeeds or raises a typed `MuninnError`,
  and every rejected write leaves the store's stats
  byte-identical. Negation first: the suite failed **8 of
  10** against the pre-fix code. Ten defects fixed in-slice:
  oversized ids (> 2⁶³−1) overflowing SQLite with untyped
  `OverflowError` (typed ceiling now in `_check_memory_id`);
  a failed `activate_batch` leaving a pending partial write;
  `associate` validating `delta` only after its first
  tombstone write (both numbers now validated before any
  SQL); bare `float()`/`int()` TypeErrors across strength /
  delta / attenuation / min_strength / threshold / limit /
  depth / top_k (single-message typed checkers; bools refused
  as numbers; NaN fails every range); `decay(NaN)` corrupting
  confidences through an untyped IntegrityError (days must
  now be finite); non-iterable / bare-string tags crashing or
  exploding into characters (list/tuple only); `update`'s
  uncaught metadata serializability failure; `MuninnConfig`
  raising untyped on non-convertible fields and accepting
  NaN half-lives (never-raising coercion helpers, messages
  unchanged); `spread_activation` seed-list and min_strength
  tightening. RM-018 golden extended deliberately (38
  templates, 31 cases; moved validators keep their exact
  messages). Validation behaviour tightened (no signature or
  schema change; RM-003/RM-004 pins green), so the **Bifröst
  contract re-verification was run before banking**: fresh
  venv (`ravens-rm025-bifrost-venv`), bifrost at b66e98cc —
  its own suites **25 passed**; BifrostBridge smoke PASS
  (store mimir_id+huginn_id; search 1 merged result;
  recall grew the Muninn activation log exactly +1;
  decay/consolidate reports; `decay_wall_clock()` through
  the bridge armed at 0 days; stats over all three backends;
  both raven health dicts carry `sqlite_version` 3.45.1;
  huginn degraded via auto-fallback to local — live Qdrant
  still NOT PROVEN; double close safe). Full suites green
  in a fresh venv (`ravens-rm025-venv`, non-editable
  installs): muninn **141 passed** (131+10), huginn
  **100 passed**; ruff + mypy floors clean. Founding tree
  NEEDS A SYNC for the validator hardening (extends the
  RM-008/RM-011/RM-012/RM-016/RM-017 sync note).
- **RM-026 — Input fuzzing, huginn. BANKED 2026-11-01.
  Class: UNIT.** Record: `docs/INPUT_FUZZING_HUGINN.md`.
  Stdlib-only property-style fuzz (seeds 20261031, 20261101,
  42) over every Huginn validator — upsert/search/get/delete
  arguments and query text (empty, huge, unicode-edge,
  NUL-bearing) — pinned by new `tests/test_input_fuzz.py`
  (10 tests): every generated input either succeeds or
  raises a typed `HuginnError`, every rejected write leaves
  the document count byte-identical, and `fly` returns an
  error flight instead of raising. Negation recorded in the
  slice doc: the suite failed **8 of 10** against the
  pre-fix code. Nine defects fixed in-slice: oversized ids
  overflowing SQLite untyped (ceiling 2⁶³−1 in
  `_check_memory_id`, the RM-025 fix mirrored); bare `int()`
  errors / silent float truncation in `search(limit=…)`
  (one typed count checker now serves limit / top_k /
  max_results / hop_count / max_results_per_hop); a huge
  `min_importance` overflowing at SQL bind time (same
  ceiling); categories unvalidated on both paths (write-side
  `str()` coercion silently storing `"123"`/`"None"`,
  read-side lists dying as untyped SQLite
  `ProgrammingError`) — one checker now guards both; tags
  crashing on non-iterables and bare strings exploding into
  character tags (list/tuple only); flight paths crashing
  with `AttributeError` on non-string queries (`fly`
  validates inside its error envelope); `analyze_query`
  sharing the crash and silently analysing None;
  `semantic_search` trusting query / documents / top_k
  entirely; `HuginnConfig` numeric fields raising untyped
  on non-convertible values with a NaN `qdrant_timeout`
  passing (never-raising coercion helpers, messages
  unchanged), plus first-time type validation for
  `st_model` and `qdrant_api_key`. RM-018 golden extended
  deliberately (44 templates, 41 cases; moved validators
  keep their exact messages). Build history, honestly: the
  slice was built in an earlier tick (~09:33–09:39 EST) and
  left unbanked; its first verification run
  (`~/workspace/.verify-tmp/rm026_verify.log`) hit the VM's
  environment disk-I/O failures (muninn 55 failed on WAL
  `disk I/O error` under heavy cross-campaign load) and
  huginn's only 2 failures were the then-missing
  `docs/SLICE_LOG.md` RM-026 entry. The banking tick
  (2026-11-01 ~10:28–10:40 EST) appended the entry,
  re-probed the write gate (5/5 WAL probes OK) and re-ran
  everything green in the fresh venv (`ravens-rm026-venv`,
  non-editable installs, byte-identical to the tree):
  muninn **141 passed** (no muninn code change; slice-log
  EXPECTED pin only), huginn **110 passed** (100+10); ruff
  + mypy floors clean. Validation behaviour tightened (no
  signature or schema change), so the **Bifröst contract
  re-verification was run before banking** in the banking
  tick: fresh venv (`ravens-rm026-bifrost-venv`, installed
  huginn verified byte-identical to this repo's source),
  bifrost at b66e98cc — its own suites **25 passed**;
  BifrostBridge smoke PASS (store mimir_id+huginn_id;
  search 1 merged result; recall grew the Muninn
  activation log exactly +1; decay/consolidate reports;
  `decay_wall_clock()` through the bridge armed at 0
  days; stats over all three backends; both raven health
  dicts carry `sqlite_version` 3.45.1; huginn degraded via
  auto-fallback to local — live Qdrant still NOT PROVEN;
  double close safe; evidence
  `~/workspace/.verify-tmp/rm026_bifrost.log`). Founding
  tree NEEDS A SYNC for the validator hardening (extends
  the RM-008/RM-011/RM-012/RM-016/RM-017/RM-025 sync
  note).
- **RM-027 — Oversize content policy. BANKED 2026-11-01.
  Class: UNIT.** Record: `docs/OVERSIZE_POLICY.md`.
  Explicit, configurable ceilings replace unbounded
  acceptance: `MuninnConfig.max_content_bytes` (default
  1048576 = 1 MiB) + `max_metadata_bytes` (default
  65536 = 64 KiB); `HuginnConfig.max_content_bytes`
  (default 1048576; Huginn memories carry no caller
  metadata, so no metadata ceiling there). Sizes are
  UTF-8 bytes of what the store holds — stored content
  text (raw string, or its JSON serialization for
  non-string content) and metadata's serialized JSON —
  so 5 × `é` costs 10 bytes. Above a ceiling the write is
  refused with the typed validation error before any
  write (`content size {} bytes exceeds max_content_bytes
  ({} bytes)` + the metadata twin): Muninn enforces on
  `remember` and on `update` (content and metadata);
  Huginn enforces in the facade before any backend is
  touched, so the policy holds on local and Qdrant alike.
  Ceilings validate at config construction (`>= 1`, typed
  configuration error; `dataclasses.replace` re-validates).
  Pinned by new `tests/test_oversize_policy.py` in both
  packages (muninn 8 tests, huginn 5): boundaries below /
  at / above each ceiling, byte counting, JSON measured as
  serialized text, refused writes leaving counts unchanged
  and the store functional. Negation: the new suites fail
  in full against the pre-RM-027 installed packages
  (muninn 8 failed, huginn 5 failed, run against the
  RM-026 venv). RM-018 goldens extended deliberately
  (muninn 35 cases / 42 templates, huginn 43 cases / 46
  templates); RM-019 surface goldens gained the new config
  fields; guides + API reference updated. Full suites
  green in a fresh venv (`ravens-rm027-venv`, non-editable
  installs), re-run on the final banking tree: muninn
  **149 passed** (141+8), huginn **115 passed** (110+5);
  ruff + mypy floors clean (rm014 venv; mypy muninn 5
  files, huginn 8 files). Public config surface changed
  additively, so the **Bifröst contract re-verification
  was run before banking**: fresh venv
  (`ravens-rm027-bifrost-venv`), bifrost at b66e98cc —
  its own suites **25 passed**; BifrostBridge smoke PASS
  (store mimir_id+huginn_id; search 2 merged results;
  recall grew the Muninn activation log exactly +1;
  decay/consolidate reports; `decay_wall_clock()` through
  the bridge armed at 0 days; stats over all three
  backends; both raven health dicts carry
  `sqlite_version` 3.45.1; huginn degraded via
  auto-fallback to local — live Qdrant still NOT PROVEN;
  double close safe; evidence
  `~/workspace/.verify-tmp/rm027_bifrost.log`). Founding
  tree NEEDS A SYNC for the config fields + enforcement
  (extends the RM-008/RM-011/RM-012/RM-016/RM-017/
  RM-025/RM-026 sync note).
- **RM-028 — Pathological paths. BANKED 2026-11-01.
  Class: UNIT.** Record: `docs/PATHOLOGICAL_PATHS.md`.
  Muninn-only (Huginn has no node paths). Defined
  behaviour for node paths, previously undefined and
  partly inconsistent (`a/b` vs `a/b/` forked identity on
  the exact read but not the prefix read; LIKE wildcards
  in segments silently matched neighbours). One
  normaliser (`_normalize_path`) now serves every entry
  point — `remember` / `store` / `update` / `move` writes,
  `retrieve` / `get_by_path` / `get_children` reads:
  split on `/`, empty and `.` segments drop, `..` climbs
  one level and clamps at the store root, kept segments
  re-join with single `/`s, root is `""`; only `/`
  separates (backslash + unicode look-alikes are ordinary
  characters). Prefix reads escape `\` / `%` / `_` with
  `ESCAPE '\'`; `get_children("")` returns every pathed
  node grouped by path (was always `{}`). Bounds on the
  normalised path: non-strings are typed
  `MuninnValidationError` before any write; at most 64
  segments and 2048 UTF-8 bytes. Pinned by new
  `tests/test_pathological_paths.py` (12 tests:
  dotdot/root spellings, spelling agreement across writes
  and reads, move/update normalisation, typed non-strings
  leaving stats unchanged, both ceilings at/above,
  literal wildcards, root children). Negation: **11 of
  12 failed** against the pre-RM-028 installed packages
  (RM-027 venv; the pass is verbatim backslash/unicode
  storage, which already held). RM-018 goldens extended
  deliberately (38 cases / 41 templates); guides + API
  reference updated. Full suites green in a fresh venv
  (`ravens-rm028-venv`, non-editable installs), final
  banking-tree runs: muninn **161 passed**, huginn
  **115 passed** (the pre-entry muninn run failed only
  the two slice-log pin tests, as in every prior slice);
  ruff + mypy floors clean (rm014 venv; mypy muninn 5
  files, huginn 8 files). Validation behaviour
  tightened (no signature or schema change; RM-003
  freeze + RM-004 snapshot green), so the **Bifröst
  contract re-verification was run before banking**:
  fresh venv (`ravens-rm028-bifrost-venv`), bifrost at
  b66e98cc — its own suites **25 passed**; BifrostBridge
  smoke PASS (store mimir_id+huginn_id; search 1 merged
  result; recall grew the Muninn activation log exactly
  +1; decay/consolidate reports; `decay_wall_clock()`
  through the bridge armed at 0 days; stats over all
  three backends; both raven health dicts carry
  `sqlite_version` 3.45.1; huginn degraded via
  auto-fallback to local — live Qdrant still NOT
  PROVEN; double close safe; evidence
  `~/workspace/.verify-tmp/rm028_bifrost.log`).
  Founding tree NEEDS A SYNC for the path normaliser
  (extends the RM-008/RM-011/RM-012/RM-016/RM-017/
  RM-025/RM-026/RM-027 sync note).
- **RM-028 count correction (2026-11-01, after banking):**
  the muninn banking count was first recorded as 162 from a
  background-run notification that proved crossed with
  another run (the same sessions re-delivered with 161 and
  163 tallies). A disk-logged re-run of the banked tree
  (commit 1cbdc20) settles it: **161 passed**
  (`~/workspace/.verify-tmp/rm028/muninn_final_rerun.log`),
  matching the collector's 161 tests. The RM-028 entries in
  this file and in `docs/SLICE_LOG.md` are corrected in the
  correction commit that carries this note. The negation
  tally in the RM-028 entries likewise came from a crossed
  notification: the negation run's own delivered output
  reads **10 failed, 2 passed** (the passes are the two
  behaviours that already held pre-fix). No other RM-028
  claim is affected.
- **RM-029 — Disk-full behaviour. BANKED 2026-11-01.
  Class: FAULT.** Record: `docs/DISK_FULL.md`. Writes against
  a full filesystem previously escaped as raw
  `sqlite3.OperationalError` (`database or disk is full`) and
  a mid-call failure could leave half-applied statements in
  the open transaction for a later commit to persist. Every
  public write now runs behind a write guard (`_storage_write`
  in `muninn/core.py`: remember/store, update/move,
  forget/delete, activate, activate_batch, associate,
  retrieve(touch=True), heal_structure, decay,
  decay_wall_clock, consolidate, backup; and in
  `huginn/local_backend.py`: upsert, delete, heal — the
  Qdrant backend already raises `HuginnBackendError`). The
  guard rolls the failed call back and raises the typed
  storage error `… write failed during {operation}: {sqlite
  message}`. The fault is injected with the real engine —
  `PRAGMA max_page_count` clamped to the current page count
  yields SQLite's own SQLITE_FULL, the same error a full
  filesystem produces; no genuinely-full-device claim is
  made. Pinned by new `tests/test_disk_full.py` in both
  packages (muninn 3, huginn 2): typed-not-raw on remember/
  update/upsert, store consistent in-session and after
  reopen, rollback proven for the 300-node activate_batch
  and for Huginn's deindex-then-write replace path.
  Negation: all 5 new tests fail against the pre-RM-029
  installed packages (RM-028 venv). RM-018 goldens extended
  deliberately (muninn 39 cases / 42 templates, huginn 44
  cases / 45 templates); guides + API reference updated.
  Full suites green in a fresh venv (`ravens-rm029-venv`,
  non-editable installs): muninn **164 passed** (161+3),
  huginn **117 passed** (115+2); ruff + mypy floors clean.
  Error behaviour of writes changed (no signature or schema
  change; RM-003/RM-004 pins green), so the **Bifröst
  contract re-verification was run before banking**: fresh
  venv (`ravens-rm029-bifrost-venv`), bifrost at b66e98cc —
  its own suites **25 passed**; BifrostBridge smoke PASS
  (store mimir_id=2 huginn_id=5; search 2 merged results;
  recall grew the Muninn activation log exactly +1;
  decay/consolidate reports; `decay_wall_clock()` through
  the bridge armed at 0 days; stats over all three
  backends; both raven health dicts carry `sqlite_version`
  3.45.1; huginn degraded via auto-fallback to local —
  live Qdrant still NOT PROVEN; double close safe; evidence
  `~/workspace/.verify-tmp/rm029_bifrost.log`). Founding
  tree NEEDS A SYNC for the write guards (extends the
  RM-008/RM-011/RM-012/RM-016/RM-017/RM-025/RM-026/RM-027/
  RM-028 sync note).
- **RM-030 — Read-only filesystem. BANKED 2026-11-01.
  Class: FAULT.** Record: `docs/READONLY_FILESYSTEM.md`.
  Opening a store whose location is read-only previously had
  no defined behaviour — as a privileged process the old code
  simply opened marked stores and wrote to them; unprivileged,
  the failure surfaced wherever SQLite or the filesystem
  refused first, raw or mistaken for corruption (which sends
  the open down the backup-restore road). Defined behaviour,
  chosen from the roadmap's two roads: **no read-only mode** —
  a store is opened for writing or not at all, and a read-only
  open fails loudly and immediately with the typed storage
  error `{package} store {path} is read-only and cannot be
  opened for writing`. The refusal sits in a pre-flight at the
  head of `open_store` in each package's `_db.py`, before any
  connection: a location is read-only when the store file or
  the directory that must hold it (the parent, or the nearest
  existing ancestor of a not-yet-created parent) carries no
  write permission bit at all, or when this process cannot
  write there; every later open stage (parent creation,
  integrity probe, connection, schema preparation) also
  translates a read-only failure (EROFS/EACCES/EPERM, SQLite's
  read-only wordings) into the same typed error, so it never
  takes the restore road and never escapes raw. Pinned by new
  `tests/test_readonly_filesystem.py` (muninn 4, huginn 3):
  refusal in under 5 s despite a 60 s busy timeout, store
  SHA-256 unchanged, no backup taken or restored, clean
  zero-recovery reopen once unmarked, new stores in read-only
  directories refused and never created, Huginn's facade
  `health()` reporting the refusal as `unhealthy` with
  `HuginnStorageError` named. Negation: all 7 new tests fail
  against the pre-RM-030 installed packages (RM-029 venv).
  RM-018 goldens extended deliberately (muninn 40 cases / 49
  templates, huginn 45 cases / 52 templates — the read-only
  template stands six times per package, once per raise site,
  and the main connection's new wrapper added a second
  "could not be prepared" template). In-slice repair of a
  discovered pre-existing defect (never-leave-a-bug law):
  the RM-008 mypy floor did not reproduce at HEAD under the
  CI invocation (`python -m mypy src/muninn` from the package
  directory, rm014-venv tools) — RM-029's `_storage_write`
  decorator returned `Any`, so `warn_return_any` fired in
  four alias methods in `muninn/core.py` (the same 4 errors
  proven on a clean HEAD worktree before the fix). The
  decorator in both packages now preserves the wrapped
  method's return type via a `TypeVar` (behaviour unchanged;
  RM-029 suites stay green), and both floors pass as CI runs
  them: ruff **All checks passed!**, mypy **Success: no
  issues found** (muninn 5 files, huginn 8 files). Full
  suites green in a fresh venv (`ravens-rm030-venv`,
  non-editable installs, final banking tree): muninn
  **168 passed** (164+4), huginn **120 passed** (117+3).
  Error behaviour of open changed (no signature or schema
  change; RM-003/RM-004 pins green), so the **Bifröst
  contract re-verification was run before banking**: fresh
  venv (`ravens-rm030-bifrost-venv`), bifrost at b66e98cc —
  its own suites **25 passed**; BifrostBridge smoke PASS
  (store mimir_id=2 huginn_id=2; search 2 merged results;
  recall grew the Muninn activation log exactly +1;
  decay/consolidate reports; `decay_wall_clock()` through
  the bridge armed at 0 days; stats over all three backends;
  both raven health dicts carry `sqlite_version` 3.45.1;
  huginn degraded via auto-fallback to local — live Qdrant
  still NOT PROVEN; double close safe; evidence
  `~/workspace/.verify-tmp/rm030_bifrost.log`). Founding tree
  NEEDS A SYNC for the read-only pre-flight + open-stage
  translations and the decorator return-type repair (extends
  the RM-008/RM-011/RM-012/RM-016/RM-017/RM-025/RM-026/
  RM-027/RM-028/RM-029 sync note).
- **RM-031 — Locked-store contention. BANKED 2026-11-01.
  Class: UNIT.** Record: `docs/LOCKED_STORE.md`. A second
  process holding the store's write lock previously had no
  defined expiry behaviour: the busy timeout was honoured,
  but an open then reported the generic preparation failure
  (`could not be prepared: database is locked`), a write
  echoed SQLite's wording through the RM-029 guard, and a
  locked failure at the open's integrity-probe stage fell
  into the corruption bucket and took the backup-restore
  road (all measured pre-fix by a probe against the RM-030
  packages: open + write waits of ~1.4–5.2 s at the
  configured timeouts, WAL pure reads unaffected). Defined
  behaviour: contention is classified at every stage —
  `_is_locked_error` in each package's `_db.py` (locked /
  busy wordings, or SQLITE_BUSY / SQLITE_LOCKED codes) —
  and every open stage (probe connect, probe quick_check,
  main connect, schema preparation) raises the one typed
  contention message `{package} store {path} is locked by
  another process (busy timeout {ms} ms expired)`; the
  RM-029 write guards raise `{package} write failed during
  {operation}: store is locked by another process (busy
  timeout expired)` after rollback. A lock released inside
  the timeout makes the open/write simply succeed;
  `busy_timeout_ms=0` fails at once; pure reads proceed
  against the WAL snapshot mid-contention (Muninn's
  `retrieve(touch=True)` is a write and follows the write
  rule); Huginn's facade `health()` reports a locked open
  as `unhealthy` naming `HuginnStorageError`. Pinned by
  new `tests/test_locked_store.py` (muninn 5, huginn 6)
  whose lock holder is a real second process (subprocess,
  raw `sqlite3` `BEGIN EXCLUSIVE`) for the open/write
  acceptance tests: waits ≥1.2 s at a 1500 ms timeout,
  exact messages, store SHA-256 unchanged + no backup
  created + no "corrupt" wording on a refused open, zero
  recovery on reopen, refused writes storing nothing and
  the same object writing after release. Negation: the
  new suites fail against the pre-RM-031 installed
  packages (RM-030 venv) exactly on the contention
  messages — muninn 3 failed / 2 passed, huginn 4 failed
  / 2 passed (the passes are release-inside-timeout and
  WAL reads, behaviours that already held, now pinned).
  RM-018 goldens extended deliberately (muninn 42 cases /
  55 templates, huginn 47 cases / 58 templates; the
  locked-open template stands four times per package, the
  probe quick_check stage added a seventh read-only site,
  each write guard gained its locked raise); guides + API
  reference updated. Full suites green in a fresh venv
  (`ravens-rm031-venv`, non-editable installs, final
  banking tree): muninn **173 passed** (168+5), huginn
  **126 passed** (120+6); ruff + mypy floors clean (rm014
  venv; mypy muninn 5 files, huginn 8 files). Open/write
  error behaviour changed (no signature or schema change;
  RM-003/RM-004 pins green), so the **Bifröst contract
  re-verification was run before banking**: fresh venv
  (`ravens-rm031-bifrost-venv`), bifrost at b66e98cc —
  its own suites **25 passed**; BifrostBridge smoke PASS
  (store mimir_id=2 huginn_id=5; search 2 merged results;
  recall grew the Muninn activation log exactly +1;
  decay/consolidate reports; `decay_wall_clock()` through
  the bridge armed at 0 days; stats over all three
  backends; both raven health dicts carry
  `sqlite_version` 3.45.1; huginn degraded via
  auto-fallback to local — live Qdrant still NOT PROVEN;
  double close safe; evidence
  `~/workspace/.verify-tmp/rm031_bifrost.log`). Founding
  tree NEEDS A SYNC for the locked classification + the
  write guards' contention shape (extends the
  RM-008/RM-011/RM-012/RM-016/RM-017/RM-025/RM-026/
  RM-027/RM-028/RM-029/RM-030 sync note).
- **RM-032 — Partial-file states. BANKED 2026-11-01.
  Class: FAULT.** Record: `docs/PARTIAL_FILE_STATES.md`.
  Partial file combinations at open — previously undefined,
  two of them silently losing memory (measured by probe
  against the RM-031 packages): a main store truncated to
  zero bytes opened as a fresh empty store even with a
  verified `.bak-1` beside it (and the empty store then
  rotated into the backup chain on later opens); a non-empty
  WAL without its main file was silently discarded by a
  fresh start; a `.bak-tmp` left by a killed backup
  lingered indefinitely. Defined now in each package's
  `_db.py` `open_store`, after the RM-030 pre-flight: a
  leftover `.bak-tmp` is removed on open and never read
  (`_discard_stale_backup_tmp`); a zero-length main file is
  classified truncated before any connection and takes the
  corruption road (restore newest verified generation, else
  the existing typed corrupt refusal, file left untouched);
  a non-empty WAL with no main file restores a verified
  backup (the restore consumes the orphaned sidecars) or
  raises the new typed refusal `… store {path} has a
  write-ahead log but no main file and no rolling backup
  verified; refusing to start empty over lost memory` — on
  refusal no main file is created and the WAL stands; an
  empty/absent WAL is not evidence, and a missing main
  without one is an ordinary new store. WAL-missing and
  garbage-WAL opens were already sound and are now pinned.
  Pinned by new `tests/test_partial_file_states.py` (10
  tests each): the temp-removal test forces a quiet open
  (store older than its generation, generation digest
  unchanged) so the removal is the new cleanup, and the
  never-a-candidate tests are adversarial (a complete valid
  store copy at the temp path still gets the refusal beside
  a corrupt main; generation-beats-temp proven by content).
  Negation: 7 failed / 3 passed per package against the
  RM-031 venv, the passes being the already-held behaviours.
  RM-018 goldens extended deliberately (muninn 43 cases /
  60 template lines, huginn 48 cases / 61 template lines,
  counted from the files — +1 CASE +1 TEMPLATE each for the
  partial-state message; noted in the slice log: the RM-031
  record's template figures do not match a line count of
  its goldens, a pre-existing discrepancy, not rewritten).
  Full suites green in a fresh venv (`ravens-rm032-venv`,
  non-editable installs, final banking tree): muninn
  **183 passed** (173+10), huginn **136 passed** (126+10);
  ruff + mypy floors clean (rm014 venv; mypy muninn 5
  files, huginn 8 files). Verification history, honestly:
  a first muninn full run showed one golden-test failure
  and a later burst of huginn golden-test failures, all
  inside a VM Python-write-gate closure window (Python
  tempfile creation refused machine-wide, the RM-015/
  RM-020 pattern, then probed open 5/5); outside the window
  the golden test passed 8/8 loop runs plus 4/4 per-case
  debug runs with an exact manual capture match, and both
  disk-logged full suites are the green counts above (logs
  `~/workspace/.verify-tmp/rm032/`) — environment class, no
  code changed for it. Open error behaviour changed (no
  signature or schema change; RM-003/RM-004 pins green),
  so the **Bifröst contract re-verification was run before
  banking**: fresh venv (`ravens-rm032-bifrost-venv`),
  bifrost at b66e98cc — its own suites **25 passed**;
  BifrostBridge smoke PASS (store mimir_id=2 huginn_id=5;
  search 2 merged results; recall grew the Muninn
  activation log exactly +1; decay/consolidate reports;
  `decay_wall_clock()` through the bridge armed at 0 days;
  stats over all three backends; both raven health dicts
  carry `sqlite_version` 3.45.1; huginn degraded via
  auto-fallback to local — live Qdrant still NOT PROVEN;
  double close safe; evidence
  `~/workspace/.verify-tmp/rm032_bifrost.log`). Founding
  tree NEEDS A SYNC for the partial-state open handling
  (extends the RM-008/RM-011/RM-012/RM-016/RM-017/RM-025/
  RM-026/RM-027/RM-028/RM-029/RM-030/RM-031 sync note).
- **RM-033 — Non-database files. BANKED 2026-11-01.
  Class: UNIT.** Record: `docs/NON_DATABASE_FILES.md`.
  (This slice's banking also completed RM-032's: its tree
  stood built, tested and documented but uncommitted when
  this tick opened — verified against its disk logs,
  targeted pins re-run green, then committed and pushed as
  d2dbfa4 before RM-033 work began.) Shapes at the store
  path that are not databases at all — previously answered
  only incidentally, one of them leaking a traceback
  (measured by probe against the RM-032 packages): a
  directory with a verified backup beside it took the
  corruption road and the restore's file copy raised a raw
  `IsADirectoryError` out of `open_store`; a directory
  without one was misreported as a corrupt store. Defined
  now in each package's `_db.py` `open_store`: a shape
  pre-flight (`_check_store_path_shape`) runs before every
  other open step — a directory raises the typed refusal
  `… store {path} is a directory, not a database file;
  refusing to open` (directory and contents untouched,
  backup neither consumed nor rotated, never deleted or
  replaced to make room for a restore; Huginn's facade
  reports it as an `unhealthy` `health()` dict), and any
  other non-regular file raises `… store {path} is not a
  regular file; refusing to open` before any open is
  attempted on it. A text file (long or short) and an empty
  file take the corruption road — restore a verified
  backup, else the typed corrupt refusal, the refused file
  left byte-identical with no sidecars created. Pinned by
  new `tests/test_non_database_files.py` (8 tests each).
  Negation: 3 failed / 5 passed per package against the
  RM-032 venv, the failures exactly the new shape
  behaviours. RM-018 goldens extended deliberately (muninn
  45 cases / 62 template lines, huginn 50 cases / 63
  template lines, counted from the files — +2 CASEs +2
  TEMPLATEs each: `directory_store`, `nonfile_store`).
  Full suites green in a fresh venv (`ravens-rm033-venv`,
  non-editable installs, final banking tree): muninn
  **191 passed** (183+8), huginn **144 passed** (136+8);
  ruff + mypy floors clean (rm014 venv; mypy muninn 5
  files, huginn 8 files). Open error behaviour changed (no
  signature or schema change; RM-003/RM-004 pins green),
  so the **Bifröst contract re-verification was run before
  banking**: fresh venv (`ravens-rm033-bifrost-venv`),
  bifrost at b66e98cc — its own suites **25 passed**;
  BifrostBridge smoke PASS (store mimir_id=2 huginn_id=5;
  search 2 merged results; recall grew the Muninn
  activation log exactly +1; decay/consolidate reports;
  `decay_wall_clock()` through the bridge armed at 0 days;
  stats over all three backends; both raven health dicts
  carry `sqlite_version` 3.45.1; huginn degraded via
  auto-fallback to local — live Qdrant still NOT PROVEN;
  double close safe; evidence
Discovered-bug fix in this slice (test harness, no package code): the RM-031 golden-case lock holder in `tests/test_error_messages.py` was kept alive only by an incidental reference cycle; when the cyclic GC collected it before the locked cases ran, its connection closed, the lock rolled back, and `locked_open` / `locked_remember` (huginn: `locked_upsert`) intermittently did not raise — diagnosed by per-case capture (first capture pass of a fresh process failed, later passes passed; a direct probe showed the lock held 4/4 after `_cases` returns, so collection timing was the race). `_cases` now returns the holder and the test holds a strong reference for the whole pass: per-case loop 6/6 clean per package, fresh processes included. Verification history, honestly: a first final muninn full run inside a machine-wide Python/SQLite write-gate closure (plain sqlite WAL creates then failing 5/5 in every directory, `tempfile` refused — the RM-015/RM-020 environment pattern, reproduced identically against the RM-032 packages) showed that one golden failure; the disk-logged re-runs outside the window, after the holder fix, are the green counts above (logs `~/workspace/.verify-tmp/rm033/`).   `~/workspace/.verify-tmp/rm033_bifrost.log`). Founding
  tree NEEDS A SYNC for the shape pre-flight (extends the
  RM-008/RM-011/RM-012/RM-016/RM-017/RM-025/RM-026/RM-027/
  RM-028/RM-029/RM-030/RM-031/RM-032 sync note).
- **RM-034 — Unicode & encoding gauntlet. BANKED 2026-11-01.
  Class: UNIT.** Record: `docs/UNICODE_GAUNTLET.md`. Valid
  Unicode was already welcome in both stores (the RM-025/
  RM-026 fuzz pinned RTL, ZWJ emoji, combining marks and
  NUL-bearing text to round-trip); the undefined shape was
  the **lone surrogate** (unpaired U+D800–U+DFFF), which
  RM-025/RM-026 explicitly left to this slice. Pre-fix
  probes measured it: Muninn string content, a path and a
  category escaped as raw `UnicodeEncodeError` (content
  hash / path-size `.encode()`, SQLite bind for category),
  while Muninn tags, metadata and JSON-valued content were
  silently stored as JSON `\udXXX` escapes and handed back
  unencodable; Huginn content died in the RM-027 size
  check, a category at the SQLite bind, a tag was silently
  stored, and a surrogate query silently searched for
  nothing. Defined now: one checker per package
  (`_check_no_lone_surrogates` in each `core.py`) refuses
  any text carrying a lone surrogate with the typed
  validation error `{field} must not contain lone
  surrogates`, before any write — Muninn checks content
  (recursively over JSON-shaped values: dict keys/values,
  list/tuple/set items at any depth; circular structures
  are left to the established typed serializability
  refusal), metadata (the same walk, including the string
  form of values the dump would stringify), tags,
  category, path (inside the RM-028 normaliser, so the
  prefix reads share the rule) and the `retrieve` filters
  (query / tags / category); Huginn checks in the facade —
  content, category, tags, every query-shaped argument via
  `_check_query_text`, read-side categories via
  `_check_category`, and `semantic_search` documents — so
  the refusal holds on local and Qdrant alike, and a
  surrogate `fly` query comes home as an error flight
  naming the refusal. The welcome half is pinned verbatim
  by new `tests/test_unicode_gauntlet.py` (muninn 17,
  huginn 10): RTL (Arabic/Hebrew) and CJK round-trip and
  search; emoji ZWJ sequences (family glyph, skin-tone
  technologist) round-trip byte-for-byte; combining marks
  are never normalised — decomposed `cafe + ◌́` and
  precomposed `café` are distinct memories in both
  stores; astral-plane characters (𝄞, 𐍈 — single code
  points above U+FFFF, not lone surrogates) pass
  untouched; refused writes leave both stores' counts
  unchanged. Negation against the pre-RM-034 code:
  muninn **12 failed / 5 passed**, huginn **6 failed /
  4 passed** (the passes are exactly the welcome half).
  RM-018 goldens extended deliberately (muninn 47 cases /
  63 templates, huginn 52 cases / 64 templates, counted
  from the files — +2 CASEs +1 TEMPLATE each, the shared
  `{} must not contain lone surrogates` template). Full
  suites green in a fresh venv (`ravens-rm034-venv`,
  non-editable installs, final banking tree): muninn
  **208 passed** (191+17), huginn **154 passed**
  (144+10); ruff + mypy floors clean (rm014 venv; mypy
  muninn 5 files, huginn 8 files). Verification history,
  honestly: two suite summaries delivered by the runtime
  during this tick belonged to other campaigns' runs
  (crossed notifications, the RM-028 pattern) and were
  discarded — every count above is from this slice's own
  disk logs under `~/workspace/.verify-tmp/rm034/`; the
  VM Python write gate also closed mid-tick (0/5 tempfile
  probes) and reopened on probing, as in RM-015/RM-020.
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
- **RM-035 — Huge-batch atomicity. BANKED 2026-11-01.
  Class: BENCH.** Record: `docs/HUGE_BATCH_ATOMICITY.md`.
  `activate_batch` gained a bulk road at ≥64 unique ids
  (`_activate_batch_bulk_locked`): the same single
  transaction and writes restated set-at-a-time —
  activations as `executemany` over generators, wiring as
  one `INSERT … SELECT` over a TEMP staging table
  self-joined on `<>`, arithmetic `pairs_wired`,
  `connections_created` subtracting pairs already wired
  in both directions (one-direction drift counts as
  created and is repaired — the per-pair loop's exact
  rule), and `idx_conn_b` dropped + recreated inside the
  same transaction (rollback restores it; RM-004/RM-022
  schema pins pass unchanged). Below 64 ids the original
  loop runs unchanged. Pinned by new
  `tests/test_huge_batch_atomicity.py` (7 tests): exact
  counts at 800 ids, de-duplication, exact repeat
  strengthening, pre-wired + drift repair, loop/bulk
  agreement across the threshold, disk-full rollback at
  bulk scale including index restoration, subprocess
  memory pin (16× pairs → peak RSS +<40 MB). Bench:
  pre-RM-035 loop probed 500 ids in 16.90 s; the bulk
  road runs 500 in **0.64 s** and the full 10k batch
  (49,995,000 pairs, 99,990,000 directed rows) in
  **1629.6 s** at peak RSS **47.5 MB**, all eight bench
  checks passed (record
  `~/workspace/.verify-tmp/rm035/bench10k.json`,
  2026-11-01T22:42:34Z, load_avg [11.23, 8.76, 7.77];
  store 12,232,638,464 bytes after). Full suites green
  in the RM-035 venv (non-editable installs, TMPDIR on
  the workspace disk), verified twice — before the bench
  and re-run on the final banking tree: muninn **215
  passed** (208+7), huginn **154 passed**; ruff + mypy
  floors clean. Behaviour at bulk scale is new (no
  signature or schema change; RM-003/RM-004 pins green),
  so the **Bifröst contract re-verification was run
  before banking**: fresh venv
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
  Banking was completed by the following keeper tick
  after the building tick stopped with the bench still
  running (see the Status note above). Founding tree
  NEEDS A SYNC for the bulk `activate_batch` road
  (extends the RM-008/RM-011/RM-012/RM-016/RM-017/
  RM-025/RM-026/RM-027/RM-028/RM-029/RM-030/RM-031/
  RM-032/RM-033/RM-034 sync note). Huginn has no batch
  operation — this slice is Muninn-only.
- **RM-036 — Adversarial tags/metadata. BANKED 2026-11-01.
  Class: UNIT.** Record: `docs/ADVERSARIAL_TAGS_METADATA.md`.
  The annotation payload's shape is bounded now. Probed
  first against the RM-035 packages: Muninn metadata or
  JSON-shaped content nested 5,000 containers deep escaped
  `remember` as a raw `RecursionError` (inside the recursive
  RM-034 surrogate walk or `json.dumps`, before the RM-027
  size check ran); a tags list of 200,000 entries was
  accepted by both ravens unbounded; a Huginn tag element
  nested 50,000 deep escaped `upsert_memory` as a raw
  `RecursionError` from the `repr` of the facade's `str()`
  coercion (probe logs `~/workspace/.verify-tmp/rm036/
  probe.py`, `probe2.py`). Defined now: one iterative depth
  bound per package (`_check_structure_depth`,
  `_MAX_STRUCTURE_DEPTH = 100` containers — explicit stack
  plus a path-scoped id set, so the check itself cannot
  overflow the stack it guards) over Muninn's JSON-shaped
  content (in `_content_payload`, ahead of the surrogate
  walk and the dump), metadata on `remember` and `update`,
  and every tag element on `remember`, `update` and the
  `retrieve` filter; and over Huginn's tag elements in the
  facade (local and Qdrant alike). Deeper is the typed
  refusal `{field} nesting depth exceeds maximum of 100`
  before any write. The walker does not descend into a
  container already on its path: self-referential content /
  metadata keep their established typed serializability
  refusals from `json.dumps`, a circular tag element still
  renders through `repr`'s ellipsis (`[[...]]`), and shared
  (DAG-shaped) substructures are walked per occurrence and
  stored as before — all pinned. The RM-027 ceilings are
  applied uniformly to the cleaned tags list (its stored
  JSON form, UTF-8 bytes): Muninn's under
  `max_metadata_bytes`, Huginn's under
  `max_content_bytes` (Huginn carries no metadata ceiling),
  refused typed with the measured size, before any write,
  on both Muninn write paths. Pinned by new
  `tests/test_adversarial_tags_metadata.py` (muninn 16,
  huginn 7). Negation against the pre-RM-036 packages
  (disk logs `~/workspace/.verify-tmp/rm036/
  muninn_negation.log`, `huginn_negation.log`): muninn
  **9 failed / 7 passed**, huginn **3 failed / 4 passed**
  — the failures are exactly the new behaviours, and the
  passes are exactly the behaviours the slice preserves
  (at-bound and at-ceiling shapes stored, circular
  refusals, DAG sharing, ellipsis tags). (Tallies
  corrected the same evening: the first-recorded 10/6
  and 5/2 came from a crossed runtime delivery matching
  neither session's disk log — see the Status note.)
  RM-018 goldens extended
  deliberately (muninn 50 cases / 65 templates, huginn
  54 cases / 66 templates, counted from the files — +3
  CASEs +2 TEMPLATEs muninn: `metadata_too_deep`,
  `content_too_deep`, `tags_oversize`; +2 +2 huginn:
  `tags_too_deep`, `tags_oversize`). Full suites green in
  a fresh venv (`ravens-rm036-venv`, non-editable installs,
  TMPDIR on the workspace disk): muninn **231 passed**
  (215+16), huginn **161 passed** (154+7); re-run on the
  final banking tree in this same tick (logs
  `~/workspace/.verify-tmp/rm036/muninn_final.log`,
  `huginn_final.log`). Ruff + mypy floors clean (rm014
  venv; mypy muninn 5 files, huginn 8 files — run from the
  package directories so each pyproject's overrides apply).
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
  live Qdrant still NOT PROVEN; double close safe; evidence
  `~/workspace/.verify-tmp/rm036/bifrost_smoke.log`).
  Founding tree NEEDS A SYNC for the depth bound and the
  tags ceiling (extends the RM-008/RM-011/RM-012/RM-016/
  RM-017/RM-025/RM-026/RM-027/RM-028/RM-029/RM-030/RM-031/
  RM-032/RM-033/RM-034/RM-035 sync note).
- **RM-037 — Concurrent openers. BANKED 2026-11-01.
  Class: UNIT.** Record: `docs/CONCURRENT_OPENERS.md`.
  Defined behaviour: **supported** — two or more objects,
  same process or cross-process, may hold one SQLite store
  at once in both packages. Each object keeps its own
  connection, lock and per-object state; committed writes
  are visible across objects at once and never lose each
  other (ordinary reads/writes serialized by SQLite, WAL +
  busy timeout, RM-031); closing one object leaves the
  others fully working. The duties that cannot interleave
  (creation, integrity probe, restore, backup-on-open,
  heal, and every rolling backup — all sharing the store
  file, the restore copy and the single `.bak-tmp` path)
  are serialized per store file by a new coordination lock
  in each package's `_db.py` (`store_coordination_lock`:
  a process-wide re-entrant lock per path, plus an `flock`
  on the sibling `<db_path>.open-lock` file where `fcntl`
  exists; the kernel releases a dead holder's flock). The
  RM-033 shape and RM-030 read-only pre-flights run before
  the lock is taken, so those refusals still create
  nothing. Pre-slice probes (the new suites against the
  RM-036 packages): sequential two-object use and
  cross-process ordinary writes were already exact; the
  races were real — six threads creating one fresh Muninn
  store met the half-created file as corruption and
  refused; concurrent Muninn `backup()` calls collided on
  `.bak-tmp`, logged `backup failed: disk I/O error` and
  returned `None`; four openers of a corrupt store
  restored over each other in both packages. Negation
  (disk logs `~/workspace/.verify-tmp/rm037/
  muninn_negation.log`, `huginn_negation.log`): muninn
  **3 failed / 5 passed**, huginn **1 failed / 7 passed**
  (huginn's creation race passed pre-slice in the recorded
  run — timing luck through the lazy facade). Pinned by
  new `tests/test_concurrent_openers.py` (muninn 8,
  huginn 8), targeted suites green twice; full suites
  green on the final banking tree in a fresh venv
  (`ravens-rm037-venv`, non-editable installs): muninn
  **239 passed** (231+8), huginn **169 passed** (161+8);
  ruff + mypy floors clean. Amendment inside the slice:
  the RM-033 text-file refusal tests now expect the
  zero-byte `.open-lock` neighbour (first final muninn
  run 238 passed / 1 failed on the old assertion, then
  amended, documented in `docs/NON_DATABASE_FILES.md`,
  and re-run green). Honest limits in the record doc:
  the RM-012 timestamp guard is per object (cross-object
  timestamps may repeat or invert by microseconds); a
  foreign raw-SQLite writer gets SQLite's locking but
  not the coordination lock; without `fcntl` the
  cross-process half degrades to the in-process lock.
  No signature or schema change (RM-003/RM-004 pins
  green; `.open-lock` added to the FORMAT_STABILITY file
  family as a transient non-store file), but open/backup
  behaviour changed, so the **Bifröst contract
  re-verification was run before banking**: fresh venv
  (`ravens-rm037-bifrost-venv`), bifrost at b66e98cc —
  its own suites **25 passed**; BifrostBridge smoke PASS
  (store mimir_id=2 huginn_id=6; search 1 merged result;
  recall grew the Muninn activation log exactly +1;
  decay/consolidate reports; `decay_wall_clock()` through
  the bridge armed at 0 days; stats over all three
  backends; both raven health dicts carry `sqlite_version`
  3.45.1; huginn degraded via auto-fallback to local —
  live Qdrant still NOT PROVEN; double close safe;
  evidence `~/workspace/.verify-tmp/rm037/
  bifrost_smoke.log`). Founding tree NEEDS A SYNC for the
  coordination lock (extends the RM-008/RM-011/RM-012/
  RM-016/RM-017/RM-025/RM-026/RM-027/RM-028/RM-029/
  RM-030/RM-031/RM-032/RM-033/RM-034/RM-035/RM-036 sync
  note). Huginn's Qdrant backend holds no local file —
  concurrent objects there are concurrent server clients;
  this slice pins the local backend only.
