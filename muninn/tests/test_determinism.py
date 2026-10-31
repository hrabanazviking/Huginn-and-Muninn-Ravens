"""RM-011 — Determinism audit for muninn.

The audit (full record: docs/DETERMINISM.md) hunted every source of
nondeterminism — dict/set iteration, timestamp ties, float
formatting in hashes, unordered SQL — and pinned or documented
each. This test is the acceptance proof: the identical workload,
run on two fresh stores, produces byte-identical store dumps once
the timestamp columns (listed in TIMESTAMP_COLUMNS, the columns
the roadmap says to exclude and list) are set aside.

The workload is also run in two child processes under different
PYTHONHASHSEED values, so hash-seed-dependent iteration order
cannot hide: the dumps must still match, byte for byte.
"""

import hashlib
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from muninn import HebbianMemory
from muninn.config import MuninnConfig

# Every timestamp column in the muninn schema. These are the ONLY
# columns excluded from the byte-identical comparison, and RM-012
# owns their discipline (UTC ISO-8601 from one helper).
TIMESTAMP_COLUMNS = {
    "nodes": {"created_at", "updated_at"},
    "activation_log": {"activated_at"},
    "hebbian_connections": {"created_at", "last_coactivated_at"},
    "node_activation": {"last_activated_at"},
    "deleted_nodes": {"deleted_at"},
}

# (table, primary ordering) — the dump reads every non-timestamp
# column of every table, ordered by the table's key.
TABLES = [
    ("meta", "key"),
    ("nodes", "id"),
    ("activation_log", "id"),
    ("hebbian_connections", "memory_a_id, memory_b_id"),
    ("node_activation", "memory_id"),
    ("deleted_nodes", "memory_id"),
]


def _workload(db_path: str) -> dict[str, str]:
    """One fixed workload; returns the public-read transcript."""
    m = HebbianMemory(MuninnConfig(db_path=db_path))
    ids = []
    # Deliberate ties: equal importance, equal categories.
    for i, text in enumerate(
        [
            "the ravens fly out at dawn and return at dusk",
            "thought and memory sit on odin shoulders",
            "the well of mímir holds hidden wisdom",
            "runes are carved and read in the old way",
        ]
    ):
        ids.append(
            m.remember(
                text,
                category="lore",
                path="world/ravens",
                importance=7,
                tags=["Ravens", " Odin "],
                metadata={"z_last": i, "a_first": text.split()[1]},
            )
        )
    json_id = m.remember(
        {"b": 2, "a": [3, 1, 2], "nested": {"y": 1, "x": 2}},
        category="data",
        importance=7,
    )
    m.activate_batch([ids[0], ids[1], ids[2]])
    m.activate(ids[0], emotional_valence=0.5)
    # Equal strengths on purpose: get_associations must resolve the
    # tie by id, not by row order.
    m.associate(ids[0], ids[3], strength=0.5)
    m.associate(ids[0], json_id, strength=0.5)
    m.decay(2.0)
    m.consolidate()
    transcript = {
        "associations": repr(
            [
                (a["memory_id"], a["strength"], a["co_activation_count"])
                for a in m.get_associations(ids[0])
            ]
        ),
        "spread": repr(list(m.spread_activation([ids[0]], depth=2).items())),
        "retrieve": repr([n.id for n in m.retrieve(path="world/ravens", top_k=10)]),
        "stats": repr(sorted(m.stats()["categories"].items())),
    }
    m.close()
    return transcript


def _dump(db_path: str) -> str:
    conn = sqlite3.connect(db_path)
    lines: list[str] = []
    for table, order in TABLES:
        cols = [
            r[1]
            for r in conn.execute(f"PRAGMA table_info({table})").fetchall()
            if r[1] not in TIMESTAMP_COLUMNS.get(table, set())
        ]
        rows = conn.execute(
            f"SELECT {', '.join(cols)} FROM {table} ORDER BY {order}"
        ).fetchall()
        for row in rows:
            cells = [
                repr(v) if isinstance(v, float) else str(v) for v in row
            ]
            lines.append(f"{table}|{'|'.join(cells)}")
    conn.close()
    return "\n".join(lines)


def _run(db_path: str) -> str:
    transcript = _workload(db_path)
    body = _dump(db_path) + "\n" + "\n".join(
        f"{k}={v}" for k, v in sorted(transcript.items())
    )
    return hashlib.sha256(body.encode()).hexdigest() + "\n" + body


def test_two_identical_workloads_byte_identical(tmp_path):
    first = _run(str(tmp_path / "a.db"))
    second = _run(str(tmp_path / "b.db"))
    assert first == second


def test_determinism_survives_hash_seed_changes(tmp_path):
    expected = _run(str(tmp_path / "inproc.db")).splitlines()[0]
    pkg_parent = str(Path(sys.modules["muninn"].__file__).resolve().parent.parent)
    for seed in ("0", "42"):
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = seed
        env["PYTHONPATH"] = pkg_parent + os.pathsep + env.get("PYTHONPATH", "")
        proc = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), str(tmp_path / f"s{seed}.db")],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.splitlines()[0] == expected


def test_equal_strength_associations_resolve_by_id(tmp_path):
    m = HebbianMemory(MuninnConfig(db_path=str(tmp_path / "m.db")))
    a = m.remember("seed memory for tie breaking", importance=5)
    others = [m.remember(f"tied memory number {i}", importance=5) for i in range(3)]
    for other in others:
        m.associate(a, other, strength=0.5)
    got = [row["memory_id"] for row in m.get_associations(a)]
    m.close()
    assert got == sorted(others)


if __name__ == "__main__":
    sys.stdout.write(_run(sys.argv[1]))
