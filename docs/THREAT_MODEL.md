# Threat Model (RM-039)

> **RM-056 update (2026-11-02, Part IV gate):** this model
> was re-reviewed against the code as it stands at the
> Part IV gate (HEAD `1208089`, RM-055 banked). Every
> register **State** cell below now states the post-Part-IV
> position, and the RM-056 re-review section at the end of
> this document records, threat by threat, what the part
> actually built and where the register's original "today"
> descriptions are superseded. The original RM-039 text is
> otherwise preserved — it is the record the part was
> built against.

Part IV — Security opens here. This document is the model
every later security slice (RM-040–RM-056) cites: the
assets a memory store holds, the actors it faces, the
trust boundaries between them, the threat register with
the state of each threat **today**, and the non-goals —
the attacks this library deliberately does not claim to
stop. It was reviewed against both codebases at the
Part III gate (HEAD `78acff3`, RM-038 banked): every
source file of both packages, both configs, both
`_db.py` store machines, the Qdrant backend, the
embedders, the logger call sites, the SQL call sites and
the dependency lists. The review record at the end lists
exactly what was inspected; claims about the Qdrant
*server* side are construction claims only — a live
Qdrant round-trip is **NOT PROVEN**.

## The system in one picture

Two in-process Python libraries. There is no daemon, no
socket of their own, and no authentication layer: a host
program (Bifröst, Hermes, a saga engine, a script)
imports a raven, constructs it with a config, and calls
its API. Everything the ravens protect lives behind that
call, in files the host's OS account owns, or — for
Huginn's optional Qdrant backend — on a Qdrant server
the host points at.

- **Muninn** — one SQLite store (WAL, `synchronous=FULL`):
  memory nodes, Hebbian wiring, an activation log. No
  network surface of any kind. Runtime dependencies:
  none (stdlib only).
- **Huginn, local backend** — one SQLite store with the
  same durability discipline: documents, a TF-IDF index,
  stored embedding vectors. No network surface.
- **Huginn, Qdrant backend** — no local store; documents
  live as points + payloads in a Qdrant collection,
  reached through the lazily imported `qdrant-client`
  extra over HTTP(S). This is the ravens' only network
  boundary. The `sentence-transformers` embedder (the
  `embeddings` extra) loads a model named by config.
- **Cross-store readers** — Bifröst's bridge (and, through
  it, Hermes) reads Muninn's `activation_log` and
  `hebbian_connections` tables directly, by the shared
  schema law (`docs/FORMAT_STABILITY.md`). Those readers
  do not pass through Muninn's API or its validation;
  the schema contract is the boundary there.

## Assets

| ID | Asset | Where it lives | Why it matters |
|---|---|---|---|
| AS-01 | Memory content — Muninn node content + metadata, Huginn document content | `nodes`, `documents`, Qdrant payloads | The most sensitive data a program has: whatever the host chose to remember, in clear text. Confidentiality and integrity. |
| AS-02 | Wiring — `hebbian_connections` strengths, counts, consolidation flags | Muninn store | The learned association structure. Quietly altered wiring changes what the host recalls together — an integrity asset, and it leaks what was used together. |
| AS-03 | The activation log — `activation_log`, `node_activation` counters + confidence | Muninn store | A behavioural history: what was activated, when, with what valence and source. Sensitive in itself; also the audit trail other defences would check. |
| AS-04 | Retrieval indexes — `doc_terms`, `corpus_stats`, `doc_vectors`, Qdrant vectors | Huginn stores | Derived from AS-01; leaking them leaks content statistically, corrupting them corrupts every answer. |
| AS-05 | Store files as a whole — main file, `-wal`/`-shm`, `.bak-1…N` generations, `.bak-tmp`, `.open-lock` | The store directory | Every generation is a full copy of AS-01–AS-04. Availability (a store that will not open is memory loss) and confidentiality stand or fall with the whole family, not just the main file. |
| AS-06 | Tombstones + `meta` registry — `deleted_nodes`, `schema_version`, `decay_last_run_at` | Both stores | Small, but load-bearing: tombstones keep forgotten ids pruned; `meta` steers open-time and decay behaviour. |
| AS-07 | The Qdrant API key (`HuginnConfig.qdrant_api_key`) | Host memory, config object, the client connection | The only credential the ravens hold. Disclosure hands an attacker the Qdrant side of AS-01. |
| AS-08 | Diagnostics — package log output, typed error messages, `health()` / `stats()` / `dump()` results | Wherever the host sends them | Paths, counts, store state, and — if a defect ever let it — content. A leak channel, not a store. |
| AS-09 | Availability of the store — openability, lock behaviour, bounded query cost | The running process | A memory that hangs, wedges, or eats the disk is a failed memory; denial of service against the store is denial of the host's past. |
| AS-10 | Content identity — the SHA-256 `content_hash` in both stores, Qdrant point ids | Both stores, Qdrant | Idempotent writes key on it. A collision silently merges two different memories into one — an integrity failure with no error anywhere. |

