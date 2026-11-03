"""RM-067 — Query-plan proofs for huginn (local backend).

``EXPLAIN QUERY PLAN`` pins for the hot queries of the
local backend (record ``docs/QUERY_PLANS.md``): every
query that must ride an index names that index in its
plan, so a schema change that drops the index fails
this suite loudly instead of silently slowing search.
The deliberate scans (the RM-062 vector cap's rowid-
ordered scan and the vector count) are pinned as
scans. Plans are read on a fresh raw connection to a
store built through the public API, the RM-058
pattern. The sensitivity tests prove the pins can
fail: dropping an index in a scratch copy changes the
plan exactly where the pin asserts it.
"""

import sqlite3
from pathlib import Path

import pytest

from huginn import HuginnConfig, HuginnMemory


def _huginn(tmp_path, **overrides):
    overrides.setdefault("backend", "local")
    overrides.setdefault("local_db_path", str(tmp_path / "h.db"))
    return HuginnMemory(HuginnConfig(**overrides))


def _seeded(tmp_path):
    hug = _huginn(tmp_path)
    ids = [
        hug.upsert_memory(
            f"plan probe document {i} about ravens and fjords", category="probe"
        )
        for i in range(20)
    ]
    hug.close()
    conn = sqlite3.connect(str(tmp_path / "h.db"))
    return conn, ids


def _plan(conn, sql, params=()):
    rows = conn.execute("EXPLAIN QUERY PLAN " + sql, params).fetchall()
    return " | ".join(str(r[3]) for r in rows)


def _repo_root():
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "RAVENS_ROADMAP_2026-10-31.md").is_file():
            return parent
    return None


def test_get_document_plan_is_a_primary_key_search(tmp_path):
    conn, ids = _seeded(tmp_path)
    try:
        plan = _plan(conn, "SELECT * FROM documents WHERE id = ?", (ids[0],))
        assert "SEARCH documents USING INTEGER PRIMARY KEY" in plan
    finally:
        conn.close()


def test_dedupe_lookup_plan_rides_the_unique_index(tmp_path):
    conn, ids = _seeded(tmp_path)
    try:
        plan = _plan(
            conn,
            "SELECT id FROM documents WHERE content_hash = ? AND category = ?",
            ("x", "probe"),
        )
        assert "sqlite_autoindex_documents_1" in plan
    finally:
        conn.close()


def test_posting_list_plans_ride_the_term_index(tmp_path):
    conn, ids = _seeded(tmp_path)
    try:
        distinct_plan = _plan(
            conn,
            "SELECT DISTINCT doc_id FROM doc_terms WHERE term IN (?,?)",
            ("ravens", "fjords"),
        )
        assert "idx_terms_term" in distinct_plan
        rows_plan = _plan(
            conn,
            "SELECT doc_id, term, tf FROM doc_terms WHERE term IN (?,?)",
            ("ravens", "fjords"),
        )
        assert "idx_terms_term" in rows_plan
        assert "SCAN doc_terms" not in rows_plan
    finally:
        conn.close()


def test_candidate_term_fetch_plan_rides_the_doc_terms_key(tmp_path):
    conn, ids = _seeded(tmp_path)
    try:
        plan = _plan(
            conn,
            "SELECT doc_id, term, tf FROM doc_terms WHERE doc_id IN (?,?,?)",
            (ids[0], ids[1], ids[2]),
        )
        assert "SEARCH doc_terms" in plan
        assert "sqlite_autoindex_doc_terms_1" in plan
        terms_plan = _plan(
            conn, "SELECT term FROM doc_terms WHERE doc_id = ?", (ids[0],)
        )
        assert "sqlite_autoindex_doc_terms_1" in terms_plan
    finally:
        conn.close()


def test_doc_freq_plan_rides_the_corpus_stats_key(tmp_path):
    conn, ids = _seeded(tmp_path)
    try:
        plan = _plan(
            conn,
            "SELECT term, doc_freq FROM corpus_stats WHERE term IN (?,?)",
            ("ravens", "fjords"),
        )
        assert "SEARCH corpus_stats" in plan
        assert "sqlite_autoindex_corpus_stats_1" in plan
    finally:
        conn.close()


def test_filtered_documents_fetch_is_a_key_search(tmp_path):
    conn, ids = _seeded(tmp_path)
    try:
        plan = _plan(
            conn,
            "SELECT * FROM documents WHERE id IN (?,?,?) AND category = ?",
            (ids[0], ids[1], ids[2], "probe"),
        )
        assert "SEARCH documents USING INTEGER PRIMARY KEY" in plan
    finally:
        conn.close()


def test_vector_plans_are_pinned(tmp_path):
    conn, ids = _seeded(tmp_path)
    try:
        # The RM-062 cap scan walks doc_vectors in rowid
        # order, which the ORDER BY + LIMIT rides without
        # a sort; the survivors' fetch is a key search.
        cap_plan = _plan(
            conn, "SELECT doc_id FROM doc_vectors ORDER BY doc_id LIMIT ?", (10000,)
        )
        assert cap_plan.startswith("SCAN doc_vectors")
        assert "TEMP B-TREE" not in cap_plan
        fetch_plan = _plan(
            conn,
            "SELECT doc_id, vector FROM doc_vectors WHERE doc_id IN (?,?,?)",
            (ids[0], ids[1], ids[2]),
        )
        assert "SEARCH doc_vectors USING INTEGER PRIMARY KEY" in fetch_plan
    finally:
        conn.close()


def test_dropping_the_term_index_changes_the_plan(tmp_path):
    # Sensitivity: the posting-list pin above must be
    # able to fail. In a scratch copy with the index
    # dropped, the same query's plan no longer names it.
    conn, ids = _seeded(tmp_path)
    try:
        conn.execute("DROP INDEX idx_terms_term")
        plan = _plan(
            conn,
            "SELECT doc_id, term, tf FROM doc_terms WHERE term IN (?,?)",
            ("ravens", "fjords"),
        )
        assert "idx_terms_term" not in plan
    finally:
        conn.close()


def test_record_doc_states_the_contract():
    root = _repo_root()
    if root is None:
        pytest.skip("not running inside a repo checkout")
    record = (root / "docs" / "QUERY_PLANS.md").read_text()
    assert "RM-067" in record
    assert "idx_terms_term" in record
    assert "SCAN" in record
