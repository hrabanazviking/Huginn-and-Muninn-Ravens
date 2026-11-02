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
  RM-037, RM-038. **Part III (Robustness) is complete** — all
  fourteen slices banked and pushed; evidence bundle in
  `docs/PART_III_EVIDENCE.md`.
- Banked (Part IV): RM-039, RM-040, RM-041, RM-042, RM-043,
  RM-044, RM-045, RM-046, RM-047, RM-048, RM-049, RM-050,
  RM-051, RM-052, RM-053, RM-054, RM-055, RM-056.
  **Part IV (Security) is complete** — all eighteen
  slices banked and pushed; evidence bundle in
  `docs/PART_IV_EVIDENCE.md`; threat model re-reviewed
  and updated at the gate.
- Banked (Part V, in progress): RM-057, RM-058, RM-059,
  RM-060, RM-061, RM-062, RM-063.
- Next: RM-064 in roadmap order (Decay/consolidate at
  scale: both are full-store UPDATEs; add chunked
  maintenance with progress reporting that preserves
  all-or-nothing semantics per chunk boundary stated
  in the report; acceptance: 100k-edge run within the
  gate. Class: BENCH).
- **RM-063 BANKED 2026-11-02 (keeper tick ~16:46 EST):**
  Warm caches — UNIT. Both packages gain an optional
  bounded in-memory cache for their single-item read
  behind one new config field per package,
  `cache_size: int = 0` (validated `>= 0`, typed
  message `cache_size must be >= 0`; RM-018 goldens
  65 → 66 CASE muninn, 69 → 70 CASE huginn, templates
  92 / 92 — Huginn also gained a second
  `HuginnMemory is closed` template from the cache
  path's closed check). Muninn caches `get_node`
  results in the core; Huginn caches document `get`
  results in the FACADE, so both backends ride one
  invalidation discipline (proven against a counting
  toy backend). **Default 0 = off** — the RM-055
  secure-defaults judgement extended in-slice (rows in
  `docs/SECURE_DEFAULTS.md`): a cache trades freshness
  for speed and is per-object only, so the safe default
  is the pre-RM-063 road, every read reading the
  store. When enabled: LRU-bounded at `cache_size`;
  stored values and hits are deep copies (caller
  mutation can never poison the cache — pinned);
  misses are never cached. **Own writes always
  invalidate** — Muninn `remember` / `remember_many`
  (their ids; backpressure victims invalidated inside
  `_apply_backpressure_locked` itself), `update` /
  `move`, `activate` / `activate_batch` /
  `retrieve(touch=True)` (activation changes
  access_count/updated_at), `forget` /
  `secure_forget`; Huginn `upsert_memory`, `delete`,
  `secure_forget`. **Per-object only, stated plainly**
  in `docs/WARM_CACHES.md`, both guides, both
  INTERFACE files and API_REFERENCE: another object /
  process (or a direct Qdrant write) is not seen until
  eviction or an own write to that id — the staleness
  window is pinned by test, not hidden. Accounting in
  a new dedicated `cache_stats` property per package
  (enabled/size/cap/hits/misses/evictions/hit_rate,
  lifetime counts, invalidation never rewrites them;
  RM-053 pattern, outside the pinned-pure
  health()/stats(); Huginn's reading never constructs
  the backend). RM-019 goldens gained the field + the
  property in both packages; no SQL added (RM-040
  audit totals unchanged), no schema change. New
  `tests/test_warm_caches.py` (muninn 15, huginn 13).
  Negation vs the RM-062 packages: warm-caches muninn
  **14 failed / 1 passed**, huginn **12 failed / 1
  passed** (the pass in each is the record-doc pin,
  which judges the tree), secure-defaults **2 failed**
  per package, error-messages **1 failed / 2 passed**
  per package, api-surface **1 failed / 2 passed**
  per package, slice-log **2 failed** per package.
  **Bifröst re-verification PASS** (public API grew
  additively; fresh venv on `/var/tmp`, bifrost
  source from the git-clean pinned b66e98cc checkout —
  its own suites **25 passed**; BifrostBridge smoke
  PASS — store mimir_id+huginn_id, search 1 merged
  result, recall grew the Muninn activation log
  exactly +1, decay/consolidate reports,
  `decay_wall_clock()` armed at 0 days, stats over
  all three backends, both raven health dicts carry
  `sqlite_version` 3.45.1, huginn local via
  auto-fallback, double close safe; evidence
  `/var/tmp/rm063/evidence/`). Full suites on the
  final banking tree (non-editable installs from a
  full-repo copy on `/var/tmp`, encryption + qdrant
  extras, cryptography 50.0.2, qdrant-client 1.20.0,
  pytest 9.2.0): muninn **411 passed** (396+15),
  huginn **335 passed** (322+13). Ruff clean (both
  packages; the one repo-root `scripts/soak.py`
  BLE001 finding is pre-existing, untouched, and
  outside the packages' ruff floor); mypy 1.20.2
  clean in a deps-free tool venv (muninn 7 files,
  huginn 9 files). Environment, honestly: the
  home-quota EDQUOT closure was shut for most of this
  tick — the slice was built in the home tree until
  the closure, then finished and verified in a
  full-repo copy on `/var/tmp` (the RM-060 pattern)
  after freeing only regenerable caches (the shared
  npm cache and this repo's mypy/pytest caches,
  ~84 MB); the `.verify-tmp` Janas store is Volmarr's
  pending decision, untouched. The closure never
  reopened for the banking step, so this slice was
  committed and pushed FROM the `/var/tmp` full-repo
  copy (remote-diffed first, fast-forward only); the
  home tree at `~/workspace/ravens-repo/` still holds
  the identical RM-063 changes uncommitted on top of
  RM-062 — the next tick with home writes open must
  reconcile it (`git fetch`, verify the working-tree
  diff matches this commit, then reset to
  `origin/main`) before taking RM-064. Live Qdrant +
  sentence-transformers stay NOT PROVEN. Founding
  tree NEEDS A SYNC for the RM-063 build (extends
  the standing package-source sync note).
- **RM-062 BANKED 2026-11-02 (keeper tick ~15:46 EST, completed
  by the following tick after an interruption):** Huginn
  vector scan — BENCH. The embedder-mode scan gains the
  in-store prefilter: the old road fetched EVERY stored
  vector's text (`SELECT doc_id, vector FROM doc_vectors`;
  ~4.8 KB of JSON per vector at 384 dims — the gate's
  100k store is 477,544,448 bytes and moved its whole
  vector table per search), sorted + capped in Python,
  and only then applied the category/importance filter
  to the document rows. All three cuts now happen in
  SQL in the RM-053 order (cap BEFORE filter, lowest ids
  first): candidate total as `COUNT(*)`, capped ids
  selected in-store (`ORDER BY doc_id LIMIT ?`, cap
  bound), the documents fetch applying the filter in
  SQL as it already did, and only survivors' vectors
  fetched by id (`WHERE doc_id IN (...)`, ids bound).
  Survivors are scored by the same linear dense-cosine
  scan — no index, no approximation — and results +
  RM-053 `last_search_stats` are bit-for-bit the old
  road's. RM-040 audit site total 57 → 59. Gate script
  `huginn/scripts/vector_scan.py` seeds 10,000 docs via
  the public upsert API (store 74,694,656 bytes) and a
  constructed 100,000-doc store (direct construction
  stated in the record; term index intentionally empty),
  parity-verified against a brute-force raw-table
  reference inside every run, one full run per tree.
  Gate medians: api 12,299.3 → 6,233.0 / 2,337.0 →
  982.5 / 3,586.7 → 1,704.8 ms; scale 101,700.6 →
  124,250.4 / 9,255.2 → 20,908.3 / 16,361.6 →
  32,315.4 ms. A controlled back-to-back pair on the
  same stores leaned the other way at both scales
  (api 13,934.4 → 16,790.2 / 1,196.5 → 2,165.7 /
  3,011.0 → 4,387.2; scale 157,713.2 → 106,831.6 /
  14,982.4 → 11,487.3 / 28,596.6 → 21,853.7) while the
  1-minute load rose ~9 → ~16 under concurrent campaign
  suites — **no wall-clock win or regression claimed
  either way** (survivor decode+score dominates; even
  the old full-table transfer is a minority cost on a
  warm tmpfs store). **Verdict, as the roadmap
  directed: the linear scan stands at personal-store
  scale; no ANN index built.** The prefilter is kept on
  the load-independent evidence: filtered/capped
  vector transfer is now proportional to survivors
  (statement-shape-pinned) and excluded vectors are
  never fetched or decoded. Record at
  `huginn/scripts/vector_scan.json` (after run,
  2026-11-02T20:42:38Z, load [5.12, 7.91, 7.72]); human
  record `docs/VECTOR_SCAN.md`; BENCHMARKS pointer;
  QUERY_COST_CAPS / HUGINN_GUIDE / ARCHITECTURE /
  API_REFERENCE notes. New `tests/test_vector_scan.py`
  (7, huginn only). Negation vs RM-061 tree:
  vector-scan **3 failed / 4 passed** (parities pass on
  both trees), sql-injection **2 failed**, slice-log
  **2 failed** per package. No public signature, table,
  column or index changed; **Bifröst re-verification
  run anyway as a precaution (RM-059 pattern): PASS**
  (fresh venv on `/var/tmp`, bifrost source from the
  git-clean pinned b66e98cc checkout — its own suites
  **25 passed**; BifrostBridge smoke PASS — store
  mimir_id+huginn_id, search 1 merged result, recall
  grew the Muninn activation log exactly +1,
  decay/consolidate reports, `decay_wall_clock()` armed
  at 0 days, stats over all three backends, both raven
  health dicts carry `sqlite_version` 3.45.1, huginn
  local via auto-fallback, double close safe; evidence
  `/var/tmp/rm062/evidence/`). Full suites on the final
  banking tree (non-editable installs from a full-repo
  copy, encryption + qdrant extras, cryptography
  50.0.2, qdrant-client 1.20.0, pytest 9.2.0): huginn
  **322 passed** (315+7); muninn **396 passed**
  (slice-log pin only) — muninn's first banking run
  showed 9 failed / 387 passed, every failure
  `database or disk is full` at WAL creation after this
  slice's own gate stores + duplicate suite runs filled
  the 2 GB /var/tmp tmpfs; after clearing them the
  identical tree passed in full (the RM-039 environment
  class). Ruff clean (whole tree); mypy clean
  (mypy 1.20.2, muninn 7 files, huginn 9 files).
  Banking provenance, honestly: the slice was built by
  the previous keeper tick, which was interrupted after
  the gate runs and test writing but before the A/B
  pair finished and before any banking step; this tick
  completed the A/B pair on the surviving seeded
  stores, filled the records, ran negation + Bifröst,
  and banked. Environment: the home-quota EDQUOT
  closure flapped repeatedly (the 20 GB
  `.verify-tmp` Janas worktree store is Volmarr's
  pending decision, untouched); writes completed via
  in-place rewrites and freeing this campaign's own
  regenerable caches. Live Qdrant +
  sentence-transformers stay NOT PROVEN. Founding tree
  NEEDS A SYNC for the RM-062 build (extends the
  standing package-source sync note).
- **RM-061 BANKED 2026-11-02 (keeper tick ~14:03 EST):**
  Huginn candidate generation — BENCH + UNIT. Local
  TF-IDF search gains posting-list pruning: from the
  query terms' posting lists alone the backend computes
  each candidate's exact dot product and a lower bound
  on its full vector norm (posting sub-norm plus the
  least the remaining terms can contribute — corpus-
  minimum idf floor times the remaining token count
  from one `SUM(tf)` aggregate), giving a true upper
  bound on the cosine score. Candidates are fully
  scored best-bound-first in batches of 128; once
  `limit` exact scores stand, a candidate whose bound
  (with a `(1 + 1e-9)` safety factor) cannot beat — or
  tie-and-outrank by the RM-011 id tie-break — the
  limit-th score is pruned without its term set ever
  being fetched. Pruning is EXACT: results are the
  unpruned search's results, proven by parity tests
  against a brute-force reference computed from the
  raw tables and re-verified inside the gate script on
  every run. `last_search_stats` gains
  `candidates_pruned` (always 0 on the vector road);
  RM-040 audit site total 53 → 57. Gate script
  `huginn/scripts/candidate_pruning.py` seeds the
  RM-020 benchmark corpus (5,000 texts dedupe to 230
  stored documents) and a new 10,000-document distinct
  corpus, three runs per tree. Structural result
  (load-independent): benchmark candidates **230 → 128
  scored, 102 pruned** on every after run; distinct
  candidates **pruned 0** of 1,129 / 853 / 1,168.
  Timings indicative only and honestly load-confounded
  (1-minute loads 1.9–14.4 across the runs): medians of
  three runs, benchmark 44.4 → 102.6 ms, distinct
  689.6 → 1,082.5 ms; a controlled back-to-back pair on
  a 3,000-document distinct store measured 198.9 →
  301.1 ms — where the bound prunes nothing the new
  road costs ~1.5×, and the record says so. The
  weakness is measured, not guessed: one corpus-wide
  term collapses the idf floor (benchmark `raven` in
  230/230 documents, floor ≈ 0.002; distinct `term766`
  in 6,990/10,000, floor 0.358 against query-term idfs
  ~3.1–3.7), and on long documents the bound norm sits
  far under the true norm (sampled 3.85 vs 17.54), so
  no distinct candidate's bound ever clears the
  threshold; a tighter bound is WAND-family future
  work, named in the record, not smuggled in. Batch
  size raised 64 → 128 during the slice's own gate
  runs. Record at `huginn/scripts/candidate_pruning.json`
  (after tree's third run, recorded
  2026-11-02T18:23:17Z, load [1.90, 6.47, 7.19]); human
  record `docs/CANDIDATE_PRUNING.md`; BENCHMARKS.md
  pointer; QUERY_COST_CAPS.md gained the
  `candidates_pruned` field note. New
  `tests/test_candidate_pruning.py` (9, huginn only).
  Negation vs the RM-060 tree: candidate-pruning suite
  **5 failed / 4 passed** (parities pass on both trees),
  query-cost-caps **2 failed**, sql-injection **2
  failed**, slice-log pins **2 failed** per package.
  **Bifröst re-verification PASS** (public API grew
  additively; fresh venv on `/var/tmp`, bifrost source
  diff-identical to the pinned b66e98cc checkout — its
  own suites **25 passed**; BifrostBridge smoke PASS —
  store mimir_id+huginn_id, search merged results,
  recall grew the Muninn activation log exactly +1,
  decay/consolidate reports, `decay_wall_clock()` armed
  at 0 days, stats over all three backends, both raven
  health dicts carry `sqlite_version` 3.45.1, huginn
  local via auto-fallback, double close safe; smoke ran
  with `HOME` on `/var/tmp` scratch, the RM-060
  adaptation; evidence `/var/tmp/rm061evidence/`).
  Full suites green on the final banking tree
  (non-editable installs from a full-repo copy,
  encryption + qdrant extras, cryptography 50.0.2,
  qdrant-client 1.20.0, pytest 9.2.0): huginn **315
  passed** (306+9), muninn **396 passed** (unchanged;
  slice-log pin only). Ruff clean (whole tree); mypy
  clean in a deps-free tool venv (muninn 7 files,
  huginn 9 files). Banking provenance, honestly: the
  slice was built by the previous keeper tick, which
  was interrupted after the gate runs and the banking
  suite runs (logs at `/var/tmp/rm061-bank/`, huginn
  315 / muninn 396 on a tree this tick diff-verified
  byte-identical to the working tree) but before the
  Bifröst run completed and before any commit; this
  tick re-ran the targeted suites fresh (huginn
  candidate-pruning + cost-caps + SQL audit + slice-log
  **26 passed**, muninn slice-log **2 passed**), re-ran
  ruff + mypy clean, completed the Bifröst
  re-verification above, and banked. Environment: the
  home-quota EDQUOT closure bit at the banking edit;
  writes reopened after this keeper freed the shared
  pip/uv/Hugging Face caches and the repo's lint/type
  caches (regenerable scratch only). Live Qdrant +
  sentence-transformers stay NOT PROVEN. Founding tree
  NEEDS A SYNC for the RM-061 build (extends the
  standing package-source sync note).
- **RM-060 BANKED 2026-11-02 (keeper tick ~10:36 EST):**
  bulk remember — BENCH. Muninn gains
  `remember_many(items) -> list[int]`: item dicts
  carrying `remember`'s arguments by name (`content`
  required; `category`, `path`, `importance`, `tags`,
  `emotional_valence`, `metadata` optional, same
  defaults), ids in input order. Contract per the
  roadmap — one transaction, one content-hash pass,
  backpressure applied once: `remember`'s preparation
  was extracted as `_prepare_remember` (validate +
  serialize + the one hash) and its insert as
  `_insert_prepared_locked`, both shared by the two
  roads, so semantics cannot drift and the RM-040
  audit total is unchanged at 98 sites (no new SQL
  shape). Every item is prepared before the transaction
  opens; all inserts land or none do — an invalid item
  or an RM-047 collision (against the store or within
  the batch) rolls the whole batch back, deliberately
  stricter than a loop; one `_tick()` stamps the batch
  (the `activate_batch` discipline); the `max_nodes`
  check runs once after the commit. Per-item
  idempotency is `remember`'s (first write wins; an
  in-batch duplicate shares its first id). Item shape
  is closed — four new typed refusals pinned as RM-018
  CASE + TEMPLATE lines (61 → 65 cases, 87 → 91
  templates). New gate script
  `muninn/scripts/bulk_remember.py` ingests 10,000
  distinct RM-020-corpus nodes into a fresh store by
  the loop and by the batch, verifying both roads
  built logically identical stores (same ids in order,
  same per-node fields excluding timestamps) inside
  every run before quoting timings. Three full runs
  (each the median of 3 ingests per road, tmpfs):
  loop 2,079.9 / 1,603.2 / 1,028.6 ms, batch 677.7 /
  603.9 / 367.4 ms — **medians of the runs: loop
  1,603.2 ms → batch 603.9 ms, 2.65×** (per-run
  speedups 3.07× / 2.65× / 2.80×), indicative only —
  1-minute load 3.6–4.6 and the loop's own time swung
  2× between runs; the durable claim is the
  test-pinned shape (one COMMIT + one backpressure
  count per batch, counted by trace callback). Record
  at `muninn/scripts/bulk_remember.json` (third run,
  recorded 2026-11-02T15:52:31Z, load [4.58, 3.79,
  4.25]); human record `docs/BULK_REMEMBER.md`;
  BENCHMARKS.md pointer. New
  `tests/test_bulk_remember.py` (17, muninn only);
  RM-013 matrix gains row M-30 with its test; RM-019
  golden gained the two `remember_many` lines;
  `test_slice_log.py` EXPECTED to RM-060 in both.
  Negation vs the RM-059 tree: bulk suite **17 failed
  / 0 passed**, idempotency **1 failed / 30 passed**
  (M-30 only), error messages **2 failed / 1 passed**,
  API surface **1 failed / 2 passed**, SQL audit 9
  passed (unchanged, as designed), slice-log pins
  **2 failed** per package. **Bifröst
  re-verification PASS** (public API grew additively;
  fresh venv on `/var/tmp`, bifrost at b66e98cc —
  its own suites **25 passed**; BifrostBridge smoke
  PASS — store mimir_id+huginn_id, search 1 merged
  result, recall grew the Muninn activation log
  exactly +1, decay/consolidate reports,
  `decay_wall_clock()` armed at 0 days, stats over
  all three backends, both raven health dicts carry
  `sqlite_version` 3.45.1, huginn local via
  auto-fallback, double close safe; evidence
  `/var/tmp/rm060evidence/`). One smoke adaptation,
  recorded honestly: the bridge's Huginn uses its
  default store path under `$HOME`, and the live
  Hermes store there could not open while the home
  quota was shut (its WAL creation draws the typed
  read-only refusal), so the smoke ran with `HOME`
  pointed at scratch on `/var/tmp` — the same bridge,
  packages and assertions, the default store in
  scratch instead of the live one. Suites in the
  RM-060 fresh venv on the final banking tree
  (non-editable installs from a full-repo copy,
  encryption + qdrant extras, cryptography 50.0.2,
  qdrant-client 1.20.0, pytest 9.2.0): huginn **306
  passed** in one full run (its first attempt died
  at collection on an EDQUOT pycache creation; the
  green run used `PYTHONDONTWRITEBYTECODE=1`, TMPDIR
  on `/var/tmp`); muninn **396 passed** (378+18)
  **assembled per-file, all 57 test files green**,
  after two full-run attempts died with a fatal Bus
  error mid-suite (`close()` in
  `test_contract_freeze`, then `activate` in
  `test_benchmark_atlas` — both files pass alone and
  in the assembly; the RM-039 environment class:
  SQLite WAL `-shm` faults while the quota is shut
  under multi-campaign write load). Ruff clean
  (whole tree, `--no-cache` under the quota flaps);
  mypy clean in a deps-free tool venv (muninn 7
  files, huginn 9 files). Environment incidents:
  the home-quota EDQUOT closure flapped shut
  repeatedly all tick (the first banking-venv
  install, the huginn collection, several doc
  writes); writes reopened after this keeper freed
  the shared pip/uv caches, this tick's spent
  negation worktree and banking venv, and the spent
  RM-058/RM-059 `/var/tmp` venv dirs of this
  campaign (regenerable scratch only; the RM-058
  dir also held a bifrost checkout copy — three
  checkouts at the same pinned b66e98cc survive in
  `~/workspace/.verify-tmp/`, and the verification
  above ran from one of them via a `/var/tmp`
  copy). Slice-internal repairs: none in package
  code — one test-design fix (the backpressure
  test's importance grading first ran past the
  1–10 cap and was re-graded before any run was
  recorded). Live Qdrant + sentence-transformers
  stay NOT PROVEN. Founding tree NEEDS A SYNC for
  the `remember_many` build (extends the standing
  package-source sync note).
