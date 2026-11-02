# Concurrent Openers — RM-037

*Robustness, slice thirteen: more than one pair of hands on
the same store.*

A memory store rarely has exactly one owner for long:
Bifröst in one process, a saga engine in another, a keeper's
maintenance pass in a third — or simply two objects in one
process, built by two parts of a program that each wanted
their own handle. Before this slice the honest documentation
said *don't*: RELIABILITY.md recorded "one writer object per
store file by design", and INTEGRATION.md warned that a
second object "will not coordinate beyond SQLite's own
locking". That warning was well founded for the open-time
duties, as the probes below show. This slice defines the
behaviour, fixes the races, and pins both.

## The defined behaviour: supported

**Two or more objects may hold the same SQLite store at
once — same process or cross-process — in both packages**
(Muninn `HebbianMemory`; Huginn's local backend, reached
through `HuginnMemory`). The rules:

1. **No shared memory.** Each object owns its connection,
   its internal lock, and its per-object state (including
   its RM-012 timestamp guard and, for Huginn, its facade's
   flight history). Nothing is cached across objects: a read
   through any object answers from the store itself.
2. **Committed means visible.** A write that commits through
   one object is visible to reads through every other object
   immediately afterwards. Sequential writes to the same
   memory through different objects behave exactly as
   through one object — the later commit is what every
   reader sees.
3. **Writes serialize in SQLite.** Ordinary reads and writes
   take no raven-level lock: WAL readers proceed against a
   snapshot, and writers queue on SQLite's write lock under
   each writer's own `busy_timeout_ms`. A writer whose wait
   expires gets the RM-031 typed contention error, rolls
   back, and stores nothing — contention is never corruption
   and never a partial write (RM-031, `docs/LOCKED_STORE.md`).
   Committed concurrent writes never lose each other: the
   tests below pin exact activation totals, exact document
   counts, and exact wiring counts across objects and across
   processes.
4. **Open-time duties serialize on the coordination lock.**
   Creation, the integrity probe, a backup restore,
   backup-on-open, the heal pass, and every rolling backup
   are *not* safe to interleave — they share the store file,
   the restore copy, and the single `.bak-tmp` snapshot path.
   They run under a per-store coordination lock
   (`store_coordination_lock` in each package's `_db.py`):
   a process-wide re-entrant lock per path, plus — on
   platforms with `fcntl` — an `flock` on the sibling
   `<db_path>.open-lock` file across processes. The kernel
   releases an `flock` when its holder dies, so a killed
   opener can never wedge the store. The lock file is zero
   bytes, is never read as data, and is left in place between
   opens (deleting it while any opener may be running would
   defeat the exclusion; it is listed in
   `docs/FORMAT_STABILITY.md`). The RM-033 shape and RM-030
   read-only pre-flights run *before* the lock is taken, so a
   refused open still creates nothing — not even the lock
   file. The coordination wait has no busy timeout: the
   holder is always another raven opener doing bounded
   open/backup work, never an arbitrary lock holder (a raw
   SQLite lock holder, RM-031's case, does not take this lock
   and still produces the busy-timeout verdict).
5. **Closing is per-object.** Closing one object closes only
   its connection; every other object keeps reading and
   writing, and a fresh object may open the same store while
   others still hold it.
6. **Two honest limits.** (a) The RM-012 monotonic-timestamp
   guard is *per object*: timestamps issued by one object
   are strictly increasing, but across objects they may
   repeat or invert by microseconds — wall-clock time is the
   only cross-object clock. (b) Coordination is a property
   of raven openers: a *foreign* process writing the file
   with raw SQLite gets rule 3 (SQLite's own locking) but
   not rule 4 — it must not race a raven's open/restore/
   backup window, the same boundary RM-031 already drew.
   On a platform without `fcntl`, rule 4's cross-process
   half degrades to the in-process lock and rule 3 alone
   carries cross-process opens.
7. **Qdrant is a different shape.** Huginn's Qdrant backend
   holds no local file: concurrent objects there are
   concurrent clients of one server, coordinated by the
   server. That road's live round-trip stays **NOT PROVEN**
   (no live server has been run); nothing in this slice
   changes that ledger line.

## What the pre-slice probes found

Probed by running the new `tests/test_concurrent_openers.py`
suites against the pre-slice (RM-036) packages — the negation
run — and then against this slice's build:

* **What already worked, now pinned.** Two objects used
  *sequentially* in one process were already exact:
  cross-visible reads, interleaved `activate` calls returning
  the exact running total (1, 2, 3, 4, …) across objects, and
  cross-process ordinary writes were already exact (Muninn
  activation totals, Huginn document counts). SQLite was
  carrying those all along; they are pinned so they cannot
  silently regress.
* **Fresh-store creation race (Muninn, real).** Six threads
  opening one *fresh* store at once: the later openers met
  the half-created file, read it as corruption ("failed
  integrity — attempting restore from backup"), and refused
  with the corrupt-and-no-backup error over a store that was
  merely being born. Huginn's identical race passed in the
  recorded negation run — the window is the same shape but
  narrower through the lazy facade, so it is timing luck,
  not a difference in kind.
* **Backup race (Muninn, real).** `backup()` called
  concurrently from two objects collided on the shared
  `.bak-tmp` snapshot: the store log shows `backup failed:
  disk I/O error` and `backup()` returned `None` — a
  silently degraded backup chain, the worst of the three
  findings because nothing raised.
* **Restore race (both, real).** Four openers racing a
  corrupt store with a verified backup restored *over each
  other* (the recovery was logged twice) while backups
  attempted inside the window failed with disk I/O errors.
  The end state happened to be sound in the recorded run;
  nothing guaranteed it.

Negation counts (disk logs `~/workspace/.verify-tmp/rm037/
muninn_negation.log`, `huginn_negation.log`): muninn
**3 failed / 5 passed**, huginn **1 failed / 7 passed** —
the failures are exactly the races above, the passes are
exactly the behaviours this slice preserves. Two test-side
corrections were made during the build, both cases of the
test being wrong and the package right: a wired pair is two
directed rows (so `total_connections` is 2, not 1), and the
first Huginn cross-process draft gave a worker the seed
document's id, so its "lost document" was an id collision
in the test itself.

## How it is proven

Pinned by `tests/test_concurrent_openers.py` in both
packages (muninn 8 tests, huginn 8 tests), all green on the
final tree and repeated green in a second run:

- two objects, same process: cross-visibility, exact
  interleaved activation totals and wiring counts (Muninn),
  exact document counts, same-id last-writer-wins and a
  cross-object delete (Huginn);
- six threads racing the creation of a fresh store: all
  open, all writes land, counts exact, reopen clean with
  `recovered_from_backup == False`;
- two *processes* (real subprocesses released by a shared
  go-file): Muninn 20 remembers + 20 activations of a shared
  node land exactly; Huginn 20 documents land exactly;
- concurrent `backup()` from two Muninn objects (5 each):
  no failure, the newest generation verifies by
  `PRAGMA quick_check`;
- four openers racing a stale store's backup-on-open: all
  succeed, one sound `.bak-1` generation stands afterwards;
- four openers racing the restore of a corrupt store: all
  succeed on the restored snapshot, at least one reports
  the recovery, the store is healthy afterwards;
- close independence: one object closes (double close a
  no-op; its own later use raises the typed closed error)
  while its sibling keeps reading and writing.

Full suites, floors, and the Bifröst re-verification for
this slice are recorded in `CAMPAIGN_STATE.md` / the slice
log. Founding tree (`~/workspace/ravens`) NEEDS A SYNC for
the coordination lock (extends the standing sync note).
