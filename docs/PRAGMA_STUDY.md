# Connection Pragmas Study — RM-066

Roadmap RM-066: *`cache_size`, `mmap_size`, `temp_store`
measured per package; defaults changed only on
evidence, recorded per pragma.* This record is the
measurement, the per-pragma verdicts, and the
reasoning. Gate scripts:
`muninn/scripts/pragma_study.py` and
`huginn/scripts/pragma_study.py`.

**Name discipline first:** this slice's `cache_size`
is SQLite's `PRAGMA cache_size` — the page cache of
the store's SQLite connection. It is *not* RM-063's
`cache_size` config field (the per-object `get_node` /
`get` warm cache). The two share a name and nothing
else; RM-063's field is untouched by this slice.

## What was measured

Neither package ever set the three studied pragmas:
each `_db.py` `_connect` set exactly `busy_timeout`,
`journal_mode=WAL`, `synchronous=FULL` and
`foreign_keys=ON`, so SQLite's compiled defaults
applied. Read back from freshly opened stores, the
defaults as found were, in both packages:
`cache_size = -2000` (2 MiB), `mmap_size = 0` (off),
`temp_store = 0` (compiled default).

The gates apply each variant to the live connection
the package opened (pragmas are per-connection, so a
study must set them on the connection the package
owns — the gates' one stated reach inside), read the
values back before quoting any timing, and fail the
run if a readback is not what was set. Variants:
`baseline` (as opened), `cache16` (`cache_size=
-16384`), `cache64` (`cache_size=-65536`), `mmap`
(`mmap_size=268435456`), `temp` (`temp_store=MEMORY`),
`all` (cache64 + mmap + temp). Every measurement is a
fresh byte copy of the seed + a fresh open + two
timed passes per workload — pass 1 with the SQLite
page cache cold, pass 2 warm on the same connection
(the OS/tmpfs cache cannot be dropped from userland;
stated, as in every BENCH record). Median of three
measurements. Every pass accumulates a fingerprint of
everything it read, and **every fingerprint in every
run was identical across all variants** — a pragma
may change speed, never results, and the gates assert
it rather than assume it.

Stores: Muninn — the RM-058 uniform store (5,000
nodes, 100,000 directed edges, 19,972,096 bytes),
workloads `read_pass` (200 `get_node`, 50 depth-2
`spread_activation`, 5 `stats()`, 100
`get_associations`, ×4) and `aggregate_pass` (40
`stats()` + 80 depth-2 spreads). Huginn — 5,000
distinct documents (RM-061 corpus formula, 16,769,024
bytes, local backend; Qdrant has no local connection
and is out of scope), workloads `search_pass` (the
three RM-061 distinct queries, 2 rounds, limit 10)
and `get_pass` (500 `get` calls — at ~6 ms a pass it
sits at the noise floor, and no verdict below rests
on it).

Two full evidence runs per package were made against
the pre-change tree (Muninn at 1-minute loads 1.66
and 1.77; Huginn at 6.41 and 5.87 — Huginn's runs are
the noisier pair and are read accordingly). After the
one adopted change, both gates were re-run on the
final tree; those records are the committed ones
(`muninn/scripts/pragma_study.json`, recorded
2026-11-03T00:43:33Z; `huginn/scripts/pragma_study.json`,
2026-11-03T00:43:59Z).

## The evidence (medians vs baseline, cold / warm)

Muninn, run 1 — baseline `read_pass` 823.4 / 902.9 ms,
`aggregate_pass` 1410.0 / 1535.0 ms:

| variant | read_pass | aggregate_pass |
|---|---|---|
| cache16 | −3.7% / +19.6% | +4.5% / −25.8% |
| cache64 | −12.1% / −24.0% | −27.8% / −35.6% |
| mmap | −15.7% / −18.9% | −31.1% / −27.7% |
| temp | +17.5% / −1.9% | +6.3% / −13.3% |

Muninn, run 2 — baseline `read_pass` 878.9 / 787.3 ms,
`aggregate_pass` 1293.3 / 1321.0 ms:

| variant | read_pass | aggregate_pass |
|---|---|---|
| cache16 | +0.9% / −5.3% | −28.5% / −24.5% |
| cache64 | −18.8% / −1.0% | −24.7% / −23.2% |
| mmap | −8.6% / −13.3% | −22.6% / −25.9% |
| temp | +6.5% / +26.3% | +6.6% / +2.5% |

Huginn `search_pass`, run 1 — baseline 1492.0 /
1394.8 ms; run 2 — baseline 922.7 / 1162.8 ms (the
baseline itself swung ~40% between runs under load;
only directions that survive both runs are read as
signal):

| variant | run 1 | run 2 |
|---|---|---|
| cache16 | −4.6% / −13.1% | +9.1% / −7.3% |
| cache64 | −7.1% / +1.2% | −1.4% / −21.3% |
| mmap | −30.5% / −21.6% | −0.2% / −19.0% |
| temp | −34.0% / −32.1% | +31.5% / −14.3% |

## Verdict per pragma

### `cache_size` — ADOPTED: `-16384` (16 MiB) in both packages

The one strong, replicable signal in the study is
Muninn's aggregate road: at the default 2 MiB page
cache, `stats()` + spread over a 100k-edge store
thrashes — cache16 read −28.5% / −24.5% in run 2 and
−25.8% warm in run 1 (one +4.5% cold reading against
three at −24..−29%); cache64 read the same road at
−23..−36% in all four readings, and the read road at
up to −24%. cache16 captures the aggregate win —
in run 2 it matches or beats cache64 there — so the
adopted size is 16 MiB, not 64: the smaller memory
commitment, and these libraries run on Pi-class
hosts. `cache_size` is a ceiling, not an allocation:
the cache grows only to hold pages actually touched,
so a small store never pays for the headroom.
Huginn's own search evidence is weaker (its working
set is smaller and its runs noisier: cache16 warm
−13.1% / −7.3%, cold mixed) — weakly positive, no
harm anywhere — and the twin `_db.py` files are kept
in lockstep, as every `_db` change before this one
has been. The default is set in `_connect` in each
package's `_db.py`, so it applies to the store
connection every package road runs on; the short-lived
read-only probe connections in `_crypto` / `_attest`
and the backup machinery keep the compiled default,
stated here. RM-040 audit site totals move +1 per
package (Muninn 103 → 104, Huginn 59 → 60) for the
one new constant statement.