- **RM-059 BANKED 2026-11-02 (keeper tick ~10:06 EST):**
  Muninn activation write path — BENCH + UNIT. New gate
  script `muninn/scripts/write_path.py` profiles
  `activate` (same id / distinct ids on a 2,000-node
  store), `activate_batch(5)` and
  `retrieve(..., touch=True)`, and counts the SQL
  statements one `activate()` executes by trace callback
  — run unchanged on both trees, three full runs per
  tree, medians reported. Before: **5 statements** per
  activation [INSERT log, INSERT counter upsert, UPDATE
  nodes, DELETE tombstone, SELECT re-read of the total
  the upsert had just written]. Two changes: (1) the
  counter upsert carries `RETURNING total_activations`
  on SQLite 3.35+, folding the re-read into the write —
  **4 statements** [INSERT, INSERT, UPDATE, DELETE],
  the floor without a schema/trigger change (four
  distinct tables change); older runtimes (WAL floor
  3.7.0) keep the upsert + re-read road behind
  `muninn.core._RETURNING_OK`, semantics identical,
  fallback test-pinned with the flag forced off.
  (2) The RM-050 attestation head write (head + count
  meta rows) is one combined
  `INSERT OR REPLACE … VALUES (?, ?), (?, ?)` instead of
  an executemany of two. Gate timings (medians of 3,
  tmpfs) recorded as indicative only and honestly
  load-confounded (before runs at load 8.6–9.5, after
  runs at 0.9–5.9): same id ×2000 215.8 → 205.9 ms;
  distinct ×2000 256.7 → 213.3 ms; batch(5) ×400
  394.4 → 211.9 ms; retrieve(touch) ×200 11,791.6 →
  8,300.9 ms — the statement count is the hard gate.
  Record at `muninn/scripts/write_path.json` (after
  tree's third run, recorded 2026-11-02T15:19:39Z,
  load [5.93, 4.73, 4.78]); human record
  `docs/WRITE_PATH.md`; BENCHMARKS.md pointer. New
  `tests/test_write_path.py` (10, muninn only):
  statement counts + shapes on both roads, attested
  head as one meta statement + chain verifies on
  reopen, count-exact semantics vs raw-SQL ground truth
  (sequential totals; log/counter/access equality
  across live, forgotten and never-remembered ids;
  tombstone clearing; confidence formula after decay;
  small-batch pair reports; touch counts), gate-script
  shape + committed record. RM-040 audit site total
  97 → 98 (fallback upsert = second constant form);
  `test_slice_log.py` EXPECTED to RM-059 in both.
  Negation vs RM-058 tree: muninn **8 failed / 13
  passed** (failures exactly on the new pins; the
  count-exact semantics pass on both trees), huginn
  **2 failed / 0 passed**. No public API, signature,
  return shape, table, column or index changed, so no
  Bifröst re-verification was required by the standing
  rule; run anyway as a precaution: **PASS** (fresh
  venv, bifrost at b66e98cc — its own suites **25
  passed**; BifrostBridge smoke PASS, evidence
  `/var/tmp/rm059/evidence/`). Full suites green in
  the RM-059 fresh venv on the final banking tree
  (non-editable installs from a full-repo copy,
  encryption + qdrant extras, cryptography 50.0.2,
  qdrant-client 1.20.0, pytest 9.2.0): muninn **378
  passed** (368+10), huginn **306 passed** (slice-log
  pin only); ruff clean (both packages, whole tree);
  mypy clean in a deps-free tool venv (muninn 7 files,
  huginn 9 files). Slice-internal repairs: the first
  gate-script run crashed on `retrieve(limit=)` (the
  parameter is `top_k`) — fixed before any before-run
  was recorded; two new-test bugs fixed in-slice (Row
  objects vs tuples in the raw-SQL helper; the fallback
  road's SELECT sits between upsert and node update,
  not last). Live Qdrant + sentence-transformers stay
  NOT PROVEN. Founding tree NEEDS A SYNC for the
  RETURNING upsert + combined head write (extends the
  standing package-source sync note).
