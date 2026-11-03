"""RM-065 — Backup-cost pins for muninn.

The gate (``muninn/scripts/backup_cost.py``, record
``docs/BACKUP_COST.md``) measured the rolling-backup
roads at 100k edges: a snapshot is a full SQLite
backup-API copy + quick_check, byte-proportional at
~4.5 ms/MB on the gate's tmpfs; backup-on-open already
skips an unchanged store; the pre-maintenance snapshot
in ``decay``/``consolidate`` is the recovery point for
the pass it precedes. The one proven waste — an open
that takes a backup followed immediately by a
maintenance pass re-snapshotting identical content
(the double pay) — is ~one snapshot in a narrow window
and does not demand an incremental or copy-on-write
rebuild of the RM-037/043/051-pinned machinery; the
verdict, the numbers, and the sound-fix design are the
record's. These tests pin the gate script's shape, a
small run's behaviour (unchanged opens never back up,
changed opens always do, snapshots verify), and the
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
    script = root / "muninn" / "scripts" / "backup_cost.py"
    spec = importlib.util.spec_from_file_location("muninn_backup_cost", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gate_script_shape():
    module = _load_gate()
    assert module.NODES == 5000
    assert module.FORWARD == 10
    assert hasattr(module, "run_backup_cost")


def test_gate_small_run_behaviour(tmp_path, monkeypatch):
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    module = _load_gate()
    record = module.run_backup_cost(nodes=60)
    assert record["slice"] == "RM-065"
    assert record["store"]["directed_edges"] == 60 * 10 * 2
    assert record["snapshot"]["verified_quick_check_and_edges"] is True
    assert record["snapshot"]["backup_bytes"] == record["store"]["store_bytes"]
    assert record["snapshot"]["ms_per_mb"] > 0
    # The open road's discipline, proven by backup hashes:
    # an unchanged store never triggers a snapshot, a
    # changed store always does.
    assert record["open"]["unchanged_took_backup"] == [False, False, False]
    assert record["open"]["changed_took_backup"] == [True, True, True]
    for kind in ("decay", "consolidate"):
        section = record["maintenance"][kind]
        assert section["auto_backup_true_median_ms"] > 0
        assert section["auto_backup_false_median_ms"] > 0
    # At any scale the double-pay question is asked and
    # answered from table content, never assumed.
    assert isinstance(
        record["double_pay"]["open_backup_equals_pre_decay_snapshot_tables"],
        bool,
    )


def test_committed_gate_record_shape():
    root = _repo_root()
    if root is None:
        pytest.skip("not running inside a repo checkout")
    record = json.loads(
        (root / "muninn" / "scripts" / "backup_cost.json").read_text()
    )
    assert record["slice"] == "RM-065"
    assert record["store"]["directed_edges"] == 100000
    assert record["snapshot"]["verified_quick_check_and_edges"] is True
    assert record["snapshot"]["median_ms"] > 0
    assert record["open"]["unchanged_took_backup"] == [False, False, False]
    assert record["open"]["changed_took_backup"] == [True, True, True]
    assert (
        record["double_pay"]["open_backup_equals_pre_decay_snapshot_tables"]
        is True
    )
    assert record["double_pay"]["redundant_snapshot_cost_ms"] > 0


def test_record_doc_states_the_verdict():
    root = _repo_root()
    if root is None:
        pytest.skip("not running inside a repo checkout")
    record = (root / "docs" / "BACKUP_COST.md").read_text()
    assert "RM-065" in record
    assert "double" in record.lower()
    assert "NOT" in record  # the verdict is stated, not implied
