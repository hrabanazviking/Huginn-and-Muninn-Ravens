# Integrity Attestation — RM-050

*Security, slice twelve: the audit trail learns to testify.*

Threat **TH-10** in `docs/THREAT_MODEL.md`: an attacker with
file write access edits rows by raw SQL — rewrites a log
entry, plants a memory, weakens a wiring — and nothing
detects it. `PRAGMA quick_check` proves SQLite's structure,
not the caller's truth, and the heal pass repairs drift
shapes, not intent.

The roadmap names the slice's shape: **an optional
HMAC/checksum chain over `activation_log`, so tampering with
the log file outside the API is detectable on open**, with
the acceptance *tamper test — modify one row by raw SQL,
open, detection reported*. The activation log is Muninn's
audit trail (asset AS-03: what was activated, when, with
what valence and source), so this slice is **Muninn-only** —
Huginn has no `activation_log`; its copy of the slice work
is the slice-log pin, as with RM-046 in reverse.

## The design

**Opt-in, off by default.** Two additive config fields,
following the RM-041/RM-044 plain-flag pattern and the
RM-049 passphrase pattern:

- `integrity_attestation: bool = False`
- `integrity_passphrase: str | None` (`repr=False`; required
  when the flag is on — its absence is a typed
  `MuninnConfigurationError` at construction)

**Stdlib only.** The chain is HMAC-SHA256; the key is
derived from the passphrase with PBKDF2-HMAC-SHA256
(600,000 iterations, per-store random 16-byte salt). No new
dependency, no extra — the stdlib has everything a MAC
needs (unlike RM-049's cipher, which is why encryption
needed the one bounded extra and attestation does not).

**The key is never stored.** The store carries only, as
`meta` rows: `attestation_version`, `attestation_salt`,
`attestation_iterations`, `attestation_head`,
`attestation_count`. There is no schema change — the
contracted `activation_log` table, the RM-004 schema
goldens and the shared-schema law are all unmoved (the
RM-049 precedent: headers live in `meta`).

**The chain.** Over rows in `id` order (the log's append
order):

```
head₀   = HMAC(key, "muninn activation attestation genesis v1" ‖ salt)
headₙ₊₁ = HMAC(key, headₙ ‖ memory_id ‖ activated_at ‖
                    repr(emotional_valence) ‖ source)   (␟-joined)
```

Every road that appends a log row extends the chain in the
same transaction as the row itself — `activate`,
`activate_batch` on both its per-pair loop road and the
RM-035 bulk road, and `retrieve(touch=True)` (the one
reinforcing read) all pass through `_log_activation_locked`
or the bulk activation insert, and both chain there. A row
and its chain link land or roll back together; before each
advance the stored head is re-read, so a transaction the
RM-029 write guard rolled back never leaves the in-memory
chain ahead of the store.

**Verification on open.** An attested open recomputes the
chain over the rows as they stand and compares head and
count. The verdict is *reported*, per the roadmap's word:
the store opens and serves; the result rides on
`HebbianMemory.integrity_attestation_status` and in
`health()`'s additive `integrity_attestation` field —
`"ok"`, `"tamper_detected"`, or `"not_enabled"` when the
flag is off — and a failure is logged at ERROR. Detection
is never silently repaired and the tampered rows are left
exactly as found: they are evidence, and what to do about
them is the caller's decision.

**A marked store refuses an unattested open.** Opening a
store that carries the attestation header without the flag
raises a typed `MuninnStorageError` before anything is
written (the RM-049 precedent, for the same reason: an
unattested open must never silently serve a store whose
owner asked for attestation). When the pre-open probe
cannot read the file, the judgement defers to the live
connection after the restore road — a store restored from
an attested backup is judged by the backup's own header.

**Enabling on an existing store bootstraps as found.** The
first attested open chains the rows already there, in id
order, and writes the header. Attestation therefore covers
the log from enablement forward; tampering from before
enablement is out of scope by definition, stated here so
nobody has to guess it.

## Honest limits

- **A wrong passphrase is indistinguishable from
  tampering.** The key is never stored, so there is
  nothing to check a passphrase against except the chain
  itself: a wrong key recomputes to a different head and
  is reported as `tamper_detected`. That is the honest
  shape of a keyless chain, and the record says so rather
  than dressing a wrong-key open as a distinct verdict the
  design cannot actually deliver.
- **The chain covers `activation_log` only** — the slice
  the roadmap names. It is not a whole-store integrity
  proof: `nodes` and `hebbian_connections` tampering is
  not detected by this chain (the heal pass and the
  RM-047 double check cover parts of that ground; a
  whole-store chain is a different, larger slice and is
  not claimed here).
- **Detection, not prevention, and not attribution.** A
  tamperer who also holds the passphrase can recompute a
  valid chain; a tamperer with the file alone cannot. The
  chain says *the log is not what Muninn wrote* — never
  who changed it, and it does not stop the change.
- **Backups are self-consistent snapshots.** A rolling
  backup copies the log and its header together through
  the SQLite backup API, so a restored backup verifies
  against its own header (test-pinned).
- **Cross-process concurrent writers** on one attested
  store can interleave chain advances in ways that report
  `tamper_detected` at the next open — the failure
  direction is a false alarm, never a silent pass, but
  attested stores are a single-writer-process discipline
  in practice. In-process use is fully serialized by the
  store lock, as all Muninn writes are.
- TH-10's register line stays Open until RM-056's Part IV
  gate updates the register with what the part actually
  built, as with TH-09 before it.
