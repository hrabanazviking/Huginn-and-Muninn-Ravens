# Determinism Audit — RM-011

*Part II — Stability. The law of this part: nothing drifts,
nothing depends on the mood of the machine.*

This document is the audit record: every source of
nondeterminism hunted, and for each one whether it was **pinned**
(made deterministic in code), **proven** (already deterministic,
with the proof named), or **documented** (inherently outside the
store's control, stated plainly). The acceptance proof lives in
`tests/test_determinism.py` in both packages: one fixed workload
run on two fresh stores produces **byte-identical store dumps**
once the timestamp columns listed below are excluded, and the
same holds in child processes under different `PYTHONHASHSEED`
values (0 and 42).

## Excluded from the dumps — the timestamp columns (listed)

Muninn: `nodes.created_at`, `nodes.updated_at`,
`activation_log.activated_at`,
`hebbian_connections.created_at`,
`hebbian_connections.last_coactivated_at`,
`node_activation.last_activated_at`, `deleted_nodes.deleted_at`.

Huginn (local): `documents.created_at`, `documents.updated_at`.

These are wall-clock values by design. Their discipline (UTC
ISO-8601 from one helper per package, monotonicity under clock
skew) is RM-012's slice, not this one's.

## Findings

### Pinned in this slice

1. **Score/strength ties in result ordering.** Every ordered
   read whose sort key can tie now carries an explicit final
   tie-break, so order never falls through to SQLite's
   unspecified row order:
   - Muninn `get_associations`: `strength DESC,
     co_activation_count DESC, memory_b_id ASC`.
   - Muninn `spread_activation`: sort key `(-activation, id)`.
   - Muninn `retrieve`: `(importance, updated_at, id)`.
   - Muninn `get_by_path` / `get_children` / `dump`:
     `id ASC` appended to the existing `ORDER BY`.
   - Huginn local TF-IDF and vector search: sort key
     `(-score, doc_id)`.
   - Huginn module-level `semantic_search`: sort key
     `(-score, index)`.
2. **Backpressure victim choice (Muninn).** When the node cap
   forces pruning, victims are chosen `ORDER BY importance,
   access_count, updated_at, id` — a tie on the first three can
   no longer prune a different node on a different run.
3. **Heal write order.** Muninn's heal reads the wiring
   `ORDER BY memory_a_id, memory_b_id`; Huginn's local heal
   repairs `corpus_stats` iterating `sorted(terms)` instead of a
   set union whose order follows the process hash seed. (The
   final healed state was already identical; the *write order*
   was the nondeterministic part.)

### Proven already deterministic

4. **Content hashes.** Muninn hashes `sha256("s:" + text)` for
   strings and `sha256("j:" + json.dumps(content,
   sort_keys=True))` for JSON content; Huginn hashes
   `sha256(category + NUL + content)`. No float is ever
   formatted into a hash input except inside `json.dumps`,
   whose float rendering (`repr`, shortest round-trip) is fixed
   by CPython. Metadata is stored via `json.dumps(...,
   sort_keys=True)`, so caller dict order cannot leak into the
   store.
5. **The hashing embedder.** SHA-256 bucketing with signed
   accumulation and L2 normalization — same text, same vector,
   on any machine. Its stored JSON vectors are part of the
   byte-identical dump proof.
6. **Float arithmetic.** TF-IDF / cosine / Hebbian updates sum
   over dicts whose insertion order is fixed by token order and
   query order — never over sets. Decay and consolidation are
   pure functions of stored values and explicit parameters.
7. **Dict ordering generally.** Python dicts preserve insertion
   order; every result dict is built in a fixed code order
   (pinned further by the RM-003 contract-freeze key sets).

### Documented, not pinned

8. **Qdrant backend result order** is the server's own scoring
   order; the local pins do not reach it. Live Qdrant remains
   **NOT PROVEN** (no live server run yet), so nothing here
   claims otherwise.
9. **Wall-clock timestamps themselves** (see the excluded list
   above) — values differ run to run by design; RM-012 owns
   their discipline.
10. **`RetrievalResult.timestamp` / `retrieval_time`** in
    Huginn flights are per-call measurements, never stored, and
    no test compares them.
11. **Physical file bytes** of the SQLite store (page layout,
    freelist, WAL sidecars) are SQLite's business and are *not*
    claimed identical — the acceptance compares logical dumps
    (every non-timestamp column of every table, key-ordered),
    which is the level the roadmap's acceptance names.
