# Part II — Stability: Evidence Bundle (RM-024, Part Gate)

*Nothing drifts, nothing flakes, nothing depends on the mood
of the machine.* Part II (RM-011–RM-024) is **complete**.
Every claim below is filed from the slice's own record —
`docs/SLICE_LOG.md` and `CAMPAIGN_STATE.md` carry the full
entries; this bundle is the index and the verdict.

## The four named evidence kinds

- **Determinism (RM-011)** — `docs/DETERMINISM.md`. Every
  ordered read whose sort key can tie now carries an
  explicit final tie-break; heal write orders are pinned;
  hash inputs never format a float outside JSON's fixed
  repr. Proven: one fixed workload on two fresh stores
  produces byte-identical logical dumps (every
  non-timestamp column of every table), in-process and in
  child processes under `PYTHONHASHSEED` 0 and 42.
- **Flake record (RM-014)** — 50 consecutive green suite
  pairs under 2 busy-loop load workers, never retried:
  muninn 99 passed / huginn 75 passed per pair, 0 failed,
  0 errors. Record: `rm014_flake_record.jsonl` (goal hidden
  files; live copy `~/workspace/.verify-tmp/rm014/
  runs-resumed.jsonl`). The interruptions on the road were
  machine teardowns, each recorded as it happened — never
  a flake.
- **Soak (RM-015)** — `docs/SOAK.md`. 24 h 06 m span
  (2026-10-31T10:47:56Z → 2026-11-01T10:54:18Z), 39
  segments, 174,523 cycles, RSS bounded (max 39.33 MB,
  final 22.18 MB), huginn store flat at 4.84–4.96 MB,
  muninn store growing linearly with work at a constant
  rate. 70 errors, all `muninn.decay:OperationalError`,
  environment-paired with the VM's extreme-load /
  write-gate episodes and disclosed in full.
- **Matrix (RM-007, from Part I, standing over Part II)** —
  local fresh-venv runs per version: Python 3.11.17,
  3.12.3 and 3.13.17 each green. A GitHub-hosted matrix
  run remains **NOT PROVEN** (the workflow is
  manual-only and has never been dispatched).

## Slice check-off

| Slice | Acceptance, in one line | Suites at banking (muninn / huginn) |
|---|---|---|
| RM-011 Determinism audit | Byte-identical logical dumps across stores, processes, hash seeds | 66 / 57 |
| RM-012 Timestamp discipline | Stored timestamps UTC ISO-8601; monotonic under a backwards clock, incl. across reopen | 70 / 60 |
| RM-013 Idempotency matrix | Every public row classified I/R/N with one test per row (28 muninn + 15 huginn rows) | 99 / 75 |
| RM-014 Flake quarantine | 50 consecutive green pairs under load, no retries | 99 / 75 per pair |
| RM-015 Long-run soak | 24-hour soak completes; growth curves published | 99 / 75 |
| RM-016 SQLite runtime pinning | `health()` carries `sqlite_version`; WAL-safe minimum 3.7.0 documented; Bifröst re-verified | 102 / 78 |
| RM-017 Config immutability | Mutation attempts raise `FrozenInstanceError`; live-store behaviour unmoved; Bifröst re-verified | 107 / 83 |
| RM-018 Stable error messages | Every typed error pinned behaviourally + by AST template (31/33 muninn cases/sites, 33/36 huginn) | 110 / 86 |
| RM-019 API surface freeze | Whole public surface snapshotted (101 / 57 golden lines); removals fail, additions pass | 113 / 89 |
| RM-020 Reproducible benchmark corpus | Corpus versioned (`CORPUS_VERSION = 1`) and SHA-256 hashed in every record; gate refuses cross-corpus comparisons | 117 / 93 |
| RM-021 Clock-free decay | `decay(days)` explicit-only; opt-in `decay_wall_clock()` marker mode, clock jumps both ways; Bifröst re-verified | 124 / 93 |
| RM-022 Store-format stability promise | Every file/table/key named with its contract class + migration rule, pinned against the goldens | 126 / 95 |
| RM-023 Shutdown cleanliness | `close()` checkpoints the WAL fully; reopen performs zero recovery; no lingering threads | 129 / 98 |
| RM-024 Part gate | This bundle | 131 / 100 |

## Contract verifications inside the part

Bifröst contract re-verification (fresh venv, bifrost at
b66e98cc, its own suites 25 passed + BifrostBridge
store/search/recall/decay/consolidate smoke PASS) ran for
every Part II slice that touched the public surface:
**RM-016, RM-017, RM-021** — three for three green.

## Floors standing at the gate

- Lint/type floor (RM-008): ruff + mypy clean in both
  packages at every Part II banking.
- Coverage floor (RM-009): `fail_under = 88` in both
  pyprojects (measured 88.80% muninn / 88.79% huginn at
  setting).
- Schema snapshots (RM-004) and contract freezes (RM-003)
  green at every banking: **no schema changed in Part
  II**, and the only public-surface change was RM-021's
  additive `decay_wall_clock()` (golden updated in its
  own commit, per the freeze semantics).

## Honesty ledger, carried forward unchanged

- Live Qdrant round-trip: **NOT PROVEN** (no live server
  run yet; every Qdrant-side claim in Part II is
  construction or fake-client proof).
- Sentence-transformers path: **NOT PROVEN** (the extra
  has not been run live).
- GitHub-hosted CI: **NOT PROVEN** (manual-only workflow,
  never dispatched; all matrix evidence is local).

## Debts the part leaves, named

- **Founding-tree sync**: the founding tree
  (`~/workspace/ravens`) is behind this repo — package
  sources (RM-008 annotations/guards, RM-011 tie-breaks,
  RM-012 `_tick`, RM-016 health, RM-017 frozen configs,
  RM-021 `decay_wall_clock()`), the benchmark scripts +
  baselines (RM-005, RM-020), and pyproject floors. The
  sync is recorded here and in `CAMPAIGN_STATE.md`; it is
  a deliberate later act, not done by this gate.
- `schema_version` is recorded, not yet gated on —
  the migration registry is RM-132's (Part X), with
  RM-082's foreign-schema behaviour ahead of it
  (`docs/FORMAT_STABILITY.md` states the interim rule).

## Gate verdict

Part II's acceptance stands on filed evidence for every
slice: determinism proven, 50/50 flake record clean, the
24-hour soak complete with disclosed errors, and every
stability surface — timestamps, idempotency, configs,
errors, API, corpus, format, shutdown — pinned by tests
that fail on drift. **Part II is complete.** The road
continues at Part III — Robustness (RM-025–RM-038).
