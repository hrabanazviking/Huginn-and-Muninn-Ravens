# RM-026 — Input fuzzing, Huginn

Property-style fuzz over every Huginn validator, pinned by
`huginn/tests/test_input_fuzz.py` (10 tests). Stdlib only — no
new dependency: corpora are generated from recorded seeds
with `random`, so every run replays exactly. The twin of
RM-025's Muninn suite, over the surfaces this slice's roadmap
line names: upsert / search / get / delete arguments and
query text (empty, huge, unicode-edge, NUL-bearing).

**Seeds: 20261031, 20261101, 42.**

## The law under test

For every generated input, on every entry point: the call
either succeeds, or raises a typed `HuginnError` subclass —
never an untyped exception — and a rejected write leaves
**no partial write**: the store's document count is exactly
what it was before the call, and the store still works
afterwards. `fly` keeps its ancestor semantics within that
law: it never raises at all, so a validation failure comes
home as a flight with `error` set and no results.

Covered surfaces: memory ids (get / delete / upsert's
`memory_id`), content, categories (write and read paths),
importance, valence, tags, the search arguments (`limit`,
`min_importance`, `category`), every query-text entry point
(`search`, `analyze_query`, `semantic_search`, `fly`,
`multi_hop_retrieve` and their numeric arguments `top_k`,
`max_results`, `hop_count`, `max_results_per_hop`), and
`HuginnConfig`'s fields. Huge (20k-token), unicode-edge
(astral emoji, ZWJ sequences, combining marks, RTL script)
and NUL-bearing content and queries are pinned to round-trip
and search exactly. Out of scope by roadmap design:
lone-surrogate strings — RM-034 owns their typed rejection,
so the string pool contains none.

## Bugs the fuzz found in v1.0.0 (all fixed in this slice)

Acceptance proven by negation first: the fuzz suite run
against the pre-fix code failed **8 of 10 tests** (the
importance/valence and huge/unicode/NUL corpora already
passed — those validators were already strict and the
storage already honest, NUL-bearing content included).

1. **Oversized ids crashed with untyped `OverflowError`.**
   Any id above the SQLite INTEGER ceiling (2⁶³−1) reached
   the driver from `get` / `delete` / `upsert_memory`.
   `_check_memory_id` now refuses ids above
   9223372036854775807 with a typed validation error (the
   RM-025 Muninn fix, mirrored).
2. **`search(limit=…)` raised bare `TypeError`/`ValueError`**
   from `int()` (strings, None, NaN, containers), and
   silently truncated non-integral floats. `limit` now goes
   through a typed count checker (plain ints pass; finite
   integral floats keep the old `int()` semantics), shared
   with `top_k` / `max_results` / `hop_count` /
   `max_results_per_hop`.
3. **A huge `min_importance` overflowed at SQL bind time**
   (`OverflowError` inside the local backend's candidate
   query). It now carries the same 2⁶³−1 ceiling as ids.
4. **Categories were unvalidated on both paths.** Writes
   coerced with `str()` — `category=123` silently stored
   `"123"`, `category=None` stored `"None"` — and reads
   passed the raw value to the backend, where a list died
   as an untyped SQLite `ProgrammingError`. One checker now
   guards both: a string on writes, a string or None on
   reads, typed refusal otherwise.
5. **Tags crashed on non-iterables** (`tags=42` → bare
   `TypeError`) and a bare string exploded into
   single-character tags. The tags argument must now be a
   list/tuple (or None); elements keep the historical
   `str()` coercion (the RM-025 Muninn fix, mirrored).
6. **The flight paths crashed on non-string queries.**
   `fly(123)` and `multi_hop_retrieve(123)` died with
   `AttributeError` from `.strip()` before the flight's
   error envelope was reached, and `fly(max_results="x")`
   raised a bare `ValueError`. Every query-shaped argument
   now goes through one typed checker; `fly` validates
   inside its envelope, so a bad query or count returns an
   error flight instead of raising.
7. **`analyze_query` shared the crash** (and silently
   analysed `None` as an empty query). It takes the same
   checker — a non-string query is the same typed refusal
   everywhere.
8. **`semantic_search` trusted its arguments entirely:**
   non-list `documents` raised a bare `TypeError`, a bare
   string was silently iterated character by character,
   non-string documents and queries were coerced inside
   the tokenizer, and `top_k` went through raw `int()`.
   Query, documents (a list/tuple of strings) and `top_k`
   are all checked now.
9. **`HuginnConfig` numeric fields raised untyped errors**
   on non-convertible values (`vector_dim="abc"`,
   `qdrant_timeout=None`, `busy_timeout_ms=None`,
   `backup_keep="x"`), and a NaN `qdrant_timeout` passed
   validation (`nan <= 0` is False). Construction now
   coerces through never-raising helpers and every check is
   phrased so NaN fails; the error messages themselves are
   unchanged. Two fields that were never type-checked at
   all are now validated: `st_model` (non-empty string) and
   `qdrant_api_key` (string or None) — new messages, pinned
   in the golden in this same commit.

Error-message discipline (RM-018): the moved validators keep
their exact original messages; the new messages (memory-id
and min_importance ceilings, `{} must be an int, got {}`,
`category must be a string`, `tags must be a list of
strings`, `documents must be a list of strings`,
`st_model must be a non-empty string`,
`qdrant_api_key must be a string or None`) are pinned in
`golden_error_messages.txt` in this same commit (44
templates, 41 cases).

No public API signature or schema changed (RM-003 freeze +
RM-004 snapshot green), but validation behaviour tightened,
so the Bifröst contract re-verification was run before
banking — see CAMPAIGN_STATE.md for the result. Founding
tree (`~/workspace/ravens`) NEEDS A SYNC for the core/config
validator hardening (extends the standing sync note).
