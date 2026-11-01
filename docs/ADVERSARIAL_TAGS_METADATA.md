# Adversarial Tags & Metadata — RM-036

RM-027 gave content and metadata explicit size ceilings, and
RM-025/RM-026 checked that metadata is serializable before
any write. What neither covered was the *shape* of the
annotation payload: how deep it nests, and whether the tags
list — bounded by no ceiling at all — could grow without
limit. RM-036 closes both, measured first by probe against
the RM-035 packages:

- Muninn metadata or JSON-shaped content nested 5,000
  containers deep escaped `remember` as a raw
  `RecursionError` — raised inside the recursive RM-034
  surrogate walk or inside `json.dumps` itself, before the
  RM-027 size check ever ran.
- A tags list of 200,000 entries was accepted by both
  ravens, however large its stored form grew.
- A Huginn tag element nested 50,000 containers deep escaped
  `upsert_memory` as a raw `RecursionError` from the `repr`
  produced by the facade's `str()` coercion.

## The depth bound

One bound in each package (`_MAX_STRUCTURE_DEPTH = 100`
containers), enforced by an iterative walker
(`_check_structure_depth`): an explicit stack plus a
path-scoped id set, so the check itself can never overflow
the stack it guards. A value nested deeper than 100
containers is refused with the typed validation error

```
{field} nesting depth exceeds maximum of 100
```

before any write. 100 is far beyond any honest memory shape
and far below the depth at which the recursive consumers
(surrogate walk, `json.dumps`, `repr`) overflow.

Where it applies:

- **Muninn** — JSON-shaped `content` (in `_content_payload`,
  ahead of the surrogate walk and the dump), `metadata` on
  `remember` and `update` (same ordering), and every tag
  element on `remember`, `update` and the `retrieve` filter
  (ahead of the `str()` coercion whose `repr` overflowed).
- **Huginn** — every tag element in `upsert_memory`, in the
  facade, so the refusal holds on the local and Qdrant
  backends alike. Huginn memories carry no caller metadata
  and Huginn content is a flat string, so tags are its whole
  structured surface.

**Self-referential structures** keep their established
answers: the walker does not descend into a container
already on its own path, so a circular content or metadata
value still reaches `json.dumps` and is refused with the
established `… must be JSON-serializable` /
`content must be a string or JSON-serializable value`
messages, and a circular tag element still renders through
`repr`'s ellipsis (`[[...]]`), exactly as before. A *shared*
(DAG-shaped) substructure is not circular: it is walked once
per occurrence and stored as before.

## The tags size bound

The RM-027 ceilings, applied uniformly to the one payload
they did not yet reach:

- **Muninn** — the cleaned tags list, measured as the UTF-8
  byte length of its stored JSON form, must fit
  `max_metadata_bytes` (the annotation ceiling that already
  bounds metadata): above it, the typed refusal
  `tags size {n} bytes exceeds max_metadata_bytes ({c} bytes)`,
  on `remember` and `update`, before any write.
- **Huginn** — the same measure must fit
  `max_content_bytes` (the only ceiling Huginn carries):
  `tags size {n} bytes exceeds max_content_bytes ({c} bytes)`,
  in the facade, before any backend is touched.

At and below the bounds, behaviour is exactly what it was:
tag cleaning (Muninn's strip/lower/64-char truncation,
Huginn's `str()` coercion) is unchanged.

## Proof

`tests/test_adversarial_tags_metadata.py` in both packages
(muninn 16 tests, huginn 7): depth at the bound stored,
depth above it and thousands deep refused typed (never a
`RecursionError`) with counts unchanged; circular
content/metadata keeping their serializability refusals;
shared substructures stored; circular tag elements rendering
with the ellipsis; tags at the ceiling stored, above it
refused typed with the measured size in the message, on both
write paths; a 200,000-tag flood refused under the default
ceilings. Negation against the pre-RM-036 packages: muninn
and huginn suites fail on exactly the new behaviours (counts
in `docs/SLICE_LOG.md` / `CAMPAIGN_STATE.md`). The new error
messages are pinned in the RM-018 goldens (CASE + TEMPLATE
in each package).
