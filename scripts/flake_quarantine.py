#!/usr/bin/env python3
"""RM-014 — Flake quarantine harness.

Runs BOTH package suites N times back to back ("pairs") under
load and records every run as one JSON line. A pair is green
only when both suites exit 0. The harness NEVER retries a run:
the first non-green pair stops the sweep, its full suite output
is saved next to the JSONL record, and the exit code is 1 — a
flake is root-caused and fixed, never retried into green.

"Under load": pass --load-workers K to keep K busy-loop CPU
workers spinning for the whole sweep (they are stopped in a
finally block); the machine's own load average is also recorded
at the start of every pair.

Usage:
    python3 scripts/flake_quarantine.py --runs 50 \
        --python /path/to/venv/bin/python \
        --out ~/workspace/.verify-tmp/rm014/runs.jsonl \
        --load-workers 2

If a sweep is interrupted externally (host reboot, OOM), resume it
into the same record file with --start-run <next pair number> and
--runs <pairs remaining>; the pairs already recorded keep their
numbers, so the file still reads as one consecutive run.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from multiprocessing import Process
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PACKAGES = ("muninn", "huginn")
PASSED_RE = re.compile(r"(\d+) passed")
FAILED_RE = re.compile(r"(\d+) failed")
ERROR_RE = re.compile(r"(\d+) errors?")


def _spin() -> None:
    while True:
        pass


def run_suite(python: str, package: str) -> dict:
    started = time.monotonic()
    proc = subprocess.run(
        [python, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"],
        cwd=REPO / package,
        capture_output=True,
        check=False,
        text=True,
    )
    duration = round(time.monotonic() - started, 2)
    tail = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
    passed = PASSED_RE.search(tail)
    failed = FAILED_RE.search(tail)
    errors = ERROR_RE.search(tail)
    return {
        "package": package,
        "returncode": proc.returncode,
        "passed": int(passed.group(1)) if passed else None,
        "failed": int(failed.group(1)) if failed else 0,
        "errors": int(errors.group(1)) if errors else 0,
        "duration_s": duration,
        "summary": tail,
        "_full_output": proc.stdout + proc.stderr,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=50)
    parser.add_argument(
        "--start-run",
        type=int,
        default=1,
        help="number of the first pair (resume an interrupted sweep "
        "into the same record file without renumbering its pairs)",
    )
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--out", required=True)
    parser.add_argument("--load-workers", type=int, default=0)
    args = parser.parse_args()

    out_path = Path(args.out).expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    workers = [Process(target=_spin, daemon=True) for _ in range(args.load_workers)]
    for worker in workers:
        worker.start()
    last_run = args.start_run + args.runs - 1
    print(
        f"flake quarantine: {args.runs} pairs (runs "
        f"{args.start_run}..{last_run}), python={args.python}, "
        f"load_workers={args.load_workers}, out={out_path}",
        flush=True,
    )
    consecutive = 0
    try:
        with out_path.open("a") as record:
            for index in range(args.start_run, last_run + 1):
                pair = {
                    "run": index,
                    "started_at": datetime.now(UTC).isoformat(),
                    "load_avg": list(os.getloadavg()),
                    "suites": {},
                }
                green = True
                for package in PACKAGES:
                    result = run_suite(args.python, package)
                    full_output = result.pop("_full_output")
                    pair["suites"][package] = result
                    if result["returncode"] != 0:
                        green = False
                        fail_log = out_path.with_suffix(
                            f".run{index}.{package}.log"
                        )
                        fail_log.write_text(full_output)
                        pair["failure_log"] = str(fail_log)
                pair["green"] = green
                record.write(json.dumps(pair) + "\n")
                record.flush()
                consecutive = consecutive + 1 if green else 0
                print(
                    f"run {index}/{last_run}: green={green} "
                    f"consecutive={consecutive} "
                    f"muninn={pair['suites']['muninn']['summary']} "
                    f"huginn={pair['suites']['huginn']['summary']}",
                    flush=True,
                )
                if not green:
                    print(
                        "STOP: non-green pair — root-cause it, never "
                        "retry into green. Full output saved.",
                        flush=True,
                    )
                    return 1
    finally:
        for worker in workers:
            worker.terminate()
    print(f"DONE: {consecutive} consecutive green pairs", flush=True)
    return 0 if consecutive == args.runs else 1


if __name__ == "__main__":
    raise SystemExit(main())
