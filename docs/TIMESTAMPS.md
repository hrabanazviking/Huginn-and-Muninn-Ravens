# Timestamp Discipline — RM-012

*Part II — Stability.*

## The one-helper rule

Every timestamp written to a store comes from exactly one
helper per package, and is UTC ISO-8601 (offset-aware,
`+00:00`):

- Muninn: `muninn.core._now()` — the only stored-timestamp
  source for nodes, the activation log, the wiring, node
  activation state, and tombstones.
- Huginn local: `huginn.local_backend._now()` — the only
  stored-timestamp source for documents.
- Huginn Qdrant backend stores **no** timestamps at all.
- The remaining `datetime.now(UTC)` calls in the packages are
  in-memory only and never stored: `MemoryNode` field defaults
  / `from_dict` fallback (Muninn) and `RetrievalResult.timestamp`
  (Huginn) — a flight's own diary, not store data.

## The monotonicity guard

Raw wall clocks go backwards (NTP steps, manual changes, VM
snapshots). Each store object therefore issues timestamps
through a guard — `HebbianMemory._tick()` /
`LocalBackend._tick()`:

- The candidate is the helper's reading.
- If the candidate is at or before the last timestamp this
  store has issued, the issued value is *last + 1 microsecond*
  instead.
- On open, the guard is **seeded from the store's own stored
  maximum** (Muninn: across the activation log, nodes, wiring,
  node-activation and tombstones; Huginn: document
  `updated_at`), so a store reopened after a clock rollback
  still issues strictly after its own history.

Consequences, both proven by clock-skew tests
(`tests/test_timestamps.py` in both packages, which patch the
helper with a backwards-running clock):

- Muninn's `activation_log` is strictly increasing in row
  order, always — log order and time order can never disagree.
- A Huginn document's `updated_at` never precedes its
  `created_at`.
- With a healthy clock the guard is invisible: issued values
  are exactly the clock's readings.

Ordering reads that sort by timestamp (RM-011) therefore sort
by a timestamp that cannot lie about sequence.