- **RM-058 BANKED 2026-11-02 (keeper tick ~09:06 EST):**
  Muninn read path — BENCH. New gate script
  `muninn/scripts/read_path.py` profiles
  `get_associations` + `spread_activation` at 100k
  edges (5,000-node ring, 100,000 directed rows, degree
  20; hub with 10,000 spokes, 20,000 directed rows),
  run unchanged on the pre- and post-slice trees, three
  full runs per tree, medians reported. Pain found at
  the hub only: limited `get_associations` fetched and
  temp-b-tree-sorted all 10,000 hub rows (~10 ms/call),
  and hub depth-2 spread issued one query per frontier
  node (10,001 queries) plus a redundant Python re-sort.
  Two changes: (1) covering index `idx_conn_a_strength`
  (memory_a_id, strength DESC, co_activation_count DESC,
  memory_b_id ASC, consolidated, last_coactivated_at as
  trailing keys — this machine's SQLite build rejects
  `INCLUDE` outright, probed on 3.45.1); no table/column
  change, created by the schema script on every open so
  pre-RM-058 stores gain it on next open (test-pinned);
  RM-004 golden extended deliberately, FORMAT_STABILITY
  names the index. (2) `spread_activation` reads each
  depth level in chunks of 500 frontier ids (bound
  `IN (...)`, ORDER BY a, b) — exactly the old walk's
  candidate order, so results and the RM-053 cap bite
  are bit-for-bit preserved (parity vs an independent
  reference walk pinned, incl. a cap bite inside the
  second chunk); new SQL shape pinned in the RM-040
  audit templates, site total unchanged. Gate numbers
  (medians of 3, tmpfs, loaded VM): hub get limit=100
  ×20 **207.2 → 3.1 ms (~67×)**; hub get limit=10000
  ×20 1,870.9 → 1,091.4 ms (~1.7×); hub spread depth2
  **208.3 → 95.3 ms (~2.2×)**; hub spread depth1 71.1 →
  76.9 ms (no win claimed); uniform reads flat. After
  plan: COVERING INDEX idx_conn_a_strength, no temp
  b-tree. Record at `muninn/scripts/read_path.json`
  (after tree's third run, recorded
  2026-11-02T14:24:28Z, load [1.98, 2.89, 3.60]);
  human record `docs/READ_PATH.md`;
  BENCHMARKS.md pointer. New
  `tests/test_read_path.py` (10, muninn only);
  `test_slice_log.py` EXPECTED to RM-058 in both.
  Negation vs RM-057 tree: muninn **12 failed / 13
  passed** (failures exactly on the new pins; parity
  passes on both trees), huginn **2 failed / 0 passed**.
  **Bifröst re-verification PASS** (fresh venv,
  bifrost at b66e98cc — its own suites **25 passed**;
  BifrostBridge smoke PASS, evidence
  `/var/tmp/rm058/evidence/`). Full suites green in
  the RM-058 fresh venv on the final banking tree
  (non-editable installs, encryption + qdrant extras,
  cryptography 50.0.2, qdrant-client 1.20.0, pytest
  9.2.0): muninn **368 passed** (358+10), huginn
  **306 passed**; ruff clean (both packages, whole
  tree); mypy clean in a deps-free tool venv (muninn
  7 files, huginn 9 files). Slice-internal repairs:
  the first after-run crashed on the `INCLUDE` clause
  (this SQLite build rejects it — index rebuilt with
  trailing keys); the RM-058 golden first missed the
  wrapped DDL's stored `( memory_a_id` form and
  FORMAT_STABILITY's index-naming pin caught the new
  index unnamed — both fixed and re-verified in-slice;
  a first suite run from a package-only copy skipped
  34 repo-root tests, so the banking suites were run
  from a full-repo copy (368/306, no skips).
  Environment incidents: home-quota EDQUOT closed
  repeatedly (freed: this campaign's spent RM-057
  venvs, the shared pip cache, repo build/pycache
  scratch); a service restart wiped /var/tmp mid-tick,
  losing the first RM-058 venv set (rebuilt; all bench
  records survived on home disk). No public API or
  return-shape change. Live Qdrant +
  sentence-transformers stay NOT PROVEN. Founding tree
  NEEDS A SYNC for the index + batched spread build
  (extends the standing package-source sync note).
