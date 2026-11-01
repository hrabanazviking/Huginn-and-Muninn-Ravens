# Shutdown Cleanliness (RM-023)

Both raven stores close the same way, and the behaviour is
now pinned by tests (`tests/test_shutdown_cleanliness.py`
in both packages):

- `close()` is the store's last act under its lock: it
  marks the store closed, then closes the one SQLite
  connection. It is **idempotent** — a second `close()` is
  a no-op, never an error. Neither package runs worker
  threads (locks only), so a close leaves no lingering
  thread behind; the tests assert exactly that against a
  pre-open thread baseline.
- Because the connection is the store's only one, closing
  it lets SQLite run its final WAL checkpoint: after
  `close()` returns, the `-wal` sidecar is **absent or
  zero bytes** — no half-written tail survives for the
  next open to replay.
- A reopen after a clean close therefore performs **zero
  recovery**: `recovered_from_backup` is `False`, health
  reports `integrity == "ok"`, all data is present, and a
  raw `PRAGMA wal_checkpoint(TRUNCATE)` against the closed
  store returns `busy == 0` with **0 log pages** — nothing
  left to checkpoint.

That is the dividing line the rest of the reliability
story relies on: recovery (restore from a `.bak-N`
generation, heal passes) is for *unclean* endings — a
crash, a kill, a corrupt file. A store that was closed
properly must never trigger it, and since this slice it
cannot do so unnoticed.
