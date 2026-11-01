# Wall-Clock Decay (RM-021)

Muninn's decay has two modes. The default mode is **clock-free**
and always has been; the wall-clock mode is **opt-in** and runs
only when it is called by name.

## The default: `decay(days)`

`decay(days=1.0)` computes purely from its explicit argument:

- edge strengths multiply by `0.5 ** (days / decay_half_life_days)`;
- node confidences multiply by their own half-life factor;
- edges below the prune threshold are deleted.

It never reads the system clock, never reads or writes the
wall-clock marker, and its signature and report are unchanged
(RM-003 / RM-019 freezes hold). Two calls with the same `days`
always do the same thing, on any machine, at any time.

## The option: `decay_wall_clock()`

`decay_wall_clock()` derives `days` from elapsed wall-clock
time, for callers that run maintenance on a schedule and want
"fade by however long it has actually been":

- The store's `meta` table carries the marker
  `decay_last_run_at` — an ISO-8601 UTC timestamp written from
  the package's one clock helper (`muninn.core._now`, RM-012).
- **First call:** no marker exists, so the call arms the marker
  at now and decays **0 days**. Enabling the mode never
  surprises a store with a mass fade.
- **Forward jump:** decays the elapsed days (fractional) and
  advances the marker to now.
- **Backward jump** (or an unmoved clock): decays 0 days and
  the marker does **not** move backward, so a later healthy
  reading measures from the held marker and cannot re-decay
  the same span.
- **Corrupt or timezone-naive marker:** treated as no marker —
  re-armed at now, 0 days, and reported via `marker_reset` in
  the report. The mode heals its own state instead of raising.

The report is `decay()`'s report plus:

| key | meaning |
|---|---|
| `mode` | always `"wall_clock"` |
| `elapsed_days` | the derived `days` that was applied |
| `last_run_at` | the marker read at call time (`None` on the first call) |
| `run_at` | this call's clock reading |
| `first_run` | `True` when no marker existed and none was corrupt |
| `marker_reset` | `True` when a corrupt/naive marker was re-armed |
| `marker_advanced` | whether the marker moved to `run_at` |

The marker lives in the store itself, so it survives restarts
and travels with the store's backups; two processes sharing a
schedule each measure from the last run either of them made.

Classification (RM-013 matrix, row M-29): **R** — safely
re-runnable. A repeat at the same clock reading decays exactly
0 further days; a blind retry can never double-decay a span.

Huginn has no decay of its own (its half-life-free TF-IDF /
vector scores are computed at query time), so this slice is
Muninn-only.
