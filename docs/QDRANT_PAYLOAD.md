# Qdrant Payload Hygiene — RM-046

*Security, slice eight: what a memory looks like on the server.*

Threat **TH-07** in `docs/THREAT_MODEL.md`: Huginn's Qdrant
backend stores each memory as a point whose payload carries
the memory (AS-01) in a Qdrant collection (TB-5). Before
this slice the write side built its payload from a fixed
dict — so a caller already could not overwrite a reserved
key through that code — but nothing pinned it, and the read
side trusted whatever a point handed back: `_point_to_doc`
coerced the payload's values (`int(...)` on importance,
`float(...)` on valence, `list(...)` on tags, whose string
form would have exploded into single characters) and never
looked at `content_hash` at all. A hostile co-tenant of the
same collection (AC-4), a tampered point, or a foreign point
written by another tool could therefore surface in search
results wearing Huginn's shape — an importance of 999, a
string's characters as tags, or arbitrary content riding
under a real memory's identity. This slice pins the write
side and makes the read side check what it is handed.

## The defined behaviour

**Payload keys are a closed set.** Exactly six keys, named
by `_PAYLOAD_KEYS` in `qdrant_backend.py`, in write order:

`content`, `category`, `importance`, `tags`,
`emotional_valence`, `content_hash`.

`upsert` builds the payload from one fixed dict literal.
Caller-supplied content, category and tags enter only as
*values* of that dict — there is no caller-controlled key
anywhere in the API or the backend signature — so no caller
input can add a key, rename one, or overwrite a reserved
one. A tag literally named `content_hash` stays a tag; a
category named `content_hash` stays a category; content
that itself parses as a payload document is stored as
content text, and the payload's real `content_hash` is the
SHA-256 of that text and its category, computed by the
backend.

**Returned payloads pass a hygiene check before they are
trusted.** `_point_to_doc` — the one road from a server
point to a caller-visible document, used by both `get` and
`search` — now requires, of every returned point:

- an integer-coercible point id;
- a payload that is a dict carrying **every** closed-set
  key (extra keys are permitted on the point but are
  dropped: the returned document is built from the closed
  set only, as it always was);
- `content` and `category` strings;
- `importance` an integer (never a bool) in [1, 10] —
  the range the write side validates;
- `tags` a list whose elements are all strings;
- `emotional_valence` a finite number (never a bool) in
  [-1, 1];
- `content_hash` a string equal to the SHA-256 of the
  returned content and category — the same hash the write
  side would have computed, so a point whose body was
  swapped after writing, or whose hash was forged, does
  not pass;
- on search results, a finite numeric score.

A point that fails any part of the check raises
`HuginnBackendError` with one of two static shapes —
`Qdrant point {id} has a malformed payload`, or, when the
point's id itself cannot be read as an integer,
`Qdrant point has a malformed payload`. The refusal is
loud, never a silent drop or a coerced repair, and its
message carries no payload content — only the point id.
Both messages are pinned in the RM-018 golden (CASE +
TEMPLATE), like every other typed message.

The check is deliberately a *shape and integrity* check,
not a truth check (NG-4): a well-formed point written by
another writer with a correct hash is returned, exactly as
a locally planted well-formed point is in the tests. What
the check refuses is a point that cannot have come from
Huginn's write side in its current form.

## How it is proven

Pinned by `tests/test_qdrant_payload.py` (14 tests, fake
clients only; hostile points are planted directly in the
fake client's store, the way a co-tenant writing to the
same collection would plant them):

- the write side: upsert stores exactly the closed key
  set with the caller's values and the backend-computed
  hash; tags named after reserved keys stay tag values;
  payload-shaped content cannot forge the stored hash or
  category; a category named after a reserved key stays a
  value; the same hostile tags round-trip through the
  public facade;
- the read side: extra keys on a returned point are
  dropped and never surfaced; a well-formed raw point with
  a correct hash is returned on `get` and `search`; a
  forged `content_hash` is refused on both roads, with the
  payload content absent from the error; every missing
  closed-set key is refused; wrong-typed or out-of-range
  reserved values (string / bool / out-of-range importance,
  string / out-of-range / NaN valence, string or
  non-string-element tags, non-string content, category and
  hash) are refused; non-dict and missing payloads are
  refused; a malformed point id and a forged search score
  are refused with the typed errors.

Negation: the same file against the pre-RM-046 installed
packages (RM-045 venv) — counts in `docs/SLICE_LOG.md` /
`CAMPAIGN_STATE.md`; the failures are the new hygiene
refusals, the passes are the write-side closed set and the
extra-key drop, which already held by construction and are
now pinned.

No public API, config or schema changed (the new raise
sites are backend-internal behaviour on a road that
previously returned coerced documents or raised untyped
`ValueError`/`TypeError`), so no RM-019 surface change —
but the RM-018 golden gained the two new templates and
their two cases deliberately in this commit. Because the
Qdrant backend's behaviour changed, the **Bifröst contract
re-verification was run before banking** as a precaution
(fresh venv, bifrost at b66e98cc — its own suites and the
BifrostBridge smoke; result in `docs/SLICE_LOG.md` and
`CAMPAIGN_STATE.md`); the bridge uses Huginn's local
backend, so this is a regression check, not Qdrant proof.

TH-07 is closed by this slice, at the code level the
threat model reviewed: the closed set is pinned on the
write road and enforced on the read road. A **live Qdrant
round-trip is still NOT PROVEN** — no real server has been
run; every proof above is against fake clients, and the
threat model's register is updated at the Part IV gate
(RM-056), per its citation rule.
