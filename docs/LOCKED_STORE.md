# Locked-Store Contention — RM-031

*Hostile filesystems, slice five: somebody else is using the
store right now.*

A memory store that several processes share — Bifröst in one
process, a saga engine in another, a keeper's maintenance pass
in a third — will sometimes find the SQLite write lock already
held when it opens or writes. Before this slice the wait itself
worked (SQLite honoured the configured busy timeout), but the
failure that surfaced when the timeout expired was not a
defined behaviour: an open reported the generic preparation
failure (`… store {path} could not be prepared: database is
locked` — indistinguishable from a schema failure except by
substring), a write echoed SQLite's own wording through the
RM-029 guard (`… write failed during {operation}: database is
locked`), and no test anywhere pinned any of it. Worse, the
classification had a hole: a locked failure at the open's
integrity-probe stage fell into the same bucket as an
unreadable header and was sent down the *corruption* road,
toward a backup restore over a store that was merely busy.

## The defined behaviour

Contention is a first-class, named outcome in both packages
(the local backend only for Huginn; Qdrant has no SQLite lock):

1. **The busy timeout is honoured.** An open or a write that
   meets a held write lock waits for it, up to the configured
   `busy_timeout_ms` (default 5000). If the holder releases
   inside the timeout, the operation simply succeeds — the
   wait is invisible in the result. `busy_timeout_ms=0` means
   no waiting: contention fails at once.
2. **Expiry is a typed error naming the contention**, with one
   stable message shape per surface, pinned by the RM-018
   goldens (new CASE + TEMPLATE lines in both packages):
   - Open — Muninn: `muninn store {path} is locked by another
     process (busy timeout {ms} ms expired)`
     (`MuninnStorageError`); Huginn: the `huginn …` twin
     (`HuginnStorageError`; the facade's `health()` keeps its
     never-raises contract and reports the refusal as an
     `unhealthy` dict with the same error named).
   - Write — Muninn: `muninn write failed during {operation}:
     store is locked by another process (busy timeout
     expired)`; Huginn: the `huginn …` twin. The write guard
     rolls the failed call back first (the RM-029 discipline),
     so a refused write stores nothing and the already-open
     object writes normally once the lock is released.
3. **Contention is never corruption.** Every stage of the open
   (the probe connection, the probe's integrity check, the
   main connection, the schema preparation) classifies a
   locked failure — SQLite's `database is locked` / `database
   table is locked` / `database is busy` wordings, or the
   SQLITE_BUSY / SQLITE_LOCKED result codes where the
   interpreter exposes them — and raises the contention error
   instead of entering the integrity/restore logic. A locked
   open takes no backup, restores nothing, and leaves the
   store file byte-identical.
4. **Pure reads are not contention.** The stores run in WAL
   mode, so readers proceed against a snapshot while another
   process holds the write lock: Muninn `stats` / `get_node` /
   `retrieve` (without `touch`) and Huginn `get` / `search`
   answer immediately and correctly mid-contention. (Muninn's
   one reinforcing read, `retrieve(touch=True)`, is a write
   and follows the write rule above.)

## How it is proven

Pinned by `tests/test_locked_store.py` in both packages
(muninn 5 tests, huginn 6). The lock holder is a **real second
process** — a subprocess running a raw `sqlite3` connection in
a `BEGIN EXCLUSIVE` transaction — for the open and write
acceptance tests, as the roadmap requires; the
released-within-timeout, reads, and zero-timeout cases use a
second connection or a timed holder process:

- Muninn: open under a held lock with a 1500 ms timeout raises
  the exact open-contention message after ≥1.2 s (the timeout
  honoured, no hang), never a raw `sqlite3.Error`, with the
  store's SHA-256 unchanged, no backup generation created, and
  a clean zero-recovery reopen after release; an open whose
  holder releases after 0.8 s succeeds inside an 8000 ms
  timeout; `remember` under a held lock raises the exact
  write-contention message, stores nothing, and the same
  object writes again after release; pure reads answer in
  under 5 s mid-contention; a zero busy timeout fails fast
  with the contention message naming `0 ms`.
- Huginn: the same open behaviour for the local backend; the
  facade's `health()` reporting the locked open as `unhealthy`
  with `HuginnStorageError` named while a real write raises
  it; `upsert_memory` under a held lock raising the exact
  write-contention message, storing nothing, and succeeding
  on the same object after release; `get` / `search`
  proceeding mid-contention; a zero busy timeout failing fast.

Negation: against the pre-RM-031 installed packages (RM-030
venv) the muninn suite fails 3 of 5 and the huginn suite 4 of
6 — exactly the contention-message assertions (the old open
message was `could not be prepared: database is locked`, the
old write message echoed `database is locked` through the
RM-029 shape). The two passes per package are the behaviours
that already held and are now pinned rather than changed:
release-inside-the-timeout succeeds, and WAL pure reads
proceed under a held write lock.