- **RM-057 BANKED 2026-11-02 (keeper tick ~08:06 EST):**
  baseline atlas — Part V (Speed) opens. New
  `scripts/atlas.py` in both packages extends the
  RM-005/006 harness to 1k / 10k / 100k nodes and
  documents for every headline operation, reusing the
  RM-020 corpus generators and RM-006 environment block;
  the seed is the write operation and all other ops use
  fixed sample batches identical at every scale, so the
  tables show cost growth with store size only. Records
  committed at `muninn/scripts/atlas.json` (recorded
  2026-11-02T13:33:00Z, load [1.26, 5.46, 5.24]) and
  `huginn/scripts/atlas.json` (recorded
  2026-11-02T13:40:22Z, load [2.39, 5.94, 5.71]); human
  record in `docs/ATLAS.md`, pointer in
  `docs/BENCHMARKS.md`. Headline findings from the
  records: Muninn reads flat to 100k (get_associations
  ×1000 185.7/86.5/87.2 ms; spread ×200 218.0/88.2/
  108.7 ms) while **stats() is the outlier** (×200
  322.5/1,794.2/31,790.6 ms ≈ 1.6/9.0/159 ms per call);
  decay/consolidate at 100k ~0.5–0.6 s; Huginn upsert a
  steady ~1.0–1.4 ms/doc (100k in 101,382.0 ms).
  Honesty items carried in the record, not buried: (1)
  Muninn's atlas raises `max_nodes` (default 20,000) to
  an exact fit per scale, filed as `config_overrides`
  — a default-config seed provably stalls at 20,001
  nodes (its leftover store counted on disk), so the
  100k row would otherwise be false; the record's
  `store_after_seed.total_nodes` equals the scale at
  all three scales. (2) Stores on **tmpfs**, the RM-005
  storage class; controlled A/B in this tick: 2,000
  activate 172.6 ms tmpfs vs 58,843.2 ms overlay disk
  (~340×) — write numbers are tmpfs numbers. (3) The
  Huginn corpus holds only **23 distinct documents**;
  RM-053 accounting filed per scale shows a
  230-candidate pool at every scale, cap never biting,
  so search cost over 100k *distinct* documents is NOT
  measured — named as the gap RM-061/RM-062 must close
  (Muninn's corpus is 100,000 of 100,000 distinct).
  (4) The 100k Muninn seed (577,093.1 ms) is a load
  artefact of a shared VM and is labelled as such.
  Slice-internal repairs: the first Muninn run's 100k
  row was discarded unrecorded once the prune was
  proven; the first Huginn run crashed on
  `last_search_stats` called as a method (it is
  RM-053's facade property) — fixed and re-run, then
  re-run once more to file the unfiltered search's
  accounting beside the filtered one's. New
  `tests/test_benchmark_atlas.py` (5 per package);
  `test_slice_log.py` EXPECTED extended to RM-057 in
  both. Negation against the RM-056 tree: **7 failed /
  0 passed per package** (5 atlas + 2 slice-log),
  failures exactly on the missing atlas files and
  entry. Full suites green in the RM-057 fresh venv on
  the final banking tree (non-editable installs,
  encryption + qdrant extras, cryptography 50.0.2,
  qdrant-client 1.20.0, pytest 9.2.0): muninn **358
  passed** (353+5), huginn **306 passed** (301+5).
  Suite history, honestly: a first muninn pass showed
  1 failed / 357 passed — the huge-batch child died on
  `database or disk is full` because this slice's own
  atlas leftovers had filled the 512 MB /tmp tmpfs;
  after clearing them the identical tree passed in
  full, an environment casualty in the RM-039 pattern.
  Ruff check clean (both packages, whole tree); mypy
  clean in a deps-free tool venv per package (muninn
  7 files, huginn 9 files — the deps venv's mypy trips
  on numpy stubs in the qdrant chain, the known reason
  the floor runs deps-free). Environment incidents:
  the home-quota EDQUOT closure bit three times this
  tick (negation scratch, atlas.json writes, the first
  huginn install — which silently half-installed and
  was redone); each time writes reopened after
  clearing only regenerable scratch (shared pip cache,
  the spent ravens-rm056-venv, rm055 negation dirs).
  Runtime output previews also proved unreliable
  twice this tick (a phantom completion notice and
  progress lines ahead of the disk); every number in
  this entry was read from the committed JSON records
  and suite logs on disk. No package source, public
  API, or schema change (scripts + records + tests +
  docs only), so no Bifröst re-verification required.
  Live Qdrant + sentence-transformers stay NOT PROVEN.
  Founding tree needs no sync for this slice; the
  standing Part II–IV package-source sync note stands.
- **RM-056 BANKED 2026-11-02 (keeper tick ~07:26 EST):**
  Part IV gate — TH-16 closed. Security evidence bundle
  filed at `docs/PART_IV_EVIDENCE.md` (every Part IV
  slice checked off with its banking suites; every
  FAULT result filed — RM-049 encryption build, RM-050
  attestation, RM-051 secure forget, each with record,
  acceptance and negation counts; Bifröst
  re-verifications inside the part RM-041/049/050/051/
  053/054 six for six green, RM-046 also ran it as a
  precaution; floors; honesty ledger unchanged — live
  Qdrant, sentence-transformers, GitHub-hosted CI all
  NOT PROVEN, `cryptography` extra proven from RM-049;
  debts named, incl. the founding-tree sync owed for
  every Part IV package-source change). **Threat model
  updated with what the part actually built**:
  `docs/THREAT_MODEL.md` carries an RM-056 banner, every
  register State cell updated (Controlled: TH-01, 03,
  04, 05, 08, 11, 12, 13, 14, 15, TH-16 at this gate;
  Partial by stated design: TH-02, 06, 07, 09, 10, 19;
  Accepted unchanged: TH-20, 21; Controlled unchanged:
  TH-17, 18), and a full RM-056 re-review section
  (threat-by-threat evidence + TB-2/TB-5/TB-6 boundary
  notes); no threat found that RM-039 did not name, no
  entry deleted, RM-039 text otherwise preserved. New
  `tests/test_part_iv_gate.py` (3 tests each package:
  bundle names every Part IV slice, files every FAULT
  result + honesty ledger, threat model carries the
  re-review + updated register); `test_slice_log.py`
  EXPECTED pins extended to RM-056 in both. Negation:
  gate tests against a scratch tree whose bundle omits
  a slice name + a FAULT marker and whose model omits
  the re-review markers: **3 failed / 0 passed per
  package**, failures exactly on the doctored pins.
  Full suites green in the RM-056 fresh venv on the
  final banking tree (non-editable installs,
  encryption + qdrant extras, cryptography 50.0.2,
  qdrant-client 1.20.0, pytest 9.2.0): muninn **353
  passed** (350+3; TMPDIR on `~/workspace/.verify-tmp`,
  369.6 s under load), huginn **301 passed** (298+3;
  26.0 s). Huginn verification note, honestly: two
  earlier huginn attempts in this tick died under the
  home-quota EDQUOT closure (exit 120, truncated logs,
  one F shown mid-run while writes were blocked — the
  RM-039 environment pattern), and the green run was
  taken after the host reboot with TMPDIR on `/tmp`;
  the identical final tree passed in full, so the F is
  recorded as a quota casualty, not a code failure.
  The pip install road also hit EDQUOT twice; writes
  reopened after this keeper cleared the shared pip
  cache and this campaign's spent RM-055 venv
  (regenerable scratch only). Ruff check clean (both
  packages, whole tree); mypy clean in a deps-free tool
  venv run per package (muninn 7 files, huginn 9
  files). No package source, public API, or schema
  change (docs + tests only), so no Bifröst
  re-verification required for the gate itself. Live
  Qdrant + sentence-transformers stay NOT PROVEN.
  Founding tree needs no NEW sync for this slice; the
  Part IV package-source sync note stands (named in
  the bundle's debts). **Part IV is complete.**
- **RM-055 BANKED 2026-11-02 (keeper tick ~07:05 EST):**
  secure defaults review — TH-15, record in
  `docs/SECURE_DEFAULTS.md`. All 38 config fields
  (MuninnConfig 19, HuginnConfig 19) re-judged in four
  classes (safe-off/safe-none, safety-positive on,
  bounded, compatibility-kept) and **no default
  changed**: every default that could leak content,
  weaken transport, execute or download is already off,
  loopback-confined, or opt-in; every on default is
  safety-positive (backups on, keep 3, permissions
  inherited) or bounded (finite 5000 ms / 2.0 s timeouts,
  validated ceilings); the compatibility-kept three are
  named plainly — `strict_path_safety=False` in both
  (recorded behaviour; the opt-in is the locked-down
  road), Huginn `backend="auto"` (Bifröst no-config
  contract; fallback not silent — lazy loopback probe,
  reason + effective backend in `health()`;
  `backend="local"` never touches the network), and
  `store_encryption` / `integrity_attestation` off (each
  needs a passphrase a default must never invent; a
  marked store refuses unprotected opens). **Drift found
  and fixed in-slice:** `store_encryption` and
  `encryption_passphrase` were missing from both guides'
  config tables and the API_REFERENCE config listings had
  drifted behind RM-049/RM-050/RM-053 — rows and listings
  added; the new suites pin that the guide names every
  field. New `tests/test_secure_defaults.py` (muninn 7,
  huginn 8) pin every field's exact default, the field
  set itself, flag postures, no invented secret, bounded
  waits/ceilings, and Huginn's default transport posture.
  Negation against the RM-054 tree: muninn **2 failed /
  5 passed**, huginn **2 failed / 6 passed** (failures are
  exactly the record/guide pins; passes are the defaults
  already reviewed-safe — the expected shape when no
  default changes). Full suites green in the RM-055
  fresh venv on the final banking tree (TMPDIR +
  installs on `~/workspace/.verify-tmp` — `/var/tmp` was
  at 91% with prior slices' venvs; encryption + qdrant
  extras installed): muninn **350 passed** (343+7),
  huginn **298 passed** (290+8); ruff check clean on the
  touched test files (a style-only Yoda-condition fix to
  the two new test files after the full run was
  re-verified targeted: 7 + 8 passed). No package source,
  public API, or schema change (docs + tests only), so
  no Bifröst re-verification required. Live Qdrant +
  sentence-transformers stay NOT PROVEN. Founding tree
  needs no sync for this slice; the standing
  package-source sync note stands. TH-15's register
  update remains RM-056's.
- **RM-054 BANKED 2026-11-02 (keeper tick ~06:26 EST):**
  error-message hygiene — TH-14, record in
  `docs/ERROR_MESSAGE_HYGIENE.md`. Fourteen wrap sites
  interpolated uncontrolled exception *text* (six SQLite
  sites per both packages — the two
  `could not be prepared` branches and the write guard's
  generic branch — plus Huginn's eight Qdrant wraps,
  which since RM-045 carried client text key-masked
  only). The leak is proven, not theoretical: a store
  trigger's `RAISE(ABORT, '…')` text — file content —
  rode verbatim into the typed error on both roads in a
  probe against the RM-053 tree. Rule now: a typed
  message is built only from fixed text,
  package-computed values, the caller's own supplied
  store path / Qdrant URL / collection name, and the
  underlying exception's **class name** (`_error_kind`
  in both `_db.py`; Qdrant's `_scrub` seam kept, contract
  changed); the full text stays on the exception chain
  only. Write guards gained a classified disk-full
  branch (`_is_full_error`: SQLITE_FULL code 13 or the
  canonical wording) emitting the package's own fixed
  `database or disk is full` text — RM-029's shape kept
  without echoing. Deliberate changes recorded per
  RM-018: seven Qdrant CASE lines now end in
  `RuntimeError`; RM-045 transport tests assert absence
  of the whole client wording (facade still key-scrubs
  reported strings as defence in depth); `could not be
  prepared` and the generic write-guard branch gained
  deterministic CASE triggers (goldens 61 / 69 cases;
  template counts corrected to the true 87 / 90, one new
  fixed disk-full template each). New
  `tests/test_error_message_hygiene.py` (muninn 7,
  huginn 8) incl. the combined planted-leak scan
  (content + foreign path + Qdrant key + both
  passphrases, in trigger text, client text and
  wrong-passphrase attempts; Huginn's health error,
  fallback reason and flight error also scanned) and an
  AST pin on exception interpolation. Negation against
  the RM-053 tree: muninn **5 failed / 2 passed**,
  huginn **5 failed / 3 passed**. **Bifröst
  re-verification PASS** (fresh venv
  `ravens-rm054-bifrost-venv` on `/var/tmp`, bifrost at
  b66e98cc — its own suites **25 passed**; BifrostBridge
  smoke PASS, evidence `/var/tmp/rm054-evidence/`).
  Full suites green in the RM-054 fresh venv on the
  final banking tree (TMPDIR + installs on `/var/tmp`,
  encryption extra installed): muninn **343 passed**
  (336+7), huginn **290 passed** (282+8); ruff check
  clean; mypy clean in the RM-052 deps-free tool venv
  (muninn 7 files, huginn 9 files). No schema or public
  signature change (RM-004 / RM-019 goldens unmoved);
  no new dependency. Live Qdrant +
  sentence-transformers stay NOT PROVEN. Founding tree
  NEEDS A SYNC for the RM-054 build (extends the
  standing package-source sync note). TH-14's register
  update remains RM-056's.
- **RM-053 BANKED 2026-11-02 (keeper tick ~05:56 EST):**
  denial-of-service bounds — TH-13, record in
  `docs/QUERY_COST_CAPS.md`. Muninn gains
  `max_spread_candidates: int = 100000` (candidate edges
  one `spread_activation` call may examine; frontier and
  neighbours in id order so a bite is deterministic) and
  Huginn gains `max_search_candidates: int = 10000`
  (candidate documents one local search may score;
  lowest ids first; cap before the category/importance
  filter; vector road decodes only surviving
  candidates' vectors). A bite returns the partial
  result — never an error — and is visible in Muninn's
  `last_spread_activation_stats` attribute and Huginn's
  new `last_search_stats` facade property (counts +
  `capped`), plus a counts-only WARNING log.
  **Design correction in-slice:** the first draft put
  the record in `stats()`/`health()` and failed the
  RM-009 read-purity pin (M09) — those snapshots are
  pinned pure, so the accounting moved to the dedicated
  accessors; the new suites pin capped calls leaving
  both snapshots byte-identical. Below the ceilings,
  behaviour is exactly the unbounded behaviour. Qdrant
  search out of scope (server owns its cost); Muninn
  `retrieve`'s scan is `max_nodes`-bounded, no second
  ceiling — both stated in the record. New
  `tests/test_query_cost_caps.py` (muninn 7, huginn 8)
  incl. the BENCH acceptance (fully connected 25-node
  graph at ceiling 200 examines exactly 200, capped;
  12-doc one-term corpus at ceiling 5 scores 5 of 12).
  Negation against the RM-052 tree: muninn **7 failed /
  0 passed**, huginn **8 failed / 0 passed**. RM-018
  goldens gained the two config cases; RM-019 goldens
  gained the fields + the Huginn property; RM-004
  schema goldens unmoved; no new dependency.
  **Bifröst re-verification PASS** (fresh venv
  `ravens-rm053-bifrost-venv` on `/var/tmp`, bifrost at
  b66e98cc — its own suites **25 passed**; BifrostBridge
  smoke PASS, evidence `/var/tmp/rm053-evidence/`).
  Full suites green in the RM-053 fresh venv on the
  final banking tree (TMPDIR + installs on `/var/tmp`,
  encryption extra installed): muninn **336 passed**
  (329+7), huginn **282 passed** (274+8); ruff check
  clean; mypy clean in the RM-052 deps-free tool venv
  (muninn 7 files, huginn 9 files). Live Qdrant +
  sentence-transformers stay NOT PROVEN. Founding tree
  NEEDS A SYNC for the RM-053 build (extends the
  standing package-source sync note). TH-13's register
  update remains RM-056's.
- **RM-052 BANKED 2026-11-02 (keeper tick ~05:26 EST):**
  dependency hygiene — TH-12, record in
  `docs/DEPENDENCY_HYGIENE.md`. The inventory, now
  test-pinned in both packages (`test_dependency_
  hygiene.py`, 7 tests each): both cores dependency-free
  and every declared requirement (build setuptools,
  cryptography, qdrant-client, sentence-transformers,
  the four dev tools) carries a `>=floor,<ceiling` bound
  with no direct references. Lockfile example added at
  `docs/examples/requirements-lock.example.txt` — the
  exact 23-pin closure pip resolved for
  `muninn[encryption]` + `huginn[encryption,qdrant]` on
  CPython 3.12.3 (frozen 2026-11-02 from this tick's
  venv; generation road + embeddings/dev exclusions in
  its header and the record). The manual CI gains a
  `dependency-scan` job (bounded `pip-audit>=2.7,<3`,
  2.10.1 at this slice; scans the lockfile example and
  an installed runtime + dev environment; parsed-YAML
  check: trigger still exactly `workflow_dispatch`).
  **Found and fixed in-slice (never-leave-a-bug):** the
  slice's own locally run scan flagged PYSEC-2026-1845
  in pytest 8.4.2 — the newest the old dev bound
  `pytest>=7,<9` allowed — whose fix (9.0.3) sat
  outside the ceiling; the runtime closure scanned
  clean in the same run. Dev bound raised to
  `pytest>=7,<10` in both pyprojects + the CI install
  line (`docs/INTEGRATION.md` corrected to match); a
  hygiene test pins that the bound reaches 9.0.3.
  Post-fix, the scan environment at pytest 9.2.0 audited
  clean (environment + lockfile example) and both
  suites run green under it. Negation against the
  RM-051 tree: 5 failed / 2 passed per package (passes
  = the pre-existing truths). No package code, public
  API, or schema change, so no Bifröst re-verification
  required. Full suites green in the RM-052 fresh venv
  on the final banking tree (TMPDIR + installs on
  `/var/tmp`, encryption extra installed): muninn
  **329 passed** (322+7), huginn **274 passed**
  (267+7); ruff clean; mypy clean in a deps-free tool
  venv (muninn 7 files, huginn 9 files — the scan
  venv's numpy stubs break the 3.11-target check, an
  environment artefact, not a finding). GitHub-hosted
  CI stays NOT PROVEN (manual-only, never dispatched);
  live Qdrant + sentence-transformers stay NOT PROVEN.
  Founding tree needs no sync for this slice (no
  package source changed); the standing package-source
  sync note stands. TH-12's register update remains
  RM-056's.
- **RM-051 BANKED 2026-11-02 (keeper tick ~05:06 EST):**
  forget is forgetting — TH-11, record in
  `docs/SECURE_FORGET.md`. The audit, proven by forensic
  byte-search in the new suites: plain `forget`/`delete`
  remove the live rows only — the content persists in
  WAL frames, in freed pages of the main file (a
  checkpoint zeroing them is a build's `secure_delete`
  default, not a promise), and in every `.bak-N`
  generation until rotation; Muninn's `activation_log`
  is kept by design (ids/timestamps, never content).
  Both guides now state that truth. New public method
  `secure_forget(memory_id) -> bool` in both packages:
  `forget`/`delete`'s validation, row work (shared via
  `_forget_rows_locked` / `_delete_rows_locked`) and
  return value, then the purge — delete under
  `PRAGMA secure_delete=ON` with the connection's prior
  setting restored (`_db.secure_delete_enabled`),
  `wal_checkpoint(TRUNCATE)`, `VACUUM`,
  `wal_checkpoint(TRUNCATE)` again, and under the
  RM-037 coordination lock every `.bak-*` discarded and
  replaced by one fresh snapshot of the purged store
  when `backup_keep` allows (`_db.purge_forgotten_content`,
  twin helpers in both `_db.py` files). The purge runs
  even when nothing live was removed (remediates a past
  plain forget). Cost stated in the record + guides: a
  full store rewrite and the loss of all older backup
  generations; not atomic across stages; another opener
  holding an old snapshot can keep WAL frames alive or
  fail the rewrite typed — close other openers first.
  Huginn's Qdrant `secure_forget` is the server-side
  delete (stub-pinned); server snapshot residue is the
  operator's domain. New `tests/test_secure_forget.py`
  (muninn 10, huginn 8): before/after forensic pair in
  the WAL-resident and already-checkpointed cases, three
  generations → one fresh, `backup_keep=0`, missing-id
  purge, tombstone parity, typed validation, RM-049
  encryption composition. Negation against the RM-050
  packages: muninn **8 failed / 2 passed**, huginn **6
  failed / 2 passed** (passes = the preserved plain-
  forget truth + the record doc). One in-slice test bug
  fixed: a Huginn search assertion shared a hyphen-split
  token with the keeper doc; it now searches the
  secret's distinctive token. RM-019 goldens gained the
  method; RM-040 audit pins +8 constant sites per
  package, all in `_db.py` (muninn 89 → 97, huginn
  45 → 53); RM-018 goldens and RM-004 schema goldens
  unmoved; no new dependency. **Bifröst re-verification
  PASS** (fresh venv `ravens-rm051-bifrost-venv` on
  `/var/tmp`, bifrost at b66e98cc — its own suites **25
  passed**; BifrostBridge smoke PASS, evidence
  `/var/tmp/rm051-evidence/`). Full suites green in the
  RM-051 fresh venv on the final banking tree (TMPDIR +
  installs on `/var/tmp`, encryption extra installed):
  muninn **322 passed** (312+10), huginn **267 passed**
  (259+8); ruff + mypy floors clean (rm050 tool venv;
  mypy muninn 7 files, huginn 9 files). TH-11's
  register update remains RM-056's. Founding tree
  NEEDS A SYNC for the `secure_forget` build (extends
  the standing package-source sync note).
- **RM-050 BANKED 2026-11-02 (keeper tick ~04:26 EST):**
  integrity attestation — TH-10, record in
  `docs/INTEGRITY_ATTESTATION.md`. Muninn-only slice
  (`activation_log` exists only in Muninn; Huginn's copy
  of the work is the slice-log pin). Optional HMAC chain
  over `activation_log`, **stdlib only** (no new
  dependency): config gains `integrity_attestation:
  bool = False` + `integrity_passphrase` (repr=False;
  missing passphrase with the flag on is a typed
  configuration error). The chain key is PBKDF2-HMAC-SHA256
  from the passphrase (600,000 iterations, per-store
  16-byte salt) and is never stored — the store carries
  salt / iterations / head / chained count as `meta` rows
  only, so there is no schema change (RM-004 goldens
  unmoved, contracted table untouched). Every appending
  road chains in the row's own transaction (`activate`,
  both `activate_batch` roads incl. the RM-035 bulk road,
  `retrieve(touch=True)`), re-reading the stored head
  before each advance so a rolled-back transaction never
  leaves the in-memory chain ahead of the store.
  Verification on open recomputes over the rows as they
  stand and *reports*: the store opens and serves, the
  verdict rides on `integrity_attestation_status` and
  `health()`'s new additive `integrity_attestation` field
  (`ok` / `tamper_detected` / `not_enabled`), failures
  logged at ERROR, tampered rows left as found. A marked
  store opened without the flag refuses typed before any
  write; the judgement defers to the live connection when
  the pre-open probe cannot read the file, and a restored
  backup is judged by its own header. Enabling on an
  existing store bootstraps over the rows as found.
  Honest limits in the record: a wrong passphrase is
  indistinguishable from tampering; the chain covers
  `activation_log` only, not the whole store; detection,
  not prevention or attribution; cross-process concurrent
  writers can false-alarm, never silently pass. New
  `tests/test_integrity_attestation.py` (13 tests);
  negation against the RM-049 packages **12 failed / 0
  passed / 1 skipped** (skip = the encryption-compose
  test, no `cryptography` in the negation venv). RM-018
  goldens extended (+2 CASE / +6 TEMPLATE; muninn 58 /
  85); RM-019 surface golden gained the fields; RM-003
  health key set gained the field; RM-040 audit total
  84 → 89 (+5 constant sites). **Bifröst re-verification
  PASS** (fresh venv `ravens-rm050-bifrost-venv` on
  `/var/tmp`, bifrost at b66e98cc — its own suites **25
  passed**; BifrostBridge smoke PASS, evidence
  `/var/tmp/rm050-evidence/`). Full suites green in the
  RM-050 fresh venv on the final banking tree (TMPDIR +
  installs on `/var/tmp`, encryption extra installed):
  muninn **312 passed** (299+13), huginn **259 passed**
  (slice-log pin only); ruff + mypy floors clean (fresh
  tool venv; mypy muninn 7 files — the new `_attest.py` —
  huginn 9 files). TH-10's register update remains
  RM-056's. Founding tree NEEDS A SYNC for the whole
  attestation build (extends the standing package-source
  sync note).
- **RM-049 BANKED 2026-11-02 (keeper tick ~03:36 EST):**
  store encryption, build — TH-09, building RM-048's
  decision to the `docs/STORE_ENCRYPTION.md` specification
  (build note appended there). Both packages gained
  `_crypto.py` (per-store random 32-byte data key,
  PBKDF2-HMAC-SHA256 KEK at 600,000 iterations over a
  per-store 16-byte salt, wrap + key-check as `meta` rows
  — no schema change, RM-004 goldens unmoved), the
  additive config pair `store_encryption: bool = False` /
  `encryption_passphrase` (repr=False; missing passphrase
  or missing extra with the flag on is a typed
  configuration error), and the `encryption` extra
  (`cryptography>=42,<51`, lazy). Values are `enc:v1:`
  AES-256-GCM envelopes (table+column as associated data)
  in the same TEXT columns: Muninn
  `nodes.content`/`metadata`/`tags`; Huginn local
  `documents.content`/`tags`, `doc_vectors.vector`, and
  the term index (`doc_terms`/`corpus_stats`) as keyed
  HMAC tags — TF-IDF scores test-pinned bit-for-bit equal
  to a plain store's. Both `content_hash` columns are
  keyed lookup tags over the RM-047 inputs; the RM-047
  double check compares decrypted content. Contracted
  tables stay plaintext-readable by plain sqlite3. The
  key proof runs BEFORE `open_store` on a pure read-only
  probe — wrong passphrase and plain opens of a marked
  store refuse typed with the store byte-for-byte
  untouched — and defers to the live connection after the
  restore road when the probe cannot read the file, so
  the corruption-recovery suites pass against encrypted
  stores. Build behaviours beyond the spec, recorded in
  the build note: flag-on over an existing plain store
  holding memories/documents refuses typed; Huginn's
  flag binds the local backend only. New
  `tests/test_store_encryption.py` (9 tests each);
  negation against the RM-048 packages **8 failed / 1
  passed** per package (pass = flag-off plaintext
  preserved). RM-018 goldens extended (+3 CASE / +11
  TEMPLATE lines per package; muninn 56/79, huginn
  66/88); RM-019 goldens gained the fields; RM-040 audit
  totals 84 / 45 with `count_sql` named. **Bifröst
  re-verification PASS** (fresh venv
  `ravens-rm049-bifrost-venv` on `/var/tmp`, bifrost at
  b66e98cc — its own suites **25 passed**; BifrostBridge
  smoke PASS, evidence `/var/tmp/rm049-evidence/`).
  Full suites green in the RM-049 fresh venv on the
  final banking tree (TMPDIR + installs on `/var/tmp`):
  muninn **299 passed** (290+9), huginn **259 passed**
  (250+9); ruff + mypy floors clean (rm042 tool venv;
  mypy muninn 6 files, huginn 9 files). The
  `cryptography` extra is PROVEN in the ravens' own
  venv from this slice (50.0.2 via the extra, exercised
  end to end); suites now run with the extra installed.
  TH-09: content Controlled / structure Partial when the
  flag is on; the register update remains RM-056's.
  Founding tree NEEDS A SYNC for the whole encryption
  build (extends the standing package-source sync note).
  Environment, honestly: the home quota (EDQUOT) closed
  repeatedly this tick; this keeper freed the shared
  Hugging Face download cache (~1.8 GB, regenerable) and
  built all RM-049 venvs and evidence on `/var/tmp`,
  running every suite with `PYTHONDONTWRITEBYTECODE=1`.
- **RM-048 BANKED 2026-11-02 (keeper tick ~03:26 EST):**
  store encryption, design — TH-09, decision record in
  `docs/STORE_ENCRYPTION.md`. Design slice only: no
  package code, public API, or schema changed. Judged
  against stdlib-first and the shared-schema law (TB-7):
  SQLCipher REJECTED (compiled fork + binding compiled
  against a system libsqlcipher a pip extra cannot
  express or bound — verified absent on this machine: no
  binary, no package, neither `pysqlcipher3` nor
  `sqlcipher3` imports; and whole-file encryption breaks
  the TB-7 readability contract — Bifröst-class readers
  open Muninn's file with stdlib `sqlite3` — while
  replacing the store machinery every durability proof
  stands on). Filesystem encryption ADOPTED as standing
  deployment guidance only (a library cannot provision
  or promise it, NG-3; it cannot discharge RM-049's
  mandate). **Decision: RM-049 builds application-level
  envelope encryption** — per-store random data key
  wrapped under a PBKDF2-HMAC-SHA256 KEK (stdlib; the
  stdlib has no cipher — verified — and no hand-rolled
  AEAD is permitted), values sealed AES-256-GCM from the
  one bounded extra `cryptography>=42,<51` (lazy,
  flag-gated), `enc:v1:` envelopes in the same TEXT
  columns (schema goldens unmoved), wrap/salt/key-check
  as `meta` rows, open-time key proof before any write
  (wrong passphrase, or a plain/flag-off open of a marked
  store, refuses typed with the store untouched). Config
  spec: `store_encryption: bool = False` +
  `encryption_passphrase` (repr=False). Transforms:
  Muninn `nodes.content`/`metadata`/`tags`; Huginn
  `documents.content`/`tags`, `doc_terms.term` +
  `corpus_stats.term` keyed-HMAC (TF-IDF is equality-only
  — scoring bit-for-bit the plaintext computation),
  `doc_vectors.vector`; `content_hash` becomes a keyed
  lookup tag in both (RM-047's double check compares
  decrypted content). The contracted tables
  (`activation_log`, `hebbian_connections`) carry no
  content and stay plaintext-readable. Honest limits in
  the record: structure/counts/timestamps/wiring/
  approximate lengths stay readable (content
  confidentiality against AC-3 is the purchase; backups
  and WAL inherit ciphertext values via the backup API);
  per-store tag equality leaks; a lost passphrase is a
  lost store; RM-049's "unreadable by plain sqlite3" is
  pinned to its honest reading — no plaintext token of a
  stored memory in a raw dump. Pinned by new
  `tests/test_store_encryption_design.py` (2 tests each
  package); negation: decision line doctored → **1
  failed / 1 passed** per package, record restored
  byte-identical (sha256 verified). No API/schema change,
  so no Bifröst re-verification required (RM-039/RM-040
  precedent). Full suites green in the RM-048 fresh venv
  on the final banking tree (TMPDIR on `/var/tmp`,
  installs from `/var/tmp` copies): muninn **290
  passed** (288+2), huginn **250 passed** (248+2); ruff +
  mypy floors clean (rm042 tool venv; mypy muninn 5
  files, huginn 8 files). Evidence
  `/var/tmp/rm048-evidence/`. Founding tree needs no
  sync for this slice (docs + tests only). TH-09 stays
  Open until RM-049 lands; the `cryptography` extra in
  the ravens' own venv remains NOT PROVEN until then.
- **RM-047 BANKED 2026-11-02 (keeper tick ~02:26 EST):**
  hash-collision honesty — TH-08, record in
  `docs/HASH_COLLISION.md`. Both packages. The collision
  assumption is documented (SHA-256 on all three store
  roads; a natural collision implausible, and the design
  no longer stands on that alone) and every
  idempotent-store road gained the length+content double
  check: Muninn `remember`'s INSERT-OR-IGNORE fallback
  (stored text length, exact text and string/JSON kind
  must equal the incoming values; Muninn's hash extracted
  to `_content_hash` as the injection seam), Huginn local
  `upsert`'s (hash, category) hit plus its
  free-explicit-id discrimination, and Huginn Qdrant's
  derived-id upsert (existing point retrieved and
  RM-046-hygiene-checked first) all refuse a different
  memory under one hash with the one typed message
  (`content hash collision: a different memory already
  holds this content hash (id {id}); refusing to merge`;
  existing memory/point untouched). Explicit-id replace
  and Muninn addressed `update` keep their semantics.
  The inherited RM-046 discovery is FIXED: Qdrant derived
  ids are masked to 63 bits, so every derived id fits the
  facade's `memory_id` ceiling; over-ceiling contents
  found deterministically now round-trip through the
  facade. New `tests/test_hash_collision.py` (muninn 8
  tests, huginn 12; forced collisions via the injected
  constant hash function — the roadmap's named acceptance
  method); negation against the RM-046 packages muninn
  **4 failed / 4 passed**, huginn **7 failed / 5 passed**.
  RM-018 goldens extended (muninn 53 CASE / 68 TEMPLATE;
  huginn 63 CASE / 77 TEMPLATE, 64 distinct). No schema
  change. **Bifröst re-verification PASS** (fresh venv
  `ravens-rm047-bifrost-venv` on `/var/tmp`, bifrost at
  b66e98cc — its own suites **25 passed**; BifrostBridge
  smoke PASS, evidence `/var/tmp/rm047-evidence/`).
  Full suites green in the RM-047 fresh venv on the
  final banking tree (TMPDIR on `/var/tmp`, installs
  from `/var/tmp` copies): muninn **288 passed**
  (280+8), huginn **248 passed** (236+12); ruff + mypy
  floors clean (rm042 tool venv, mypy cache on
  `/var/tmp`; mypy muninn 5 files, huginn 8 files).
  Founding tree NEEDS A SYNC for the double checks, the
  hash seam and the 63-bit derivation (extends the
  standing package-source sync note). Environment,
  honestly: the home quota (EDQUOT) was full at this
  tick's start and repeatedly mid-tick; this keeper
  freed the shared chroma cache (~88 MB), the
  regenerated shared pip cache (~2.5 GB) and the shared
  rattler download cache (~2.8 GB), and built all
  RM-047 venvs and evidence on `/var/tmp`.
- **RM-046 BANKED 2026-11-02 (keeper tick ~01:26 EST):**
  Qdrant payload hygiene — TH-07, record in
  `docs/QDRANT_PAYLOAD.md`. Huginn-only slice. Write road
  pinned: `upsert`'s payload is one fixed dict carrying
  exactly the six `_PAYLOAD_KEYS` (`content`, `category`,
  `importance`, `tags`, `emotional_valence`,
  `content_hash`); caller content/category/tags are values
  only, never keys, so a reserved key cannot be added or
  overwritten through the API (tags named `content_hash`,
  payload-shaped content, a category named `content_hash`
  all proven to stay values with the backend-computed
  hash). Read road hardened: `_point_to_doc` (the one
  point→document road for `get` + `search`) now
  hygiene-checks every returned point — integer id, dict
  payload with every closed-set key present, content/
  category strings, importance a non-bool int in [1, 10],
  tags a list of strings, valence a finite non-bool number
  in [-1, 1], `content_hash` equal to the SHA-256 of the
  returned content+category, finite numeric score — and
  raises `HuginnBackendError` naming only the point id
  (never payload content) instead of the pre-slice
  coercions or untyped errors; extra keys are dropped, as
  before. New `tests/test_qdrant_payload.py` (14 tests,
  hostile points planted in the fake store as a
  co-tenant would); negation against the RM-045 packages
  **7 failed / 7 passed** (failures = exactly the new
  refusals). RM-018 goldens extended (61 CASE / 74
  TEMPLATE, 62 distinct; two new malformed-payload
  messages with deterministic cases). **Bifröst
  re-verification PASS** as a precaution (fresh venv
  `ravens-rm046-bifrost-venv` on `/var/tmp`, bifrost at
  b66e98cc — its own suites **25 passed**; BifrostBridge
  smoke PASS, evidence `/var/tmp/rm046-evidence/`).
  Full suites green in the RM-046 fresh venv on the
  final banking tree (TMPDIR on `/var/tmp`, installs
  from `/var/tmp` copies): muninn **280 passed** (no
  code change; slice-log pin only), huginn **236
  passed** (222+14); ruff + mypy floors clean (rm042
  tool venv; mypy muninn 5 files, huginn 8 files).
  Founding tree NEEDS A SYNC for the payload hygiene
  check (extends the standing package-source sync note).
  Environment, honestly: the home quota (EDQUOT) closed
  repeatedly all tick; this keeper freed this campaign's
  own regenerable scratch (repo build dirs + tool
  caches, the shared pip cache) and built all RM-046
  venvs and evidence on `/var/tmp`.
- **RM-045 BANKED 2026-11-02 (keeper tick ~00:56 EST):**
  Qdrant transport safety — TH-06, record in
  `docs/QDRANT_TRANSPORT.md`. Huginn-only slice.
  `HuginnConfig` validation now enforces the transport
  rule at construction: scheme must be http/https with a
  host; `https` accepted for any host; plain `http` only
  for loopback hosts (`localhost`/`*.localhost`/
  127.0.0.0/8/`::1` via `ipaddress`; lookalikes refused),
  so the default `http://localhost:6333` is unchanged;
  the opt-out is the new additive flag
  `allow_insecure_http: bool = False`. Three static typed
  refusal messages (four raise sites) carry neither the
  key nor the URL. Key handling audited + pinned: sole
  destination is the `QdrantClient` constructor (recording
  fake proves url/key/timeout delivered exactly);
  `field(repr=False)` keeps it out of `repr(config)`;
  every wrapped client error (ping, collection create,
  upsert, delete, retrieve, search, count) is scrubbed of
  the key (`***`) before raising, and the facade scrubs
  `auto`'s fallback reason + INFO line and `health()`'s
  unhealthy error the same way. New
  `tests/test_qdrant_transport.py` (15 tests, leaky fake
  clients embedding the key in exception text — the
  roadmap's error-string scan); negation against the
  RM-044 packages **13 failed / 2 passed** (passes = the
  preserved loopback defaults + constructor delivery).
  The existing fake-client suite now opts in explicitly
  for its non-localhost fake hosts. RM-018 goldens
  extended (59 CASE / 72 TEMPLATE, 60 distinct); RM-019
  golden gained the field. **Bifröst re-verification
  PASS** (fresh venv `ravens-rm045-bifrost-venv` on
  `/var/tmp`, bifrost at b66e98cc — its own suites **25
  passed**; BifrostBridge smoke PASS, evidence
  `~/workspace/.verify-tmp/rm045/`). Full suites green in
  the RM-045 fresh venv on the final banking tree
  (TMPDIR on `/var/tmp`, installs from `/var/tmp` copies):
  muninn **280 passed** (no code change; slice-log pin
  only), huginn **222 passed** (207+15); ruff + mypy
  floors clean (rm042 tool venv; mypy muninn 5 files,
  huginn 8 files). Founding tree NEEDS A SYNC for the
  config flag + transport validation and the scrubbing
  (extends the standing package-source sync note).
  Environment, honestly: the home quota (EDQUOT) closed
  repeatedly all tick; this keeper freed this campaign's
  own spent scratch (~170 MB of pytest/bench/tmp scratch
  across the `rm0*` evidence dirs + the RM-008/RM-009
  drift copies; every log, script and record kept) and
  built all RM-045 venvs on `/var/tmp`.
- **RM-044 BANKED 2026-11-02 (keeper tick ~00:06 EST):**
  log redaction — TH-05, record in `docs/LOG_REDACTION.md`.
  Both configs gain `debug_log_content: bool = False`
  (additive; plain boolean flag). Flag off (default): no
  log record at any level, DEBUG included, carries memory
  content — the RM-039 inspection posture is now
  test-pinned over the store, search and heal paths. Flag
  on: exactly the store and search paths emit content, at
  DEBUG level only (muninn `remember`/`retrieve`; huginn
  facade `upsert_memory`/`search`, binding whichever
  backend serves the call); content never appears at INFO
  or above, and the heal paths carry none at any level
  even with the flag on (counts-only reports by design).
  Exception strings are scoped out honestly (RM-054 /
  TH-14; Qdrant key side RM-045 / TH-06). New
  `tests/test_log_redaction.py` (7 tests each; huginn
  local backend); negation against the RM-043 packages
  **4 failed / 3 passed** per package (passes = the
  preserved default-off behaviours). RM-019 goldens
  gained the field. **Bifröst re-verification PASS**
  (fresh venv `ravens-rm044-bifrost-venv` on `/var/tmp`,
  bifrost at b66e98cc — its own suites **25 passed**;
  BifrostBridge smoke PASS, evidence
  `~/workspace/.verify-tmp/rm044/`). Full suites green in
  the RM-044 fresh venv on the final banking tree
  (TMPDIR on `/var/tmp`): muninn **280 passed** (273+7),
  huginn **207 passed** (200+7); ruff + mypy floors clean
  (rm042 tool venv; mypy muninn 5 files, huginn 8 files).
  Founding tree NEEDS A SYNC for the config field + the
  gated DEBUG emissions (extends the standing
  package-source sync note).
- **RM-043 BANKED 2026-11-01 (keeper tick ~23:06 EST, same
  tick as RM-042):** backup confidentiality — TH-04, record
  in `docs/BACKUP_CONFIDENTIALITY.md`. The rolling-backup
  snapshot in both packages' `_take_backup_unlocked` now
  inherits the store file's own mode at the moment it is
  taken (new `_inherit_store_permissions`, best-effort —
  logged, never raised), before verification and rotation:
  a `0o600` store's backups are `0o600` under any umask, a
  deliberately loosened store's backups inherit exactly
  that mode, and a rotated generation keeps the mode it
  was taken with. New `tests/test_backup_confidentiality.py`
  (muninn 5 tests, huginn 4, POSIX-only); negation against
  the RM-042 packages muninn **4 failed / 1 passed** (the
  pass: backup-on-open at `0o640`, where SQLite's Unix VFS
  already copied the mode on its own), huginn **4 failed /
  0 passed**. No public API or schema change, so no
  Bifröst re-verification required (RM-040 precedent).
  Full suites green in the RM-043 fresh venv on the final
  banking tree (TMPDIR on `/var/tmp`): muninn **273
  passed** (268+5), huginn **200 passed** (196+4); ruff +
  mypy floors clean (rm042 tool venv; mypy muninn 5 files,
  huginn 8 files). Founding tree NEEDS A SYNC for the
  backup helper (extends the standing package-source sync
  note).
- **RM-042 BANKED 2026-11-01 (keeper tick ~23:06 EST):**
  file permissions — TH-03's creation side, record in
  `docs/FILE_PERMISSIONS.md`. A store file an open creates
  (fresh, or restored onto a path that did not exist) is
  set owner-only `0o600` in both packages' `_db.py`
  (`_secure_new_store_files`, best-effort — a refused chmod
  is logged, never raised), with its `-wal`/`-shm`
  sidecars; `created_by_this_open` is captured before the
  restore logic, so existing files are never
  re-permissioned. An existing looser file is reported by
  `health()` in the new additive field
  `file_permissions_warning` (`store_permissions_warning`
  helper: `None` when the file has no `0o077` bits, else a
  string naming the actual mode, e.g. `0644`). Huginn's
  field is on the local backend, carried through the
  facade; Qdrant has no local file and no field. Backups
  are RM-043, untouched here. New
  `tests/test_file_permissions.py` in both packages (7
  tests each, POSIX-only); negation against the RM-041
  packages **7 failed / 0 passed** per package. RM-019
  contract-freeze health key sets gained the field.
  **Bifröst re-verification PASS** (fresh venv
  `ravens-rm042-bifrost-venv` on `/var/tmp`, bifrost at
  b66e98cc — its own suites **25 passed**; BifrostBridge
  smoke PASS, evidence
  `~/workspace/.verify-tmp/rm042/`). Full suites green in
  the RM-042 fresh venv on the final banking tree
  (TMPDIR on `/var/tmp`): muninn **268 passed**
  (261+7), huginn **196 passed** (189+7); ruff + mypy
  floors clean (fresh tool venv on `/var/tmp`, caches
  redirected; mypy muninn 5 files, huginn 8 files).
  Founding tree NEEDS A SYNC for the `_db.py` helpers +
  the `health()` field (extends the standing
  package-source sync note). Environment, honestly: the
  home quota (EDQUOT) closed repeatedly during this tick;
  this keeper deleted this campaign's own spent scratch
  (~146 MB: RM-041 suite venv after its negation evidence
  was captured, RM-014 tool venv) and built all RM-042
  venvs on `/var/tmp`, redirecting TMPDIR, the mypy
  cache, and the Bifrost smoke's HOME there (the smoke's
  first run omitted `huginn_id` because Huginn's default
  `~/.hermes` store hit the quota — environment class,
  diagnosed, not a package defect; full PASS with HOME
  redirected).
- **RM-041 BANKED 2026-11-01 (keeper tick ~22:16 EST):**
  path safety — TH-02's opt-in strict mode, record in
  `docs/PATH_SAFETY.md`. Both configs gain
  `strict_path_safety: bool = False` (additive; a plain
  boolean flag like `auto_backup`). Default off is the
  recorded behaviour, pinned by tests (paths
  `~`-expanded, never symlink-resolved, parents
  unchecked — symlinked file/parent and `0o777` parent
  all open as before). With the flag on, a new
  `_check_path_safety` pre-flight in each package's
  `_db.py` (head of `open_store`, before the RM-037
  coordination lock — a refused open creates nothing,
  not even `.open-lock` — and again inside the locked
  open) refuses with the typed storage error: the store
  path or any parent component a symlink (lstat-judged,
  never followed), or the immediate parent directory
  world-writable (`mode & 0o002`; only the immediate
  parent is judged — `/tmp`-class ancestors are
  world-writable by design; a not-yet-existing parent
  is created under the umask and judged from the next
  open). The restore road is covered (same open, same
  path). Huginn's flag binds the local backend only.
  New `tests/test_path_safety.py` in both packages
  (9 tests each); negation against the RM-040 packages
  6 failed / 3 passed per package (passes = the
  preserved defaults). RM-018 goldens extended (muninn
  52 cases / 67 templates, huginn 56 / 68; stale header
  counts corrected to the true totals); RM-019 surface
  goldens gained the field. **Bifröst re-verification
  PASS** (fresh venv `ravens-rm041-bifrost-venv`,
  bifrost at b66e98cc — its own suites **25 passed**;
  BifrostBridge smoke PASS, evidence
  `~/workspace/.verify-tmp/rm041/`). Full suites green
  in the RM-041 fresh venv on the final banking tree
  (TMPDIR on `/var/tmp`): muninn **261 passed**
  (252+9), huginn **189 passed** (180+9); ruff + mypy
  floors clean (rm014 venv; mypy muninn 5 files,
  huginn 8 files). Founding tree NEEDS A SYNC for the
  config field + pre-flight (extends the standing
  package-source sync note). Environment, honestly:
  the home quota (EDQUOT) closed repeatedly during
  this tick; writes reopened after this keeper deleted
  this campaign's own spent scratch (~1.1 GB: RM-035's
  bench tmp, RM-015's soak stores — durable samples
  copy stands in the goal hidden files — RM-007's
  matrix venvs, RM-014's pytest scratch, and the
  rm036–rm039 suite TMPDIR scratch; all evidence logs
  kept).