The final-tree confirmation runs read the new
default back as found (`cache_size = -16384` in both
packages) with fingerprints still identical
everywhere. Their cross-variant deltas are *not*
quoted as evidence: the 1-minute load fell across
each run (≈4.3 → 3.4), and the baseline-identical
`cache16` variant — which by construction must read
~0% against the new baseline — read −18..−40% on
Muninn's warm passes, the built-in signature of load
drift. The gates keep that tripwire by design.

### `mmap_size` — measured faster, NOT adopted

mmap is the most consistent performer after the page
cache (Muninn −9..−31% across both runs and both
workloads; Huginn search warm −21.6% / −19.0%), and
it is still not adopted. Reason, recorded plainly:
memory-mapping the store file converts the fault
family Parts II–III taught these libraries to refuse
politely — a truncated, partially-copied or otherwise
short store file (RM-030 / RM-032 / RM-033 territory)
— from a typed storage error into a `SIGBUS` that
kills the *host process* outright. A library whose
charter is crash-proof, embeddable behaviour does not
take a default that trades its typed refusals for
process death in exchange for a fifth to a quarter of
read speed. This is the study's named open option:
it may be revisited when Part VIII's fault-injection
evidence can speak to mmap fault containment, or as
an explicit opt-in a deployment chooses for itself —
never as the silent default. `mmap_size` stays 0.

### `temp_store` — no effect found; compiled default stands

No replicable effect in either package: Muninn's
readings scatter from +26.3% to −13.3% across runs,
and Huginn's two runs contradict each other outright
(−34.0% / −32.1% in run 1, +31.5% / −14.3% in run 2).
The packages' hot roads simply do not spill enough
temporary b-tree work to files for the setting to
bite at this scale. No change: `temp_store` stays at
the compiled default (0).

## What did not change

No public API, no config field, no schema, no SQL
shape beyond the one added constant `PRAGMA`
statement per package. `synchronous=FULL`,
`journal_mode=WAL`, `foreign_keys=ON` and
`busy_timeout` are untouched — this slice studied
performance pragmas only, and no durability setting
was ever a candidate. Live Qdrant and
sentence-transformers stay NOT PROVEN.
