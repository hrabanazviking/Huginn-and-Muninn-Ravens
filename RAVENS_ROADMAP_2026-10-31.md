# RAVENS ROADMAP — 2026-10-31

The road for Huginn and Muninn after v1.0.0: improve them vastly,
with the biggest weight on **stability, robustness, security,
speed, self-healing, error-correcting, crash-proofing,
scalability, modularity, multi-threading, intelligent functions
and advanced intelligence, and adaptability to all kinds of uses
and data types** — in Volmarr's words, and in that spirit.

212 slices (RM-001–RM-212), seventeen parts. Slices are numbered
consecutively and each is independently shippable: it lands with
its tests, its docs updated in the same commit, or it does not
land. Parts are ordered so foundations come before the
intelligence built on them, but any part may be taken up once its
named dependencies stand.

## Governing laws (bind every slice)

1. **No Docker, ever.** Native installs and venvs only.
2. **Stdlib-first.** A new dependency is a decision that must be
   argued in the slice that introduces it, bounded
   (`>=floor,<next_major`), and placed behind an optional extra
   unless the package cannot function without it. Muninn's core
   stays dependency-free unless a slice proves otherwise.
3. **Reads stay pure.** No read API mutates the store. A
   reinforcing read must be explicitly named, opt-in, documented
   and tested as a write (the v1.0.0 precedent: Muninn's
   `retrieve(..., touch=True)`; Huginn has none).
4. **Counts come from runners only.** Test counts, benchmark
   numbers and proof claims are quoted from tool output, never
   estimated, never rounded into a better story.
5. **Honesty classes.** Every proof claim carries its class:
   `UNIT` (tests), `FAULT` (fault-injection/chaos runs),
   `BENCH` (measured benchmark gates), `LIVE` (against a real
   external server or real hardware), `NOT PROVEN` (the road is
   named but the evidence does not exist yet). A slice that needs
   LIVE proof and cannot get it closes as NOT PROVEN with the
   missing evidence named — never as done.
6. **No silent data loss.** Any change to durability, backup or
   healing behaviour must keep the v1.0.0 guarantee: corruption
   is recovered loudly or reported loudly; a store never quietly
   starts empty over lost data.
7. **The shared schema is law.** Muninn's `activation_log` and
   `hebbian_connections` tables are read directly by Bifröst and
   Hermes. Their shape changes only through the schema-version
   slices (Part X) with migration proof against the pinned
   Bifröst contract.
8. **Docs move with code.** A slice that changes behaviour
   updates the affected guides, the API reference and the
   package's INTERFACE.md in the same commit.

---

## Part I — Foundations & Gates (RM-001–RM-010)

*Re-prove v1.0.0 as shipped from this repo, and build the gates
every later part must pass.*

- **RM-001 — Repo-shipped baseline.** Fresh venv; `pip install
  ./muninn ./huginn` from this repo; both suites green from the
  installed packages; counts recorded in the slice log.
  Acceptance: muninn 36/36, huginn 27/27 or better, from the repo
  copies. Class: UNIT.
- **RM-002 — Manual-only CI.** A workflow that runs both suites
  on `workflow_dispatch` only — never on push (Volmarr's standing
  rule for all his repos). Acceptance: workflow file present,
  triggers verified by inspection.
- **RM-003 — Contract freeze tests.** Golden tests pinning the
  exact Bifröst call shapes and result keys of BUILD_NOTES §1,
  so no later slice can drift the contract unknowingly.
  Acceptance: a deliberate signature change fails the suite.
  Class: UNIT.
- **RM-004 — Schema snapshot tests.** Golden dumps of both
  stores' `sqlite_master` (muninn six tables, huginn local five)
  + indexes; any schema change must update the snapshot
  deliberately. Acceptance: snapshot diff fails CI when
  unreviewed. Class: UNIT.
- **RM-005 — Benchmark harness as a gate.** Promote
  `scripts/benchmark.py` in both packages into a repeatable gate
  with recorded baselines and regression thresholds (default:
  fail on >25% regression in any headline operation). Numbers
  labelled with machine + load. Class: BENCH.
- **RM-006 — Loaded-machine honesty in benchmarks.** The harness
  records CPU count, load average and Python/SQLite versions
  beside every number, so indicative numbers can never be quoted
  as absolutes. Acceptance: benchmark output carries the full
  environment block.
- **RM-007 — Test-matrix slice.** Suites run under Python 3.11,
  3.12 and 3.13 in the manual CI. Acceptance: matrix green or
  failures named per version. Class: UNIT.
- **RM-008 — Lint/type floor.** `ruff` + a strictness-ratcheted
  type check over both packages; findings fixed, not suppressed.
  Acceptance: clean run recorded.
- **RM-009 — Coverage floor.** Line coverage measured for both
  packages; floor set at the measured v1.0.0 level and ratcheted
  in later slices. Acceptance: coverage report committed;
  floor enforced by the manual CI.
- **RM-010 — Slice-log discipline.** A `docs/SLICE_LOG.md`
  convention: every closed slice appends its evidence (counts,
  class, commit). Acceptance: log exists; RM-001–RM-009 entries
  backfilled from real records only.

## Part II — Stability (RM-011–RM-024)

*Nothing drifts, nothing flakes, nothing depends on the mood of
the machine.*

- **RM-011 — Determinism audit.** Hunt every nondeterministic
  behaviour (dict ordering, timestamp ties, float formatting in
  hashes); pin or document each. Acceptance: two identical
  workload runs produce byte-identical store dumps (excluding
  timestamps, which are listed). Class: UNIT.
- **RM-012 — Timestamp discipline.** All stored timestamps UTC
  ISO-8601 from one helper per package; monotonicity guard so a
  backwards system clock cannot produce out-of-order activation
  logs. Acceptance: clock-skew test. Class: UNIT.
- **RM-013 — Idempotency matrix.** A written + tested matrix of
  every public API: idempotent / safely re-runnable /
  intentionally not (activate), with retry-safety proven per
  row. Acceptance: matrix in docs/API_REFERENCE.md; one test
  per row. Class: UNIT.
- **RM-014 — Flake quarantine.** Run both suites 50× under load;
  any flake is root-caused and fixed, never retried into green.
  Acceptance: 50 consecutive green runs recorded. Class: UNIT.