- **RM-040 BANKED 2026-11-01 (keeper tick ~21:56 EST):**
  SQL-injection audit — TH-01 closed for the SQLite
  surfaces. The slice stood built but unbanked when this
  tick opened (audit doc, both hostile-battery test
  files, SLICE_LOG entry + EXPECTED pins to RM-040 all
  in the working tree, written ~20:39–20:42 EST): its
  first full muninn run had failed en masse (42 failed /
  176 passed / 34 errors, `muninn_final.log`) and a
  detached wait-and-run prober (started 02:06 UTC) was
  still waiting for the write gate. This tick diagnosed
  the gate as the home quota (EDQUOT on every write
  under `~` despite 39G free on disk — the aggregate of
  the concurrent campaigns), killed the prober so it
  could not race a re-run, and freed this campaign's own
  disposable space (spent `ravens-rm039-venv` + RM-040's
  bench/pytest scratch), after which writes reopened.
  Verification re-run by this tick with TMPDIR on
  `/var/tmp` (2G tmpfs, free): targeted battery muninn
  **9 passed**, huginn **7 passed**; FULL suites green
  in the RM-040 fresh venv (`ravens-rm040-venv`,
  non-editable installs) on the final banking tree —
  muninn **252 passed** (243+9), huginn **180 passed**
  (173+7), exactly the counts the unbanked SLICE_LOG
  entry claimed (logs `muninn_final2.log` /
  `huginn_final2.log` under
  `~/workspace/.verify-tmp/rm040/`); ruff + mypy floors
  clean (rm014 venv; mypy muninn 5 files, huginn 8
  files). Audit substance (from the banked entry): AST
  inventory — muninn 81 execute sites (76 constant, 2
  pinned f-string templates, 3 variable sites), huginn
  42 (36 constant, 4 execute f-strings + 1
  variable-feeding f-string, 2 variable sites); every
  caller value bound as `?`; hostile contents stored
  and retrieved verbatim with all tables intact;
  negation muninn 2 failed / 7 passed, huginn 1 failed
  / 6 passed. No package code, public API, or schema
  change (docs + tests only), so no Bifröst
  re-verification required. Founding tree needs no sync
  for this slice; the Part II/III package-source sync
  note stands.
