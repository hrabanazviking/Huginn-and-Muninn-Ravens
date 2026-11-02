"""RM-059 — Activation write path pins.

The slice, proven by ``scripts/write_path.py``:

- ``_log_activation_locked`` (the one helper behind
  ``activate``, the small-batch road of ``activate_batch``
  and ``retrieve(..., touch=True)``) now runs in the fewest
  statements that keep the semantics: four data statements
  with attestation off — log INSERT, counter upsert, node
  UPDATE, tombstone DELETE. The pre-slice fifth statement
  (a SELECT re-reading the counter total the upsert had
  just written) is folded into the upsert itself via
  ``RETURNING`` on SQLite 3.35+; older runtimes keep the
  re-read road, semantics identical.
- With attestation on, the chain head (two meta rows) is
  written by one combined statement instead of an
  executemany of two.

These tests pin the executed-statement counts and shapes
(trace callback over the store's own connection), the
count-exact semantics against raw-SQL ground truth (log
rows, counter totals, confidence, access counts,
tombstone clearing — on a live node, a forgotten id and
a never-remembered id), the pre-3.35 fallback road (flag
forced off), the attested road end to end, and the
committed gate record. No test depends on wall-clock
timings.
"""

import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

import muninn.core as core
from muninn import HebbianMemory
from muninn.config import MuninnConfig

PKG = Path(__file__).parent.parent
SCRIPT = PKG / "scripts" / "write_path.py"
COMMITTED = PKG / "scripts" / "write_path.json"
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
_COUNTED = ("INSERT", "UPDATE", "DELETE", "SELECT")


