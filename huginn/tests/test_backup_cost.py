"""RM-065 — Backup-cost pins for huginn.

The gate (``huginn/scripts/backup_cost.py``, record
``docs/BACKUP_COST.md``) measured the local backend's
rolling-backup roads at 100k documents: the snapshot
is the same full SQLite backup-API copy + quick_check
as Muninn's twin machinery, byte-proportional at
~5.0 ms/MB on the gate's tmpfs, and backup-on-open
already skips an unchanged store (proven by the
backup file's hash standing still) while a changed
store always takes one. No incremental or
copy-on-write strategy is built — the verdict and
its reasoning are the record's (see the Muninn
suite for the pre-maintenance and double-pay half).
These tests pin the gate script's shape, a small
run's behaviour, and the committed record + doc.
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
    script = root / "huginn" / "scripts" / "backup_cost.py"
    spec = importlib.util.spec_from_file_location("huginn_backup_cost", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gate_script_shape():
    module = _load_gate()
    assert module.DOCS == 100_000
    assert hasattr(module, "run_backup_cost")


def test_gate_small_run_behaviour(tmp_path, monkeypatch):
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    module = _load_gate()
    record = module.run_backup_cost(docs=400)
    assert record["slice"] == "RM-065"
    assert record["store"]["documents"] == 400
    assert record["snapshot"]["verified_quick_check_and_documents"] is True
    assert record["snapshot"]["backup_bytes"] == record["store"]["store_bytes"]
    assert record["snapshot"]["ms_per_mb"] > 0
    assert record["open"]["unchanged_took_backup"] == [False, False, False]
    assert record["open"]["changed_took_backup"] == [True, True, True]


def test_committed_gate_record_shape():
    root = _repo_root()
    if root is None:
        pytest.skip("not running inside a repo checkout")
    record = json.loads(
        (root / "huginn" / "scripts" / "backup_cost.json").read_text()
    )
    assert record["slice"] == "RM-065"
    assert record["store"]["documents"] == 100000
    assert record["snapshot"]["verified_quick_check_and_documents"] is True
    assert record["snapshot"]["median_ms"] > 0
    assert record["open"]["unchanged_took_backup"] == [False, False, False]
    assert record["open"]["changed_took_backup"] == [True, True, True]


def test_record_doc_states_the_verdict():
    root = _repo_root()
    if root is None:
        pytest.skip("not running inside a repo checkout")
    record = (root / "docs" / "BACKUP_COST.md").read_text()
    assert "RM-065" in record
    assert "NOT" in record  # the verdict is stated, not implied