- **RM-015 — Long-run soak.** A 24-hour mixed-workload soak
  harness (store/activate/search/decay/consolidate cycling)
  reporting memory growth, file growth and error counts.
  Acceptance: soak completes with bounded growth curves
  published. Class: BENCH.
- **RM-016 — Version-pinning of the sqlite runtime.** Record
  SQLite version in `health()` for both packages; document the
  minimum WAL-safe version. Acceptance: health output carries
  `sqlite_version`. Class: UNIT.
- **RM-017 — Config immutability.** Config objects frozen after
  validation (or defensively copied), so a caller mutating a
  dataclass mid-flight cannot change a live store's behaviour.
  Acceptance: mutation attempt test. Class: UNIT.
- **RM-018 — Stable error messages.** Error strings treated as
  API: snapshot tests for every typed error's message shape.
  Acceptance: message change = deliberate snapshot update.
  Class: UNIT.
- **RM-019 — API surface freeze test.** `__all__` and public
  signatures snapshotted per package; additions allowed,
  removals/renames fail until a major-version slice. Class:
  UNIT.
- **RM-020 — Reproducible benchmark corpus.** The synthetic
  benchmark corpora seeded deterministically and versioned, so
  BENCH comparisons across slices compare like with like.
  Acceptance: corpus hash recorded in benchmark output.
- **RM-021 — Clock-free decay.** Decay computed from explicit
  `days` only (already true) plus an optional wall-clock mode
  that reads last-run time from the store's meta table —
  off by default, tested for clock jumps both ways. Class:
  UNIT.
- **RM-022 — Store-format stability promise.** A
  `docs/FORMAT_STABILITY.md`: which files/tables are contractual
  (shared schema, backups, meta keys) and the migration promise
  attached to each. Acceptance: doc reviewed against code.
- **RM-023 — Shutdown cleanliness.** `close()` leaves no
  lingering threads, no half-written WAL: reopening after close
  performs zero recovery. Acceptance: close/reopen test asserts
  `recovered_from_backup == False` and clean `PRAGMA
  wal_checkpoint` state. Class: UNIT.
- **RM-024 — Part gate.** Part II evidence bundle: determinism,
  soak, flake and matrix results filed; roadmap check-off.

## Part III — Robustness (RM-025–RM-038)

*Hostile inputs, weird filesystems, half-dead disks — the ravens
keep their shape.*

- **RM-025 — Input fuzzing, muninn.** Property-based fuzz over
  every validator (ids, valence, importance, paths, tags,
  metadata): no input produces an untyped exception or a
  partial write. Acceptance: fuzz suite green, seeds recorded.
  Class: UNIT.
- **RM-026 — Input fuzzing, huginn.** Same discipline over
  upsert/search/get/delete arguments and query text (empty,
  huge, unicode-edge, NUL-bearing). Class: UNIT.
- **RM-027 — Oversize content policy.** Explicit, configurable
  ceilings for content size and metadata size with typed
  refusal — instead of today's unbounded acceptance.
  Acceptance: boundary tests at, above and below the ceiling.
  Class: UNIT.
- **RM-028 — Pathological paths.** Node paths with `..`, empty
  segments, trailing slashes, very deep nesting, unicode
  separators: defined behaviour, tested. Class: UNIT.
- **RM-029 — Disk-full behaviour.** Writes against a full
  filesystem (fault-injected) surface as typed StorageErrors
  with the store still openable and consistent afterwards.
  Class: FAULT.
- **RM-030 — Read-only filesystem.** Opening a store read-only
  fails loudly and immediately (or opens in an explicit
  read-only mode slice, if designed here) — never hangs on
  busy-timeout. Class: FAULT.
- **RM-031 — Locked-store contention.** A second process holding
  the write lock: busy_timeout honoured, then a typed error
  naming the contention. Acceptance: two-process test. Class:
  UNIT.
- **RM-032 — Partial-file states.** Store present but WAL
  missing, WAL present but store truncated, `.bak-tmp` left
  behind by a killed backup: open behaviour defined + tested
  for each combination. Class: FAULT.
- **RM-033 — Non-database files.** A text file, an empty file,
  and a directory at the db path: all answered with typed
  errors, never tracebacks. Class: UNIT.
- **RM-034 — Unicode & encoding gauntlet.** Content in RTL
  scripts, emoji ZWJ sequences, combining marks, lone
  surrogates (rejected with typed error, since JSON/SQLite
  cannot hold them honestly). Class: UNIT.
- **RM-035 — Huge-batch atomicity.** `activate_batch` with
  10k ids: one transaction, exact pair counts, memory-bounded.
  Acceptance: count proof + peak-memory note. Class: BENCH.
- **RM-036 — Adversarial tags/metadata.** Deeply nested,
  self-referential and enormous metadata: serializability
  checked before write (already), plus depth/size bounds from
  RM-027 applied uniformly. Class: UNIT.
- **RM-037 — Concurrent openers.** Two objects (same process
  and cross-process) opening one store: behaviour defined
  (both work, serialized by SQLite) and tested; documented as
  supported or explicitly refused — one of the two, in writing.
  Class: UNIT.
- **RM-038 — Part gate.** Robustness evidence bundle filed,
  including every FAULT result.


## Part IV — Security (RM-039–RM-056)

*A memory store holds the most sensitive data a program has.
Treat it that way.*

- **RM-039 — Threat model.** `docs/THREAT_MODEL.md`: assets
  (memory content, wiring, logs), actors (buggy caller, hostile
  input source, local file attacker, network attacker against
  Qdrant), trust boundaries, and the explicit non-goals.
  Acceptance: model reviewed against both codebases; every
  later security slice cites it.
- **RM-040 — SQL-injection audit.** Every SQL string in both
  packages audited: values always bound; the only interpolated
  SQL (placeholder counts, update column names) proven to come
  from closed sets. Acceptance: audit table in the slice log;
  a hostile-content test battery (quotes, `'; DROP TABLE`,
  unicode tricks) stored and retrieved verbatim. Class: UNIT.
- **RM-041 — Path safety.** Store paths are never
  symlink-resolved today (recorded behaviour); add an explicit
  opt-in strict mode that refuses symlinked db paths and
  world-writable parent dirs, for locked-down deployments.
  Acceptance: symlink test battery. Class: UNIT.
