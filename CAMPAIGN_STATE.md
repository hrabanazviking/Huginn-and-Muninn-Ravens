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
- Banked (Part II): RM-011.
- In progress: none.
- Next: RM-012 in roadmap order (Part II — Stability).

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
