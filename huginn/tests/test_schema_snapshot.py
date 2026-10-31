"""RM-004 — Schema snapshot test for the huginn local store.

Golden dump of the fresh local store's sqlite_master (five tables +
indexes) in golden_schema.txt beside this file. Any schema change —
a column, a default, an index — fails this test until the golden file
is updated deliberately in the same commit as the change.
"""

import difflib
import re
import sqlite3
from pathlib import Path

from huginn import HuginnConfig, HuginnMemory

GOLDEN = Path(__file__).parent / "golden_schema.txt"


def _dump(db_path):
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
    ).fetchall()
    conn.close()
    lines = []
    for typ, name, tbl, sql in rows:
        norm = re.sub(r"\s+", " ", sql or "").strip()
        lines.append(f"{typ}|{name}|{tbl}|{norm}")
    return lines


def _golden_lines():
    return [
        line
        for line in GOLDEN.read_text().splitlines()
        if line and not line.startswith("#")
    ]


def test_schema_matches_golden_snapshot(tmp_path):
    db_path = tmp_path / "h.db"
    h = HuginnMemory(HuginnConfig(backend="local", local_db_path=str(db_path)))
    # Huginn constructs lazily: the local store exists only after first use.
    h.upsert_memory(content="schema snapshot seed", category="meta")
    h.close()
    actual = _dump(db_path)
    golden = _golden_lines()
    if actual != golden:
        diff = "\n".join(
            difflib.unified_diff(
                golden, actual, fromfile="golden_schema.txt", tofile="live store"
            )
        )
        raise AssertionError(
            "huginn local schema drifted from the RM-004 golden snapshot. "
            "If this change is deliberate, update golden_schema.txt in "
            "the same commit.\n" + diff
        )


def test_golden_table_count():
    tables = [line for line in _golden_lines() if line.startswith("table|")]
    assert len(tables) == 5  # roadmap RM-004: huginn local five tables