- **RM-039 BANKED 2026-11-01 (keeper tick ~19:56 EST):**
  threat model — `docs/THREAT_MODEL.md` reviewed against
  both codebases at the RM-038 head (78acff3): 10 assets,
  4 actors (+2 named sub-cases), 7 trust boundaries, a
  21-threat register (TH-01–TH-21) with states today,
  8 explicit non-goals, and the citation rule mapping
  RM-040–RM-056 to the threats they own. Headline open
  findings: no `chmod` anywhere (TH-03), plaintext stores
  + backups (TH-09), no tamper evidence (TH-10), forget
  leaves WAL/backup/log residue (TH-11), Qdrant default
  plaintext HTTP with no TLS rule (TH-06). Pinned by new
  `tests/test_threat_model.py` in both packages (2 tests
  each); negation: RM-047 lines removed → mapping test
  fails (1 failed / 1 passed). EXPECTED pins extended to
  RM-039. Suites: huginn **173 passed** in one full
  final-tree run; muninn **243 passed** assembled
  per-file (all 38 files green; chunk logs in
  `~/workspace/.verify-tmp/rm039/chunks/`) — the home
  quota kept closing mid-run under concurrent campaigns
  (EDQUOT Errno 122 proven in the pytest internal-error
  log; SQLite SIGBUS in heavy-write tests while shut;
  `test_huge_batch_atomicity` passes in 7.1 s on a free
  filesystem). Writes reopened after deleting five of
  this campaign's spent venvs + the shared pip/uv
  download caches. First full muninn run also lost one
  wall-clock test to the load (file passes alone, 6/6,
  and in its chunk). Ruff + mypy floors clean. No
  package code, API, or schema change, so no Bifröst
  re-verification required. Founding tree needs no sync
  for this slice (docs + tests only).
