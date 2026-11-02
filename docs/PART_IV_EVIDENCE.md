# Part IV — Security: Evidence Bundle (RM-056, Part Gate)

*A memory store holds the most sensitive data a program
has. Treat it that way.* Part IV (RM-039–RM-056) is
**complete**. Every claim below is filed from the slice's
own record — `docs/SLICE_LOG.md` and `CAMPAIGN_STATE.md`
carry the full entries; this bundle is the index and the
verdict. The threat model (`docs/THREAT_MODEL.md`) was
re-reviewed at this gate and every register state updated
with what the part actually built; the re-review record
is in that document, and its summary is filed below.

## The FAULT results (every one, as the gate requires)

Three Part IV slices carry the FAULT class — fault
injection against real stores, tampering, and residue.
All three closed green:

- **Store encryption, build (RM-049)** —
  `docs/STORE_ENCRYPTION.md` (the RM-048 design record
  stands in the same file). Application-level envelope
  encryption behind the bounded `cryptography` extra and
  an opt-in flag: content values sealed AES-256-GCM in
  the same TEXT columns (no schema change), the data key
  wrapped under a PBKDF2-HMAC-SHA256 KEK, open-time key
  proof before any write — a wrong passphrase and a
  plain (flag-off) open of a marked store both refuse
  typed with the store byte-for-byte untouched, and the
  kill-9 + recovery suites pass against encrypted
  stores. Pinned by `tests/test_store_encryption.py`
  (9 tests per package). Negation against the RM-048
  packages: 8 failed / 1 passed per package.
- **Integrity attestation (RM-050)** —
  `docs/INTEGRITY_ATTESTATION.md`. An optional stdlib
  HMAC-SHA256 chain over Muninn's `activation_log`:
  modify one row by raw SQL, open, and the tampering is
  *reported* — `integrity_attestation` in `health()`
  reads `tamper_detected`, the failure is logged at
  ERROR, and the tampered rows are left as found
  (detection, not silent repair). Inserted and deleted
  rows, a rewritten chain head, and a wrong passphrase
  are all detected or refused as recorded. Pinned by
  `tests/test_integrity_attestation.py` (13 tests,
  Muninn; Huginn has no activation log — its slice work
  is the slice-log pin). Negation against the RM-049
  packages: 12 failed / 0 passed / 1 skipped.
- **Forget is forgetting (RM-051)** —
  `docs/SECURE_FORGET.md`. The forensic audit first
  proved the truth about plain `forget` / `delete`: the
  live rows go, but the content persists in WAL frames,
  in freed pages, and in every rolling backup generation
  until rotation — and both guides now state that truth.
  The new `secure_forget` purges: the delete runs under
  `secure_delete=ON`, both WAL checkpoints truncate,
  `VACUUM` rebuilds the store from live rows only, and
  every `.bak-*` generation is discarded and replaced by
  one fresh snapshot of the purged store. The forensic
  before/after byte-search finds the forgotten string in
  **no** file after `secure_forget` — main, `-wal`,
  `-shm`, every generation, open, closed and reopened.
  Pinned by `tests/test_secure_forget.py` (muninn 10,
  huginn 8). Negation against the RM-050 packages:
  muninn 8 failed / 2 passed, huginn 6 failed / 2 passed
  (the passes are exactly the preserved behaviours).

## The rest of the security evidence

- **The model itself (RM-039)** —
  `docs/THREAT_MODEL.md`. Ten assets, four actors (plus
  two named sub-cases), seven trust boundaries,
  twenty-one threats (TH-01–TH-21), eight explicit
  non-goals — reviewed against both codebases at the
  Part III gate, with the citation rule every later
  slice in this part obeyed: each slice-log entry cites
  the threats it owns, and this gate (RM-056) re-checked
  the whole register.
- **Injection and path safety (RM-040, RM-041)** —
  `docs/SQL_INJECTION_AUDIT.md` (every SQL site in both
  packages inventoried by AST: values always bound, the
  only interpolated SQL proven to come from closed sets;
  a hostile-content battery stored and retrieved
  verbatim), `docs/PATH_SAFETY.md` (an opt-in strict
  mode, `strict_path_safety`, that refuses symlinked
  store paths/parents and world-writable immediate
  parents before anything is created; the default
  recorded behaviour is unchanged and pinned as such).
