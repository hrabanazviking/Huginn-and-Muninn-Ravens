"""RM-066 — Connection-pragmas pins for muninn.

The gate (``muninn/scripts/pragma_study.py``, record
``docs/PRAGMA_STUDY.md``) measured SQLite's
``cache_size`` / ``mmap_size`` / ``temp_store`` on the
store connection at 100k edges. Verdicts: the page
cache default is adopted at ``cache_size=-16384``
(16 MiB, a ceiling not an allocation) in ``_connect``
— the aggregate road's working set thrashes the
compiled 2 MiB default; mmap was measured faster but
NOT adopted (it converts the truncated-file fault
family into host-process SIGBUS, against the
crash-proof charter); temp_store showed no replicable
effect and keeps the compiled default. These tests
pin the adopted default on a real open, the gate
script's shape, a small run's behaviour (readbacks
are what each variant set, fingerprints identical —
a pragma may change speed, never results), and the
committed record + record doc.
"""

import importlib.util
import json
from pathlib import Path

import pytest


def _repo_root():
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "RAVENS_ROADMAP_2026-10-31.md").is_file():
            return parent
    return None


def _load_gate():
    root = _repo_root()
    assert root is not None
    script = root / "muninn" / "scripts" / "pragma_study.py"
    spec = importlib.util.spec_from_file_location("muninn_pragma_study", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_open_applies_the_adopted_cache_default(tmp_path):
    from muninn import HebbianMemory
    from muninn.config import MuninnConfig

    mem = HebbianMemory(
        MuninnConfig(db_path=str(tmp_path / "store.db"), auto_backup=False)
    )
    try:
        conn = mem._get_conn()
        # RM-066 adopted default: 16 MiB page cache (a
        # ceiling, not an allocation).
        assert conn.execute("PRAGMA cache_size").fetchone()[0] == -16384
        # Measured but deliberately NOT adopted (the
        # record carries the reasoning for each).
        assert conn.execute("PRAGMA mmap_size").fetchone()[0] == 0
        assert conn.execute("PRAGMA temp_store").fetchone()[0] == 0
    finally:
        mem.close()


def test_gate_script_shape():
    module = _load_gate()
    assert module.NODES == 5000
    assert module.FORWARD == 10
    assert module.VARIANTS == (
        "baseline",
        "cache16",
        "cache64",
        "mmap",
        "temp",
        "all",
    )
    assert hasattr(module, "run_pragma_study")


def test_gate_small_run_behaviour(tmp_path, monkeypatch):
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    module = _load_gate()
    record = module.run_pragma_study(nodes=60)
    assert record["slice"] == "RM-066"
    assert record["store"]["directed_edges"] == 60 * 10 * 2
    # The baseline is the adopted default on this tree:
    # a 16 MiB page cache, mmap off, temp_store compiled.
    assert record["defaults_as_found"] == {
        "cache_size": -16384,
        "mmap_size": 0,
        "temp_store": 0,
    }
    # Every variant's readback is what the variant set —
    # cache16 must equal the (adopted-default) baseline.
    assert record["variants"]["cache16"]["pragmas"] == record["variants"][
        "baseline"
    ]["pragmas"]
    assert record["variants"]["cache64"]["pragmas"]["cache_size"] == -65536
    assert record["variants"]["mmap"]["pragmas"]["mmap_size"] == 268435456
    assert record["variants"]["temp"]["pragmas"]["temp_store"] == 2
    # A pragma may change speed, never results.
    assert record["fingerprints_equal_across_variants"] is True
    for variant in record["variants"].values():
        for workload in ("read_pass", "aggregate_pass"):
            for temperature in ("cold", "warm"):
                assert variant[workload][temperature]["median_ms"] > 0


def test_committed_gate_record_shape():
    root = _repo_root()
    if root is None:
        pytest.skip("not running inside a repo checkout")
    record = json.loads(
        (root / "muninn" / "scripts" / "pragma_study.json").read_text()
    )
    assert record["slice"] == "RM-066"
    assert record["store"]["directed_edges"] == 100000
    assert record["defaults_as_found"]["cache_size"] == -16384
    assert record["fingerprints_equal_across_variants"] is True


def test_record_doc_states_the_verdicts():
    root = _repo_root()
    if root is None:
        pytest.skip("not running inside a repo checkout")
    record = (root / "docs" / "PRAGMA_STUDY.md").read_text()
    assert "RM-066" in record
    for pragma in ("cache_size", "mmap_size", "temp_store"):
        assert pragma in record
    assert "ADOPTED" in record  # cache_size, at -16384
    assert "NOT adopted" in record  # mmap_size, reasoning recorded
