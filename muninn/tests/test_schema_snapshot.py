"""RM-004 — Schema snapshot test for the muninn store.

Golden dump of the fresh store's sqlite_master (six tables + indexes)
in golden_schema.txt beside this file. Any schema change — a column, a
default, an index — fails this test until the golden file is updated
deliberately in the same commit as the change. The shared tables
(activation_log, hebbian_connections) are contractual with Bifröst and
Hermes; schema changes go through roadmap Part X with migration proof.
"""

import difflib
import re
import sqlite3
from pathlib import Path

from muninn import HebbianMemory
from muninn.config import MuninnConfig

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
    db_path = tmp_path / "m.db"
    m = HebbianMemory(MuninnConfig(db_path=str(db_path)))
    m.close()
    actual = _dump(db_path)
    golden = _golden_lines()
    if actual != golden:
        diff = "\n".join(
            difflib.unified_diff(
                golden, actual, fromfile="golden_schema.txt", tofile="live store"
            )
        )
        raise AssertionError(
            "muninn schema drifted from the RM-004 golden snapshot. If "
            "this change is deliberate, update golden_schema.txt in the "
            "same commit and follow roadmap Part X.\n" + diff
        )


def test_golden_table_count():
    tables = [l for l in _golden_lines() if l.startswith("table|")]
    assert len(tables) == 6  # roadmap RM-004: muninn six tables
    names = {l.split("|")[1] for l in tables}
    assert {"activation_log", "hebbian_connections"} <= names
