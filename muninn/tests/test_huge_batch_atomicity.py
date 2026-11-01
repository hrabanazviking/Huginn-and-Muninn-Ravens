"""RM-035 — Huge-batch atomicity for muninn.

``activate_batch`` with a huge id list is the Hebbian operation at
its widest: 10k unique ids wire n(n-1)/2 = 49,995,000 unordered
pairs (99,990,000 directed rows). The v1.0.0 implementation looped
in Python over every pair — four SQL statements per pair; a probe
on this machine measured 500 ids in 16.9 s, which scales to hours
for 10k. This suite pins the RM-035 contract:

* batches at or above ``_HUGE_BATCH_MIN_IDS`` unique ids take a
  bulk road — the same writes and counts, generated inside SQLite —
  with Python-side memory O(ids), never O(pairs);
* the counts are EXACT: the report dict, the activation log, the
  directed connection rows, strengths and co-activation counts;
* a pre-wired subset (and a one-direction drift) is counted and
  strengthened exactly as the per-pair loop counted it;
* the batch is still ONE transaction: a disk-full failure part-way
  through a huge batch leaves nothing behind — and the secondary
  index the bulk road rebuilds inside the transaction is restored
  by the rollback;
* the 10k acceptance itself (counts + peak memory) is a BENCH
  proof, run as a standalone script against the banked tree and
  recorded in docs/HUGE_BATCH_ATOMICITY.md — the same division of
  labour as the RM-015 soak: the suite pins the semantics at
  feasible scale, the bench record proves the headline number.
"""

import json
import subprocess
import sys

import pytest

from muninn import HebbianMemory, MuninnStorageError
from muninn.config import MuninnConfig
from muninn.core import _HUGE_BATCH_MIN_IDS

LR = 0.1  # MuninnConfig's default learning_rate


def _mem(tmp_path, name="m.db"):
    return HebbianMemory(MuninnConfig(db_path=str(tmp_path / name)))


def _count(m, sql, params=()):
    return m._get_conn().execute(sql, params).fetchone()[0]


def _directed_rows(m):
    return _count(m, "SELECT COUNT(*) FROM hebbian_connections")


