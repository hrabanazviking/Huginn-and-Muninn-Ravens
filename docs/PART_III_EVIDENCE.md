# Part III — Robustness: Evidence Bundle (RM-038, Part Gate)

*Hostile inputs, weird filesystems, half-dead disks — the
ravens keep their shape.* Part III (RM-025–RM-038) is
**complete**. Every claim below is filed from the slice's
own record — `docs/SLICE_LOG.md` and `CAMPAIGN_STATE.md`
carry the full entries; this bundle is the index and the
verdict.

## The FAULT results (every one, as the gate requires)

Three Part III slices carry the FAULT class — fault
injection against real filesystem conditions. All three
closed green, with the store openable and consistent
afterwards in each case:

- **Disk-full (RM-029)** — `docs/DISK_FULL.md`. Every
  public write in both packages runs behind a write guard:
  on a storage failure the failed call's transaction is
  rolled back (no partial write survives, nothing leaks
  into a later commit — proven for Muninn's 300-node
  `activate_batch` and for Huginn's replace-by-id upsert,
  which de-indexes before it writes) and the caller gets
  the typed `MuninnStorageError` / `HuginnStorageError`.
  Pinned by `tests/test_disk_full.py` (muninn 3, huginn 2).
- **Read-only filesystem (RM-030)** —
  `docs/READONLY_FILESYSTEM.md`. There is no read-only
  mode: a store is opened for writing or not at all. A
  pre-flight at the head of `open_store` refuses a
  read-only location loudly and immediately with the
  typed storage error, before any connection — a
  read-only open never takes the corruption/restore road
  and never escapes raw (`EROFS`/`EACCES`/`EPERM` and
  SQLite's read-only wordings are translated at every
  later open stage too). Pinned by
  `tests/test_readonly_filesystem.py` (muninn 4,
  huginn 3).
- **Partial-file states (RM-032)** —
  `docs/PARTIAL_FILE_STATES.md`. Defined open behaviour
  for each half-dead combination: a zero-length main file
  takes the corruption road *before* any connection
  (restore the newest verified generation, else the typed
  corrupt refusal, the truncated file left untouched)
  instead of silently opening as an empty store over a
  verified backup; a non-empty WAL without its main file
  restores a verified backup instead of being silently
  discarded; a `.bak-tmp` left by a killed backup is
  cleaned on open. Pinned by
  `tests/test_partial_file_states.py` (muninn 10,
  huginn 10).

## The rest of the robustness evidence

- **Fuzzing (RM-025, RM-026)** —
  `docs/INPUT_FUZZING_MUNINN.md`,
  `docs/INPUT_FUZZING_HUGINN.md`. Property-style fuzz over
  every validator in both packages, stdlib-only, seeds
  20261031 / 20261101 / 42 recorded: every generated input
  either succeeds or raises a typed package error, and
  every rejected write leaves the store byte-identical.
  Negation: each suite failed 8 of 10 tests against the
  pre-fix code. Nineteen defects were found and fixed
  across the two slices (oversize ids overflowing SQLite,
  a partial write left pending by a failed
  `activate_batch`, validation after a first write in
  `associate`, bare `float()`/`int()` escapes, NaN decay,
  bare-string tags exploding into characters, and kin).
- **Ceilings and shapes (RM-027, RM-028, RM-036)** —
  `docs/OVERSIZE_POLICY.md` (configurable content and
  metadata ceilings, typed refusal before any write,
  boundary-tested at / above / below),
  `docs/PATHOLOGICAL_PATHS.md` (one path normaliser for
  every entry point: `..` clamps at the root, empty and
  `.` segments drop, LIKE-wildcard segments name exactly
  themselves), `docs/ADVERSARIAL_TAGS_METADATA.md` (one
  iterative depth bound of 100 containers over JSON
  content, metadata and tag elements — thousands-deep
  values are typed refusals, never raw `RecursionError`s;
  the RM-027 ceilings applied uniformly to the cleaned
  tags list, so a 200,000-tag flood is refused).
- **Contention and concurrency (RM-031, RM-037)** —
  `docs/LOCKED_STORE.md` (busy timeout honoured, then the
  one typed contention message naming the store and the
  expired timeout, at every open stage — never the
  corruption road), `docs/CONCURRENT_OPENERS.md`
  (concurrent openers **defined as supported** and made
  true: a per-store coordination lock serializes
  creation, probe, restore, backup-on-open, heal and
  every rolling backup, while SQLite serializes ordinary
  reads/writes; the pre-slice races — fresh-store creation
  read as corruption, concurrent `backup()` colliding on
  `.bak-tmp`, restore-over-restore — were proven first by
  negation, muninn 3 failed / 5 passed, huginn 1 failed /
  7 passed).
- **File shapes and encodings (RM-033, RM-034)** —
  `docs/NON_DATABASE_FILES.md` (a directory, a text file
  and an empty file at the db path all answered with
  typed errors, never tracebacks — a shape pre-flight
  runs before every other open step),
  `docs/UNICODE_GAUNTLET.md` (lone surrogates refused
  with a typed validation error in both ravens before any
  write; valid unicode pinned verbatim — RTL/CJK
  round-trip and search, emoji ZWJ byte-for-byte,
  combining marks never normalised, astral characters
  pass).