- **RM-038 BANKED 2026-11-01 (keeper tick ~19:36 EST):**
  Part III gate — `docs/PART_III_EVIDENCE.md` files every
  FAULT result (RM-029 disk-full, RM-030 read-only
  filesystem, RM-032 partial-file states), a check-off for
  RM-025–RM-038 with banking counts, the part's thirteen
  Bifröst re-verifications (RM-025–RM-037, each fresh-venv,
  bifrost suites 25 passed, bridge smoke PASS), the floors
  standing (ruff + mypy clean; coverage floor 88; no schema
  changed in Part III), the honesty ledger unchanged (live
  Qdrant NOT PROVEN, sentence-transformers NOT PROVEN,
  GitHub-hosted CI NOT PROVEN), and the debts named
  (founding-tree sync; `schema_version` not gated until
  RM-082/RM-132; the per-object timestamp guard's
  cross-object limit). Pinned by new
  `tests/test_part_iii_gate.py` in both packages (2 tests
  each); EXPECTED pins in both `test_slice_log.py` copies
  extended to RM-038. Full suites green in a fresh venv
  (`ravens-rm038-venv`, non-editable installs, TMPDIR on
  the workspace disk): muninn **241 passed** (239+2),
  huginn **171 passed** (169+2); ruff + mypy floors clean
  (rm014 venv; mypy muninn 5 files, huginn 8 files). No
  package code, API, or schema change, so no Bifröst
  re-verification required for the gate itself. Evidence
  logs under `~/workspace/.verify-tmp/rm038/`.
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
- **RM-038 — Part gate. BANKED 2026-11-01. Class: UNIT.**
  Record: `docs/PART_III_EVIDENCE.md` — the Part III
  evidence bundle. Every FAULT result is filed: RM-029
  (disk-full: typed storage errors, the failed call's
  transaction rolled back exactly, the store openable and
  consistent afterwards), RM-030 (read-only filesystem:
  loud immediate typed refusal in a pre-flight before any
  connection, no read-only mode, no hang), RM-032
  (partial-file states: zero-length main file, non-empty
  WAL without its main file, and a stale `.bak-tmp` each
  given defined, tested open behaviour). The bundle also
  indexes the rest of the part: both fuzz suites
  (RM-025/RM-026, recorded seeds, nineteen defects found
  and fixed in-slice), the oversize ceilings (RM-027),
  the path normaliser (RM-028), locked-store contention
  (RM-031), non-database files (RM-033), the unicode
  gauntlet (RM-034), huge-batch atomicity (RM-035, BENCH:
  10k ids, 49,995,000 pairs / 99,990,000 directed rows in
  1629.6 s at peak RSS 47.5 MB, all eight bench checks
  passed), adversarial tags/metadata (RM-036), and
  concurrent openers defined as supported (RM-037); a
  one-line acceptance + banking-counts check-off for
  every slice RM-025–RM-038; the part's thirteen Bifröst
  contract re-verifications (RM-025 through RM-037 — each
  fresh venv, bifrost at b66e98cc, its own suites 25
  passed, BifrostBridge smoke PASS); the floors standing
  at the gate (ruff + mypy clean at every banking,
  coverage floor 88, schema + contract freezes green
  throughout — no schema changed in Part III); the
  honesty ledger carried forward unchanged (live Qdrant
  NOT PROVEN, sentence-transformers NOT PROVEN,
  GitHub-hosted CI NOT PROVEN); and the debts named
  (founding-tree sync owed for all Part III package
  sources on top of the Part II debt; `schema_version`
  recorded-not-gated until RM-082 / RM-132; RM-012's
  per-object timestamp guard may repeat or invert by
  microseconds across RM-037's concurrent objects, stated
  in the RM-037 record). Pinned by new
  `tests/test_part_iii_gate.py` in both packages (2 tests
  each: the bundle names every Part III slice and files
  every FAULT result); both `test_slice_log.py` EXPECTED
  pins extended to RM-038 in this commit. Full suites
  green in a fresh venv (`ravens-rm038-venv`, non-editable
  installs, TMPDIR on the workspace disk): muninn **241
  passed** (239+2), huginn **171 passed** (169+2); ruff +
  mypy floors clean (rm014 venv; mypy muninn 5 files,
  huginn 8 files). No package code, public API, or schema
  change, so no Bifröst re-verification required for the
  gate itself. Founding tree needs no NEW sync for this
  slice (docs + tests only); the Part III package-source
  sync note stands. **Part III (Robustness) is complete
  with this slice** — 14 of 14 slices banked. The road
  continues at Part IV — Security (RM-039–RM-056).