## Actors

- **AC-1 — The buggy caller.** Trusted host code that
  misuses the API: wrong types, absurd ranges, retries
  after ambiguous failures, paths it did not mean. Not
  malicious, but the source of most real damage. The
  ravens' answer is validation before any write, typed
  errors, and idempotency discipline (Parts I–III).
- **AC-2 — The hostile input source.** Whoever or
  whatever supplies the *values* a well-behaved caller
  stores or queries with: untrusted text, tags, metadata
  and queries flowing in from users, files, the network,
  or another agent. The caller is honest; the data is
  not. This actor aims at injection (TH-01), resource
  exhaustion (TH-13), payload forgery on the Qdrant side
  (TH-07), hash-collision merging (TH-08), and memory
  poisoning (TH-21).
- **AC-3 — The local file attacker.** Someone (or some
  other program) who can read or write the store
  directory but does not run as the host program: another
  OS account on a shared machine, a backup or sync tool
  gone wrong, malware in another account, a stolen disk
  or backup copy. This actor reads AS-05 in clear text
  today (TH-03, TH-04, TH-09), tampers with rows by raw
  SQL (TH-10), resurrects forgotten content from WAL
  frames and old generations (TH-11), and redirects the
  store path itself where a symlink can be planted
  (TH-02). A crafted store file handed to the opener is
  this actor reaching through AC-1's hands (TH-19).
- **AC-4 — The network attacker (Qdrant only).** An
  eavesdropper, a man-in-the-middle, or a rogue server on
  the path between Huginn and its Qdrant server — or a
  hostile client of that same server. Aims at the API
  key and the payloads in transit (TH-06) and at
  cross-tenant payload interference (TH-07). Muninn and
  Huginn-local give this actor nothing: they open no
  connection.

Two sub-cases, named so they are not mistaken for
separate actors: a **compromised optional dependency**
(the `qdrant-client` or `sentence-transformers` extras,
or a model file they load) executes *inside* the host
process and is therefore inside every boundary below —
it is handled as a supply-chain threat (TH-12), not as
an outside actor; and a **hostile co-tenant process**
running under the *same* OS account as the host is, for
file purposes, indistinguishable from the host itself
(see NG-1).

## Trust boundaries

- **TB-1 — Caller ↔ API (both ravens).** Every value
  crosses here untrusted, whether the caller is buggy
  (AC-1) or relaying hostile data (AC-2). Controls
  today: per-parameter validators that raise typed
  errors *before* any write, size ceilings (RM-027),
  structure-depth bound (RM-036), lone-surrogate refusal
  (RM-034), frozen validated configs (RM-017). This is
  the best-defended boundary in the system — Parts II
  and III were largely spent on it.
- **TB-2 — Library ↔ store files (filesystem).** The
  library trusts the OS to give it back the bytes it
  wrote, and trusts no one else to have touched them.
  Controls today are *durability* controls (WAL +
  `synchronous=FULL`, verified rolling backups, loud
  restore-or-refuse on corruption) — they answer
  accidents and crashes. Against a deliberate writer
  (AC-3) there is today **no** confidentiality control
  and **no** tamper evidence at this boundary: the
  files are plaintext SQLite under default permissions.
  That gap is TH-03 / TH-09 / TH-10, owned by
  RM-042 / RM-048–049 / RM-050.
