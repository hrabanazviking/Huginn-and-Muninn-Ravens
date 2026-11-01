# API Surface Freeze (RM-019)

The ravens' public API is now frozen as a complete inventory,
not just at the points Bifröst touches.

RM-003 froze the Bifröst contract: the signatures and result
keys of the handful of methods the bridge calls. RM-019 widens
that freeze to the **whole public surface** of both packages,
snapshotted in `tests/golden_api_surface.txt` per package and
enforced by `tests/test_api_surface.py`.

## What the snapshot contains

Per package (muninn **101 lines**, huginn **57 lines**):

- `ALL` — every name in the top-level `__all__`.
- `CLASS` — every exported class with its direct base classes,
  which pins the error hierarchy (`MuninnValidationError` under
  both `MuninnError` and `ValueError`, and so on) and the
  `Muninn` facade's inheritance from `HebbianMemory`.
- `METHOD` — every public method of every exported class
  (inherited methods included, so the facade is pinned to keep
  the whole ancestor surface), with its signature in the RM-003
  shape: `name:KIND=default` per parameter, `self`/`cls`
  excluded. Builtin-inherited members (`object`/`Exception`
  machinery) are not package surface and are excluded.
- `FIELD` — every dataclass field of the exported dataclasses
  (`MuninnConfig`, `MemoryNode`, `HuginnConfig`,
  `RetrievalResult`) with declared type and default
  (`<required>` / `<factory>` where there is no plain default).
- `PROPERTY` / `ATTR` — public properties (e.g.
  `MemoryNode.category`) and public class attributes (e.g.
  `HebbianMemory.MAX_QUERY_RESULTS`).
- `FUNCTION` — exported module-level functions (huginn's
  `analyze_query`, `semantic_search`).
- `VERSION` — the presence of `__version__` (its value is the
  version's own business, not the freeze's).

Signatures are pinned in the (name, kind, default) shape only —
annotations are not part of the freeze, matching RM-003.

## The rule

- **Additions are allowed.** A new export, method or field
  does not fail the suite. It should still be added to the
  golden in the commit that introduces it, so the snapshot
  stays a complete inventory; the companion test pins that the
  test's own inventory and `__all__` agree exactly, so a new
  export cannot slip in unlisted.
- **Removals, renames and signature changes fail.** Any golden
  line the live surface no longer produces fails
  `test_no_golden_surface_line_is_missing`, until a deliberate
  major-version slice updates the golden in its own commit.

## Acceptance, proven by negation

On scratch copies of the installed packages (discarded):

- renaming muninn `HebbianMemory.stats` fails the freeze test
  (1 failed / 2 passed);
- changing muninn `decay`'s default `1.0 → 2.0` fails it
  (1 failed / 2 passed);
- dropping `semantic_search` from huginn's `__all__` fails it
  (2 failed / 1 passed);
- adding a brand-new public method to `HebbianMemory` passes
  (3 passed) — additions really are allowed.

No package code, public API, or schema changed in this slice,
so no Bifröst re-verification was required.
