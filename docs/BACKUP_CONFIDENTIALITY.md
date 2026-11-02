# Backup Confidentiality — RM-043

*Security, slice five: the copies are the content too.*

Threat **TH-04** in `docs/THREAT_MODEL.md`: the rolling
`.bak-N` generations are full copies of memory, kept beside
the store for as long as `backup_keep` says. RM-042 made new
store files owner-only, but a backup snapshot was still
created by SQLite under the process umask — so an
owner-only store's backup could land at `0o644` (or worse
under a permissive umask), readable by every local account,
undoing RM-042 for exactly the data that matters most: the
recovery copies. (On some roads SQLite's Unix VFS copies a
sibling file's mode on its own — the negation run below
shows one such road — but that was an accident of the VFS,
not a guarantee: the explicit `backup()` road and every
Huginn road did not inherit.)

## The defined behaviour

**A backup inherits the store file's permissions.** In
`_take_backup_unlocked` (both packages), the moment the
snapshot (`.bak-tmp`) is written and closed — before it is
verified and rotated into place — it is chmodded to the
store file's own mode at that moment
(`_inherit_store_permissions`). Every road that takes a
backup goes through this one function: explicit `backup()`
calls, the auto-backup on open, and the maintenance
backups before decay/consolidate.

Inheritance is exact, in both directions:

- An owner-only store (`0o600`, the RM-042 default for new
  stores) produces owner-only backups — under any umask,
  including umask `0`.
- A store the owner deliberately loosened (say `0o644`)
  produces `0o644` backups. This slice does not force
  `0o600`: the store's stated mode is the owner's choice
  for the data, and its copies follow it. (RM-042's
  `health()` warning is how a loosened store is surfaced.)
- A rotated generation keeps the mode it was taken with:
  if the store's mode changes between backups, each
  generation carries its own era's mode.

The chmod is best-effort, like RM-042's: a refused chmod is
logged and the backup proceeds — a backup that cannot be
re-permissioned is still a valid backup, and rotation must
not fail over a hardening step.

## How it is proven

Pinned by `tests/test_backup_confidentiality.py` in both
packages (muninn 5 tests, huginn 4, POSIX-only):

- Muninn: `backup()` of an owner-only store yields a
  `0o600` `.bak-1` — including under umask `0`; a store
  loosened to `0o644` yields a `0o644` backup; the
  auto-backup on open inherits `0o640`; and across a mode
  change, the newest generation carries the new mode
  while the rotated generation keeps its own.
- Huginn: the auto-backup on open of an owner-only store
  is `0o600`; `take_backup` inherits under umask `0` and
  from a loosened `0o644` store; rotation keeps each
  generation's own mode as in Muninn.

Negation: the same files against the pre-RM-043 installed
packages (RM-042 venv): muninn **4 failed / 1 passed**,
huginn **4 failed / 0 passed**. The one muninn pass is
`test_backup_on_open_inherits_store_mode` — on that road
SQLite's Unix VFS already copied the store's mode to the
snapshot file on its own; the slice makes inheritance
explicit and universal instead of road-dependent.

No public API or schema changed in this slice, so no
Bifröst re-verification was required (the RM-040
precedent: docs + store-machinery behaviour only, no
surface change).

TH-04 is closed by this slice, on top of RM-042's TH-03
creation side. The threat model's register is updated at
the Part IV gate (RM-056), per its citation rule.
