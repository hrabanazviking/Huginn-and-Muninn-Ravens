# Store Encryption, Design — RM-048

*Security, slice ten: the at-rest question, decided before it is built.*

Threat **TH-09** in `docs/THREAT_MODEL.md`: the ravens'
stores are plaintext SQLite. Anyone who can read the files
— the local file attacker (AC-3), a stolen disk, a copied
backup generation — has every memory in clear text. The
threat model left the answer open by design and named this
slice to decide it: **SQLCipher vs application-level
envelope encryption vs filesystem encryption**, judged
against the campaign's two standing constraints — the
**stdlib-first** dependency law and the **shared-schema
law** (the cross-store contract under which Bifröst-class
readers read Muninn's `activation_log` /
`hebbian_connections` tables directly, with the stdlib
`sqlite3` module, bypassing Muninn's API; TB-7 in the
threat model). This record is the decision RM-049 builds.
It is a design slice only: no package code changes here.

## What exactly needs protecting

The content-bearing values, per store (from the RM-004
schema snapshots):

- **Muninn** — `nodes.content`, `nodes.metadata`,
  `nodes.tags`. Everything else in the store is structure
  and behaviour: the wiring (`hebbian_connections`), the
  activation log (`activation_log`: ids, timestamps,
  valence, source — no content text), counters, tombstones,
  timestamps, category, path. Notably, the two tables the
  shared-schema law contracts out to direct readers carry
  **no memory content at all**.
- **Huginn (local)** — `documents.content`,
  `documents.tags`, and the *derived* content:
  `doc_terms.term` / `corpus_stats.term` (the store's own
  tokens — a plaintext token index leaks content
  statistically, asset AS-04 in the threat model) and
  `doc_vectors.vector` (stored embeddings, likewise
  derived from content).
- **Huginn (Qdrant)** — out of scope for this decision.
  The server owns its disk (non-goal NG-6); the ravens'
  side of that boundary — transport and key handling —
  was closed by RM-045/RM-046. Nothing in RM-049 encrypts
  Qdrant payloads.
- **The backup family** — rolling backups are made through
  SQLite's own backup API, which copies the stored values;
  WAL frames likewise hold stored values. Whatever form a
  value has *in the store*, it has in every generation and
  frame. A value-layer scheme therefore inherits backup
  and WAL coverage for free; a scheme that encrypts around
  SQLite instead of inside it does not.

## The candidates, judged

### A — SQLCipher (whole-database encryption)

The whole file is ciphertext; plain `sqlite3` cannot open
it at all. The cryptography is well regarded. It fails
this campaign's constraints on dependency and contract
grounds, not on cipher quality:

- **Not stdlib-first, not even pip-first.** SQLCipher is a
  compiled fork of SQLite plus a separately built Python
  binding (`pysqlcipher3` / `sqlcipher3`). Neither is
  installable from the standard library, and a pip install
  of the binding compiles against a *system* libsqlcipher
  that must already exist. Verified on this machine at
  decision time (2026-11-02): no `sqlcipher` binary, no
  libsqlcipher package, and neither binding imports. An
  `encryption` extra that silently requires an OS package
  the package manager cannot express is a dependency the
  slice record could not honestly bound
  (`>=floor,<next_major` bounds a version, not a system
  library), and it breaks the ravens' run-anywhere posture
  (a Pi, a laptop, a Hermes host would each need the
  system library first, at a version in lockstep with the
  binding).
- **It breaks TB-7 as contracted.** The shared-schema
  law's readers open Muninn's file with the stdlib
  `sqlite3` module and read `activation_log` /
  `hebbian_connections` directly. Under SQLCipher those
  reads fail outright without the key *and* the SQLCipher
  library in every reader — bridge, Hermes, any future
  contract reader. The schema (table shapes) would
  survive; the *readability contract the schema exists
  for* would not, and repairing it is work in other
  repos this campaign does not own.
- **It replaces the store machinery it must coexist
  with.** The durability contract (WAL, `synchronous=
  FULL`, verified backups through the stdlib connection's
  backup API, quick-check, the heal pass) is implemented
  against the stdlib module's connection; a second driver
  re-opens every one of those proofs (RM-049's own
  acceptance demands the kill-9 and recovery suites pass
  against encrypted stores).