- **File and backup confidentiality (RM-042, RM-043)**
  — `docs/FILE_PERMISSIONS.md` (new store files created
  owner-only `0600` under any umask, sidecars included;
  an existing looser file is never re-permissioned and
  is instead reported by `health()`'s
  `file_permissions_warning`), `docs/BACKUP_CONFIDENTIALITY.md`
  (every rolling backup inherits the store file's exact
  mode at the moment it is taken, on every backup road).
- **Diagnostics hygiene (RM-044, RM-054)** —
  `docs/LOG_REDACTION.md` (no package log record carries
  memory content at INFO or below, ever; content may
  appear only at DEBUG, only with the off-by-default
  `debug_log_content` flag, and only on two named paths
  per package), `docs/ERROR_MESSAGE_HYGIENE.md` (typed
  errors are built only from fixed text,
  package-computed values, the caller's own supplied
  path/URL/collection, and the underlying exception's
  class name — the proven leak, a store trigger's
  `RAISE(ABORT, '…')` text riding verbatim into typed
  errors, is closed and regression-pinned; fourteen
  uncontrolled-text wrap sites closed).
- **Qdrant boundary (RM-045, RM-046)** —
  `docs/QDRANT_TRANSPORT.md` (HTTPS required by default
  for non-loopback Qdrant URLs, with the explicit
  `allow_insecure_http` opt-out; the API key's one
  destination is the client constructor, it is excluded
  from the config `repr`, and at this slice's build
  every wrapped client error was key-scrubbed —
  superseded in mechanism by RM-054, which forwards
  only the exception's class name; the facade still
  key-scrubs the strings it reports, as defence in
  depth), `docs/QDRANT_PAYLOAD.md` (payload keys are a
  closed set of six, built from one fixed dict; returned
  points pass a shape-and-integrity hygiene check —
  including `content_hash` equality — before they are
  trusted, and a malformed point is a loud typed refusal,
  never a coerced repair). All Qdrant-side proof is
  construction or fake-client proof; live behaviour
  stays in the honesty ledger below.
- **Identity and at-rest (RM-047, RM-048)** —
  `docs/HASH_COLLISION.md` (SHA-256 stated as the
  collision assumption, and a length+exact-content
  double check on every idempotent-store road, so a
  collision — crafted, forged, or from the Qdrant
  derived id's truncated space, now masked to 63 bits —
  refuses typed instead of silently merging),
  `docs/STORE_ENCRYPTION.md`'s design record (SQLCipher
  rejected on the record — a compiled fork an extra
  cannot express, and whole-file encryption would break
  the TB-7 shared-schema readability the contract
  stands on; filesystem encryption adopted as deployment
  guidance, not a library promise; envelope encryption
  chosen and built by RM-049 above).
- **Supply chain and cost (RM-052, RM-053)** —
  `docs/DEPENDENCY_HYGIENE.md` (both cores
  dependency-free; every declared requirement bounded
  `>=floor,<ceiling` and test-pinned; a 23-pin lockfile
  example; a bounded `pip-audit` scan step in the manual
  CI — and the slice's own scan caught PYSEC-2026-1845
  in the newest pytest its old dev bound allowed, fixed
  in-slice by raising the bound to reach the fix),
  `docs/QUERY_COST_CAPS.md` (explicit candidate-set
  caps — Muninn `max_spread_candidates`,
  Huginn `max_search_candidates` — deterministic in
  their bite, returning the partial result, never an
  error, with the bite visible in dedicated stat
  accessors and a counts-only WARNING; below the
  ceilings behaviour is exactly the unbounded
  behaviour).
