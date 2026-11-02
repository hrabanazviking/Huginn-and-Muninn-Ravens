# File Permissions — RM-042

*Security, slice four: who else on this machine can read the store.*

Threat **TH-03** in `docs/THREAT_MODEL.md`: before this slice,
no package code set or checked permissions anywhere — a new
store file was created by SQLite under the process umask, so
on a typical `022` umask the file landed at `0o644`: readable
by every local account (AC-3 → AS-01, TB-2). The memories were
plaintext to anyone with a login on the box. This slice closes
the creation side and makes the legacy side visible.

## The defined behaviour

**New store files are created owner-only.** When an open
creates the store file — a fresh store, or a store restored
onto a path that did not exist (the RM-032 orphaned-WAL road)
— the open sets the file to `0o600` once the schema is
applied, together with its `-wal` / `-shm` sidecars (the WAL
holds uncheckpointed memory while the store is open). The
chmod is unconditional on the creation path, so it holds
under any umask — under umask `0` the file would otherwise
land at `0o666`, and the tests pin that it lands at `0o600`
instead.

"Where the OS allows" is literal: the chmod is best-effort.
A platform or filesystem that refuses it is logged
(`could not set owner-only permissions on ...`) and the open
proceeds — permissions harden a store, they are not a reason
to refuse a healthy one. On POSIX, the platform the roadmap's
acceptance names, the chmod succeeds.

**Existing store files are reported, never re-permissioned.**
Opening a store that already exists never changes its mode:
the owner may have loosened it deliberately, and a library
silently rewriting file permissions on open would be its own
surprise. Instead, `health()` reports it:

- `file_permissions_warning` is `None` when the store file
  grants nothing to group or other accounts (no `0o077`
  bits set).
- Otherwise it is the string
  `store file permissions {mode:04o} are looser than owner-only 0600; group or other local accounts can access the store file`,
  naming the file's actual mode (e.g. `0644`, `0640`).

The field is additive in both packages' `health()` dicts
(Muninn's own; Huginn's local backend's, carried through the
facade). The Qdrant backend has no local file and carries no
such field. `health()` stays a pure read: the warning is one
`stat`, no chmod on the read path, ever — the only
reinforcing reads in these packages remain the explicitly
named ones.

Two scoping decisions, stated plainly:

- **Only the store file itself is judged for the warning.**
  Sidecar modes follow the store's creation (above); a
  pre-existing store's sidecars are transient SQLite files,
  removed on a clean close.
- **Rolling backups are not this slice.** The `.bak-N`
  generations are full copies of memory and their
  confidentiality is RM-043, next in roadmap order; until
  it banks, a backup taken from a pre-RM-042 store can still
  carry that store's era's permissions.

## How it is proven

Pinned by `tests/test_file_permissions.py` in both packages
(7 tests each, POSIX-only):

- A new store file is exactly `0o600` after storing and
  after close — including under umask `0`.
- While a new store is open, any `-wal` / `-shm` sidecars
  that exist are `0o600`.
- A new store's `health()` carries
  `file_permissions_warning is None`.
- An existing file loosened to `0o644` reopens, works, is
  **still** `0o644` after the open (never re-permissioned),
  and its `health()` warning names `0644` and `0600`; at
  `0o640` the warning names `0640`.
- An existing `0o600` file reopens with no warning and its
  mode unchanged.

Negation: the same files against the pre-RM-042 installed
packages (RM-041 venv) fail all seven tests per package
(7 failed / 0 passed — the new behaviour and the new health
field are both absent there).

The RM-019 contract-freeze health key sets in both packages
gained `file_permissions_warning` deliberately. The public
`health()` surface changed additively, so the **Bifröst
contract re-verification was run before banking**:
fresh venv (`ravens-rm042-bifrost-venv`, on `/var/tmp`),
bifrost at b66e98cc — its own suites **25 passed**;
BifrostBridge smoke PASS (store mimir_id+huginn_id;
search 1 merged result; recall grew the Muninn
activation log exactly +1; decay/consolidate reports;
`decay_wall_clock()` armed at 0 days; stats over all
three backends; both raven health dicts carry
`sqlite_version` 3.45.1 through the bridge; double
close safe; evidence `~/workspace/.verify-tmp/rm042/`;
a live Qdrant round-trip is still NOT PROVEN).

TH-03's creation side is closed by this slice; the backup
side is RM-043. The threat model's register is updated at
the Part IV gate (RM-056), per its citation rule.