### B — Application-level envelope encryption (value layer)

The library encrypts each content-bearing value before it
reaches SQL and decrypts it on the way out, using one
per-store data key wrapped by a caller-supplied
passphrase. The SQLite file, schema, and store machinery
are untouched; only the *values* in the columns listed
above change form.

- **Stdlib-first, honestly bounded.** Python's stdlib
  contains no symmetric cipher at all (verified at
  decision time: `hashlib`, `hmac`, `secrets` only — no
  AEAD primitive), so *any* in-library encryption needs
  exactly one dependency; hand-rolling a cipher from
  stdlib primitives is rejected outright (never build
  your own AEAD). The one dependency is the `cryptography`
  package's `AESGCM` — the canonical, audited AEAD —
  taken as an **optional extra only**, lazily imported
  only when encryption is switched on, bounded
  `cryptography>=42,<51` (floor: the first line whose
  `AESGCM` API is the modern stable form the build will
  pin in tests; ceiling per the campaign's
  `>=floor,<next_major` law). Key derivation
  (PBKDF2-HMAC-SHA256) and the lookup HMAC below are
  stdlib (`hashlib.pbkdf2_hmac`, `hmac`). Muninn's core
  install stays dependency-free; Huginn gains a third
  extra next to `qdrant` / `embeddings`, not a core
  dependency. A missing extra with the flag on is a typed
  configuration error at construction, never an import
  crash mid-store.
- **The shared-schema law survives intact.** No table,
  column, or type changes: encrypted values are `TEXT`
  in the same `TEXT` columns (an envelope encoding,
  below), so the RM-004 schema goldens do not move.
  `activation_log` and `hebbian_connections` — the
  contracted tables, which carry no content — stay
  plaintext and stay directly readable by Bifröst-class
  readers with stdlib `sqlite3`, exactly as today. What
  those readers never had (node content) is what becomes
  ciphertext.
- **The durability machinery is untouched.** Encryption
  happens above `_db.py`'s connection, so WAL,
  `synchronous=FULL`, verified backups, restore, and the
  heal pass run on the same bytes-road as today — the
  reason RM-049's kill-9 + recovery acceptance is
  credible rather than hopeful. Backups and WAL frames
  inherit ciphertext automatically (above).
- **The honest cost: structure is not hidden.**
  Category, path, importance, valence, timestamps,
  counts, the wiring graph, and the activation history
  remain readable to anyone holding the file, and row
  counts and approximate content lengths (ciphertext
  length tracks plaintext length) leak. This decision
  buys **content confidentiality** against AC-3 —
  stolen disk, copied backup, another account reading
  the file — and says so. It does not claim to hide that
  a memory exists, when it was written, or what it wires
  to. (SQLCipher would hide structure too; that is the
  real thing given up, and it is given up for the
  dependency and contract reasons above, knowingly.)

### C — Filesystem encryption (deployment layer)

LUKS / fscrypt under the store directory. Zero code,
zero dependencies, hides everything including structure
while the volume is locked, and is the *only* candidate
that also covers scratch the library does not own. But
a library cannot provision it, detect it reliably, or
promise it: it is the host's platform (non-goal NG-3
already assigns the platform underneath to the host),
it protects nothing once the volume is unlocked and the
host account is reading (a copied live file is plaintext
again), and RM-049's mandate — an in-library build behind
an extra and a config flag, with a wrong key refused by
the library — cannot be discharged by a deployment
recommendation. Judged: **recommended, not chosen** —
recorded as the deployment guidance below, complementary
to the build, not a substitute for it.

## Decision

**RM-049 builds candidate B: application-level envelope
encryption**, specified in the next section tightly
enough to implement without re-deciding. Candidate A is
rejected (system-library dependency a pip extra cannot
express; TB-7 readability contract broken in every
direct reader). Candidate C is adopted as standing
deployment guidance alongside the build: hosts that need
structure-hiding or powered-off-disk protection for the
whole store directory should put the store on an
encrypted volume *as well* — the two compose, and neither
pretends to be the other.