- **TB-3 — Library ↔ rolling backups.** The same bytes
  as TB-2 in a second set of files, with a longer
  memory: backups deliberately retain what the live
  store has forgotten until generations rotate
  (TH-04, TH-11; RM-043, RM-051).
- **TB-4 — Library ↔ host diagnostics.** Loggers
  (`muninn`, `muninn.store`, `huginn`, `huginn.store`,
  `huginn.local`, `huginn.qdrant`), typed error strings,
  and the diagnostic reads (`health`, `stats`, `dump`).
  Whatever crosses here may be shipped to log files and
  dashboards the ravens do not control, so content must
  not cross it (TH-05, TH-14; RM-044, RM-054).
- **TB-5 — Huginn ↔ Qdrant server (network).** The only
  boundary that leaves the machine. Crossings: the API
  key (AS-07), memory payloads (AS-01), queries and
  their embeddings, and the server's answers — which the
  backend trusts for ids, payloads and scores. Controls
  today: the key is passed only to the client
  constructor and never logged by package code; nothing
  else. There is no TLS requirement, no key-leak scan of
  error strings, and no reserved-key defence on
  payloads (TH-06, TH-07; RM-045, RM-046). All of this is
  reviewed from code — live behaviour is NOT PROVEN.
- **TB-6 — Host ↔ optional extras (supply chain).**
  `qdrant-client`, `sentence-transformers`, and any
  model the latter downloads execute in-process with
  the host's full privileges. Controls today: both
  extras are bounded (`>=floor,<next_major`), lazily
  imported, and absent from the core install; Muninn
  has no extras at all (TH-12; RM-052).
- **TB-7 — Cross-store readers ↔ Muninn's shared tables.**
  Bifröst-class readers cross directly to
  `activation_log` / `hebbian_connections`, bypassing
  TB-1 entirely. The control is contractual, not
  technical: the shared schema law and its freeze tests
  (RM-003, RM-004). A reader that writes those tables
  outside the contract is outside this model (NG-5).

## Threat register

State words: **Controlled** = a defence exists today and
is pinned by tests; **Partial** = a defence exists but
is incomplete, unproven, or known to leak at an edge;
**Open** = no defence today; the owning slice is named.
Every Part IV slice RM-040–RM-056 appears in the last
column; the citation rule below binds them to the
threats they close.

