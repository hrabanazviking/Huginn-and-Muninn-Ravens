# Hash-Collision Honesty — RM-047

*Security, slice nine: a hash is evidence of identity, not identity.*

Threat **TH-08** in `docs/THREAT_MODEL.md`: both ravens make
storage idempotent by content hash. Muninn keys a node on
(content_hash, category, path); Huginn keys a document on
(content_hash, category) locally, and on Qdrant derives the
point id from the hash. Before this slice the hash alone was
trusted on every one of those roads: Muninn's fallback after
`INSERT OR IGNORE` returned the existing row's id whatever
content it held; Huginn's local upsert updated the found row
in place with the incoming content; Huginn's Qdrant upsert
blindly overwrote the point at the derived id. Two different
memories sharing one hash would have silently become one
memory — the second store merging into, or overwriting, the
first, with no error anywhere.

## The collision assumption, stated

Content-hash identity uses **SHA-256** in all three places
(Muninn hashes the stored text with a kind prefix, `s:` for
a string and `j:` for JSON; Huginn hashes category + content
in both backends). The assumption the design stands on:

- A *natural* SHA-256 collision — two honestly produced
  memories with the same hash — is implausible: no collision
  has ever been found for SHA-256, and the birthday bound
  over a personal memory store's lifetime volume is
  negligible.
- The design does **not** stand on that assumption alone.
  A *crafted* collision (an attacker who can choose both
  contents), a tampered store row whose hash was forged by
  raw SQL, a hostile co-tenant's point on Qdrant, or a
  future regression to a weaker hash must still not be able
  to merge two memories silently. That is what the double
  check below is for: the hash proposes identity, the check
  disposes.
- The Qdrant derived id is additionally a *truncation*: it
  was the hash's first 64 bits. Truncation collisions are
  far more plausible than full-hash ones (birthday bound
  near 2³² points), and the derivation had a second defect,
  recorded as a discovery in RM-046's slice entry: the full
  unsigned 64-bit value exceeds the facade's `memory_id`
  ceiling of 2⁶³−1 for roughly half of all contents, so such
  a memory could be stored but never fetched through
  `HuginnMemory.get`. This slice masks the derivation to
  **63 bits**, so every derived id fits the ceiling, and the
  upsert double check guards the truncated space that
  remains.

## The defined behaviour

Wherever a hash hit is about to be treated as "the same
memory", the hit is verified by a **length+content double
check** before anything is merged, returned, or overwritten:

- **Muninn `remember`** — when the insert is ignored because
  (hash, category, path) already exists, the existing row is
  fetched and its stored text length, its exact stored text,
  and its kind (string vs JSON) must all equal the incoming
  values. Only then is the existing id returned.
- **Huginn local `upsert`** — a row found by (hash, category)
  must carry content of the same length and the exact same
  content before the idempotent update proceeds. The same
  check discriminates the free-explicit-id case: a different
  memory under the incoming hash is a collision refusal, not
  the ordinary "content already lives at id …" clash.
- **Huginn Qdrant `upsert` (derived id only)** — before the
  upsert, the point already at the derived id is retrieved
  and hygiene-checked (RM-046); its category, content length
  and exact content must match the incoming memory. Only
  then does the upsert proceed.

A failed check raises a typed error with one message shape
on all three roads — `content hash collision: a different
memory already holds this content hash (id {id}); refusing
to merge` — a `MuninnValidationError` / `HuginnValidationError`
on the local roads, a `HuginnBackendError` on Qdrant. The
message names only the existing id, never either content,
and the existing memory or point is left exactly as it was.

Two roads are deliberately **not** collision-checked,
because they are not the idempotent path: an explicit
`memory_id` (Huginn) or `update()` on an addressed node
(Muninn) is the caller naming the memory to replace, and
keeps its replace semantics — Muninn's `update` already
refuses a move onto another node's (content, category,
path) with its duplicate error, and Huginn's explicit-id
local update onto a third row's hash still fails loudly on
the unique index rather than merging.

The length half of the check is the cheap first screen the
roadmap names (a different-length collision is refused
without comparing bodies); the exact-content half is what
makes the promise unconditional — a same-length collision
is refused too, so the guarantee does not depend on SHA-256
staying unbroken, only on the check being run.

## How it is proven

Pinned by `tests/test_hash_collision.py` in both packages
(muninn 8 tests, huginn 12 tests; Qdrant proof against fake
clients only):

- **Forced collisions via an injected hash function** — the
  acceptance's named method: each backend's one store-path
  hash function (Muninn's `_content_hash`, extracted from
  `_content_payload` for exactly this seam; Huginn's
  module-level `_content_hash` in each backend) is replaced
  with a constant, so every content hashes alike. Different-
  length and same-length different contents are refused on
  all three roads, with the existing memory/point untouched
  and alone; a string-vs-JSON kind collision is refused in
  Muninn; the free-explicit-id collision in Huginn local is
  the collision error, not the clash error.
- **Preserved behaviour under the same forced hash**: a
  true duplicate (identical content) still returns the
  existing id on all three roads; a different category or
  path is a different identity key and stores separately;
  explicit-id replace still replaces.
- **Planted/tamper shapes without injection**: a Muninn row
  and a Huginn local row planted by raw SQL carrying a
  victim content's real hash but different content are
  refused on the victim's store (these two triggers also
  pin the RM-018 golden CASEs); a Qdrant point planted at a
  target's derived id, carrying different content under its
  own correct hash, is refused and left untouched.
- **Derived-id ceiling**: contents whose pre-slice unmasked
  derivation exceeded 2⁶³−1 are found deterministically and
  shown to derive within the ceiling now, and one such
  content round-trips through the public facade's
  `upsert_memory`/`get` against the fake client.

Negation: the same files against the pre-RM-047 installed
packages (RM-046 venv) — counts in `docs/SLICE_LOG.md` /
`CAMPAIGN_STATE.md`; the failures are exactly the new
refusals and the ceiling fix, the passes the preserved
behaviours above.

The new messages are pinned in the RM-018 goldens (Muninn
53 CASE / 68 TEMPLATE; Huginn 63 CASE / 77 TEMPLATE, 64
distinct). No schema changed — the shared cross-store
schema law is untouched, and Muninn's `nodes` table is
unchanged. The Qdrant backend's behaviour and derived-id
derivation changed, so the **Bifröst contract
re-verification was run before banking** (fresh venv,
bifrost at b66e98cc — its own suites and the BifrostBridge
smoke; result in `docs/SLICE_LOG.md` and
`CAMPAIGN_STATE.md`); the bridge uses Huginn's local
backend, so this is a regression check, not Qdrant proof.

TH-08 is closed by this slice, at the code level the threat
model reviewed: the collision assumption is documented
here and the length+hash double check stands on every
idempotent-store road. A **live Qdrant round-trip is still
NOT PROVEN** — no real server has been run; every Qdrant
proof above is against fake clients, and the threat model's
register is updated at the Part IV gate (RM-056), per its
citation rule.