- **RM-042 — File permissions.** New store files created with
  owner-only permissions (0600) where the OS allows; existing
  looser files reported in `health()` as a warning field.
  Acceptance: permission tests on Linux. Class: UNIT.
- **RM-043 — Backup confidentiality.** Rolling backups inherit
  the store's permissions (they are full copies of memory);
  verified by test. Class: UNIT.
- **RM-044 — Log redaction.** Package loggers never emit memory
  content at INFO or below; a debug-content flag, off by
  default, is the only road to content in logs. Acceptance:
  log-capture tests over store/search/heal paths. Class: UNIT.
- **RM-045 — Qdrant transport safety.** API key handling
  audited (never logged, never in error strings); HTTPS
  required by default for non-localhost Qdrant URLs, with an
  explicit `allow_insecure_http` opt-out. Acceptance: error
  strings scanned in tests for key material. Class: UNIT.
- **RM-046 — Qdrant payload hygiene.** Payload keys are a closed
  set; caller tags/content can never overwrite reserved keys.
  Acceptance: hostile-payload tests against the fake client.
  Class: UNIT.
- **RM-047 — Hash-collision honesty.** Content-hash identity
  uses SHA-256; document the collision assumption and add a
  length+hash double check on the idempotent-store path so a
  collision can never silently merge two different memories.
  Acceptance: forced-collision test via injected hash
  function. Class: UNIT.
- **RM-048 — Store encryption, design.** A design slice only:
  SQLCipher vs application-level envelope encryption vs
  filesystem encryption, judged against stdlib-first and the
  shared-schema law. Output: a decision record, not code.
- **RM-049 — Store encryption, build.** Implement RM-048's
  decision behind an optional extra and a config flag; stores
  remain readable by the plain build when encryption is off.
  Acceptance: encrypted store unreadable by plain sqlite3;
  wrong-key open raises typed error; kill-9 + recovery suites
  pass against encrypted stores. Class: FAULT.
- **RM-050 — Integrity attestation.** Optional HMAC/checksum
  chain over `activation_log` so tampering with the log file
  outside the API is detectable on open. Acceptance:
  tamper test — modify one row by raw SQL, open, detection
  reported. Class: FAULT.
- **RM-051 — Forget is forgetting.** Audit `forget`/`delete`
  for residual copies: WAL frames and backups can still hold
  "deleted" content; document the truth and add a
  `secure_forget` that rewrites + checkpoints + rotates
  backups, with its cost stated. Acceptance: forensic test
  searching the files for a forgotten string before/after.
  Class: FAULT.
- **RM-052 — Dependency hygiene.** Both packages' extras pinned
  with upper bounds (already); add a lockfile example and a
  vulnerability-scan step to the manual CI. Class: UNIT.
- **RM-053 — Denial-of-service bounds.** Query cost ceilings:
  spread_activation and local search already bound their
  work; add explicit candidate-set caps with typed/stat
  visibility when a cap bites. Acceptance: worst-case
  synthetic corpus stays within the stated bound. Class:
  BENCH.
- **RM-054 — Error-message hygiene.** Typed errors never carry
  file contents, keys or full paths beyond the store path the
  caller itself supplied. Acceptance: message-scan tests.
  Class: UNIT.
- **RM-055 — Secure defaults review.** Every config default
  re-judged for safety (timeouts, backup counts, fallback
  behaviour) and the judgements recorded in the guides.
- **RM-056 — Part gate.** Security evidence bundle filed;
  threat model updated with what the part actually built.

## Part V — Speed (RM-057–RM-072)

*Measured, gated, and honest about the machine the numbers came
from.*

- **RM-057 — Baseline atlas.** Benchmarks at 1k / 10k / 100k
  nodes and documents for both packages, all headline
  operations, environment block attached (extends RM-005/006).
  Class: BENCH.
- **RM-058 — Muninn read path.** `get_associations` and
  `spread_activation` profiled at 100k edges; index or query
  changes only where the atlas shows pain. Acceptance: gate
  numbers before/after. Class: BENCH.
- **RM-059 — Activation write path.** `activate` currently does
  several statements per call; batch the counter/log/node
  updates into the fewest statements that keep the semantics,
  proven by the count-exact tests. Class: BENCH + UNIT.
- **RM-060 — Bulk remember.** A `remember_many` batch API: one
  transaction, one content-hash pass, backpressure applied
  once. Acceptance: 10k-node ingest benchmark vs the loop it
  replaces. Class: BENCH.
- **RM-061 — Huginn candidate generation.** Local TF-IDF search
  currently scores every candidate's full term set; add
  posting-list pruning (top-term candidate narrowing) with a
  recall test proving result parity on the benchmark corpus.
  Class: BENCH + UNIT.
- **RM-062 — Huginn vector scan.** The embedder-mode scan is
  linear over stored vectors; add an optional in-store
  prefilter (category/importance pushed into SQL — partly
  true today) and measure honestly at 100k docs; if linear
  still wins at personal-store scale, record that and stop.
  Class: BENCH.
- **RM-063 — Warm caches.** Optional bounded in-memory cache
  for `get_node` / document `get` with explicit invalidation
  on writes through the same object; documented as
  per-object only. Acceptance: hit-rate + staleness tests.
  Class: UNIT.
- **RM-064 — Decay/consolidate at scale.** Both are full-store
  UPDATEs; add chunked maintenance with progress reporting
  that preserves all-or-nothing semantics per chunk boundary
  stated in the report. Acceptance: 100k-edge run within the
  gate. Class: BENCH.
- **RM-065 — Backup cost.** Backup-on-open and
  pre-maintenance snapshots measured at 100k scale; add
  incremental or copy-on-write strategies only if the numbers
  demand it. Class: BENCH.
- **RM-066 — Connection pragmas study.** `cache_size`,
  `mmap_size`, `temp_store` measured per package; defaults
  changed only on evidence, recorded per pragma. Class:
  BENCH.
- **RM-067 — Query-plan proofs.** `EXPLAIN QUERY PLAN` tests
  for the hot queries of both packages, asserting index use —
  a schema change that drops an index fails loudly. Class:
  UNIT.