| ID | Threat (actor → asset, boundary) | State today | Owned by |
|---|---|---|---|
| TH-01 | SQL injection: a caller value reaches SQL as syntax and reads or destroys the store (AC-2 → AS-01/02, TB-1). Review found every value bound as a parameter; the only interpolated SQL is the `busy_timeout` PRAGMA (an `int()` cast of config), Muninn `update()`'s column names (keys of a dict built only from validated literals, behind a closed field allow-list), Huginn-local's `IN (?,?,…)` placeholder strings (built from `len()` only), and the static schema script. Found by inspection — not yet proven by a hostile battery. | Controlled | RM-040 |
| TH-02 | Store-path redirection: a symlinked db path or parent, or a world-writable parent directory, sends the store — or its restore — somewhere the attacker controls (AC-3 → AS-05, TB-2). Paths are `~`-expanded and deliberately **not** symlink-resolved today (`resolved_path` documents this); parent directories are created on open. There is no strict mode. | Partial (opt-in strict mode; default recorded behaviour unchanged, per RM-041/RM-055) | RM-041 |
| TH-03 | Local disclosure via file permissions: store files are created by SQLite under the process umask and no package code sets or checks permissions, so on a typical `022` umask the memories of AS-01 are readable by every local account (AC-3 → AS-01, TB-2). | Controlled | RM-042 |
| TH-04 | Backup disclosure: the `.bak-N` generations are full copies of memory and inherit whatever TH-03 leaves open, for as long as they are kept (AC-3 → AS-05, TB-3). | Controlled | RM-043 |
| TH-05 | Content in logs: a log call or a diagnostic emits memory content where hosts ship logs onward (AC-2/AC-3 → AS-01 via AS-08, TB-4). Review of every logger call site found paths, counts, heal-count reports, the Qdrant URL and exception strings — no content argument anywhere — but nothing scans for a regression, and exception strings are not controlled (see TH-14). | Controlled | RM-044 |
| TH-06 | Qdrant transport: the API key and payloads cross the network; the default URL is plaintext `http://localhost:6333`, any `http://` URL is accepted for any host, the key is handed to the client with no handling audit, and wrapped client exceptions — whose text the ravens do not control — are returned to the caller and, in `auto` mode, logged at INFO with the fallback reason (AC-4 → AS-07/AS-01, TB-5). Localhost plaintext is a stated convenience, not a control. Live behaviour NOT PROVEN. | Partial (controls built and fake-client pinned; live behaviour NOT PROVEN) | RM-045 |
| TH-07 | Qdrant payload forgery: payload keys are written from a fixed dict in the backend today, so a caller cannot overwrite reserved keys *through this code* — but nothing pins that, and a hostile co-tenant of the same collection (AC-4) faces no defence at all; Huginn trusts returned payloads for content, category and importance (AC-2/AC-4 → AS-01/AS-04, TB-5). Fake-client proof only; live NOT PROVEN. | Partial (closed set + read hygiene pinned by fake client; live NOT PROVEN; well-formed foreign points accepted by design) | RM-046 |
| TH-08 | Hash-collision merge: two different memories with one `content_hash` silently become one memory under the idempotency rule — Muninn keys on (hash, category, path), Huginn on (hash, category); Huginn's Qdrant id derivation additionally truncates the hash to 64 bits when no caller id is given, widening that path's collision surface (AC-2 → AS-10, TB-1/TB-5). SHA-256 makes a natural collision implausible; a *crafted* one, or a future weaker path, has no second check today. | Controlled | RM-047 |
| TH-09 | No confidentiality at rest: anyone who can read the files (TH-03's reader, a stolen disk, a copied backup) has every memory in clear text (AC-3 → AS-01, TB-2/TB-3). This is the design question of Part IV — SQLCipher vs envelope vs filesystem encryption, judged against stdlib-first and the shared-schema law (TB-7 constrains it: encrypted Muninn tables are unreadable to Bifröst's direct reads). | Partial (opt-in envelope encryption built, RM-049; a default store is plaintext by the caller's choice; structure/counts stay readable even when on) | RM-048, RM-049 |
| TH-10 | Silent tampering: an attacker with file write access edits rows by raw SQL — weakens a wiring, rewrites a log entry, plants a memory — and nothing detects it; `quick_check` proves SQLite's structure, not the caller's truth, and the heal pass repairs *drift shapes*, not intent (AC-3 → AS-02/AS-03, TB-2). No integrity chain exists today. | Partial (opt-in attestation over `activation_log` only; detection reported, not prevented; Muninn only) | RM-050 |
| TH-11 | Forget does not forget: `forget`/`delete` remove the live rows (and Muninn tombstones the id), but the content can persist in WAL frames not yet checkpointed, in every `.bak-N` generation until rotation, and — for Muninn — the activation log keeps its rows by design ("it is a log"), including the forgotten id's history (AC-3 → AS-01, TB-2/TB-3). The truth is undocumented in the guides today and there is no secure-forget operation. | Controlled (via `secure_forget`; plain forget's residue truth documented in both guides) | RM-051 |
| TH-12 | Dependency compromise or rot: a vulnerable or malicious extra, or an unpinned future version, executes in-process (AC-2 supply chain → all assets, TB-6). Core installs are dependency-free and extras are bounded, but there is no lockfile example and no vulnerability scan in CI. | Controlled (locally run scan proven; a GitHub-hosted run of the scan job is NOT PROVEN) | RM-052 |
| TH-13 | Denial of service through the API: expensive reads (`spread_activation`, local search scoring) and huge or adversarial inputs consume unbounded CPU/time; a store filled to `max_nodes` thrashes backpressure (AC-1/AC-2 → AS-09, TB-1). Input *sizes* are bounded today (RM-027 ceilings, RM-036 depth bound, RM-035's memory-bounded batch road); candidate-set *work* caps with visibility when a cap bites do not exist yet. | Controlled | RM-053 |
| TH-14 | Sensitive data in error messages: typed errors deliberately carry the store path the caller supplied and, on storage failures, the underlying SQLite/client exception text, which the ravens do not control and have never scanned for file contents, keys, or paths beyond the caller's own (AC-2/AC-3 → AS-08, TB-4/TB-5). RM-018 pins the message *shapes*; it does not scan them for secrets. | Controlled | RM-054 |
| TH-15 | Unsafe defaults: a default that is convenient in development and wrong in deployment (backup counts, timeouts, `auto` fallback silently degrading to local, plaintext localhost Qdrant) ships to every caller who never opens the config (AC-1 → all, TB-1/TB-5). Defaults have been judged piecemeal per slice; they have never had one recorded security review. | Controlled (review recorded; the three compatibility-kept defaults are named in `docs/SECURE_DEFAULTS.md`) | RM-055 |
| TH-16 | Model drift: this document rots as the code moves, and later slices claim protections the code does not have. | Controlled at this gate (whole register re-checked by RM-056; drift remains a standing process risk for future part gates) | RM-056 (gate: bundle + this model updated) |
| TH-17 | Hostile input crashing or half-writing the store: untyped exceptions, partial writes, stack exhaustion from adversarial values (AC-2 → AS-09/AS-01, TB-1). Fuzz-proven and regression-pinned in Part III (RM-025, RM-026, RM-034, RM-036). | Controlled | — (Part III; TH-13 owns the cost side) |
| TH-18 | Accidental corruption and silent data loss: crashes, torn writes, disk faults (no actor — the machine itself → AS-05, TB-2). The durability contract answers it: WAL + FULL sync, verified backups, loud restore-or-refuse, never silently empty (RM-029–RM-033, RM-037). Deliberate corruption is TH-10, not this. | Controlled | — (Parts II–III; Part VI expands healing) |
| TH-19 | Hostile store file: a crafted database handed to the opener (AC-3 through AC-1 → AS-01, TB-2). Shape pre-flight refuses directories and non-regular files and the corruption road restores-or-refuses (RM-032, RM-033), heal repairs known drift — but `schema_version` is recorded, not gated on, so a foreign-schema store is not yet refused *as* foreign. | Partial | RM-082 / RM-132 (named here; Part VI/X own it) |
| TH-20 | Contract-reader exposure: cross-store readers (TB-7) see Muninn's raw tables, including the activation log, with no API in between; anything Bifröst logs or forwards is beyond the ravens' control. Accepted by the shared-schema law; the ravens' duty is only that the tables mean what the contract says. | Accepted (contractual) | — |
| TH-21 | Memory poisoning: a hostile input source stores false, manipulative, or prompt-shaped content through an honest caller, and later retrieval returns it with the store's full credibility (AC-2 → AS-01 integrity-of-meaning, TB-1). The ravens guarantee faithful storage and retrieval of what was given; they keep provenance where the schema has it (activation `source`, category, path) but they judge no content's truth, and no slice in this part changes that. Retrieval-side mitigations belong to the intelligence parts and to hosts. | Accepted (bounded) | — (hosts + Parts XII–XIII) |

## Explicit non-goals

- **NG-1 — No defence against the host process itself.**
  The ravens are libraries, not services. Code running
  in the same process (the caller, a compromised extra,
  anything with the host's OS account and the store
  open) can read every memory through the API or the
  file directly. No slice in this part pretends
  otherwise; process and account isolation are the
  host's and the OS's jobs.
- **NG-2 — No authentication or authorization.** There
  are no users, roles, or per-memory permissions inside
  the ravens. A host that needs them enforces them
  before the call (TB-1 is a validation boundary, not an
  identity boundary).
- **NG-3 — No protection from the platform underneath.**
  A hypervisor, kernel, or disk the attacker already
  owns; OS-level snapshots, sync tools, and backups the
  host makes outside the ravens' file family (TB-2
  covers only the files the ravens create); memory
  scraping of the running process. Filesystem encryption
  may be RM-048's answer for the at-rest question — even
  then it is the host's deployment, not the library's
  promise.