- **RM-039 — Threat model. BANKED 2026-11-01. Class: UNIT
  (inspection).** Record: `docs/THREAT_MODEL.md` — Part IV's
  foundation, reviewed against both codebases at HEAD
  78acff3 (all sources of both packages, both pyprojects,
  inventories of every SQL site, logger site, file-creation
  site, the Qdrant client construction + payload dict, both
  content_hash definitions, and both forget/delete paths —
  the review record is in the document). Ten assets
  (AS-01–AS-10), the roadmap's four actors (AC-1 buggy
  caller, AC-2 hostile input source, AC-3 local file
  attacker, AC-4 network attacker against Qdrant; sub-cases:
  compromised optional dependency, hostile co-tenant
  process), seven trust boundaries (TB-1 caller↔API, TB-2
  library↔store files, TB-3 library↔backups, TB-4
  library↔diagnostics, TB-5 Huginn↔Qdrant, TB-6 optional
  extras, TB-7 cross-store readers of the shared tables),
  twenty-one threats (TH-01–TH-21) each with its state
  today and owning slice, eight explicit non-goals
  (NG-1–NG-8), the model's assumptions, and the citation
  rule: every RM-040–RM-056 slice-log entry cites the
  threats it closes, and a newly found threat amends the
  model in its own commit. States, plainly: TH-17/TH-18
  Controlled (Parts II–III); TH-01/05/07/08/12/13/14/15/19
  Partial; TH-02/03/04/06/09/10/11/16 Open; TH-20/TH-21
  Accepted (contractual / bounded). Pinned by new
  `tests/test_threat_model.py` in both packages (2 tests
  each); EXPECTED pins in both `test_slice_log.py` copies
  extended to RM-039. Negation: a scratch copy of the model
  with the RM-047 lines removed fails the mapping test
  (1 failed / 1 passed). Suites in a fresh venv
  (`ravens-rm039-venv`, non-editable installs): huginn
  **173 passed** (171+2) in one full final-tree run
  (TMPDIR on the workspace disk); muninn **243 passed**
  (241+2) assembled per-file, all 38 test files green
  (per-file logs `~/workspace/.verify-tmp/rm039/chunks/`),
  because the home quota kept closing mid-run under the
  concurrent campaigns — EDQUOT (Errno 122) proven in a
  pytest internal-error log, SQLite SIGBUS in heavy-write
  tests while the quota was shut, `test_huge_batch_
  atomicity` green in 7.1 s on the then-free /tmp; the
  first full muninn run also failed one wall-clock-decay
  test under load average ~12 (the file passes alone and
  in its chunk; RM-001 environment pattern). Writes
  reopened after this keeper deleted five of this
  campaign's spent per-slice venvs and the shared pip/uv
  download caches (~2.5G, regenerable; huggingface and
  rattler caches untouched). Ruff + mypy floors clean
  (rm014 venv; mypy muninn 5 files, huginn 8 files). No
  package code, public API, or schema change, so no
  Bifröst re-verification required. Founding tree needs
  no sync for this slice (docs + tests only); the
  Part II/III package-source sync note stands.
- **RM-040 — SQL-injection audit. BANKED 2026-11-01. Class:
  UNIT.** Record: `docs/SQL_INJECTION_AUDIT.md` — TH-01
  closed for the SQLite surfaces. AST inventory on the
  RM-039 head: muninn 81 execute sites (`_db.py` 8,
  `core.py` 73) — 76 constant (every caller value bound
  as `?`; the rest value-free), 2 f-string templates
  (`PRAGMA busy_timeout={int(...)}`; `UPDATE nodes SET
  {assignments}` with keys only from the closed field
  allow-list, values bound), 3 variable sites
  (`executescript(schema_sql)` = static `SCHEMA_SQL`;
  the timestamp seed loop over constant tuples;
  `retrieve`'s constant base + constant fragments with
  category/path/LIKE pattern all bound and the LIKE
  pattern escaped). Huginn 42 sites (`_db.py` 8,
  `local_backend.py` 34) — 36 constant, 4 execute-site
  f-strings (`busy_timeout` as muninn; three
  `IN ({placeholders})` built from `len()` only, every
  element bound), 1 variable-feeding f-string, 2
  variable sites (static `SCHEMA_SQL`;
  `_candidate_docs_locked`'s bound query). No
  `%`-formatting, concatenation, or `.format()` builds
  SQL in either package. Proven by the hostile battery
  in new `tests/test_sql_injection.py` in both packages
  (muninn 9 tests, huginn 7): hostile contents /
  categories / tags / metadata / paths stored and
  retrieved verbatim with every table intact, injection
  as a filter matches nothing, a hostile `update()`
  field name is a typed refusal. The same files pin the
  audit (site totals, exact template sets, exact
  variable-site names), so a new SQL shape fails the
  suite until the audit is re-run. Negation: an injected
  f-string site in a scratch Muninn fails both audit
  tests (2 failed / 7 passed); a concatenation site in
  a scratch Huginn fails its classification test
  (1 failed / 6 passed). Banking verification was
  re-run by the ~21:56 EST keeper tick (see the Status
  entry above for the quota diagnosis, the killed
  wait-and-run prober, and the freed campaign space):
  full suites green in the RM-040 fresh venv on the
  final tree, TMPDIR on `/var/tmp` — muninn **252
  passed** (243+9), huginn **180 passed** (173+7);
  ruff + mypy floors clean (rm014 venv; mypy muninn 5
  files, huginn 8 files). No package code, public API,
  or schema change (docs + tests only), so no Bifröst
  re-verification required. Founding tree needs no sync
  for this slice; the Part II/III package-source sync
  note stands.
- **RM-041 — Path safety. BANKED 2026-11-01. Class:
  UNIT.** Record: `docs/PATH_SAFETY.md` — TH-02 closed
  for callers who opt in. Both configs gain
  `strict_path_safety: bool = False`, additive at the
  end of each dataclass, a plain boolean flag like
  `auto_backup` (no new config-error site). Default off
  is the recorded behaviour and is pinned as such:
  store paths are `~`-expanded, never symlink-resolved,
  and parent permissions are unchecked — a symlinked
  store file, a store under a symlinked parent, and a
  store in a `0o777` parent all open and work exactly
  as before (three default-mode tests per package). With
  the flag on, `_check_path_safety` in each package's
  `_db.py` refuses on open with the typed storage
  error, as a pre-flight at the head of `open_store`
  with the RM-030/RM-033 pre-flights — before the
  RM-037 coordination lock, so a refused open creates
  nothing, not even the `.open-lock` file — and again
  inside the locked open: (1) the store path itself or
  any parent directory component of its absolute path
  is a symlink — every existing component judged by
  `is_symlink` (lstat; links judged, never followed);
  (2) the store's immediate parent directory is
  world-writable (`mode & 0o002`). Two scoping
  decisions, stated in the record: only the immediate
  parent is judged world-writable (system ancestors
  such as `/tmp` are world-writable by design, sticky-
  bit shared space), and a parent that does not exist
  yet is created by the open under the process umask
  and judged from the next open on (a symlinked
  not-yet-created path is still refused, because the
  link components already exist). Strict mode refuses;
  it never resolves or redirects the caller's path. The
  restore road is covered, since a restore writes to
  the same path inside the same open. Huginn's flag
  applies to the local backend only; the Qdrant
  backend has no local file. Pinned by new
  `tests/test_path_safety.py` in both packages (9 tests
  each; refusals proven against the facade for Muninn
  and against `LocalBackend` for Huginn, whose facade
  is lazy). Negation against the RM-040 installed
  packages: 6 failed / 3 passed per package — the three
  passes are exactly the preserved default-mode
  behaviours. RM-018 goldens extended deliberately in
  both packages: muninn **52 cases / 67 templates**,
  huginn **56 cases / 68 templates** (the two new raise
  sites in each `_db.py` plus their CASE triggers; the
  goldens' stale header counts were corrected to the
  true totals in this commit). RM-019 API-surface
  goldens gained the field and the updated config
  `__init__` lines. Guides + API reference updated.
  Public config surface changed additively, so the
  **Bifröst contract re-verification was run before
  banking**: fresh venv (`ravens-rm041-bifrost-venv`),
  bifrost at b66e98cc — its own suites **25 passed**;
  BifrostBridge smoke PASS (store mimir_id+huginn_id;
  search 1 merged result; recall grew the Muninn
  activation log exactly +1; decay/consolidate
  reports; `decay_wall_clock()` armed at 0 days; stats
  over all three backends; both raven health dicts
  carry `sqlite_version` 3.45.1 through the bridge;
  huginn degraded via auto-fallback to local —
  qdrant-client not installed in the venv, the
  founding condition; live Qdrant still NOT PROVEN;
  double close safe; evidence
  `~/workspace/.verify-tmp/rm041/`). Full suites green
  in a fresh venv (`ravens-rm041-venv`, non-editable
  installs, TMPDIR on `/var/tmp`): muninn **261
  passed** (252+9), huginn **189 passed** (180+9);
  ruff + mypy floors clean (rm014 venv; mypy muninn 5
  files, huginn 8 files). Founding tree
  (`~/workspace/ravens`) NEEDS A SYNC for the config
  field + the `_db.py` pre-flight (extends the
  standing package-source sync note). TH-02's register
  state is re-checked at the RM-056 part gate, per the
  threat model's rule.
