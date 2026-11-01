#!/usr/bin/env python3
"""RM-015 — Long-run soak harness.

Cycles a mixed workload over BOTH packages for a long duration
(the roadmap soak is 24 hours) and samples growth + health into
one JSON line per sample:

    muninn:  remember / activate_batch / retrieve / decay /
             consolidate cycling over a fixed corpus
    huginn:  upsert_memory / search cycling over a fixed corpus
             (local backend, tfidf embedder — no network)

The corpus is FIXED (seeded, deterministic), so a healthy run's
store files plateau: any unbounded growth in the samples is a
finding, not an artefact of the workload. Maintenance (decay +
consolidate) runs every --maintenance-every cycles. Package
errors are counted per operation and recorded, never hidden and
never retried; the harness itself keeps cycling so one bad op
cannot end the soak early. Sampling reads this process's RSS
from /proc/self/status and the store files' sizes (db + -wal +
-shm) from disk.

Samples append to the --out JSONL file, one line per sample,
flushed immediately; the first line of each process segment is
marked ``segment_start``. If the process is killed externally,
restarting it against the same --out and --workdir continues
the record (the stores reopen and heal themselves); the soak's
total span is read from the record's first and last samples.

Usage:
    python3 scripts/soak.py --duration-hours 24 \
        --workdir ~/workspace/.verify-tmp/rm015/stores \
        --out ~/workspace/.verify-tmp/rm015/samples.jsonl \
        --interval-s 60
"""

import argparse
import json
import os
import random
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

WORDS = [
    "raven", "fjord", "harbour", "lantern", "ember", "willow",
    "stone", "river", "winter", "summer", "ash", "oak", "iron",
    "silver", "copper", "meadow", "cliff", "storm", "tide",
    "shore", "pine", "birch", "wolf", "bear", "eagle", "owl",
    "fox", "hare", "deer", "salmon",
]
CATEGORIES = ("fact", "event", "person", "place", "idea")


def corpus_text(rng: random.Random, index: int) -> str:
    words = " ".join(rng.choice(WORDS) for _ in range(12))
    return f"soak memory {index}: {words}"


def rss_bytes() -> int:
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1]) * 1024
    return 0


def store_bytes(*paths: Path) -> int:
    total = 0
    for base in paths:
        for suffix in ("", "-wal", "-shm"):
            candidate = Path(str(base) + suffix)
            if candidate.is_file():
                total += candidate.stat().st_size
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration-hours", type=float, default=24.0)
    parser.add_argument("--interval-s", type=float, default=60.0)
    parser.add_argument("--cycle-pause-s", type=float, default=0.05)
    parser.add_argument("--corpus", type=int, default=500)
    parser.add_argument("--maintenance-every", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20261031)
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    from huginn import HuginnConfig, HuginnMemory
    from muninn import HebbianMemory, MuninnConfig

    workdir = Path(args.workdir).expanduser()
    workdir.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out).expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    muninn_db = workdir / "muninn_soak.db"
    huginn_db = workdir / "huginn_soak.db"

    rng = random.Random(args.seed)
    corpus = [corpus_text(rng, i) for i in range(args.corpus)]

    muninn = HebbianMemory(MuninnConfig(db_path=str(muninn_db)))
    huginn = HuginnMemory(
        HuginnConfig(backend="local", local_db_path=str(huginn_db))
    )
    print(
        f"soak: duration_hours={args.duration_hours} corpus={args.corpus} "
        f"interval_s={args.interval_s} workdir={workdir} out={out_path}",
        flush=True,
    )

    ops: dict[str, int] = {}
    errors: dict[str, int] = {}

    def counted[T](op: str, fn: Callable[[], T]) -> T | None:
        try:
            result = fn()
            ops[op] = ops.get(op, 0) + 1
            return result
        except Exception as exc:  # counted, never hidden, never retried
            key = f"{op}:{type(exc).__name__}"
            errors[key] = errors.get(key, 0) + 1
            return None

    started = time.monotonic()
    deadline = started + args.duration_hours * 3600.0
    cycle = 0
    sample_no = 0
    next_sample = started
    with out_path.open("a") as record:

        def sample(kind: str) -> None:
            nonlocal sample_no
            sample_no += 1
            line = {
                "sample": sample_no,
                "kind": kind,
                "ts": datetime.now(UTC).isoformat(),
                "elapsed_s": round(time.monotonic() - started, 1),
                "cycle": cycle,
                "rss_bytes": rss_bytes(),
                "muninn_store_bytes": store_bytes(muninn_db),
                "huginn_store_bytes": store_bytes(huginn_db),
                "ops": dict(sorted(ops.items())),
                "errors": dict(sorted(errors.items())),
                "error_total": sum(errors.values()),
                "load_avg": list(os.getloadavg()),
            }
            record.write(json.dumps(line) + "\n")
            record.flush()
            print(
                f"sample {sample_no} ({kind}): cycle={cycle} "
                f"rss={line['rss_bytes']} muninn_db={line['muninn_store_bytes']} "
                f"huginn_db={line['huginn_store_bytes']} "
                f"errors={line['error_total']}",
                flush=True,
            )

        sample("segment_start")
        next_sample = started + args.interval_s
        while time.monotonic() < deadline:
            cycle += 1
            idx = rng.randrange(args.corpus)
            text = corpus[idx]
            category = CATEGORIES[idx % len(CATEGORIES)]
            mid = counted(
                "muninn.remember",
                lambda text=text, category=category, idx=idx: muninn.remember(
                    text, category=category, importance=1 + idx % 9
                ),
            )
            counted(
                "huginn.upsert",
                lambda text=text, category=category, idx=idx: (
                    huginn.upsert_memory(
                        text, category=category, importance=1 + idx % 9
                    )
                ),
            )
            if mid is not None:
                batch = [mid] + [
                    (idx + step) % args.corpus + 1 for step in (1, 2, 3)
                ]
                counted(
                    "muninn.activate_batch",
                    lambda batch=batch: muninn.activate_batch(batch),
                )
                counted(
                    "muninn.retrieve",
                    lambda text=text: muninn.retrieve(text, top_k=5),
                )
            counted(
                "huginn.search",
                lambda text=text: huginn.search(text, limit=5),
            )
            if cycle % args.maintenance_every == 0:
                counted("muninn.decay", lambda: muninn.decay(0.1))
                counted("muninn.consolidate", lambda: muninn.consolidate())
            if time.monotonic() >= next_sample:
                sample("interval")
                next_sample = time.monotonic() + args.interval_s
            if args.cycle_pause_s:
                time.sleep(args.cycle_pause_s)
        sample("final")
    muninn.close()
    huginn.close()
    print(
        f"DONE: cycles={cycle} samples={sample_no} "
        f"errors={sum(errors.values())}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