- **RM-068 — Serialization cost.** `MemoryNode.to_dict`,
  JSON tags/metadata handling profiled; cheap wins taken
  (e.g. avoiding re-parse on hot paths) with parity tests.
  Class: BENCH.
- **RM-069 — Huginn tokenization speed.** The tokenizer is on
  every upsert/search; regex or caching improvements measured
  against a fixed corpus with output-parity proof. Class:
  BENCH + UNIT.
- **RM-070 — Startup cost.** Import + construct + open timed
  cold and warm; the lazy-construction guarantee kept while
  open cost is profiled (heal pass is the suspect). Class:
  BENCH.
- **RM-071 — Regression gates wired.** RM-005's gate now
  covers the atlas operations; a >25% regression blocks the
  slice that caused it. Class: BENCH.
- **RM-072 — Part gate.** Speed evidence bundle: atlas,
  before/after tables, and the list of optimizations
  *rejected* on evidence, with their numbers.

## Part VI — Self-Healing (RM-073–RM-086)

*From repairing drift to surviving real damage — with a report
every time.*

- **RM-073 — Corruption taxonomy.** Enumerate the corruption
  classes per store (header, page, index, WAL, backup-chain,
  schema drift, logical drift) and which v1.0.0 already
  survives; the rest become this part's work list. Output:
  taxonomy in docs/RELIABILITY.md.
- **RM-074 — Page-level damage.** Fault-inject single-page
  corruption in the middle of each store: today's road is
  full-backup restore; measure and document the data-loss
  window honestly. Class: FAULT.
- **RM-075 — Salvage mode.** When no backup verifies, attempt
  row-level salvage into a *new* store (never overwriting the
  corpse), returning a salvage report: what was recovered,
  what was lost, per table. Acceptance: salvage of a
  page-corrupted store recovers the undamaged tables' rows.
  Class: FAULT.
- **RM-076 — Index rebuild.** A `rebuild_indexes` maintenance
  operation (REINDEX + term-index recount) exposed and
  tested, for stores whose indexes disagree with their rows.
  Class: FAULT.
- **RM-077 — WAL surgery.** A store whose `-wal` is corrupt
  while the main file is sound: open must recover the main
  file and say what the WAL cost. Acceptance: targeted
  fault test. Class: FAULT.
- **RM-078 — Backup-chain verification.** A `verify_backups()`
  health operation that quick-checks every generation and
  reports per-generation status, so a rotting chain is seen
  before it is needed. Class: UNIT.
- **RM-079 — Heal drills.** A scheduled self-test: the package
  builds a scratch copy of the live store, corrupts it in
  each taxonomy class, heals it, and reports — proving the
  healing road works *today*, not just in unit tests.
  Acceptance: drill report shape + one full drill run.
  Class: FAULT.
- **RM-080 — Logical-drift expansion, muninn.** Heal grows:
  negative strengths, strengths > 1, orphan node_activation
  rows for never-activated ids, duplicate-path case drift —
  each repaired or reported, none silently kept. Class: UNIT.
- **RM-081 — Logical-drift expansion, huginn.** Heal grows:
  documents whose stored hash disagrees with their content,
  vectors whose dimension disagrees with config, terms with
  zero doc_freq lingering. Class: UNIT.
- **RM-082 — Schema drift healing.** A store from an older
  schema_version is migrated on open (once Part X's versioning
  exists); until then, a foreign-schema store is refused with
  a typed error naming both versions. Class: UNIT.
- **RM-083 — Heal reporting standard.** One report shape
  across both packages (fixes counted by class, warnings
  listed, unrecoverable items named), surfaced identically in
  `health()`. Acceptance: shape snapshot tests. Class: UNIT.
- **RM-084 — Repair provenance.** Every heal action also
  appends a row to a `meta` repair log inside the store, so a
  store carries its own healing history. Class: UNIT.
- **RM-085 — Backup diversity.** One backup generation kept in
  a *different directory* (config option), so a directory-level
  accident cannot take store + all backups at once. Class:
  FAULT.
- **RM-086 — Part gate.** Self-healing evidence bundle:
  taxonomy coverage table with a FAULT result per class.

## Part VII — Error-Correcting (RM-087–RM-098)

*Richer typed recovery: callers should always know exactly what
happened and what is safe to do next.*

- **RM-087 — Error taxonomy v2.** Each typed error gains a
  stable machine-readable `code` and a `retryable` flag;
  messages stay human. Acceptance: code snapshot tests;
  guides updated. Class: UNIT.
- **RM-088 — Error context.** Errors carry structured context
  (operation, store path, backend, phase) as attributes —
  never content (per RM-054). Class: UNIT.
- **RM-089 — Partial-failure reports.** Batch APIs return (or
  raise with) a per-item outcome report instead of a bare
  failure, where the semantics are per-item. Acceptance:
  mixed-validity batch tests. Class: UNIT.
- **RM-090 — Transactional guarantees doc + tests.** One test
  per public write proving all-or-nothing under an injected
  mid-write exception. Class: FAULT.
- **RM-091 — Retry-safe writes audit.** Every write re-judged
  for safe retry after an ambiguous failure (crash between
  commit and return); the idempotency matrix (RM-013) updated
  with the verdicts. Class: FAULT.
- **RM-092 — Validation completeness.** A generated checklist
  mapping every public parameter to its validator; gaps
  closed. Acceptance: checklist test reads signatures and
  asserts coverage. Class: UNIT.
- **RM-093 — Correction suggestions.** Validation errors for
  near-miss values (importance 0 or 11, valence just out of
  range) name the legal range and the received value —
  already partly true; made uniform. Class: UNIT.
- **RM-094 — Backend error translation.** Qdrant client
  exceptions translated into the typed hierarchy with the
  original chained (`raise ... from`), one translation table,
  tested against the fake client. Class: UNIT.
- **RM-095 — Health as diagnosis.** `health()` grows from
  status to diagnosis: the top suspected cause + the
  operation that would confirm it, for each degraded state.
  Class: UNIT.
- **RM-096 — Recovery playbooks.** docs/RECOVERY.md: for every
  typed error a caller can receive, what it means and the
  sane responses, with examples. Acceptance: every error code
  from RM-087 appears.