- **NG-4 — No judgement of content truth.** Poisoning
  (TH-21) is bounded, not solved: the ravens store what
  they are given and return what they stored. Truth,
  relevance, and whether a memory *should* be believed
  belong to the host and to Parts XII–XIII.
- **NG-5 — No defence of the contract from its own
  readers.** TB-7 readers are trusted by the shared
  schema law. A reader that corrupts the shared tables
  has broken a contract, not a control; TH-10's
  attestation, when it lands, is what could notice.
- **NG-6 — Qdrant server security is the server's.**
  Hardening the Qdrant deployment itself (its own auth,
  its disk, its other collections) belongs to whoever
  runs it. The ravens' Part IV duties stop at their side
  of TB-5: key handling, transport requirements, payload
  hygiene.
- **NG-7 — No anonymity or traffic hiding.** Queries to
  Qdrant reveal their embeddings; log timestamps reveal
  rhythms of use. Making the host's *behaviour*
  unobservable is not attempted anywhere in this part.
- **NG-8 — The sentence-transformers model is the
  caller's choice.** Which model file is fetched, from
  where, and whether it is trustworthy (TB-6) is a host
  decision; RM-052's hygiene covers the package pins,
  not model provenance.

## Assumptions the model stands on

1. The host OS keeps accounts apart: "another local
   account cannot read the files" is a *goal state*
   (RM-042), while "the host account's own processes are
   trusted" is an *assumption* (NG-1).
