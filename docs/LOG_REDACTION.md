# Log Redaction — RM-044

*Security, slice six: what the loggers may say.*

Threat **TH-05** in `docs/THREAT_MODEL.md`: a log call or a
diagnostic emits memory content where hosts ship logs onward
— the store's most sensitive data leaving through a side
channel (AS-01 via AS-08, across TB-4). The RM-039 review of
every logger call site found paths, counts, heal-count
reports, the Qdrant URL and exception strings — no content
argument anywhere — but that was *inspection only*: nothing
scanned for a regression, and no sanctioned road existed by
which a developer debugging locally could ever see content
in a log deliberately. This slice pins the inspected
behaviour in tests and adds that one road, gated and
level-bound.

## The defined behaviour

**No package log record carries memory content by default.**
Six loggers exist (`muninn`, `muninn.store`, `huginn`,
`huginn.store`, `huginn.local`, `huginn.qdrant`); their emit
sites carry only paths, counts, heal-count reports, the
Qdrant URL and exception strings. That stays true at every
level, DEBUG included, unless the flag below is on.

**`debug_log_content` is a config flag on both packages,
off by default:**

- `MuninnConfig(..., debug_log_content=True)`
- `HuginnConfig(..., debug_log_content=True)`

With the flag **on**, exactly two paths per package may emit
content, and only at **DEBUG** level:

- Muninn: `remember` (the stored text, with its new id) and
  `retrieve` (the query and the returned nodes' contents).
- Huginn: `upsert_memory` (the stored content, with its id)
  and `search` (the query and the returned results'
  contents) — in the facade, so the rule binds whichever
  backend serves the call.

Content never appears at INFO or above, flag or no flag.
Every other path — above all the heal paths, whose reports
are counts by design — carries no content at any level even
with the flag on. The flag is a plain boolean, used as
given, like `auto_backup` / `strict_path_safety`.

Two honest scopings:

- **Exception strings are not content this slice controls.**
  A wrapped exception's text (a SQLite or Qdrant client
  error) can in principle quote caller data; scrubbing
  typed-error *messages* is RM-054's road (TH-14), and the
  Qdrant key/transport side is RM-045's (TH-06). This slice
  governs what the packages' own log calls emit.
- **The flag is per-object configuration**, frozen at
  construction (RM-017): a host enables it for one store
  object deliberately, never globally or by environment
  accident within these packages.

## How it is proven

Pinned by `tests/test_log_redaction.py` in both packages
(7 tests each, local backend for Huginn):

- Default off: the config default is `False`, pinned
  directly.
- Flag off, capture at DEBUG over the package logger tree:
  the store path (`remember` / `upsert_memory`), the
  search path (`retrieve` / `search`) and the heal path
  (planted drift repaired by `heal_structure` / the local
  backend's `heal`, whose counts-only warning really is
  emitted) each produce no record containing the secret
  content, at any level.
- Flag on: the store and search paths each emit the content
  in a DEBUG record, and every record carrying it is DEBUG
  — none at INFO or above.
- Flag on, heal path: the heal warning still carries counts
  only; no record contains the content.

Negation: the same files against the pre-RM-044 installed
packages (RM-043 venv) fail 4 / pass 3 per package — the
failures are the flag itself (unknown config field) and
every flag-on behaviour; the three passes are the
default-off behaviours this slice preserves.

The RM-019 API-surface goldens gained the new config field
in both packages. The public config surface changed
additively, so the **Bifröst contract re-verification was
run before banking** (fresh venv, bifrost at b66e98cc —
its own suites and the BifrostBridge smoke; result in
`docs/SLICE_LOG.md` and `CAMPAIGN_STATE.md`; a live Qdrant
round-trip is still NOT PROVEN).

TH-05 is closed by this slice: the no-content default is
now test-pinned rather than inspection-only, and the single
road to content in logs is explicit, off by default, and
DEBUG-bound. The threat model's register is updated at the
Part IV gate (RM-056), per its citation rule.
