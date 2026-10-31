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

- Banked: RM-001, RM-002, RM-003.
- In progress: none.
- Next: RM-004 in roadmap order.

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
