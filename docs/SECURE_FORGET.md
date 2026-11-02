# Secure Forget — RM-051

*Security, slice thirteen: forgetting that actually forgets.*

Threat **TH-11** in `docs/THREAT_MODEL.md`: `forget` /
`delete` remove the live rows (and Muninn tombstones the
id), but the forgotten content can persist in the store's
other copies. Before this slice that truth was documented
only in the threat model; the guides said nothing, and no
operation existed that could make a forgotten memory leave
the disk. This slice documents the truth in both guides
and adds the operation: **`secure_forget(memory_id)`** in
both packages.

## The audit: where a plainly forgotten memory survives

Proven by the forensic tests in
`tests/test_secure_forget.py` (both packages), which search
the store's files byte-for-byte for a unique string:

| Copy | Plain `forget` / `delete` | Why it survives |
|---|---|---|
| Live rows (`nodes` / `documents`, wiring, term index, vectors) | **removed** | — |
| WAL (`<store>-wal`) | **survives** until checkpoint | The delete is itself a WAL write; the frames holding the pre-delete page images stay in the log until a checkpoint folds and truncates it. |
| Main store file | **survives** in freed pages | Deleting a row frees its page; SQLite reuses freed pages eventually, but until then the bytes are still on disk. Whether a checkpoint zeroes them depends on the SQLite build's `secure_delete` default — a build property, not a promise this library may lean on. |
| Rolling backups (`.bak-N`, `.bak-tmp`) | **survives** in every generation | Each generation is a full copy of the store as it was. Rotation alone retires a generation only after `backup_keep` *further* backups, and the pre-forget generations sit readable the whole time. |
| Muninn `activation_log` | kept **by design** | It is a log: it carries the forgotten id, timestamps, valence and source — never content. `secure_forget` keeps it exactly as `forget` does. The tombstone in `deleted_nodes` likewise carries only the id and the deletion time. |
| Huginn Qdrant backend | the point is deleted server-side | There is no local file. What the server's own snapshots, WAL and backups retain is the Qdrant operator's domain — see the limits below. |

One more honest scoping: `secure_forget` purges **the
forgotten memory's own copies**. If the same string also
lives inside a *different* memory (the caller stored it
twice), that memory is untouched — forgetting it is its
own call.

## The defined behaviour

`secure_forget(memory_id) -> bool` — the same validation,
the same row work and the same return value as
`forget` / `delete` (`True` when anything live was
removed), plus the purge:

1. **Secure delete.** The row deletion runs under
   `PRAGMA secure_delete=ON`, so the page images SQLite
   writes carry zeros where the content stood, on every
   build — not only builds whose default is on. The
   pragma is per-connection: `secure_delete_enabled` in
   each package's `_db.py` reads the value it found
   (`OFF` / `ON` / `FAST`) and restores it on exit, so
   the call never silently changes the connection's
   posture for later writes.
2. **Checkpoint.** `PRAGMA wal_checkpoint(TRUNCATE)`
   folds the WAL into the main file and empties it — no
   frame keeps the pre-delete page images.
3. **Rewrite.** `VACUUM` rebuilds the main file from the
   live rows only; freed pages are not copied to the new
   file, whatever the build's `secure_delete` default.
4. **Checkpoint again.** The `VACUUM` itself wrote
   through the WAL; it is truncated too.
5. **Backups replaced.** Under the per-store
   coordination lock (RM-037 — the generations are
   shared with every other opener), every `.bak-*`
   file — all generations plus a stale `.bak-tmp` — is
   discarded, and when `backup_keep` allows one, a
   single fresh snapshot of the purged store is taken
   as the new `.bak-1`.

The purge runs **even when nothing live was removed**:
`secure_forget` of an id an earlier plain `forget`
already deleted returns `False` and still purges, so a
caller can remediate a past forget. With
`backup_keep=0` no fresh snapshot is taken and no
generation is left.

