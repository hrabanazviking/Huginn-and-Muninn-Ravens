"""RM-006 — Loaded-machine honesty, end-to-end, for muninn.

Runs the real benchmark script as a subprocess at a tiny workload
and asserts its OUTPUT — both the printed text and the JSON record
— carries the full environment block: CPU count, load average,
Python and SQLite versions, machine, and timestamp. The versions
in the output must equal the versions of the interpreter running
this test, so a canned or stale block cannot pass.
"""

import json
import platform
import sqlite3
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "benchmark.py"
ENV_KEYS = (
    "recorded_at",
    "machine",
    "system",
    "platform",
    "node",
    "cpu_count",
    "load_avg",
    "python_version",
    "sqlite_version",
)


def _run_benchmark(tmp_path):
    out_json = tmp_path / "record.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--nodes", "20",
            "--activations", "50",
            "--batches", "5",
            "--no-check",
            "--output", str(out_json),
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout, json.loads(out_json.read_text())


def test_benchmark_text_output_carries_full_environment_block(tmp_path):
    stdout, _ = _run_benchmark(tmp_path)
    assert "environment:" in stdout
    for key in ENV_KEYS:
        assert f"{key}:" in stdout, f"printed output missing {key}"
    # The printed versions are this interpreter's real versions.
    assert platform.python_version() in stdout
    assert sqlite3.sqlite_version in stdout


def test_benchmark_json_record_carries_full_environment_block(tmp_path):
    _, record = _run_benchmark(tmp_path)
    env = record["environment"]
    for key in ENV_KEYS:
        assert key in env, f"JSON environment missing {key}"
    assert env["python_version"] == platform.python_version()
    assert env["sqlite_version"] == sqlite3.sqlite_version
    assert isinstance(env["cpu_count"], int) and env["cpu_count"] >= 1
    # Load average is a 3-number list on platforms that provide it.
    assert env["load_avg"] is None or (
        len(env["load_avg"]) == 3
        and all(isinstance(v, float) for v in env["load_avg"])
    )
    assert set(record["results_ms"])  # numbers exist beside the block