Two rejected sub-options, named so RM-049 does not
re-litigate them: encrypting only `content` and leaving
Muninn's `metadata`/`tags` and Huginn's token index in
plaintext (a token index *is* content, statistically —
AS-04; a partial envelope that leaks the vocabulary of
every memory is confidentiality theatre), and a
home-grown stream construction over stdlib HMAC (no
hand-rolled ciphers, ever).

## The RM-049 build specification

Configuration (both packages, additive, frozen-config
compatible):

- `store_encryption: bool = False` — the flag. Off is
  today's behaviour, byte for byte: no import of the
  extra, no value transformation, stores readable by the
  plain build exactly as RM-049's mandate requires.
- `encryption_passphrase: str | None = None` — the
  caller's secret, `field(repr=False)` (the RM-045
  key-hygiene precedent), required when the flag is on
  (its absence is a typed configuration error), never
  stored, never logged, never in an error string
  (RM-054 scans own the general rule). Hosts source it
  from their own secret handling; the ravens hold it
  only in the config object.
- Extra: `encryption = ["cryptography>=42,<51"]` in both
  packages (Muninn's first extra; its core stays empty).

Key hierarchy and envelope format:

- At store creation with the flag on, one random 32-byte
  **data key** is generated (`secrets.token_bytes`). A
  **key-encryption key** is derived from the passphrase
  with PBKDF2-HMAC-SHA256 (stdlib; per-store random
  16-byte salt, iteration count stored with the wrap and
  set at 600,000 for new stores). The data key is wrapped
  with AES-256-GCM under the KEK.
- The wrap, the salt, the iteration count, and a
  **key-check value** (AES-256-GCM under the data key
  over a fixed known constant) live in the existing
  `meta` table as ordinary rows — data, not schema.
  A store whose `meta` carries the encryption marker is
  an encrypted store, permanently, for its whole life:
  turning the flag off later does not decrypt it.
- Every encrypted value is stored as one `TEXT` envelope:
  `enc:v1:` followed by base64 of (12-byte nonce ‖
  AES-256-GCM ciphertext+tag) under the data key, with
  the column's identity bound as GCM associated data
  (table+column name), so a ciphertext transplanted
  between columns or stores does not verify.
- **Open-time key proof, before any write:** an open with
  the flag on unwraps the data key and verifies the
  key-check value; a wrong passphrase fails the unwrap
  and the open raises the package's typed storage error,
  with the store untouched — RM-049's wrong-key
  acceptance. An open with the flag *off* (or by a plain
  build without the extra) of a marked store likewise
  refuses with a typed error naming the fact of
  encryption, never serving ciphertext as content and
  never "recovering" over it.

What is transformed, per package (the list above,
made operational):

- **Muninn** — envelope-encrypt `nodes.content`,
  `nodes.metadata`, `nodes.tags`. `content_hash` becomes
  a **keyed lookup tag**: HMAC-SHA256 under a
  lookup subkey derived from the data key, over exactly
  the pre-encryption hash input (kind prefix ‖ content,
  RM-047), so the UNIQUE key, the idempotent-store path,
  and the RM-047 length+content double check work
  unchanged — the double check now compares *decrypted*
  stored content against the incoming plaintext, and the
  hash-equality the store can see is the tag's. Honest
  residue: the tag leaks *equality* between memories of
  one store to a file reader (never across stores —
  per-store keys), the accepted price of keeping
  idempotency server-free.
- **Huginn (local)** — envelope-encrypt
  `documents.content`, `documents.tags`, and
  `doc_vectors.vector` (vector search already loads all
  vectors and scores in-process, so decryption rides a
  road that exists). Tokenize-then-transform the index:
  `doc_terms.term` and `corpus_stats.term` store the
  keyed HMAC of each token under the lookup subkey, and
  queries are transformed the same way before lookup —
  TF-IDF only ever compares terms for equality, so
  scoring is bit-for-bit the plaintext computation over
  transformed terms. `content_hash` is the keyed lookup
  tag as in Muninn. Category and importance stay
  plaintext (they are query filters — encrypting them
  would end filtered search; the leak is named, above).
- **Both** — pure reads stay pure (decryption is a read,
  never a write; `touch=True` keeps its RM-012/RM-013
  semantics), and the public API does not change shape:
  callers pass and receive plaintext exactly as today.
  RM-019 surface goldens gain the two config fields;
  RM-018 goldens gain the wrong-key / plain-open refusal
  messages; the RM-003 contract freeze is otherwise
  unmoved, and the Bifröst contract re-verification is
  required before banking (public-surface change).

What RM-049 must prove (its acceptance, read through
this decision):

- An encrypted store's **memory content is unreadable
  by plain sqlite3**: the file opens (structure is not
  the claim), but every content-bearing value above is
  an `enc:v1:` envelope — a raw SQL dump of `nodes` /
  `documents` / `doc_terms` / `doc_vectors` contains no
  plaintext token of a stored memory. This is the
  precise, honest reading of the roadmap's "unreadable
  by plain sqlite3" for the candidate the roadmap's own
  judging criteria select; whole-file illegibility was
  candidate A's property, rejected for the reasons
  recorded here.
- Wrong key refused at open, typed, store untouched
  (above); correct key reopens and round-trips.
- Kill-9 + recovery suites pass against encrypted
  stores, and the durability proofs are the *same*
  suites, not a parallel weakened set — the value layer
  must not become a second store machine.

## Standing guidance and limits (recorded, not built)

- **Deployment:** for structure-hiding, keep stores on
  an encrypted volume (candidate C) in addition to the
  library envelope; RM-042's owner-only permissions and
  RM-043's inheriting backups remain the first line, the
  envelope is what survives a copied file.
- **Not covered, by design:** the host process and its
  own account (NG-1), structure/metadata as listed,
  Qdrant-side storage (NG-6), passphrase recovery — there
  is none; a lost passphrase is a lost store, stated
  here so RM-049's docs and guides (RM-055's defaults
  review will re-judge the flag's default-off posture)
  repeat it verbatim.
- **TH-09 after RM-049 lands:** content **Controlled**
  when the flag is on, structure **Partial** — the
  register update itself is RM-056's, per the threat
  model's citation rule. Until RM-049 lands, TH-09 stays
  **Open**, now with its decision recorded.

Provenance of the factual claims in this record: the
schema lists are the RM-004 goldens; the backup/WAL
inheritance is `_db.py`'s documented backup-API
construction; the shared tables' contents are the same
goldens; SQLCipher's absence on the decision machine and
the stdlib's lack of a cipher were checked directly on
2026-11-02; the `cryptography` version installed on this
machine (50.0.2) sits inside the chosen bound, though the
extra itself — like the live Qdrant round-trip and the
sentence-transformers path — is **NOT PROVEN** in the
ravens' own venv until RM-049 installs and runs it.

## Build note (RM-049, 2026-11-02)

Built as specified above, in both packages: `_crypto.py`
(per-store data key, PBKDF2-HMAC-SHA256 KEK at 600,000
iterations, AES-256-GCM wrap + key check in `meta`,
`enc:v1:` envelopes with table+column associated data,
keyed HMAC lookup tags), the `store_encryption` /
`encryption_passphrase` (repr=False) config pair, and the
`encryption = ["cryptography>=42,<51"]` extra (Muninn's
first). The key proof runs **before** `open_store` on a pure
read-only probe, so the wrong-passphrase and plain-open
refusals leave the store byte-for-byte untouched; when the
probe cannot read the file at all (a corrupt main store),
the proof is deferred to the live connection after the
restore road has run — a restored encrypted backup unlocks
with the same passphrase, and the recovery suites pass
against encrypted stores in both packages. Two behaviours
the specification left to the build, recorded here: the
flag switched **on** over an existing plain store that
already holds memories/documents refuses typed (no silent
half-encryption, no in-place migration in this slice), and
Huginn's flag binds the local backend only (Qdrant stays
out of scope, per the decision). Suites from this slice
run with the `encryption` extra installed; the extra
itself is now PROVEN in the ravens' own venv
(cryptography 50.0.2, installed and exercised end to end).
TH-09 stands as the decision predicted once the flag is
on: content **Controlled**, structure **Partial** — the
register update itself remains RM-056's.