- **Defaults (RM-055)** — `docs/SECURE_DEFAULTS.md`.
  All 38 config fields (19 per package) re-judged in
  four classes; **no default changed** — every default
  that could leak content, weaken transport, execute or
  download is already off, loopback-confined or opt-in,
  every on default is safety-positive or bounded, and
  the three compatibility-kept judgements are named
  plainly (strict path safety off in both, Huginn
  `backend="auto"` with its not-silent fallback,
  encryption/attestation off because a default must
  never invent a passphrase). Drift the review found —
  config rows missing from the guides and API reference
  — was fixed in-slice and is now test-pinned.

## Threat register, re-checked at this gate

The full re-review is recorded in `docs/THREAT_MODEL.md`
(RM-056 section); the verdicts in one view:

- **Controlled:** TH-01 (injection), TH-03 (file
  permissions), TH-04 (backup confidentiality), TH-05
  (content in logs), TH-08 (hash-collision merge),
  TH-12 (dependency hygiene — the locally run scan is
  proven; a GitHub-hosted run is not), TH-13 (query
  cost), TH-14 (error messages), TH-15 (defaults
  review), TH-17 and TH-18 (unchanged from Parts
  II–III).
- **Partial, by stated design:** TH-02 (strict path
  safety is opt-in; the default recorded behaviour
  stands, per RM-041/RM-055), TH-06 and TH-07 (Qdrant
  controls built and fake-client pinned; live behaviour
  NOT PROVEN), TH-09 (confidentiality at rest exists as
  the opt-in RM-049 build; a default store is plaintext
  by the caller's choice, and structure/counts stay
  readable even encrypted), TH-10 (attestation is
  opt-in, Muninn's activation log only, detection
  reported not prevented), TH-11 (plain forget's
  residue truth is documented and `secure_forget` is
  the purging operation; plain `forget` itself keeps
  its recorded semantics), TH-16 (model drift — closed
  at this gate by this re-review; a standing process
  risk every future part gate re-checks), TH-19
  (unchanged; owned by RM-082 / RM-132).
- **Accepted, unchanged:** TH-20 (contract-reader
  exposure), TH-21 (memory poisoning — bounded, judged
  by hosts and the intelligence parts, never by the
  store).

No threat was found in Part IV that the RM-039 model
did not name; no register entry was deleted.

## Slice check-off

| Slice | Acceptance, in one line | Suites at banking (muninn / huginn) |
|---|---|---|
| RM-039 Threat model | Assets/actors/boundaries/register reviewed against both codebases; citation rule set | 243 / 173 |
| RM-040 SQL-injection audit | Every SQL site inventoried; values bound; hostile battery verbatim | 252 / 180 |
| RM-041 Path safety | Opt-in strict mode refuses symlinked paths + world-writable parents | 261 / 189 |
| RM-042 File permissions | New stores `0600` under any umask; looser existing files reported in `health()` | 268 / 196 |
| RM-043 Backup confidentiality | Every backup inherits the store file's exact mode | 273 / 200 |
| RM-044 Log redaction | No content in logs at INFO or below; DEBUG content only behind an off-by-default flag | 280 / 207 |
| RM-045 Qdrant transport safety | HTTPS by default beyond loopback; key handling audited + scrubbed | 280 / 222 |
| RM-046 Qdrant payload hygiene | Closed payload key set; returned points hygiene-checked before trust | 280 / 236 |
| RM-047 Hash-collision honesty | Length+content double check on every idempotent road; typed collision refusal | 288 / 248 |
| RM-048 Store encryption, design | Decision record: envelope encryption chosen, SQLCipher rejected on the record | 290 / 250 |
| RM-049 Store encryption, build | FAULT: encrypted store unreadable in content by plain sqlite3; wrong-key open refuses typed | 299 / 259 |
| RM-050 Integrity attestation | FAULT: raw-SQL tamper of the activation log detected and reported on open | 312 / 259 |
| RM-051 Forget is forgetting | FAULT: `secure_forget` purges WAL, freed pages and every backup generation | 322 / 267 |
| RM-052 Dependency hygiene | Bounds pinned, lockfile example filed, scan in manual CI; PYSEC-2026-1845 fixed in-slice | 329 / 274 |
| RM-053 Denial-of-service bounds | BENCH: candidate-set caps bite deterministically at exactly the stated bound, with visibility | 336 / 282 |
| RM-054 Error-message hygiene | Typed errors carry no uncontrolled exception text; planted-leak scan pinned | 343 / 290 |
| RM-055 Secure defaults review | All 38 defaults re-judged and recorded in the guides; no default changed; drift fixed | 350 / 298 |
| RM-056 Part gate | This bundle; threat model re-reviewed and updated | (gate counts in `CAMPAIGN_STATE.md`) |

