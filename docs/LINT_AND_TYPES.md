# Lint & Type Floor (RM-008)

Both packages carry a lint/type floor in their own
`pyproject.toml`. Findings are fixed, never suppressed: there is
no `noqa`, no per-file ignore, and no `# type: ignore` anywhere in
either tree. The floor is pinned by `tests/test_lint_type_floor.py`
in both packages and run by the manual CI on every dispatch.

## The floor

**Ruff** (`ruff>=0.6,<1`, dev extra only):

- `target-version = "py311"`, `line-length = 100`
- Rule families: `E` (pycodestyle errors), `W` (warnings),
  `F` (pyflakes), `I` (import order), `UP` (pyupgrade),
  `B` (bugbear), `SIM` (simplify), `C4` (comprehensions)
- Scope: `src`, `tests`, `scripts` of both packages

**Mypy** (`mypy>=1.11,<2`, dev extra only) — ratchet level 1:

- `python_version = "3.11"`
- `disallow_untyped_defs`, `disallow_incomplete_defs`,
  `check_untyped_defs`, `warn_return_any`, `no_implicit_optional`,
  `warn_unused_configs` — all on
- Scope: the `src/<package>` tree of each package, run from inside
  that package's directory so its own config governs
- Huginn carries exactly one scoped exception, and it is a
  configuration fact, not a code finding: `qdrant_client` and
  `sentence_transformers` are optional extras, imported lazily
  inside functions, and are not installed in the type-check
  environment. A `[[tool.mypy.overrides]]` entry marks exactly
  those two modules `ignore_missing_imports`; a test pins the
  override list so it cannot widen silently.

Both tools are dev-only: they sit in each package's `dev` extra,
bounded `>=floor,<next_major` per the roadmap's dependency law.
Neither package gains a runtime dependency.

## Run it

```sh
pip install "ruff>=0.6,<1" "mypy>=1.11,<2"
ruff check muninn/src muninn/tests muninn/scripts
ruff check huginn/src huginn/tests huginn/scripts
(cd muninn && mypy src/muninn)
(cd huginn && mypy src/huginn)
```

## What the first run found, and what was fixed (2026-10-31)

Under this floor the untouched v1.0.0 trees produced **196 ruff
findings** and **9 mypy findings**. All were fixed in code:

- Annotation modernisation (the bulk): `Dict`/`List`/`Optional`
  → builtin generics and `X | None`, `datetime.timezone.utc` →
  `datetime.UTC`, quoted annotations unquoted, import blocks
  sorted, unused imports removed, `__all__` sorted.
- Real code fixes the floor earned its keep on:
  - Four validator helpers returned an `Any` from an `int`-typed
    function; they now return `int(value)` after the isinstance
    guard (mypy `no-any-return`).
  - Three SQLite insert sites called `int(cur.lastrowid)` where
    the type is `int | None`; each now raises the package's
    storage error loudly if an insert ever reports success
    without a row id, instead of dying on a bare `TypeError`.
  - Four `try/except: pass` close paths rewritten as
    `contextlib.suppress(...)` — same behaviour, stated plainly.
  - `zip()` calls gained explicit `strict=`: `strict=True` in the
    qdrant test fake (equal lengths by construction), and a
    deliberate, commented `strict=False` in `huginn.text`'s
    `dense_cosine` — a stored vector written under another
    embedder must not crash a pure read.
  - Nine over-length lines wrapped; the ambiguous comprehension
    variable `l` renamed; a nested `dict()` call in a test helper
    rewritten as a literal; the benchmark gate's change-ratio
    if/else collapsed to the expression it already was.
  - The trees also carried **10 pre-existing `noqa` suppressions**
    (not counted above — a `noqa` hides its finding): seven lambda
    factories in the qdrant test fake (E731) are now real
    `@staticmethod` factories, and the benchmark scripts' three
    path-bootstrap imports (E402) moved into the single function
    that uses them. After this slice there is no `noqa` and no
    `# type: ignore` anywhere in either tree — verified by grep,
    not by memory.

## Clean-run evidence (2026-10-31, this VM)

- `ruff check` over both packages' `src` + `tests` + `scripts`:
  **All checks passed!** (ruff 0.15.22)
- `mypy src/muninn`: **Success: no issues found in 5 source
  files**; `mypy src/huginn`: **Success: no issues found in
  8 source files** (mypy 1.20.2)
- Full suites after the fixes, installed packages, per package:
  muninn **58 passed**, huginn **49 passed** — the pre-floor
  counts (54 / 44) plus each package's new floor pins (4 + 5),
  with zero behavioural regressions.

## The ratchet road (named next raises)

The floor is level 1, not the ceiling. Named next steps, in
order, each its own slice-sized change with findings fixed:

1. Mypy: add `warn_redundant_casts` and `strict_equality`.
   Measured 2026-10-31 on the level-1 trees: these two flags
   surface a further set of findings (redundant casts and
   comparisons against `Any`-typed config values, e.g. in
   muninn's `core.py` consolidation path) — real work, deliberately
   not bundled into this slice.
2. Mypy: work toward `disallow_untyped_calls` and eventually
   `--strict` proper.
3. Ruff: evaluate the `BLE` (blind-except), `S` (security) and
   `PLR` (refactor) families; several current `except Exception`
   sites are deliberate fallback boundaries (backend probing) and
   will need case-by-case judgement, not blanket fixes.

A GitHub-hosted run of the new CI steps is NOT PROVEN — the
workflow has never been dispatched (RM-002 posture); the local
runs above are the evidence.