2. The Python runtime and SQLite library behave as
   documented (WAL, `synchronous=FULL`, parameter
   binding). A compromised interpreter is NG-1/NG-3.
3. The caller supplies the store path and the Qdrant
   URL; both are configuration, and a hostile *config*
   is a hostile caller — AC-1's config mistakes are in
   scope (TH-15), a deliberately hostile host is NG-1.
4. Clocks may jump (RM-012's guard holds ordering);
   nothing in this part depends on wall-clock truth.
5. For TB-5, "localhost" Qdrant is treated as a local
   trust zone by convenience today; RM-045 decides what
   the default may stay.

## Citation rule for RM-040–RM-056

Every later Part IV slice cites this model in its slice
log entry: the threat IDs it closes, mitigates, or
deliberately leaves, quoted from the register above. A
slice that discovers a threat this model does not name
amends this document in its own commit and says so.
RM-056 (the part gate) re-reviews this model against the
code as it then stands and updates every State cell.

| Slice | Threats it owns |
|---|---|
| RM-040 SQL-injection audit | TH-01 |
| RM-041 Path safety | TH-02 |
| RM-042 File permissions | TH-03 |
| RM-043 Backup confidentiality | TH-04 |
| RM-044 Log redaction | TH-05 |
| RM-045 Qdrant transport safety | TH-06 |
| RM-046 Qdrant payload hygiene | TH-07 |
| RM-047 Hash-collision honesty | TH-08 |
| RM-048 Store encryption, design | TH-09 |
| RM-049 Store encryption, build | TH-09 |
| RM-050 Integrity attestation | TH-10 |
| RM-051 Forget is forgetting | TH-11 |
| RM-052 Dependency hygiene | TH-12 |
| RM-053 Denial-of-service bounds | TH-13 |
| RM-054 Error-message hygiene | TH-14 |
| RM-055 Secure defaults review | TH-15 |
| RM-056 Part gate | TH-16 (and the whole register re-checked) |

## Review record (RM-039, 2026-11-01)

Reviewed at HEAD `78acff3` (RM-038): all sources of both
packages (`muninn`: `__init__`, `config`, `core`, `_db`,
`errors` — 2,662 lines; `huginn`: `__init__`, `config`,
`core`, `_db`, `errors`, `local_backend`,
`qdrant_backend`, `text` — 2,497 lines), both
`pyproject.toml` dependency lists (core: none; extras:
bounded `qdrant-client`, `sentence-transformers`, dev
tools), and the standing docs this model must not
contradict (`FORMAT_STABILITY.md`, `RELIABILITY.md`,
the RM-013 idempotency matrix in `API_REFERENCE.md`).
Inventories taken by search over the sources, not from
memory: every `execute`/`executemany`/`executescript`
site (the TH-01 interpolation list), every `logging`
site (the TH-05 inventory: six loggers, emit sites carry
paths, counts, heal-count reports, the Qdrant URL, and
exception strings — no content argument), every file
creation site (no `chmod` exists in either package —
TH-03), the Qdrant client construction and payload dict
(TH-06, TH-07), both `content_hash` definitions and the
Qdrant id derivation (TH-08), and both forget/delete
paths (TH-11: Muninn deletes node + wiring, tombstones
the id, and keeps the activation log; Huginn deletes
document + terms + vector rows; neither touches WAL
history or backup generations — by design, named here).

Honesty ledger for this document: a live Qdrant
round-trip is **NOT PROVEN**, so TH-06/TH-07 describe the
code's construction, not an observed server; the
sentence-transformers path is **NOT PROVEN** live;
nothing in this model is a claim that a defence works —
States marked Partial rest on the inspection recorded
above, and each owning slice owes the proof.

## RM-056 re-review (2026-11-02, Part IV gate)

Re-reviewed at HEAD `1208089` (RM-055 banked): every
Part IV slice record (`docs/SLICE_LOG.md` RM-039–RM-055,
`CAMPAIGN_STATE.md`, and the per-slice record documents
named below), both packages' banking suites (muninn 350
passed, huginn 298 passed at RM-055), and the register
above, threat by threat. No threat was found in Part IV
that this model did not name; no register entry was
deleted; TH-19, TH-20 and TH-21 stand exactly as written.
What the part actually built, per threat:

