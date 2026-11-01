# Disk-Full Behaviour — RM-029

*Hostile filesystems, slice three: the disk fills up mid-write.*

Before this slice, a write that hit a full filesystem escaped as
a raw `sqlite3.OperationalError` (`database or disk is full`) —
an untyped exception from the storage layer leaking through the
public API, contradicting both packages' founding promise that
every deliberate failure is one of their typed errors. Worse, a
failure part-way through a multi-statement write (an upsert that
had already de-indexed the old document, a batch activation that
had already logged some rows) left its half-applied statements
sitting in the open transaction, where the *next* successful
call's commit would silently persist them.

## The defined behaviour

Every public write in both packages now runs behind a write
guard (`_storage_write` in `muninn/core.py`, covering
`remember` / `store`, `update` / `move`, `forget` / `delete`,
`activate`, `activate_batch`, `associate`, `retrieve(touch=True)`,
`heal_structure`, `decay`, `decay_wall_clock`, `consolidate`,
`backup`; and in `huginn/local_backend.py`, covering the local
backend's `upsert`, `delete` and `heal` — the Qdrant backend
already translates its failures into `HuginnBackendError`).

When the storage layer raises during a guarded write, the guard:

1. **rolls the transaction back** — the failed call leaves no
   partial write behind, and nothing from it can leak into a
   later commit;
2. **raises the package's typed storage error** —
   `MuninnStorageError` / `HuginnStorageError` — with the shape
   `… write failed during {operation}: {sqlite's message}`, so a
   disk-full reads e.g. `muninn write failed during remember:
   database or disk is full`. The message shape is pinned by the
   RM-018 goldens (new CASE + TEMPLATE lines in both packages).

The store itself is untouched by the failure beyond the rolled-
back call: it stays open in the same session, reads and (once
space returns) writes keep working, and close/reopen finds the
store consistent with all previously committed data intact.

## How it is proven

Fault injection uses the real engine, not a mock:
`PRAGMA max_page_count` is clamped to the store's current page
count through the store's own connection, so the next write
that needs a new page receives SQLite's own SQLITE_FULL — the
identical error a full filesystem produces. (A genuinely full
device is environment-dependent and destructive to arrange in a
test suite; the engine-level error is the same code path, and
the injection is stated here rather than dressed up as a real
full disk.)

Pinned by `tests/test_disk_full.py` in both packages:

- Muninn: `remember` and `update` against a capped store raise
  `MuninnStorageError` (never a raw `sqlite3.Error`), counts and
  original content unchanged, writes succeed again after the
  cap is lifted, and a close/reopen finds integrity `ok` with
  the failed write absent; a 300-node `activate_batch` that
  fails part-way leaves zero activations and zero edges, even
  after a later successful commit.
- Huginn: `upsert_memory` against a capped store raises
  `HuginnStorageError` with the same invariants; replacing a
  document by explicit id — the path that de-indexes the old
  document *before* writing the new content — rolls back
  completely, so the original document keeps both its content
  and its search index after a later successful commit.

Negation: all five tests fail against the pre-RM-029 installed
packages (RM-028 venv).
