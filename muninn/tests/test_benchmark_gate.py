"""RM-005 — Benchmark gate tests for muninn.

The gate logic in scripts/benchmark.py is pure: given current and
baseline headline timings it decides pass/fail at a regression
threshold (default 25%). These tests pin that logic deterministically
— wall-clock benchmark runs themselves are BENCH evidence, recorded
in scripts/baseline.json and CAMPAIGN_STATE.md, never asserted here
(a loaded machine must not be able to flake the unit suite).

Also pinned: the committed baseline exists, carries every headline
operation, a 0.25 threshold, and the environment block (machine +
load + versions) that RM-005 requires beside every number.
"""

import importlib.util
import json
from pathlib import Path

SCRIPTS = Path(__file__).parent.parent / "scripts"


def _load_benchmark_module():
    spec = importlib.util.spec_from_file_location(
        "muninn_benchmark", SCRIPTS / "benchmark.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bench = _load_benchmark_module()
BASELINE = json.loads((SCRIPTS / "baseline.json").read_text())


def _flat_baseline():
    return {op: 100.0 for op in bench.HEADLINE_OPS}


def test_baseline_file_shape():
    assert BASELINE["package"] == "muninn"
    assert BASELINE["threshold"] == 0.25
    assert set(BASELINE["results_ms"]) == set(bench.HEADLINE_OPS)
    assert all(v > 0 for v in BASELINE["results_ms"].values())


def test_baseline_carries_environment_block():
    env = BASELINE["environment"]
    for key in (
        "machine",
        "system",
        "cpu_count",
        "load_avg",
        "python_version",
        "sqlite_version",
        "recorded_at",
    ):
        assert key in env, f"baseline environment missing {key}"
    assert env["python_version"]
    assert env["sqlite_version"]


def test_environment_block_shape():
    env = bench.environment_block()
    assert env["cpu_count"] >= 1
    assert env["python_version"]
    assert env["sqlite_version"]
    assert "load_avg" in env  # may be None where getloadavg is absent


def test_gate_passes_on_identical_numbers():
    base = _flat_baseline()
    assert bench.compare_to_baseline(dict(base), base) == []


def test_gate_passes_within_threshold():
    base = _flat_baseline()
    current = {op: 124.0 for op in bench.HEADLINE_OPS}  # +24% < 25%
    assert bench.compare_to_baseline(current, base) == []
    faster = {op: 50.0 for op in bench.HEADLINE_OPS}
    assert bench.compare_to_baseline(faster, base) == []


def test_gate_fails_beyond_threshold():
    base = _flat_baseline()
    current = {op: 100.0 for op in bench.HEADLINE_OPS}
    current["activate"] = 126.0  # +26% > 25%
    regressions = bench.compare_to_baseline(current, base)
    assert [r["operation"] for r in regressions] == ["activate"]
    assert abs(regressions[0]["regression"] - 0.26) < 1e-9


def test_gate_threshold_is_configurable():
    base = _flat_baseline()
    current = {op: 140.0 for op in bench.HEADLINE_OPS}  # +40%
    assert bench.compare_to_baseline(current, base, threshold=0.5) == []
    assert bench.compare_to_baseline(current, base, threshold=0.25)


def test_gate_missing_operation_is_a_failure_not_a_pass():
    base = _flat_baseline()
    current = {op: 100.0 for op in bench.HEADLINE_OPS}
    del current["decay"]
    regressions = bench.compare_to_baseline(current, base)
    assert [(r["operation"], r["reason"]) for r in regressions] == [
        ("decay", "missing_from_current")
    ]
    regressions = bench.compare_to_baseline(_flat_baseline(), {"activate": 1.0})
    assert any(r.get("reason") == "missing_from_baseline" for r in regressions)