- **RM-097 — No-traceback guarantee.** A test harness calling
  every public API with the full fuzz corpus asserting only
  typed errors escape (plus documented Python errors for
  programmer misuse, listed by name). Class: UNIT.
- **RM-098 — Part gate.** Error-correcting evidence bundle
  filed; taxonomy frozen for 1.x.

## Part VIII — Crash-Proof: Fault Injection & Chaos (RM-099–RM-112)

*v1.0.0 proved kill-9 at a few points. This part tries to kill
the ravens every way a machine can.*

- **RM-099 — Fault-injection harness.** A shared test harness
  (per package, stdlib) that runs a workload subprocess and
  kills it at randomized points — before open, mid-write,
  mid-backup, mid-heal, mid-decay, mid-consolidate — then
  reopens and asserts the invariants. Class: FAULT.
- **RM-100 — Kill-matrix, muninn.** The harness across every
  muninn write API, 100 randomized kills each; committed-prefix
  property: whatever was acknowledged survives. Class: FAULT.
- **RM-101 — Kill-matrix, huginn.** Same across upsert/delete
  and both local modes (tfidf + vector). Class: FAULT.
- **RM-102 — Power-loss simulation.** Where the host allows,
  `fsync`-behaviour verified with a remount/read-only flip
  drill; where it does not, the slice closes NOT PROVEN for
  that road and says so. Class: FAULT / NOT PROVEN.
- **RM-103 — Crash during backup rotation.** Kill between
  snapshot-verify and rotation: previous generations intact,
  `.bak-tmp` cleaned or ignored on next open (see RM-032).
  Class: FAULT.
- **RM-104 — Crash during recovery.** Kill the process *while
  it is restoring from backup*: the next open still converges
  to a healthy store (restore is itself crash-safe or
  restarted). Class: FAULT.
- **RM-105 — Double-fault.** Corrupt main store *and* the
  newest backup simultaneously: recovery falls to the next
  verified generation; if none, typed error (never empty).
  Class: FAULT.
- **RM-106 — Clock chaos.** System clock jumps ±30 days
  between operations: no crash, ordering rules of RM-012 hold,
  decay's explicit-days semantics unaffected. Class: FAULT.
- **RM-107 — Signal storm.** SIGTERM/SIGINT mid-operation in a
  long batch: the process either finishes the transaction or
  rolls it back — never half. Class: FAULT.
- **RM-108 — Resource exhaustion.** File-descriptor and memory
  pressure during open and search: typed errors, no
  corruption, no leaked descriptors after failure. Class:
  FAULT.
- **RM-109 — Chaos soak.** 24h randomized chaos (kills,
  contention, clock jumps) over both packages with continuous
  invariant checking; the soak report joins the evidence
  bundle. Class: FAULT + BENCH.
- **RM-110 — Invariant checker as a tool.** The soak's checker
  shipped as `scripts/check_store.py` per package: any user
  can audit a store file offline. Class: UNIT.
- **RM-111 — Recovery-time bound.** Time-to-healthy after each
  fault class measured and published; a regression beyond the
  bound fails the part gate. Class: BENCH.
- **RM-112 — Part gate.** Crash-proof evidence bundle: the
  full kill matrices and chaos report, with every NOT PROVEN
  road named.

## Part IX — Scalability (RM-113–RM-126)

*From a personal store of thousands to archives of millions —
honestly, in steps.*

- **RM-113 — Scale atlas.** Benchmarks at 1M nodes / 1M
  documents (synthetic, seeded) for the operations that can
  plausibly survive; the ones that cannot are named, with
  their measured ceilings. Class: BENCH.
- **RM-114 — Streaming reads.** Cursor-based iteration over
  nodes/documents/associations (`iter_nodes`, `iter_documents`)
  with bounded memory, for export and migration. Class: UNIT.
- **RM-115 — Bulk export/import.** Dump/restore a whole store
  to/from a documented line-delimited format (JSONL), with
  integrity verification on import. Acceptance: round-trip
  equality on the atlas corpus. Class: UNIT.
- **RM-116 — Muninn sharding design.** Design slice: partition
  by id-range vs by category/path; cross-shard spread
  semantics stated or explicitly refused. Decision record,
  not code.
- **RM-117 — Muninn read replica.** A read-only follower that
  tails the WAL/snapshots of a writer store for read scaling,
  with staleness reported in its health. Acceptance: replica
  answers pure reads while the writer works. Class: UNIT.
- **RM-118 — Huginn large-corpus road.** At 1M documents the
  local TF-IDF candidate path measured; if it fails the gate,
  the honest answer is the Qdrant backend — plus an in-store
  partitioned-index variant is prototyped and measured
  before any promise. Class: BENCH.
- **RM-119 — Activation-log growth.** The log is append-only
  by design; add archival compaction (fold old log rows into
  counters, keep the fold auditable) behind a config flag,
  default off. Acceptance: counts identical before/after on
  the atlas corpus. Class: UNIT.
- **RM-120 — Edge-count scaling.** Hebbian wiring is O(n²) in
  the worst case by nature; add per-node degree caps with a
  stated eviction policy (weakest-first), off by default,
  tested for the symmetry invariant. Class: UNIT.
- **RM-121 — Multi-store tenancy.** A registry object holding
  many named stores with per-store config, for hosts (like
  Hermes profiles) that run several memories side by side.
  Class: UNIT.
- **RM-122 — Memory-mapped read mode.** An explicitly
  experimental read-only mmap mode, benchmarked against the
  standard connection; shipped only if it wins honestly.
  Class: BENCH.
- **RM-123 — Write throughput ceiling.** Batched-ingest
  pipeline for both packages (producer queue → single writer)
  measured at atlas scale. Class: BENCH.
- **RM-124 — Qdrant at scale.** Collection tuning notes +
  a 1M-point load test *when a real server is available*;
  otherwise NOT PROVEN and the fake-client limits stated.
  Class: LIVE / NOT PROVEN.
- **RM-125 — Backpressure v2.** Muninn's `max_nodes` policy
  generalized: configurable value function (importance,
  access, recency, confidence) with the default unchanged.
  Class: UNIT.
- **RM-126 — Part gate.** Scalability evidence bundle with
  measured ceilings printed in the guides — no extrapolated
  promises.

## Part X — Modularity (RM-127–RM-138)

