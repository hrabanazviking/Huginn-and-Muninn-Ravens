"""RM-003 — Contract freeze (golden) tests for muninn.

Pins the exact Bifröst call shapes and result keys of BUILD_NOTES §1
(hrabanazviking/bifrost @ b66e98cc) as data, so no later slice can drift
the contract unknowingly: a deliberate signature or result-key change
fails this suite until the golden data below is updated on purpose —
in the same commit as the contract change, with the Bifröst
re-verification the roadmap requires for API changes.

Behavioural exercise of the same calls lives in test_contract.py; this
file pins their *shape*.
"""

import dataclasses
import inspect

from muninn import HebbianMemory
from muninn.config import MuninnConfig


def _shape(fn):
    """(name, kind, repr(default)) per parameter, excluding self."""
    out = []
    for p in inspect.signature(fn).parameters.values():
        if p.name == "self":
            continue
        default = "<required>" if p.default is inspect.Parameter.empty else repr(p.default)
        out.append((p.name, p.kind.name, default))
    return out


# Golden signatures — BUILD_NOTES §1.1. Update ONLY deliberately.
GOLDEN_SIGNATURES = {
    "__init__": [
        ("config", "POSITIONAL_OR_KEYWORD", "None"),
        ("overrides", "VAR_KEYWORD", "<required>"),
    ],
    "activate": [
        ("memory_id", "POSITIONAL_OR_KEYWORD", "<required>"),
        ("emotional_valence", "KEYWORD_ONLY", "0.0"),
        ("source", "KEYWORD_ONLY", "'api'"),
    ],
    "activate_batch": [
        ("memory_ids", "POSITIONAL_OR_KEYWORD", "<required>"),
        ("emotional_valence", "KEYWORD_ONLY", "0.0"),
        ("source", "KEYWORD_ONLY", "'api'"),
    ],
    "get_associations": [
        ("memory_id", "POSITIONAL_OR_KEYWORD", "<required>"),
        ("min_strength", "POSITIONAL_OR_KEYWORD", "0.0"),
        ("limit", "POSITIONAL_OR_KEYWORD", "100"),
    ],
    "decay": [("days", "POSITIONAL_OR_KEYWORD", "1.0")],
    "consolidate": [("threshold", "POSITIONAL_OR_KEYWORD", "None")],
    "health": [],
    "stats": [],
    "close": [],
    "_get_conn": [],
}


def test_golden_signatures():
    for name, golden in GOLDEN_SIGNATURES.items():
        actual = _shape(getattr(HebbianMemory, name))
        assert actual == golden, (
            f"HebbianMemory.{name} signature drifted from the frozen "
            f"Bifröst contract: {actual} != {golden}. If this change is "
            "deliberate, update the golden data and re-run the Bifröst "
            "contract verification before banking."
        )


def test_config_is_dataclass_with_keyword_db_path():
    assert dataclasses.is_dataclass(MuninnConfig)
    fields = {f.name for f in dataclasses.fields(MuninnConfig)}
    assert "db_path" in fields
    # Bifröst constructs with the db_path keyword only.
    cfg = MuninnConfig(db_path="/tmp/freeze-check.db")
    assert cfg.db_path == "/tmp/freeze-check.db"


def test_golden_result_keys(tmp_path):
    m = HebbianMemory(MuninnConfig(db_path=str(tmp_path / "m.db")))
    m.activate_batch([1, 2], emotional_valence=0.5)
    try:
        assert set(m.stats()) == {
            "categories", "consolidated_connections", "db_path",
            "strongest_connection", "total_activations",
            "total_connections", "total_nodes",
        }
        assert set(m.health()) == {
            "activations", "connections", "db_path",
            "file_permissions_warning", "integrity",
            "nodes", "recovered_from_backup", "schema_version",
            "sqlite_version", "status",
        }
        assoc = m.get_associations(1)
        assert assoc, "batch wiring must produce an association"
        assert set(assoc[0]) == {
            "memory_id", "strength", "co_activation_count",
            "consolidated", "last_coactivated_at",
        }
        assert set(m.decay(days=1)) == {
            "confidence_factor", "confidences_decayed", "days",
            "edge_factor", "edges_decayed", "edges_pruned",
        }
        assert set(m.consolidate()) == {
            "heal", "newly_consolidated", "threshold",
            "total_consolidated", "unmarked",
        }
    finally:
        m.close()
