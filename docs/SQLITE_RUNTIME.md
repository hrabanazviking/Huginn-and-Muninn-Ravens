# SQLite Runtime — Version Pinning (RM-016)

Both raven stores are SQLite files in WAL journal mode, so
the SQLite library version is part of each store's runtime
contract: WAL behaviour, healing and backup all ride on it.

## What is recorded

Since RM-016, `health()` carries **`sqlite_version`** — the
value of `sqlite3.sqlite_version`, i.e. the version of the
SQLite library the running process actually loaded:

- **Muninn:** `HebbianMemory.health()` (and the `Muninn`
  facade, which inherits it).
- **Huginn:** the local backend's `health()`, passed through
  by the `HuginnMemory` facade.

The value is read from the runtime, never hard-coded, and
`health()` stays a pure read (RM-013 row: reads never move
the store).

## Minimum WAL-safe version

**3.7.0.** The WAL (write-ahead logging) journal mode both
stores open with was introduced in SQLite 3.7.0 (2010-07-21);
no earlier runtime can open these stores in their configured
mode at all. Any runtime at or above 3.7.0 satisfies the
floor. The ravens do not pin an exact version — deployments
report their runtime through `health()` instead, so a
behaviour difference can always be traced to the library
that produced it.

Runtime measured at this slice's banking (this VM):
**SQLite 3.45.1**, Python 3.12.3 — the same runtime recorded
since RM-001.

## Where the key is absent, honestly

- **Huginn's Qdrant backend** runs no SQLite; its `health()`
  carries no `sqlite_version` (its runtime is the Qdrant
  server). A live Qdrant round-trip remains NOT PROVEN.
- **Huginn's facade early-return** for a failing explicitly
  configured backend reports the error only; no store was
  opened, so no runtime version is claimed.