def test_bulk_batch_exact_counts_at_scale(tmp_path):
    m = _mem(tmp_path)
    real = [m.remember(f"bulk target {i}") for i in range(5)]
    n = 800
    ids = list(range(1, n + 1))
    result = m.activate_batch(ids)
    pairs = n * (n - 1) // 2
    assert result == {
        "activated": n,
        "pairs_wired": pairs,
        "connections_created": pairs,
        "connections_strengthened": 0,
    }
    # The store itself agrees, row for row.
    assert _count(m, "SELECT COUNT(*) FROM activation_log") == n
    assert _count(m, "SELECT COUNT(*) FROM node_activation") == n
    assert _directed_rows(m) == 2 * pairs
    assert _count(
        m, "SELECT COUNT(*) FROM hebbian_connections WHERE co_activation_count != 1"
    ) == 0
    assert _count(
        m, "SELECT COUNT(*) FROM hebbian_connections WHERE strength != ?", (LR,)
    ) == 0
    # Self-pairs never exist; every id was activated exactly once.
    assert _count(
        m, "SELECT COUNT(*) FROM hebbian_connections WHERE memory_a_id = memory_b_id"
    ) == 0
    for mid in (ids[0], ids[len(ids) // 2], ids[-1]):
        assert m.activation_count(mid) == 1
    # Real nodes inside the batch got their access bump, like the loop.
    for node_id in real:
        assert m.get_node(node_id).access_count == 1
    m.close()


def test_bulk_batch_dedupes_before_counting(tmp_path):
    m = _mem(tmp_path)
    n = 200
    result = m.activate_batch(list(range(1, n + 1)) * 3)
    pairs = n * (n - 1) // 2
    assert result["activated"] == n
    assert result["pairs_wired"] == pairs
    assert _directed_rows(m) == 2 * pairs
    m.close()


def test_bulk_batch_repeat_strengthens_exactly(tmp_path):
    m = _mem(tmp_path)
    n = 200
    ids = list(range(1, n + 1))
    pairs = n * (n - 1) // 2
    m.activate_batch(ids)
    second = m.activate_batch(ids)
    assert second == {
        "activated": n,
        "pairs_wired": pairs,
        "connections_created": 0,
        "connections_strengthened": pairs,
    }
    expected = 1.0 - (1.0 - LR) * (1.0 - LR)
    assert _count(
        m,
        "SELECT COUNT(*) FROM hebbian_connections"
        " WHERE ABS(strength - ?) > 1e-12 OR co_activation_count != 2",
        (expected,),
    ) == 0
    assert _directed_rows(m) == 2 * pairs
    m.close()


def test_bulk_batch_counts_prewired_and_repairs_drift(tmp_path):
    m = _mem(tmp_path)
    # Pre-wire 1-2, 1-3, 2-3 on the loop road, then break one
    # direction of 2-3 by hand: the pair is no longer complete.
    m.activate_batch([1, 2, 3])
    conn = m._get_conn()
    conn.execute(
        "DELETE FROM hebbian_connections WHERE memory_a_id = 3 AND memory_b_id = 2"
    )
    conn.commit()
    n = 100
    result = m.activate_batch(list(range(1, n + 1)))
    pairs = n * (n - 1) // 2
    # Complete before: 1-2 and 1-3 only — the drifted pair counts
    # as created, exactly as _wire_pair_locked reported it.
    assert result["connections_created"] == pairs - 2
    assert result["connections_strengthened"] == 2
    assert _directed_rows(m) == 2 * pairs
    rows = {
        (a, b): (s, c)
        for a, b, s, c in conn.execute(
            "SELECT memory_a_id, memory_b_id, strength, co_activation_count"
            " FROM hebbian_connections"
            " WHERE memory_a_id IN (1, 2, 3) AND memory_b_id IN (1, 2, 3)"
        )
    }
    strengthened = 1.0 - (1.0 - LR) * (1.0 - LR)
    # Both directions of the drifted pair are back: the surviving
    # direction was strengthened, the missing one recreated fresh.
    assert rows[(2, 3)] == (pytest.approx(strengthened), 2)
    assert rows[(3, 2)] == (LR, 1)
    assert rows[(1, 2)] == (pytest.approx(strengthened), 2)
    m.close()


def test_threshold_boundary_loop_and_bulk_agree(tmp_path):
    for n in (_HUGE_BATCH_MIN_IDS - 1, _HUGE_BATCH_MIN_IDS):
        m = _mem(tmp_path, name=f"m{n}.db")
        result = m.activate_batch(list(range(1, n + 1)))
        pairs = n * (n - 1) // 2
        assert result["pairs_wired"] == pairs
        assert result["connections_created"] == pairs
        assert _directed_rows(m) == 2 * pairs
        assert _count(m, "SELECT COUNT(*) FROM activation_log") == n
        m.close()


def test_bulk_batch_disk_full_rolls_back_everything(tmp_path):
    m = _mem(tmp_path)
    n = 400
    ids = list(range(1, n + 1))
    conn = m._get_conn()
    pages = conn.execute("PRAGMA page_count").fetchone()[0]
    conn.execute(f"PRAGMA max_page_count={int(pages)}")
    with pytest.raises(MuninnStorageError):
        m.activate_batch(ids)
    # Nothing survived: no activations, no connections — and the
    # rollback restored the index the bulk road had dropped inside
    # its transaction.
    assert m.activation_count(ids[0]) == 0
    assert _directed_rows(m) == 0
    assert _count(
        m,
        "SELECT COUNT(*) FROM sqlite_master"
        " WHERE type = 'index' AND name = 'idx_conn_b'",
    ) == 1
    conn.execute("PRAGMA max_page_count=1073741823")
    result = m.activate_batch(ids)
    pairs = n * (n - 1) // 2
    assert result["connections_created"] == pairs
    assert _directed_rows(m) == 2 * pairs
    m.close()


_CHILD = """
import json, resource, sys
from muninn import HebbianMemory
from muninn.config import MuninnConfig

n = int(sys.argv[1])
m = HebbianMemory(MuninnConfig(db_path=sys.argv[2]))
result = m.activate_batch(list(range(1, n + 1)))
rows = m._get_conn().execute("SELECT COUNT(*) FROM hebbian_connections").fetchone()[0]
m.close()
print(json.dumps({
    "result": result,
    "directed_rows": rows,
    "peak_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
}))
"""


def _run_child(tmp_path, n):
    db = tmp_path / f"child{n}.db"
    proc = subprocess.run(
        [sys.executable, "-", str(n), str(db)],
        input=_CHILD,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert proc.returncode == 0, proc.stderr
    record = json.loads(proc.stdout.strip().splitlines()[-1])
    # The child's store is ~105 bytes per directed row — evidence
    # already extracted; do not leave ~130 MB sitting in tmp dirs.
    for suffix in ("", "-wal", "-shm"):
        db.with_name(db.name + suffix).unlink(missing_ok=True)
    return record


def test_bulk_batch_memory_is_bounded_by_ids_not_pairs(tmp_path):
    small = _run_child(tmp_path, 300)
    large = _run_child(tmp_path, 1200)
    # 16x the pairs (44,850 -> 719,400), the same memory story:
    # peak RSS grows by a small constant, never with the pair count.
    assert large["result"]["pairs_wired"] == 719_400
    assert large["directed_rows"] == 2 * 719_400
    assert small["result"]["pairs_wired"] == 44_850
    assert large["peak_rss_mb"] < small["peak_rss_mb"] + 40
    assert large["peak_rss_mb"] < 200
