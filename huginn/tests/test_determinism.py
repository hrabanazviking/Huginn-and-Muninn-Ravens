"""RM-011 — Determinism audit for huginn (local backend).

The audit (full record: docs/DETERMINISM.md) hunted every source
of nondeterminism — dict/set iteration, timestamp ties, float
formatting in hashes, unordered SQL — and pinned or documented
each. This test is the acceptance proof: the identical workload,
run on two fresh local stores, produces byte-identical store
dumps once the timestamp columns (listed in TIMESTAMP_COLUMNS,
the columns the roadmap says to exclude and list) are set aside.
Search transcripts are part of the compared body, with scores
serialized by repr — float formatting is part of the proof.

The workload is also run in two child processes under different
PYTHONHASHSEED values, so hash-seed-dependent iteration order
cannot hide: the dumps must still match, byte for byte. The
Qdrant backend's result order is the server's own and is NOT
covered here (live Qdrant stays NOT PROVEN).
"""

import hashlib
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from huginn import HuginnMemory
from huginn.config import HuginnConfig

# Every timestamp column in the huginn local schema — the ONLY
# columns excluded from the byte-identical comparison.
TIMESTAMP_COLUMNS = {
    "documents": {"created_at", "updated_at"},
}

TABLES = [
    ("meta", "key"),
    ("documents", "id"),
    ("doc_terms", "doc_id, term"),
    ("corpus_stats", "term"),
    ("doc_vectors", "doc_id"),
]

DOCS = [
    ("the ravens fly out at dawn and return at dusk", "lore", 7),
    ("thought and memory sit on odin shoulders", "lore", 7),
    ("the well of mímir holds hidden wisdom", "lore", 5),
    ("ravens ravens ravens over the battlefield", "lore", 5),
    # Identical term profile to the previous document: their TF-IDF
    # scores tie exactly, so search order proves the id tie-break.
    ("ravens ravens ravens over the battlefield", "other", 5),
]


def _workload(db_path: str) -> dict[str, str]:
    """One fixed workload; returns the public-read transcript."""
    h = HuginnMemory(
        HuginnConfig(backend="local", local_db_path=db_path, embedder="hashing")
    )
    ids = [
        h.upsert_memory(text, category=cat, importance=imp, tags=["ravens"])
        for text, cat, imp in DOCS
    ]
    h.upsert_memory(DOCS[0][0], category="lore", importance=9)  # re-upsert
    transcript = {
        "search_vectors": repr(
            [
                (r["id"], repr(r["score"]))
                for r in h.search("ravens battlefield", limit=10)
            ]
        ),
        "search_category": repr(
            [(r["id"], repr(r["score"])) for r in h.search("ravens", limit=10)]
        ),
        "ids": repr(ids),
        "health_keys": repr(sorted(h.health())),
    }
    h.close()
    # A second store on the default TF-IDF path (no embedder): its
    # dump joins the compared body in _run via the .tfidf suffix.
    t = HuginnMemory(HuginnConfig(backend="local", local_db_path=db_path + ".tfidf"))
    for text, cat, imp in DOCS:
        t.upsert_memory(text, category=cat, importance=imp, tags=["ravens"])
    transcript["search_tfidf"] = repr(
        [(r["id"], repr(r["score"])) for r in t.search("ravens battlefield", limit=10)]
    )
    t.close()
    # The module-level semantic_search tie-break is pinned in
    # huginn.core; its transcript rides along too.
    from huginn.core import semantic_search

    transcript["semantic_search"] = repr(
        [(i, repr(s)) for i, s in semantic_search("ravens", [d[0] for d in DOCS])]
    )
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
            cells = [repr(v) if isinstance(v, float) else str(v) for v in row]
            lines.append(f"{table}|{'|'.join(cells)}")
    conn.close()
    return "\n".join(lines)


def _run(db_path: str) -> str:
    transcript = _workload(db_path)
    body = (
        _dump(db_path)
        + "\n"
        + _dump(db_path + ".tfidf")
        + "\n"
        + "\n".join(f"{k}={v}" for k, v in sorted(transcript.items()))
    )
    return hashlib.sha256(body.encode()).hexdigest() + "\n" + body


def test_two_identical_workloads_byte_identical(tmp_path):
    first = _run(str(tmp_path / "a.db"))
    second = _run(str(tmp_path / "b.db"))
    assert first == second


def test_determinism_survives_hash_seed_changes(tmp_path):
    expected = _run(str(tmp_path / "inproc.db")).splitlines()[0]
    pkg_parent = str(Path(sys.modules["huginn"].__file__).resolve().parent.parent)
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


def test_tied_search_scores_resolve_by_id(tmp_path):
    h = HuginnMemory(
        HuginnConfig(
            backend="local", local_db_path=str(tmp_path / "h.db"), embedder="hashing"
        )
    )
    first = h.upsert_memory("ravens ravens ravens over the battlefield")
    second = h.upsert_memory(
        "ravens ravens ravens over the battlefield", category="other"
    )
    got = [r["id"] for r in h.search("ravens battlefield", limit=10)]
    h.close()
    assert got.index(first) < got.index(second)


if __name__ == "__main__":
    sys.stdout.write(_run(sys.argv[1]))