- **TH-01 — Controlled.** RM-040's AST inventory and
  hostile battery (`docs/SQL_INJECTION_AUDIT.md`) proved
  the inspection: every value bound, interpolated SQL
  only from closed sets. The audit totals are test-pinned
  and moved only as later slices added named constant
  sites (RM-049, RM-050, RM-051).
- **TH-02 — Partial, by stated design.** RM-041 built the
  opt-in strict mode (`docs/PATH_SAFETY.md`);
  RM-055 re-judged the off default and kept it, on the
  record: flipping it would refuse legitimate symlinked
  deployments at open. The locked-down road exists and
  is test-pinned; the default road is the recorded
  behaviour, knowingly.
- **TH-03 — Controlled.** RM-042 (`docs/FILE_PERMISSIONS.md`):
  new stores `0600` under any umask; a looser existing
  file is reported in `health()`, never silently
  re-permissioned.
- **TH-04 — Controlled.** RM-043
  (`docs/BACKUP_CONFIDENTIALITY.md`): every backup
  inherits the store file's exact mode on every road.
- **TH-05 — Controlled.** RM-044 (`docs/LOG_REDACTION.md`):
  no content in logs at INFO or below; DEBUG content only
  behind `debug_log_content`, off by default. The
  exception-text caveat that slice named was closed by
  RM-054 (TH-14).
- **TH-06 — Partial.** RM-045 (`docs/QDRANT_TRANSPORT.md`)
  built HTTPS-by-default beyond loopback, the
  `allow_insecure_http` opt-out, and the key-handling
  audit; RM-054 replaced wrapped client *text* with the
  exception's class name, so the key-scrub is now defence
  in depth on the facade's reported strings rather than
  the only barrier. Live behaviour remains **NOT PROVEN**
  — all of this is construction and fake-client proof.