*Pluggable everything, without disturbing the defaults that
work.*

- **RM-127 — Storage-engine interface, muninn.** Extract the
  store operations behind an internal protocol so the SQLite
  engine is one implementation; the public API does not move.
  Acceptance: full suite green against the interface.
  Class: UNIT.
- **RM-128 — Storage-engine interface, huginn local.** Same
  for the local backend's document/index operations. Class:
  UNIT.
- **RM-129 — Embedder protocol v2.** The `Embedder` protocol
  gains batch embedding + dimension discovery; hashing and
  sentence-transformers conform; a call-counting fake proves
  batching is used by upsert paths. Class: UNIT.
- **RM-130 — Ranking plugins.** Huginn scoring becomes a
  strategy object (tfidf / vector / hybrid from Part XII)
  selected by config, default unchanged. Class: UNIT.
- **RM-131 — Clock & id sources.** Time and id allocation
  become injectable (for tests and for hosts with their own
  id space), defaults unchanged. Class: UNIT.
- **RM-132 — Schema versioning machinery.** `meta.
  schema_version` gains a migration registry: ordered,
  transactional, tested migrations, exercised by a synthetic
  v1→v2 migration that changes nothing semantically. Class:
  UNIT.
- **RM-133 — Event hooks.** Optional observer callbacks
  (on_store, on_activate, on_decay, on_recover, on_heal)
  that can observe but never veto or mutate; used by Part XVI
  observability. Hooks that raise are isolated and logged.
  Class: UNIT.
- **RM-134 — Serializer plugins.** Node content serializers
  beyond JSON (e.g. pickle explicitly refused; msgpack behind
  an extra if argued), with the content_is_json flag
  generalized honestly. Class: UNIT.
- **RM-135 — Backend registry, huginn.** Backends register by
  name (`local`, `qdrant`, + future), so a new backend is an
  addition, not a patch. Acceptance: registry test with a
  toy backend. Class: UNIT.
- **RM-136 — Shared-core extraction study.** The two `_db.py`
  files are deliberate duplicates; study extracting a private
  shared wheel vs keeping duplication, judged by the
  independent-install law. Decision record; code only if the
  record says so.
- **RM-137 — Configuration providers.** Config loadable from
  dict / environment / TOML file through one documented
  loader per package; precedence stated; secrets (Qdrant API
  key) only from environment or explicit argument, never
  from a file that gets logged. Class: UNIT.
- **RM-138 — Part gate.** Modularity evidence bundle; every
  new interface carries a conformance test a third-party
  implementation could run.

## Part XI — Multi-Threading & Async (RM-139–RM-150)

*One lock per store is correct. This part finds out how much
further honesty allows.*

- **RM-139 — Concurrency model doc.** The v1.0.0 model (one
  connection, RLock serialization) written up precisely,
  including what it does *not* promise. 
- **RM-140 — Read concurrency study.** SQLite WAL allows
  concurrent readers; prototype a read-connection pool behind
  the pure-read APIs and measure. Shipped only if the race
  suites stay exact. Class: BENCH + FAULT.
- **RM-141 — Lock granularity.** Split the single RLock into
  read/write discipline only where RM-140's evidence supports
  it; every step re-proven by the race tests with exact
  totals. Class: UNIT.
- **RM-142 — Thread-pool batch APIs.** `activate_batch` /
  bulk ingest variants that parallelize the *preparation*
  (hashing, tokenizing, embedding) while keeping writes
  serialized. Class: BENCH.
- **RM-143 — Async facade, muninn.** `AsyncHebbianMemory`
  wrapping the sync API on a dedicated executor thread —
  honest wrapping, labelled as such. Class: UNIT.
- **RM-144 — Async facade, huginn.** `AsyncHuginnMemory`,
  same discipline; embedding calls (the genuinely slow part)
  run off the event loop. Class: UNIT.
- **RM-145 — Async-native Qdrant.** Where qdrant-client's
  async client is available, the async facade uses it
  natively instead of the executor. Proven against the fake
  client; live road NOT PROVEN until a server exists.
  Class: UNIT / NOT PROVEN.
- **RM-146 — Cross-process coordination.** Document + test
  the multi-process story (SQLite locking, busy_timeout,
  retry guidance) as a first-class supported mode. Class:
  UNIT.
- **RM-147 — Deadlock drills.** Adversarial interleavings
  (hooks calling back into the same store, nested batches)
  proven deadlock-free or explicitly refused by re-entrancy
  guards. Class: FAULT.
- **RM-148 — Contention benchmarks.** Throughput vs thread
  count curves (1–32 threads) for read, write and mixed
  workloads; the curves published, knees named. Class:
  BENCH.
- **RM-149 — Cancellation semantics.** Long operations
  (spread over huge graphs, bulk import) accept cancellation
  tokens and stop at transaction boundaries. Class: UNIT.
- **RM-150 — Part gate.** Threading evidence bundle: race
  suites exact, curves published, async facades' honesty
  labels in the guides.

## Part XII — Intelligent Functions (RM-151–RM-164)

*The ravens get smarter at their own jobs — retrieval quality,
memory judgement — with quality measured, not asserted.*

- **RM-151 — Retrieval quality harness.** A judged corpus
  (queries with known relevant memories) and metrics
  (recall@k, MRR) for Huginn, runnable per backend/embedder.
  Without this, no intelligence slice may claim improvement.
  Class: BENCH.
- **RM-152 — Neural embeddings, proven.** Install the
  `embeddings` extra in the verification environment; run the
  quality harness with sentence-transformers on local +
  hashing; publish the numbers. This closes v1.0.0's NOT
  PROVEN for the embedder path *in the harness environment*.
  Class: BENCH.
- **RM-153 — Live Qdrant proof.** Stand up a real Qdrant
  server natively (no Docker) on a test host; round-trip,
  filters, fallback and quality harness against it. Closes
  v1.0.0's live-server NOT PROVEN, or records exactly why it
  still cannot run. Class: LIVE.
- **RM-154 — Hybrid ranking.** Lexical + vector scores fused
  (reciprocal-rank or weighted, configurable) in the local
  backend; quality harness must show a win or the slice
  records a draw and stops. Class: BENCH.