def _load_script():
    spec = importlib.util.spec_from_file_location("muninn_write_path", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def mem(tmp_path):
    m = HebbianMemory(MuninnConfig(db_path=str(tmp_path / "m.db")))
    yield m
    m.close()


def _traced(mem, fn):
    """Run ``fn`` with the trace callback on; return
    (fn's result, [data-statement kinds in order],
    [full statement texts])."""
    seen = []
    conn = mem._get_conn()
    conn.set_trace_callback(seen.append)
    try:
        result = fn()
    finally:
        conn.set_trace_callback(None)
    kinds = []
    texts = []
    for sql in seen:
        head = sql.lstrip().split(None, 1)[0].upper() if sql.strip() else ""
        if head in _COUNTED:
            kinds.append(head)
            texts.append(" ".join(sql.split()))
    return result, kinds, texts


def _raw(mem, sql, params=()):
    return [tuple(r) for r in mem._get_conn().execute(sql, params).fetchall()]


# ─── statement counts ────────────────────────────────────────


def test_activate_executes_four_statements(mem):
    node_id = mem.remember("counted activation")
    total, kinds, texts = _traced(mem, lambda: mem.activate(node_id))
    assert total == 1
    if core._RETURNING_OK:
        assert kinds == ["INSERT", "INSERT", "UPDATE", "DELETE"]
        assert texts[0].startswith("INSERT INTO activation_log")
        assert texts[1].startswith("INSERT INTO node_activation")
        assert texts[1].endswith("RETURNING total_activations")
        assert texts[2].startswith("UPDATE nodes SET access_count")
        assert texts[3].startswith("DELETE FROM deleted_nodes")
    else:
        assert kinds == ["INSERT", "INSERT", "SELECT", "UPDATE", "DELETE"]


def test_activate_fallback_road_is_count_exact(mem, monkeypatch):
    """The pre-3.35 road (upsert + SELECT re-read), forced
    on: same totals, same rows, one more statement."""
    monkeypatch.setattr(core, "_RETURNING_OK", False)
    node_id = mem.remember("fallback activation")
    totals = []
    for _ in range(3):
        total, kinds, _texts = _traced(mem, lambda: mem.activate(node_id))
        totals.append(total)
    assert totals == [1, 2, 3]
    assert kinds == ["INSERT", "INSERT", "SELECT", "UPDATE", "DELETE"]
    assert mem.activation_count(node_id) == 3
    assert _raw(mem, "SELECT COUNT(*) FROM activation_log") == [(3,)]


def test_attested_activate_writes_head_in_one_statement(tmp_path):
    m = HebbianMemory(
        MuninnConfig(
            db_path=str(tmp_path / "a.db"),
            integrity_attestation=True,
            integrity_passphrase="rm059 attestation passphrase",
        )
    )
    node_id = m.remember("attested activation")
    _total, _kinds, texts = _traced(m, lambda: m.activate(node_id))
    meta_writes = [t for t in texts if t.startswith("INSERT OR REPLACE INTO meta")]
    # Exactly one meta write statement, carrying both rows.
    assert len(meta_writes) == 1
    assert ", (" in meta_writes[0]
    assert m.health()["integrity_attestation"] == "ok"
    m.close()
    # And the chain the combined write advanced verifies on
    # a fresh open — the head really landed, both rows.
    m2 = HebbianMemory(
        MuninnConfig(
            db_path=str(tmp_path / "a.db"),
            integrity_attestation=True,
            integrity_passphrase="rm059 attestation passphrase",
        )
    )
    assert m2.health()["integrity_attestation"] == "ok"
    assert m2.activation_count(node_id) == 1
    m2.close()


# ─── count-exact semantics ───────────────────────────────────


def test_activate_counts_are_exact(mem):
    a = mem.remember("first node")
    b = mem.remember("second node")
    assert [mem.activate(a) for _ in range(4)] == [1, 2, 3, 4]
    assert [mem.activate(b) for _ in range(2)] == [1, 2]
    # An id with no node still counts (the log is the log).
    assert [mem.activate(999_001) for _ in range(2)] == [1, 2]
    assert mem.activation_count(a) == 4
    assert mem.activation_count(b) == 2
    assert mem.activation_count(999_001) == 2
    rows = _raw(
        mem,
        "SELECT memory_id, COUNT(*) FROM activation_log"
        " GROUP BY memory_id ORDER BY memory_id",
    )
    assert rows == [(a, 4), (b, 2), (999_001, 2)]
    counters = _raw(
        mem,
        "SELECT memory_id, total_activations FROM node_activation"
        " ORDER BY memory_id",
    )
    assert counters == [(a, 4), (b, 2), (999_001, 2)]
    # The live nodes' access counts moved exactly with their
    # activations; the log's timestamps strictly increase in
    # issue order (RM-012, untouched by this slice).
    assert mem.get_node(a).access_count == 4
    assert mem.get_node(b).access_count == 2
    stamps = [r[0] for r in _raw(mem, "SELECT activated_at FROM activation_log ORDER BY id")]
    assert stamps == sorted(stamps) and len(set(stamps)) == len(stamps)


def test_activate_confidence_formula_unchanged(mem):
    """Counter upsert semantics are the pre-slice formula:
    first activation lands confidence 1.0; after a decay
    drops it, an activation restores it by exactly
    ``c + lr * (1 - c)``."""
    node_id = mem.remember("confidence subject")
    mem.activate(node_id)
    row = _raw(
        mem, "SELECT confidence FROM node_activation WHERE memory_id = ?", (node_id,)
    )
    assert row == [(1.0,)]
    mem.decay(days=30.0)
    (dropped,) = _raw(
        mem, "SELECT confidence FROM node_activation WHERE memory_id = ?", (node_id,)
    )[0]
    assert dropped < 1.0
    mem.activate(node_id)
    (restored,) = _raw(
        mem, "SELECT confidence FROM node_activation WHERE memory_id = ?", (node_id,)
    )[0]
    lr = mem.config.learning_rate
    assert restored == pytest.approx(min(1.0, dropped + lr * (1.0 - dropped)))


def test_activate_clears_tombstone_and_keeps_counting(mem):
    node_id = mem.remember("soon forgotten")
    mem.activate(node_id)
    assert mem.forget(node_id) is True
    assert _raw(mem, "SELECT memory_id FROM deleted_nodes") == [(node_id,)]
    # The counter survives the forget (the log is kept), and
    # re-activating the id clears its tombstone.
    assert mem.activate(node_id) == 2
    assert _raw(mem, "SELECT memory_id FROM deleted_nodes") == []
    assert mem.activation_count(node_id) == 2


def test_activate_batch_small_road_counts_exact(mem):
    ids = [mem.remember(f"batch node {i}") for i in range(5)]
    report = mem.activate_batch(ids)
    assert report == {
        "activated": 5,
        "pairs_wired": 10,
        "connections_created": 10,
        "connections_strengthened": 0,
    }
    report2 = mem.activate_batch(ids)
    assert report2["connections_created"] == 0
    assert report2["connections_strengthened"] == 10
    for mid in ids:
        assert mem.activation_count(mid) == 2
        assert mem.get_node(mid).access_count == 2
    assert _raw(mem, "SELECT COUNT(*) FROM activation_log") == [(10,)]


def test_retrieve_touch_counts_exact(mem):
    ids = [mem.remember(f"touch node {i}", category="touchcat") for i in range(3)]
    got = mem.retrieve(category="touchcat", touch=True)
    assert {n.id for n in got} == set(ids)
    for mid in ids:
        assert mem.activation_count(mid) == 1
        assert mem.get_node(mid).access_count == 1
    # A pure read afterwards moves nothing (RM-009).
    mem.retrieve(category="touchcat")
    for mid in ids:
        assert mem.activation_count(mid) == 1


# ─── the gate script + committed record ──────────────────────


def test_gate_script_small_run_shape():
    module = _load_script()
    record = module.run_write_path(n_nodes=40)
    assert record["kind"] == "write_path"
    assert set(record["results_ms"]) == set(module.OPS)
    expected = 4 if core._RETURNING_OK else 5
    assert record["details"]["statements_per_activate"] == expected
    for key in ENV_KEYS:
        assert key in record["environment"]


def test_committed_record_carries_the_gate():
    record = json.loads(COMMITTED.read_text())
    assert record["package"] == "muninn"
    assert record["kind"] == "write_path"
    assert set(record["results_ms"]) == {
        "activate_same_id",
        "activate_distinct_ids",
        "activate_batch5",
        "retrieve_touch",
    }
    # The committed record was made on this machine's SQLite
    # (3.45.1, RETURNING road): four statements, no SELECT.
    assert record["details"]["statements_per_activate"] == 4
    assert record["details"]["statement_kinds_per_activate"] == [
        "INSERT",
        "INSERT",
        "UPDATE",
        "DELETE",
    ]
    for key in ENV_KEYS:
        assert key in record["environment"]
    assert sqlite3.sqlite_version == record["environment"]["sqlite_version"]