- **TH-07 — Partial.** RM-046 (`docs/QDRANT_PAYLOAD.md`)
  pinned the closed six-key payload set and made returned
  points pass a shape-and-integrity check before trust.
  A well-formed point with a correct hash written by
  another writer is returned, by design (NG-4's shape
  check is not a truth check). Live behaviour NOT PROVEN.
- **TH-08 — Controlled.** RM-047 (`docs/HASH_COLLISION.md`):
  length+exact-content double check on every
  idempotent-store road, forced-collision tests via an
  injected hash, and the Qdrant derived id masked to
  63 bits.
- **TH-09 — Partial, by stated design.** RM-048 decided
  and RM-049 built application-level envelope encryption
  (`docs/STORE_ENCRYPTION.md`), fault-proven: content
  unreadable by plain sqlite3, wrong-key opens refuse
  typed, contracted tables stay plaintext-readable per
  TB-7. It is opt-in — a store is encrypted when its
  caller chooses it, and a marked store refuses
  unprotected opens; structure, counts, timestamps and
  approximate lengths stay readable even when on, as the
  decision record states.
- **TH-10 — Partial, by stated design.** RM-050
  (`docs/INTEGRITY_ATTESTATION.md`) built the opt-in
  HMAC chain over `activation_log` only, Muninn only:
  raw-SQL tampering is detected and *reported* on open.
  Tampering with other tables, and prevention or
  attribution, were never this slice's claim.
- **TH-11 — Controlled.** RM-051 (`docs/SECURE_FORGET.md`)
  documented plain forget's residue truth in both guides
  and built `secure_forget`, whose forensic byte-search
  finds the forgotten string in no surviving file.
- **TH-12 — Controlled, with one honesty rider.**
  RM-052 (`docs/DEPENDENCY_HYGIENE.md`) pinned the
  bounds, filed the lockfile example, added the scan job,
  and ran the scan locally — catching and fixing
  PYSEC-2026-1845 in-slice. A GitHub-hosted run of the
  job is **NOT PROVEN** (manual-only, never dispatched).
- **TH-13 — Controlled.** RM-053 (`docs/QUERY_COST_CAPS.md`):
  explicit candidate-set caps on both named reads, with
  deterministic bite and stat visibility.
- **TH-14 — Controlled.** RM-054
  (`docs/ERROR_MESSAGE_HYGIENE.md`): typed messages are
  built only from fixed text, package-computed values,
  the caller's own supplied path/URL/collection, and the
  underlying exception's class name; the planted-leak
  scan is test-pinned.
- **TH-15 — Controlled.** RM-055 (`docs/SECURE_DEFAULTS.md`):
  all 38 defaults re-judged, none changed, the three
  compatibility-kept judgements named plainly, and the
  guide/API-reference drift the review found fixed and
  test-pinned.
- **TH-16 — Controlled at this gate.** This re-review is
  the control the model names: the gate (RM-056) updated
  every State cell against the filed evidence
  (`docs/PART_IV_EVIDENCE.md`). Drift remains a standing
  process risk; every future part gate re-checks the
  register the same way.

Boundary notes, updated by the part: TB-2 now carries
real controls where RM-039 found only durability —
owner-only creation (RM-042), an opt-in path-safety
pre-flight (RM-041), opt-in content encryption (RM-049)
and opt-in tamper evidence for the activation log
(RM-050). TB-5 carries the transport and payload controls
above, all unproven live. TB-6 carries bounds, a lockfile
example and a scan step (RM-052). TB-1, TB-3, TB-4 and
TB-7 are as the model describes, with TB-3 answered by
RM-043/RM-051 and TB-4 by RM-044/RM-054.

Honesty ledger for this re-review, unchanged from
RM-039: a live Qdrant round-trip is **NOT PROVEN**;
the sentence-transformers path is **NOT PROVEN** live;
nothing above upgrades a construction claim into a live
one.
