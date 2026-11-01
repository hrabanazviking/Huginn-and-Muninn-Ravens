# Pathological Paths — RM-028

A Muninn node path is a store-internal hierarchical label —
`/`-separated segments, like `people/family` — used by
`remember` / `update` / `move` on the write side and by
`get_by_path`, `get_children`, `retrieve(path=…)` and
`get_tree_structure` on the read side. It is **not** a
filesystem path: nothing in either package ever resolves a
node path against a disk, so "path traversal" here is a
question of store semantics, not of escaping onto a host.

Before this slice the behaviour for odd spellings was
undefined and, in places, inconsistent: `a/b` and `a/b/` were
different stored paths for the exact-match read but the same
prefix for the child read; `..` and empty segments were stored
verbatim; and the prefix reads built SQL `LIKE` patterns from
the raw path, so a segment containing `%` or `_` silently
matched its neighbours. RM-028 defines the behaviour and pins
it in `muninn/tests/test_pathological_paths.py`.

## The defined behaviour

**Normalisation.** Every path — written or queried, they all
pass through one normaliser — is folded to a single canonical
spelling before it touches the store:

- split on `/`; empty segments (leading, trailing or doubled
  slashes) and `.` segments are dropped;
- `..` removes the previous kept segment, and at the root it
  is dropped — paths are clamped at the store root, so
  `a/../../y` is `y` and `../x` is `x`;
- the kept segments are re-joined with single `/`s; the root
  path is `""`, and every spelling of it (`""`, `/`, `.`,
  `..`, …) folds to `""`.

Because writes and reads normalise identically, two spellings
of one logical path are the same path everywhere: a
`remember` retry under a different spelling hits the
idempotent `(content_hash, category, path)` identity instead
of forking a duplicate, and `get_by_path("/a/b/")` finds the
node stored as `a/b`. Stores written before this slice keep
working for every path that was already canonical (every path
the guides ever showed); a pre-slice store holding a
non-canonical spelling keeps that row until it is moved —
reads of its canonical spelling will not match it, which is
stated here rather than healed silently.

**Only `/` separates.** A backslash is an ordinary segment
character on every platform (`a\b` is one segment, not two),
and so are the unicode look-alikes (U+FF0F `／`, U+2044,
U+2215, …): `a／b` is one segment. Segments are otherwise
kept verbatim — case, spaces and punctuation included.

**Wildcards are literal.** Prefix reads escape `\`, `%` and
`_` and match with `ESCAPE '\'`, so a segment that happens to
contain a LIKE metacharacter names exactly itself:
`get_children("a_b")` returns the `a_b` subtree and never
`aXb`'s.

**The root's children.** `get_children("")` returns every
node at a non-root path, grouped by path — the root itself is
not its own child. (Before this slice the root query was
spelled into a prefix no stored path could match and always
returned `{}`.)

## The bounds

A path must be a string. Anything else — `None`, a number, a
list, bytes — is a typed `MuninnValidationError`
(`path must be a string, got …`) on every entry point,
raised before any write; a rejected path leaves the store
unchanged. Two ceilings apply to the *normalised* path:

| Bound | Limit | Error |
|---|---|---|
| Depth | 64 segments | `path depth {n} exceeds maximum of 64 segments` |
| Size | 2048 UTF-8 bytes | `path size {n} bytes exceeds maximum of 2048 bytes` |

Depth counts kept segments after `..` has climbed, and size
counts UTF-8 bytes, not characters (the RM-027 convention).
Both limits are generous against real hierarchies — the
founding workloads nest a handful of levels — while keeping
a hostile or runaway caller from parking an unbounded label
on every node. The three new messages are pinned in the
RM-018 goldens (CASE + TEMPLATE).

Huginn has no node paths (its memories are addressed by id
and category), so this slice is Muninn-only, like RM-021.
