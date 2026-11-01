# RM-025 — Input fuzzing, Muninn

Property-style fuzz over every Muninn validator, pinned by
`muninn/tests/test_input_fuzz.py` (10 tests). Stdlib only — no
new dependency: corpora are generated from recorded seeds with
`random`, so every run replays exactly.

**Seeds: 20261031, 20261101, 42.**

## The law under test

For every generated input, on every entry point: the call either
succeeds, or raises a typed `MuninnError` subclass — never an
untyped exception — and a rejected write leaves **no partial
write**: the store's stats (nodes / connections / activations)
are exactly what they were before the call, and the store still
works afterwards.

Covered surfaces: memory ids (activate / get_node /
activation_count / get_associations / forget / update /
spread_activation seeds), valence, importance, associate
strength/delta, activate_batch atomicity, the numeric parameters
(min_strength, attenuation, depth, limit, top_k, consolidate
threshold, decay days), tags and metadata (remember / update /
retrieve), content, paths, categories, and `MuninnConfig`'s
fields. Out of scope by roadmap design: lone-surrogate content
strings — RM-034 owns their typed rejection, so the string pool
contains none.

## Bugs the fuzz found in v1.0.0 (all fixed in this slice)

Acceptance proven by negation first: the fuzz suite run against
the pre-fix code failed **8 of 10 tests** (the valence/importance
and content/path corpora already passed — those validators were
already strict).

1. **Oversized ids crashed with untyped `OverflowError`.** Any
   id above the SQLite INTEGER ceiling (2⁶³−1) reached the
   driver. `_check_memory_id` now refuses ids above
   9223372036854775807 with a typed validation error.
2. **A failed `activate_batch` left a partial write pending.**
   `[valid_id, 2**100]` logged the valid id's activation inside
   the open transaction before the second id overflowed; the
   next successful commit would have persisted it. Fixed by
   (1) — every id is now fully validated before any write.
3. **`associate` validated `delta` after its first write.** The
   rate check sat inside the write loop, after a tombstone
   delete had already been issued in the same uncommitted
   transaction. Both numeric arguments are now validated before
   the lock is taken and before any SQL runs.
4. **Non-numeric strength / delta / attenuation / min_strength /
   threshold raised bare `TypeError`/`ValueError`** from
   `float()` (strings, containers, objects). All five now go
   through single-message typed checkers; bools are refused as
   numbers, and NaN fails every range check.
5. **`decay(days=NaN)` corrupted confidences.** NaN passed the
   `days < 0` check, the factor became NaN, and SQLite raised an
   untyped `IntegrityError` on the NOT NULL confidence column
   mid-write. `days` must now be finite (`math.isfinite`);
   infinities are refused with the same typed message.
6. **Integer parameters (`limit`, `depth`, `top_k`) raised
   untyped errors** for non-numeric / NaN / infinite values via
   `int()`. They now go through one typed count checker (plain
   ints pass; finite integral floats keep the old `int()`
   semantics; everything else is a typed refusal naming the
   parameter).
7. **Tags arguments crashed on non-iterables** (`tags=42`,
   `tags=True` → bare `TypeError`; a retrieve tag filter with a
   non-string element → `AttributeError`). The tags argument
   must now be a list/tuple (or None); a bare string is refused
   instead of exploding into single-character tags. Elements
   keep the historical `str()` coercion.
8. **`update(metadata=<circular>)` raised an untyped
   `ValueError`** — `remember` caught the serializability
   failure, `update` did not. Both now raise the same typed
   "metadata must be JSON-serializable".
9. **`MuninnConfig` fields raised untyped errors** on
   non-convertible values (e.g. `learning_rate="abc"`,
   `busy_timeout_ms=None`), and NaN half-lives passed validation
   (`nan <= 0` is False). Construction now coerces through
   never-raising helpers and every check is phrased so NaN
   fails; the error messages themselves are unchanged.
10. **`spread_activation` tightened:** a non-list `seed_ids`
    argument and an out-of-range `min_strength` are now typed
    refusals instead of iteration accidents / silent filters.

Error-message discipline (RM-018): the moved validators keep
their exact original messages; the new messages (memory-id
ceiling, `{} must be an int, got {}`, `tags must be a list of
strings`, `seed_ids must be a list of ints`) are pinned in
`golden_error_messages.txt` in this same commit (38 templates,
31 cases).

No public API signature or schema changed (RM-003 freeze +
RM-004 snapshot green), but validation behaviour tightened, so
the Bifröst contract re-verification was run before banking —
see CAMPAIGN_STATE.md for the result. Founding tree
(`~/workspace/ravens`) NEEDS A SYNC for the core/config
validator hardening (extends the standing sync note).
