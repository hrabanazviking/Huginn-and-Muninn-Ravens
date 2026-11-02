# Path Safety — RM-041

*Security, slice three: where the store path itself points.*

Threat **TH-02** in `docs/THREAT_MODEL.md`: a symlinked store
path or parent directory, or a world-writable parent
directory, lets a local file attacker (AC-3) redirect a store
— or its restore — somewhere the attacker controls. Before
this slice the behaviour was only *recorded*: both packages
expand `~` in the store path and deliberately do **not**
symlink-resolve it (`resolved_path()` /
`resolved_local_path()` document this), parent directories
are created on open, and no mode checked any of it. That
recorded behaviour stays the default. This slice adds the
explicit opt-in strict mode the roadmap asked for.

## The defined behaviour

**`strict_path_safety` is a config flag on both packages,
off by default:**

- `MuninnConfig(..., strict_path_safety=True)`
- `HuginnConfig(..., strict_path_safety=True)` — the local
  backend only; the Qdrant backend has no local file and is
  untouched by this slice.

With strict mode **off** (the default), nothing changes:
symlinked store paths, symlinked parents, and
world-writable parents open exactly as before. The default
is pinned by tests, so the opt-in cannot silently become
the default.

With strict mode **on**, opening a store refuses — loudly,
with the package's typed storage error — either shape:

1. **A symlink in the path.** The store file itself, or any
   parent directory component of its absolute path, is a
   symlink. Every existing component is judged by
   `is_symlink()` (an `lstat` — the links themselves are
   judged, never followed to their targets).
   - Muninn: `muninn store {path} is a symlink or has a
     symlinked parent and strict path safety is enabled;
     refusing to open` (`MuninnStorageError`)
   - Huginn: `huginn store {path} is a symlink or has a
     symlinked parent and strict path safety is enabled;
     refusing to open` (`HuginnStorageError`)
2. **A world-writable parent directory.** The directory
   that holds the store carries the world-writable bit
   (`mode & 0o002`), so any local account could plant or
   replace files in it.
   - Muninn: `muninn store {path} has a world-writable
     parent directory and strict path safety is enabled;
     refusing to open`
   - Huginn: `huginn store {path} has a world-writable
     parent directory and strict path safety is enabled;
     refusing to open`

Both messages are pinned by the RM-018 goldens (new CASE +
TEMPLATE lines in both packages).

The refusal is structural, like RM-030/RM-033: the check is
a pre-flight at the head of `open_store` in each package's
`_db.py`, running with the shape and read-only pre-flights
*before* the coordination lock is taken — so a refused open
creates nothing, not even the RM-037 `.open-lock` file, and
never reaches the integrity/restore logic (a restore writes
to the store path too, so the redirection road is closed
for restores as much as for first opens). The same check
runs again inside the locked open, with the other
pre-flights.

Two scoping decisions, stated plainly:

- **Only the immediate parent is judged world-writable.**
  System ancestors such as `/tmp` are world-writable by
  design (sticky-bit shared space every process relies
  on); judging them would make strict mode unusable
  anywhere under them. The threat is the store's own
  directory being shared, and that is what is checked.
- **A parent that does not exist yet is not pre-judged.**
  The open creates it under the process umask (never
  world-writable under any sane umask); the check then
  applies to it from the next open on. Strict mode still
  refuses a *symlinked* not-yet-created path, because the
  symlink components themselves already exist.

Strict mode does not resolve or rewrite the path in any
case: it refuses, it never silently redirects the caller
to the resolved target — where a store lives stays the
caller's stated choice or a loud error.

## How it is proven

Pinned by `tests/test_path_safety.py` in both packages
(9 tests each):

- Default mode (both packages): a symlinked store path, a
  store under a symlinked parent, and a store in a
  `0o777` parent all open and work exactly as before.
- Strict mode (both packages): a symlinked store file, a
  symlinked immediate parent, and a symlinked ancestor
  (store nested below the link) are each refused with the
  exact symlink message, and nothing is created — no
  store file at the target, no `.open-lock` beside the
  refused path; a `0o777` parent is refused with the
  exact world-writable message, and the same parent at
  `0o755` opens and works; a normal store opens, stores,
  and reopens with zero recovery; a store under a
  not-yet-existing parent is created and works.

Negation: the same files against the pre-RM-041 installed
packages (RM-040 venv) fail exactly the six strict-mode
tests per package (6 failed / 3 passed — the three passes
are the default-mode behaviours this slice preserves).

The RM-019 API-surface goldens gained the new config field
in both packages. The public config surface changed
additively, so the **Bifröst contract re-verification was
run before banking** (fresh venv
`ravens-rm041-bifrost-venv`, bifrost at b66e98cc — its own
suites **25 passed**; BifrostBridge smoke PASS, evidence
`~/workspace/.verify-tmp/rm041/bifrost_smoke.log`; huginn
degraded via auto-fallback to local — qdrant-client not
installed in the venv, the founding condition; a live
Qdrant round-trip is still NOT PROVEN).

TH-02 is closed by this slice for callers who opt in; the
default posture is unchanged and is a documented choice,
not an oversight — the threat model's register is updated
at the Part IV gate (RM-056), per its citation rule.