- **RM-155 — Query understanding v2.** `analyze_query` grows:
  entity/keyword extraction beyond stopwords, negation
  detection, and category inference — all as *reported
  analysis*; retrieval uses it only where the harness proves
  a win. Class: BENCH.
- **RM-156 — Importance-aware ranking.** Search results
  re-ranked by a stated blend of score × importance ×
  recency × confidence (Muninn's, when composed), behind a
  config flag, default off; harness-judged. Class: BENCH.
- **RM-157 — Salience scoring, muninn.** A computed salience
  per node (importance, activation history, wiring degree,
  valence magnitude) exposed as a pure read and used by
  backpressure/consolidation policies when enabled. Class:
  UNIT.
- **RM-158 — Forgetting curves.** Decay gains an
  Ebbinghaus-style per-node curve option (stability grows
  with reactivations) beside the half-life default; the
  default does not change. Acceptance: curve tests at known
  points. Class: UNIT.
- **RM-159 — Consolidation intelligence.** Consolidation
  learns which edges *predict* future co-activation (held-out
  log evaluation) and reports its precision; threshold
  auto-suggestion (report only, never silent change).
  Class: BENCH.
- **RM-160 — Near-duplicate detection.** A maintenance
  operation reporting near-duplicate nodes/documents (by
  content similarity) with a merge *proposal* — merging
  itself stays an explicit caller act. Class: UNIT.
- **RM-161 — Multi-hop reasoning v2.** `multi_hop_retrieve`
  gains path scoring (each hop's chain carries a combined
  score) and cycle protection; quality harness compares
  against v1 behaviour. Class: BENCH.
- **RM-162 — Association explanation.** `explain(a, b)` in
  muninn: the paths and strengths connecting two memories —
  the wiring made legible. Pure read. Class: UNIT.
- **RM-163 — Retrieval explanation.** Huginn search results
  optionally carry `why` (matched terms / vector neighbours
  summary), behind a flag, so callers can show their work.
  Class: UNIT.
- **RM-164 — Part gate.** Intelligence evidence bundle:
  harness numbers per backend/embedder/ranker, with every
  claimed win tied to a metric delta.

## Part XIII — Advanced Intelligence (RM-165–RM-178)

*Beyond better retrieval: the ravens reason over what they
keep. Every slice here is judged by the Part XII harness or an
equal — no vibes.*

- **RM-165 — Cross-raven federation.** A composed facade
  (new module, neither package changed) that queries Huginn
  for candidates and expands them through Muninn's spread
  activation, returning one ranked, explained result set —
  Bifröst's composite idea, as a reusable library. Class:
  UNIT.
- **RM-166 — Memory-guided query expansion.** Queries expanded
  with terms from strongly-associated memories (via the
  federation facade), harness-judged against unexpanded
  retrieval. Class: BENCH.
- **RM-167 — Reflective consolidation.** A "sleep" cycle that
  runs decay + consolidation + near-duplicate proposals +
  salience recomputation as one reported maintenance pass,
  scheduled by the *caller*; the ravens never wake on their
  own. Class: UNIT.
- **RM-168 — Episode threading.** Muninn nodes gain optional
  episode grouping (sequences that belong together in time),
  with retrieval that can return whole episodes. Class:
  UNIT.
- **RM-169 — Contradiction watch.** New content that strongly
  matches but negates an existing memory (negation detection
  from RM-155) is flagged in a review queue — flagged, never
  silently resolved. Class: UNIT.
- **RM-170 — Confidence calibration.** Node confidence vs
  observed future usefulness measured over the activation
  log; the confidence update rule re-fit or honestly
  reported as already sound. Class: BENCH.
- **RM-171 — Valence-aware retrieval.** Optional retrieval
  bias by emotional-valence match to a target state,
  flag-gated, harness-judged for not wrecking relevance.
  Class: BENCH.
- **RM-172 — Concept graph export.** The wiring exported as a
  labelled graph (nodes, edges, strengths) in a documented
  format for visualisation and external analysis. Pure read.
  Class: UNIT.
- **RM-173 — Predictive prefetch.** Given a set of just-used
  memories, predict the likely-next set (spread + log
  patterns) as a pure read hosts can cache by. Class: BENCH.
- **RM-174 — Learning-rate adaptation.** Per-pair learning
  rates that adapt to observed co-activation reliability,
  behind a flag; the classic bounded rule stays the default.
  Class: BENCH.
- **RM-175 — Cross-store identity resolution.** Tooling for
  hosts that keep the same memory in several stores: id
  mapping tables + a reconciliation report (the Bifröst
  Mímir↔Huginn↔Muninn problem, generalized). Class: UNIT.
- **RM-176 — Summarization hooks.** Interfaces (not models)
  by which a host's own LLM can summarize clusters of nodes
  into digest memories, with provenance links kept — the
  ravens store and wire; the host thinks. Class: UNIT.
- **RM-177 — Forgetting with dignity.** Importance- and
  salience-aware archival: cold memories moved to an archive
  store file, still retrievable, never silently dropped;
  the archive is a first-class store, not a bin. Class:
  UNIT.
- **RM-178 — Part gate.** Advanced-intelligence evidence
  bundle: every feature flag's harness verdict printed,
  including the ones that lost.

## Part XIV — Adaptability (RM-179–RM-190)

*All kinds of uses, all kinds of data.*

- **RM-179 — Typed content kinds.** Beyond string/JSON:
  registered content kinds (event, document, dialogue turn,
  structured record) with per-kind validation and indexing
  hints, stored through the existing content machinery.
  Class: UNIT.
- **RM-180 — Binary by reference.** Large/binary payloads
  stored outside the DB by content-addressed reference, with
  integrity verification on read and garbage collection of
  unreferenced blobs. Class: UNIT.
- **RM-181 — Document ingestion.** Chunking + ingest helpers
  (long text → linked chunk nodes/documents with provenance)
  in an optional `ravens-documents` extra module per
  package. Class: UNIT.
- **RM-182 — Event streams.** An append-shaped ingest API
  for event/time-series memories, with time-window retrieval
  in both packages. Class: UNIT.
- **RM-183 — Postgres backend study.** Design slice: what a
  Postgres storage engine (via RM-127/128 interfaces) would
  keep and break — the shared-schema law, transactions,
  WAL story. Decision record.
- **RM-184 — Postgres backend build.** If RM-183 argues yes:
  the engine, behind an extra, passing the same conformance
  suite as SQLite. Class: UNIT (LIVE for a real server
  proof, else NOT PROVEN for that leg).
- **RM-185 — Redis cache tier.** An optional Redis-backed
  cache in front of pure reads, with invalidation discipline
  stated and tested against a fake client; live proof NOT
  PROVEN until a server exists. Class: UNIT / NOT PROVEN.
- **RM-186 — Qdrant-native collections.** Multiple named
  collections per Huginn object (per-category or per-tenant),
  with the single-collection default unchanged. Class: UNIT.
- **RM-187 — A wire protocol.** A small documented
  JSON-lines protocol + reference server (stdlib) so
  non-Python programs can use the ravens — the seam made
  portable. Class: UNIT.
- **RM-188 — Language bindings via the protocol.** A thin
  TypeScript client for RM-187's protocol, generated docs,
  conformance-tested against the reference server. Class:
  UNIT.
- **RM-189 — Embedded profile.** A documented minimal
  configuration for tiny hosts (small caches, backups off
  only by explicit choice, single-file stores) — the toaster
  profile — with its trade-offs printed. Class: UNIT.
- **RM-190 — Part gate.** Adaptability evidence bundle:
  every new data kind/store/protocol with its conformance
  results and its NOT PROVEN legs named.

## Part XV — Interop (RM-191–RM-198)

*The ravens at work in Volmarr's other halls.*

- **RM-191 — Bifröst pin refresh.** Re-verify against the
  then-current Bifröst head; if Bifröst has moved, re-extract
  the contract and diff it against BUILD_NOTES §1. Class:
  UNIT.
- **RM-192 — Hermes binding.** The volmarr-core memory fabric
  gains the flags to enable the ravens' write paths
  (consolidation, decay, reinforcement, ingestion) behind
  explicit switches, per the Slice 86/87 audit trail.
  Acceptance: Hermes contract tests green; defaults keep
  today's behaviour. Class: UNIT.
- **RM-193 — Ember binding.** Project Ember's own bifrost
  copy reconciled with this repo as the single source; the
  toaster profile (RM-189) proven on the smallest target
  available. Class: UNIT / LIVE where hardware is involved.
- **RM-194 — Rúnmál binding.** Rúnmál's chat memory wired to
  the ravens as an optional backend, behind its own config,
  defaults unchanged. Class: UNIT.
- **RM-195 — ThoughtForge binding.** ThoughtForge's knowledge
  store gains a ravens adapter for its cite-or-explain
  memory enforcement; the citation shapes documented.
  Class: UNIT.
- **RM-196 — Yggdrasil node memory.** A Yggdrasil node agent
  uses the ravens as its local memory (per-node stores,
  RM-121 tenancy), as a reference integration with tests.
  Class: UNIT.
- **RM-197 — Migration tooling.** `ravens-migrate`: move a
  store between engines/backends (SQLite→Postgres,
  local→Qdrant) with verification reports. Class: UNIT.
- **RM-198 — Part gate.** Interop evidence bundle: every
  binding with the host project's own tests cited by count.

## Part XVI — Observability (RM-199–RM-206)

*If it healed, decayed, fell back or slowed down, you can see
it.*

- **RM-199 — Structured events.** The RM-133 hooks given a
  documented event schema (JSON-serializable, content-free
  by default per RM-044). Class: UNIT.
- **RM-200 — Metrics surface.** Counters/histograms
  (operations, latencies, heal fixes, fallback count)
  exportable as a plain dict and as Prometheus text, behind
  no dependency. Class: UNIT.
- **RM-201 — Health history.** A bounded ring of recent
  health snapshots per object, so "when did it degrade?" is
  answerable. Class: UNIT.
- **RM-202 — Slow-operation log.** Operations beyond a
  configurable threshold logged with operation + size (never
  content), with the threshold in config. Class: UNIT.
- **RM-203 — Store inspector CLI.** `python -m muninn` /
  `python -m huginn` inspect commands: health, stats,
  backup verification, invariant check (RM-110) — read-only.
  Class: UNIT.
- **RM-204 — Trace ids.** Caller-supplied correlation ids
  threaded through logs and events for one operation.
  Class: UNIT.
- **RM-205 — Dashboard data export.** One JSON document per
  store summarizing everything a dashboard needs (health,
  stats, scale, healing history) — the kiosk-shaped view.
  Class: UNIT.
- **RM-206 — Part gate.** Observability evidence bundle:
  the event schema and metrics list frozen for 1.x.

## Part XVII — Proof Spine (RM-207–RM-212)

*The road re-measures itself. Nothing in Parts I–XVI is
"done" until this part says so, from fresh runs.*

- **RM-207 — Full re-verification.** Fresh venvs, clean
  machine where possible: both suites, both kill matrices,
  the chaos soak summary, the quality harness, the
  benchmark atlas — all re-run and published as one
  evidence document. Class: ALL.
- **RM-208 — The NOT PROVEN ledger.** Every NOT PROVEN item
  accumulated across all parts, in one list, each with the
  exact evidence that would close it and what it would take
  to obtain. Nothing falls off this list quietly.
- **RM-209 — Claims audit.** README, guides and INTERFACE
  files re-read against the code; every claim traced to a
  test, a benchmark or a labelled opinion. Disagreements
  fixed in the docs' favour of the code.
- **RM-210 — External review pass.** The packages handed to
  a fresh reader (human or agent) who has not seen the
  build, with instructions to break them; findings triaged
  into fixes or roadmap amendments.
- **RM-211 — Version 2.0 decision.** From the whole road's
  evidence: what 2.0 is (and is not), which deferred designs
  (RM-048, RM-116, RM-136, RM-183) graduate, and the
  migration promise carried forward.
- **RM-212 — Roadmap closure.** This roadmap re-read end to
  end; every slice marked done / not-proven / superseded
  with its evidence link. The next roadmap, if any, starts
  from that truth.

---

*Roadmap written 2026-10-31, the day the ravens got their
GitHub home. It governs until Volmarr amends it. Slices are
worked in part order by default; within the laws above, a
later slice may be pulled forward when a host project needs
it — the pull is recorded in the slice log.*
