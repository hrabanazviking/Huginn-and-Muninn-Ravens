"""RM-057 — Baseline atlas pin for huginn.

The atlas (``scripts/atlas.py``) extends the RM-005/006 bench
harness to 1k / 10k / 100k documents for every headline
operation, with the RM-006 environment block attached. These
tests pin the atlas's shape deterministically — scales,
headline-op coverage, corpus honesty, environment
completeness — and verify the committed record at
``scripts/atlas.json`` really carries every scale and
operation. No test depends on wall-clock timings: only that
each recorded value is a non-negative number. Local backend
only; a live Qdrant round-trip stays NOT PROVEN.
"""

import hashlib
import importlib.util
import json
import platform
import sqlite3
from pathlib import Path

PKG = Path(__file__).parent.parent
SCRIPT = PKG / "scripts" / "atlas.py"
COMMITTED = PKG / "scripts" / "atlas.json"
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


def _load_atlas_module():
    spec = importlib.util.spec_from_file_location("huginn_atlas", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_benchmark_module():
    spec = importlib.util.spec_from_file_location(
        "huginn_benchmark", PKG / "scripts" / "benchmark.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_atlas_scales_are_1k_10k_100k():
    atlas = _load_atlas_module()
    assert tuple(atlas.SCALES) == (1000, 10000, 100000)


def test_atlas_headline_ops_match_the_gate_contract():
    atlas = _load_atlas_module()
    bench = _load_benchmark_module()
    assert tuple(atlas.HEADLINE_OPS) == tuple(bench.HEADLINE_OPS)


def test_atlas_sample_counts_are_fixed_across_scales():
    atlas = _load_atlas_module()
    # The atlas varies store size only: the search sample counts
    # are single fixed values, named once in SAMPLE.
    assert atlas.SAMPLE == {"n_search": 50, "n_search_filtered": 25}


def test_atlas_run_at_tiny_scales_covers_every_headline_op(tmp_path, monkeypatch):
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    atlas = _load_atlas_module()
    record = atlas.run_atlas((20, 40))
    assert record["package"] == "huginn"
    assert record["kind"] == "atlas"
    for key in ENV_KEYS:
        assert key in record["environment"], f"environment block missing {key}"
    assert record["environment"]["python_version"] == platform.python_version()
    assert record["environment"]["sqlite_version"] == sqlite3.sqlite_version
    bench = _load_benchmark_module()
    assert [entry["scale"] for entry in record["scales"]] == [20, 40]
    for entry in record["scales"]:
        for op in bench.HEADLINE_OPS:
            assert op in entry["results_ms"], f"scale {entry['scale']} missing {op}"
            assert entry["results_ms"][op] >= 0
        corpus = entry["details"]["corpus"]
        assert corpus["count"] == entry["scale"]
        digest = hashlib.sha256()
        for text in bench.corpus_texts(entry["scale"]):
            digest.update(text.encode("utf-8"))
            digest.update(b"\n")
        assert corpus["sha256"] == digest.hexdigest()
        assert entry["details"]["backend"] == "local"
        assert set(entry["details"]["search_p95_ms"]) == {"search", "search_filtered"}
        assert "last_search_stats_after_filtered" in entry["details"]
        assert "last_search_stats_after_search" in entry["details"]


def test_committed_atlas_record_covers_all_scales_and_ops():
    record = json.loads(COMMITTED.read_text())
    assert record["package"] == "huginn"
    assert record["kind"] == "atlas"
    for key in ENV_KEYS:
        assert key in record["environment"], f"environment block missing {key}"
    assert [entry["scale"] for entry in record["scales"]] == [1000, 10000, 100000]
    bench = _load_benchmark_module()
    for entry in record["scales"]:
        for op in bench.HEADLINE_OPS:
            assert op in entry["results_ms"], f"scale {entry['scale']} missing {op}"
            assert isinstance(entry["results_ms"][op], (int, float))
            assert entry["results_ms"][op] >= 0
        assert entry["details"]["corpus"]["count"] == entry["scale"]
        assert entry["details"]["backend"] == "local"
        assert "last_search_stats_after_search" in entry["details"]
        assert "last_search_stats_after_filtered" in entry["details"]