- **Huge-batch atomicity (RM-035, BENCH)** —
  `docs/HUGE_BATCH_ATOMICITY.md`. `activate_batch` gained
  a bulk road at ≥64 unique ids inside the same single
  transaction: 500 ids went from 16.90 s (per-pair loop)
  to 0.64 s, and the 10k bench completed all eight checks
  — 49,995,000 pairs / 99,990,000 directed rows in
  1629.6 s at peak RSS 47.5 MB — with exact counts,
  including one-direction drift repair, proven by tests.

## Slice check-off

| Slice | Acceptance, in one line | Suites at banking (muninn / huginn) |
|---|---|---|
| RM-025 Input fuzzing, muninn | Every validator fuzzed; only typed errors, no partial writes; 10 defects fixed | 141 / 100 |
| RM-026 Input fuzzing, huginn | Same discipline over upsert/search/get/delete + query text; 9 defects fixed | 141 / 110 |
| RM-027 Oversize content policy | Configurable content/metadata ceilings; typed refusal before any write | 149 / 115 |
| RM-028 Pathological paths | One normaliser, `..` clamped at root, wildcard segments literal | 161 / 115 |
| RM-029 Disk-full behaviour | FAULT: typed storage errors, rollback exact, store still openable | 164 / 117 |
| RM-030 Read-only filesystem | FAULT: loud immediate typed refusal; no read-only mode, no hang | 168 / 120 |
| RM-031 Locked-store contention | Busy timeout honoured, then one typed contention message; two-process test | 173 / 126 |
| RM-032 Partial-file states | FAULT: zero-length store, orphan WAL, stale `.bak-tmp` each defined + tested | 183 / 136 |
| RM-033 Non-database files | Directory / text / empty file at the db path: typed errors, never tracebacks | 191 / 144 |
| RM-034 Unicode & encoding gauntlet | Lone surrogates refused typed; valid unicode verbatim, never normalised | 208 / 154 |
| RM-035 Huge-batch atomicity | BENCH: 10k ids, 49,995,000 pairs exact, 1629.6 s, peak RSS 47.5 MB | 215 / 154 |
| RM-036 Adversarial tags/metadata | Depth bound 100 over content/metadata/tags; tag ceilings uniform | 231 / 161 |
| RM-037 Concurrent openers | Defined as supported; coordination lock serializes open duties + backups | 239 / 169 |
| RM-038 Part gate | This bundle | 241 / 171 |

One discovered bug was fixed inside the part beyond the
fuzz finds: RM-033's build diagnosed a flaky RM-031
golden case in the test harness itself (the lock holder
was kept alive only by an incidental reference cycle, so
GC timing could close it mid-pass); `_cases` now returns
the holder and the test holds a strong reference — a
test-side fix, no package code, per-case loop 6/6 clean
per package.

## Contract verifications inside the part

Bifröst contract re-verification (fresh venv, bifrost at
b66e98cc, its own suites 25 passed + BifrostBridge
store/search/recall/decay/consolidate smoke PASS) ran for
every Part III slice — **RM-025 through RM-037, thirteen
for thirteen green** — because every slice in this part
changed validation, open, or write behaviour.

## Floors standing at the gate

- Lint/type floor (RM-008): ruff + mypy clean in both
  packages at every Part III banking.
- Coverage floor (RM-009): `fail_under = 88` in both
  pyprojects.
- Schema snapshots (RM-004) and contract freezes (RM-003)
  green at every banking: **no schema changed in Part
  III** (RM-035's index drop/recreate happens inside its
  transaction and restores on rollback; RM-037's
  `.open-lock` is a transient non-store neighbour file,
  recorded in the format-stability family).

## Honesty ledger, carried forward unchanged

- Live Qdrant round-trip: **NOT PROVEN** (no live server
  run yet; every Qdrant-side claim in Part III is
  construction or fake-client proof — Huginn's oversize
  policy is enforced in the facade before any backend is
  touched, so it holds on Qdrant by construction).
- Sentence-transformers path: **NOT PROVEN** (the extra
  has not been run live).
- GitHub-hosted CI: **NOT PROVEN** (manual-only workflow,
  never dispatched; all matrix evidence is local).

## Debts the part leaves, named

- **Founding-tree sync**: the founding tree
  (`~/workspace/ravens`) is behind this repo by every
  Part III package-source change on top of the Part II
  debt (fuzz fixes, ceilings, path normaliser, write
  guard, read-only and shape pre-flights, contention
  classification, partial-file roads, surrogate checker,
  bulk batch road, depth bound, coordination lock). The
  sync is recorded here and in `CAMPAIGN_STATE.md`; it is
  a deliberate later act, not done by this gate.
- `schema_version` is recorded, not yet gated on —
  RM-082 (Part VI) defines foreign-schema behaviour and
  RM-132 (Part X) builds the migration registry
  (`docs/FORMAT_STABILITY.md` states the interim rule).
- RM-012's timestamp guard is per object: under
  RM-037's supported concurrent openers, cross-object
  timestamps may repeat or invert by microseconds —
  stated in `docs/CONCURRENT_OPENERS.md`, not hidden.

## Gate verdict

Part III's acceptance stands on filed evidence for every
slice: both fuzz suites green against recorded seeds
with nineteen defects fixed, every FAULT result filed
above (disk-full, read-only, partial-file states), the
contention and concurrent-opener behaviours defined in
writing and pinned, and the 10k huge-batch bench exact.
**Part III is complete.** The road continues at Part IV
— Security (RM-039–RM-056).