## Contract verifications inside the part

Bifröst contract re-verification (fresh venv, bifrost at
b66e98cc, its own suites 25 passed + BifrostBridge
store/search/recall/decay/consolidate smoke PASS) ran
for every Part IV slice that changed a public API or the
shared schema: **RM-041, RM-049, RM-050, RM-051, RM-053,
RM-054** — six for six green (RM-046 also ran it as a
precaution). The gate itself changes no package source,
public API, or schema, so no re-verification is required
for RM-056.

## Floors standing at the gate

- Lint/type floor (RM-008): ruff + mypy clean in both
  packages at every Part IV banking.
- Coverage floor (RM-009): `fail_under = 88` in both
  pyprojects.
- Schema snapshots (RM-004) and contract freezes
  (RM-003) green at every banking: **no schema changed
  in Part IV** — RM-049's envelopes live in the same
  TEXT columns and RM-050's chain header in `meta` rows,
  so the contracted tables (`activation_log`,
  `hebbian_connections`, integer memory ids) are exactly
  as frozen, and encrypted stores keep those tables
  plaintext-readable by direct readers, as RM-048's
  decision required.

## Honesty ledger, carried forward unchanged

- Live Qdrant round-trip: **NOT PROVEN** (no live server
  run yet; every Qdrant-side claim in Part IV —
  transport, payload hygiene, the Qdrant
  `secure_forget`, the derived-id double check — is
  construction or fake-client proof).
- Sentence-transformers path: **NOT PROVEN** (the extra
  has not been run live).
- GitHub-hosted CI: **NOT PROVEN** (manual-only workflow,
  never dispatched — including RM-052's new
  dependency-scan job; the scan itself was run locally
  and its results are filed in `docs/DEPENDENCY_HYGIENE.md`).
- The `cryptography` extra, by contrast, **is** proven
  from RM-049: installed via the extra in the ravens'
  own venvs and exercised end to end (50.0.2 at that
  banking).

## Debts the part leaves, named

- **Founding-tree sync**: the founding tree
  (`~/workspace/ravens`) is behind this repo by every
  Part IV package-source change on top of the Part
  II/III debt (path-safety pre-flight, permissions,
  backup inheritance, log-content flag, Qdrant transport
  and payload checks, hash double checks, the whole
  `_crypto.py` encryption build, the `_attest.py`
  attestation chain, `secure_forget` and its purge
  helpers, the query-cost caps, and the error-message
  rule). The sync is recorded here and in
  `CAMPAIGN_STATE.md`; it is a deliberate later act, not
  done by this gate.
- `schema_version` is recorded, not yet gated on —
  TH-19's owners stand: RM-082 (Part VI) defines
  foreign-schema behaviour and RM-132 (Part X) builds
  the migration registry.
- The opt-in shape of Part IV's defences is itself a
  recorded posture, not an oversight: strict path
  safety, store encryption, and integrity attestation
  are each off by default for the reasons RM-041,
  RM-048 and RM-055 filed, and each marked store
  refuses an unprotected open, so opting in is
  complete once chosen.

## Gate verdict

Part IV's acceptance stands on filed evidence for every
slice: an audited injection surface, owner-only files
and backups, redacted logs and hygienic errors, a
guarded network boundary, collision-honest identity,
opt-in encryption and attestation that were
fault-proven against real stores, a forget that can
truly forget, bounded dependencies and bounded query
cost, and defaults that have had their one recorded
security review. The threat model that opened the part
closes it updated, with no threat silently dropped.
**Part IV is complete.** The road continues at
Part V — Speed (RM-057–RM-072).
