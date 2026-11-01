# RM-015 — Long-Run Soak Report

**Slice:** RM-015 — Long-run soak (Part II — Stability)
**Class:** BENCH
**Harness:** `scripts/soak.py` (committed with this slice)
**Record:** 1,043 samples, durable copy held with the campaign
records (`rm015_soak_samples.jsonl`); working record at
`~/workspace/.verify-tmp/rm015/samples.jsonl`

## What ran

A mixed workload cycling over both packages for a record span
of **24 h 06 m 22 s** — first sample `2026-10-31T10:47:56Z`,
last sample `2026-11-01T10:54:18Z`:

- **Muninn:** remember / activate_batch / retrieve, with decay
  + consolidate maintenance cycling over a fixed 500-text
  corpus.
- **Huginn:** upsert_memory / search over the same fixed
  corpus (local backend, tfidf embedder — no network).

Totals read from the record itself (summed
last-cycle-per-segment, the campaign's standing method):

| Measure | Value |
|---|---|
| Segments started | 39 |
| Samples | 1,043 |
| Cycles (summed) | 174,523 |
| Errors (summed) | **70** |
| Final muninn store | 49,357,960 B |
| Final huginn store | 4,935,808 B |
| Final RSS | 22,183,936 B |

## Errors — disclosed, not hidden

The 70 errors are all one kind: `muninn.decay:OperationalError`,
accumulated in five earlier segments (7 + 41 + 3 + 9 + 10).
Each cluster is paired in the soak log with
`muninn: backup failed: disk I/O error` lines from the same
period — the VM's extreme-load / write-gate episodes documented
throughout the campaign record. Cause not proven (environment
class; never reproduced on a quiet machine). No other operation
ever errored: remember, activate_batch, retrieve, consolidate,
upsert and search all ran error-free for the full span, and the
final segment ran 1,862 cycles with 0 errors. RM-015's
acceptance reports error counts; it does not require zero.

## Growth curves — the acceptance evidence

Hourly maxima from the record (store figures are the record's
db + wal + shm byte fields):

| Hour | Muninn max (MB) | Huginn max (MB) | RSS max (MB) |
|---|---|---|---|
| 0 | 7.26 | 4.92 | 39.33 |
| 1 | 9.98 | 4.92 | 35.11 |
| 2 | 11.57 | 4.93 | 34.37 |
| 3 | 11.80 | 4.92 | 28.63 |
| 4 | 14.27 | 4.94 | 29.42 |
| 5 | 18.31 | 4.94 | 25.16 |
| 6 | 20.64 | 4.94 | 29.44 |
| 7 | 23.58 | 4.96 | 28.84 |
| 8 | 24.76 | 4.96 | 29.17 |
| 9 | 27.17 | 4.94 | 28.62 |
| 10 | 28.44 | 4.94 | 29.18 |
| 11 | 30.69 | 4.94 | 25.35 |
| 12 | 32.74 | 4.94 | 22.97 |
| 13 | 33.97 | 4.95 | 29.25 |
| 14 | 35.94 | 4.94 | 29.47 |
| 15 | 37.96 | 4.94 | 29.27 |
| 16 | 39.89 | 4.94 | 22.75 |
| 17 | 40.26 | 4.94 | 29.61 |
| 18 | 43.05 | 4.93 | 25.65 |
| 19 | 44.70 | 4.93 | 22.13 |
| 20 | 46.60 | 4.94 | 21.86 |
| 21 | 47.19 | 4.94 | 29.46 |
| 22 | 48.85 | 4.94 | 26.09 |
| 23 | 49.27 | 4.94 | 29.30 |
| 24 | 49.36 | 4.94 | 22.18 |

Reading the curves honestly:

- **RSS is bounded.** The all-time maximum (39.33 MB) occurs in
  hour 0; every later hour's maximum is ≤ 35.11 MB and the
  final sample sits at 22.18 MB. No memory growth trend.
- **Huginn's store is flat.** 4.92 MB in hour 0, 4.94 MB at the
  end, never outside 4.84–4.96 MB after hour 1 — the fixed
  corpus upserts replace in place, exactly as designed.
- **Muninn's store grows linearly in work done, at a constant
  rate.** Per-1,000-cycle file cost by window: 428 KiB
  (hours 0–4, includes the initial corpus fill), then 254,
  244, 246, 249 and 239 KiB per 1,000 cycles for hours 4–8,
  8–12, 12–16, 16–20 and 20–24. The rate is flat from hour 4
  on — growth proportional to operations performed (each cycle
  remembers a new node and appends activation-log rows), not
  an accelerating leak. A store that must plateau under a
  remember-heavy workload would need a retention policy; that
  is a design question for a later slice, not a soak finding
  of unbounded growth.

## Interruptions

The soak process was torn down externally 38 times (VM
reboots and the same silent-teardown pattern recorded during
RM-014; causes not proven except two VM reboots, which are
proven by uptime). Each time the keeper resumed it against the
same `--workdir` and `--out`; every segment_start sample shows
both stores reopening with their existing data — the stores
healed/reopened cleanly 38 times, which is itself evidence for
the self-healing line of this roadmap. One resume was held for
one tick when the machine's write gate was proven closed by a
sustained probe (0/60 writes landing); it resumed on the next
tick's fully green probe (60/60). No second soak ever ran on
this tree. Each check was recorded in `CAMPAIGN_STATE.md` as it
happened; the banking summary is in `docs/SLICE_LOG.md`.

## Verdict

Acceptance met: the 24-hour mixed-workload soak completed
(record span 24 h 06 m), reporting memory growth (bounded),
file growth (huginn flat; muninn linear at a constant
~245 KiB / 1,000 cycles) and error counts (70, one kind,
environment-paired, disclosed above).