For Huginn's Qdrant backend, `secure_forget` is the
server-side `delete`: the point is removed through the
client, and that is the whole operation this backend can
perform.

## The cost, stated

* **A full store rewrite.** `VACUUM` rebuilds the whole
  file: time on the order of the store's size, temporary
  disk space of the same order while the new file is
  built, and an exclusive lock for the duration — other
  writers wait (or, past the busy timeout, fail typed).
  This is deliberately not the default delete: it is the
  operation a caller reaches for when a memory must
  actually be gone.
* **The backup history is destroyed.** All older
  generations are replaced by the single fresh snapshot.
  Rolling back to a state from before the purge is
  impossible afterwards — that is the point of the
  operation, and it is why the generations are replaced
  rather than merely rotated.
* **Not atomic across its stages.** The row deletion
  commits first (the memory is gone from the API from
  that moment); the file purge follows. If another
  opener holds the store, a checkpoint can report busy
  (frames stay until the reader lets go) and the
  `VACUUM` can fail with a typed locked-store error —
  close other openers first, and re-run `secure_forget`
  to re-run the purge. The slice does not pretend a
  multi-file purge is a transaction.

Out of scope, honestly: copies outside the store's own
file family — a caller's own exports, an OS-level
snapshot or backup of the whole directory, a second
store the caller copied the memory into, and (for
Qdrant) the server's own storage. `secure_forget`
governs the files the library itself makes.

## How it is proven

Pinned by `tests/test_secure_forget.py` in both packages
(muninn 10 tests, huginn 8):

- **Before:** after plain `forget` / `delete`, the
  forgotten string is still byte-findable in the
  `.bak-1` generation (both packages).
- **After:** after `secure_forget`, no file in the
  store's family (main, `-wal`, `-shm`, every `.bak-*`)
  holds the string — while the store is still open,
  after close, and after reopen — covering both the
  WAL-resident case and the already-checkpointed case
  (secret proven present in the main file before the
  call). Every other memory survives, live and inside
  the fresh `.bak-1`.
- All three backup generations present before the call
  are replaced by exactly one fresh generation
  (Muninn); `backup_keep=0` leaves none (both).
- A missing id returns `False` and the purge still runs
  (both); id validation is the typed error, as in
  `forget` / `delete` (both); Muninn's tombstone and
  wiring semantics are `forget`'s (a later re-remember
  of the same content is a fresh node).
- An encrypted store (RM-049) composes: the plaintext
  never reaches disk at all, and `secure_forget` still
  removes and purges (both, with the `encryption` extra).
- Huginn's Qdrant delegation is pinned against a stub
  client: `secure_forget` deletes the point through the
  client and reports `True` / `False` exactly as
  `delete` does. A live Qdrant round-trip stays
  **NOT PROVEN**.

Negation against the RM-050 packages: the new suites
fail there — `secure_forget` does not exist (tallies in
the slice log).

The slice adds one public method per facade
(`HebbianMemory.secure_forget` / `Muninn.secure_forget`,
`HuginnMemory.secure_forget`), so the RM-019 API-surface
goldens gained those lines and the **Bifröst contract
re-verification was run before banking** (fresh venv,
bifrost at b66e98cc; result in the slice log). No schema
changed (RM-004 goldens unmoved). The RM-040 SQL audit
gained eight constant sites per package — the purge
machinery's `secure_delete` pragma read / set / restore
and its `wal_checkpoint(TRUNCATE)` / `VACUUM` stages,
no values at all — and both audit pins were updated
(Muninn 89 → 97, Huginn 45 → 53). No new dependency:
the whole slice is stdlib + SQLite pragmas.

TH-11 is closed for the local stores by this slice —
documented truth plus an operation that makes the
files forget — with the Qdrant server-side residue
named as the operator's domain. The threat model's
register is updated at the Part IV gate (RM-056), per
its citation rule.
