"""RM-062 — Huginn vector scan: the in-store prefilter.

The embedder-mode search used to fetch EVERY stored vector's
text out of SQLite, sort and cap the rows in Python, and only
then apply the category/importance filter to the document
rows — a filtered or capped search still paid the transfer of
every vector in the store. This slice pushes all three cuts
into SQL, in the RM-053 order (candidate cap BEFORE the
filter, lowest ids first):

1. the candidate total is a ``COUNT``, not a fetch;
2. the capped candidate ids are selected in the store
   (``ORDER BY doc_id``, ``LIMIT`` the cap);
3. the documents fetch applies category/importance in SQL
   (as it already did);
4. only the surviving documents' vectors are fetched, by id.

What does not change is the scoring: the survivors are still
scored by the same linear dense-cosine scan, and the results
and the RM-053 accounting are exactly the old road's. These
tests prove:

* parity against a brute-force reference computed from the
  store's raw tables, across filters and limits (the gate
  script ``scripts/vector_scan.py`` re-proves it inside every
  run, at 10k and 100k documents, before quoting timings);
* the prefilter's statement shape — no full-table vector
  fetch reaches SQLite during a search, the cap is a SQL
  ``LIMIT``, and the only vector fetch is by surviving id;
* the RM-053 cap-before-filter order is preserved on the
  vector road;
* vectors of filtered-out / capped-out documents are never
  decoded (their stored text may be garbage; the search
  still answers);
* an encrypted store (RM-049) searches identically.

Record: ``docs/VECTOR_SCAN.md`` — including the honest
verdict the roadmap asked for: at personal-store scale the
linear scan of the survivors stands; no approximate index
is built.
"""

import importlib.util
import json
import random
import sqlite3
from pathlib import Path

import pytest

from huginn import HuginnMemory
from huginn.config import HuginnConfig
from huginn.text import HashingEmbedder, dense_cosine

PKG = Path(__file__).parent.parent
SCRIPT = PKG / "scripts" / "vector_scan.py"
COMMITTED = PKG / "scripts" / "vector_scan.json"
QUERY = "alpha bravo charlie"


def _huginn(tmp_path, name="h.db", **overrides):
    overrides.setdefault("embedder", "hashing")
    config = HuginnConfig(
        backend="local",
        local_db_path=str(tmp_path / name),
        **overrides,
    )
    return HuginnMemory(config)


def _reference(db_path, query_text, *, limit, category=None, min_importance=1, cap=10000):
    """The vector search computed from the raw tables: every
    stored vector decoded, the RM-053 cap (lowest ids) and
    the category/importance filters applied in this code,
    scored with the package's own dense cosine."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        docs = {
            int(r[0]): (r[1], int(r[2]))
            for r in conn.execute(
                "SELECT id, category, importance FROM documents"
            ).fetchall()
        }
        query_vec = HashingEmbedder(384).embed(query_text)
        scored = []
        seen = 0
        for doc_id, vector_text in conn.execute(
            "SELECT doc_id, vector FROM doc_vectors ORDER BY doc_id"
        ):
            if seen >= cap:
                break
            seen += 1
            doc_id = int(doc_id)
            if doc_id not in docs:
                continue
            cat, imp = docs[doc_id]
            if category and cat != category:
                continue
            if imp < min_importance:
                continue
            score = dense_cosine(query_vec, json.loads(vector_text))
            if score > 0.0:
                scored.append((score, doc_id))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [{"id": d, "score": s} for s, d in scored[:limit]], seen
    finally:
        conn.close()


def _assert_parity(mem, db_path, query=QUERY, **kwargs):
    limit = kwargs.get("limit", 10)
    results = mem.search(query, **kwargs)
    expected, _ = _reference(
        db_path,
        query,
        limit=limit,
        category=kwargs.get("category"),
        min_importance=kwargs.get("min_importance", 1),
        cap=mem.config.max_search_candidates,
    )
    got = [{"id": r["id"], "score": r["score"]} for r in results]
    assert got == expected
    return mem.last_search_stats


def _corpus(mem, count=300):
    rng = random.Random(20261031)
    vocab = [f"word{i}" for i in range(200)] + ["alpha", "bravo", "charlie"]
    for i in range(count):
        words = [rng.choice(vocab) for _ in range(rng.randint(5, 50))]
        mem.upsert_memory(
            content=" ".join(words),
            category=f"cat{i % 3}",
            importance=rng.randint(1, 10),
        )


def test_parity_across_filters_and_limits(tmp_path):
    mem = _huginn(tmp_path)
    try:
        _corpus(mem)
        db_path = str(tmp_path / "h.db")
        for limit in (1, 3, 10, 50):
            _assert_parity(mem, db_path, limit=limit)
        _assert_parity(mem, db_path, category="cat1")
        _assert_parity(mem, db_path, min_importance=8)
        _assert_parity(mem, db_path, category="cat2", min_importance=5)
        _assert_parity(mem, db_path, query="word7 word8", limit=10)
    finally:
        mem.close()


def test_prefilter_statement_shape(tmp_path):
    mem = _huginn(tmp_path)
    try:
        _corpus(mem, count=40)
        mem.search(QUERY, limit=5)  # construct the backend
        backend = mem._backend
        statements = []
        backend._conn.set_trace_callback(statements.append)
        try:
            mem.search(QUERY, limit=5, category="cat1")
        finally:
            backend._conn.set_trace_callback(None)
        vector_fetches = [
            s for s in statements if "FROM doc_vectors" in s and "vector" in s.split("FROM")[0]
        ]
        # The old road's full-table fetch is gone: the only
        # statement that selects the vector column carries the
        # surviving-id IN (...) restriction.
        assert vector_fetches, "the search fetched no vectors at all"
        for stmt in vector_fetches:
            assert "WHERE doc_id IN" in stmt
        # The candidate total is a COUNT and the cap is a SQL
        # LIMIT over doc ids — neither moves vector text.
        assert any("COUNT(*)" in s and "doc_vectors" in s for s in statements)
        assert any(
            "SELECT doc_id FROM doc_vectors" in s and "LIMIT" in s
            for s in statements
        )
    finally:
        mem.close()


def test_cap_still_applies_before_the_category_filter(tmp_path):
    mem = _huginn(tmp_path, max_search_candidates=5)
    try:
        for i in range(5):
            mem.upsert_memory(f"alpha bravo tale {i}", category="alpha")
        for i in range(7):
            mem.upsert_memory(f"alpha bravo tale {i}", category="beta")
        results = mem.search("alpha bravo", limit=10, category="beta")
        stats = mem.last_search_stats
        # RM-053's order, preserved: all five scored candidates
        # were alpha; the beta documents sat beyond the bite.
        assert results == []
        assert stats["candidates_total"] == 12
        assert stats["candidates_scored"] == 0
        assert stats["capped"] is True
    finally:
        mem.close()


def test_excluded_vectors_are_never_decoded(tmp_path):
    mem = _huginn(tmp_path, max_search_candidates=10)
    try:
        keep = [
            mem.upsert_memory(f"alpha bravo charlie keeper {i}", category="keep")
            for i in range(6)
        ]
        dropped = [
            mem.upsert_memory(f"alpha bravo charlie dropped {i}", category="drop")
            for i in range(6)
        ]
        capped_out = [
            mem.upsert_memory(f"alpha bravo charlie late {i}", category="keep")
            for i in range(6)
        ]
        # Corrupt every vector the searches below must not
        # touch: the category-filtered-out documents' vectors,
        # and the vectors beyond the candidate cap.
        conn = sqlite3.connect(str(tmp_path / "h.db"))
        try:
            for doc_id in dropped + capped_out:
                conn.execute(
                    "UPDATE doc_vectors SET vector = 'not json' WHERE doc_id = ?",
                    (doc_id,),
                )
            conn.commit()
        finally:
            conn.close()
        # A category search over the capped candidate set sees
        # only clean keeper vectors among the survivors.
        results = mem.search(QUERY, limit=10, category="keep")
        assert {r["id"] for r in results} == set(keep)
        # The capped unfiltered search scores the same first
        # ten candidates (6 keepers + 4 dropped)... the dropped
        # four ARE survivors here, so this road would decode
        # them — assert instead on the cap alone with a store
        # whose first candidates are all clean.
        mem2 = _huginn(tmp_path, name="h2.db", max_search_candidates=6)
        try:
            first = [
                mem2.upsert_memory(f"alpha bravo charlie early {i}", category="keep")
                for i in range(6)
            ]
            late = [
                mem2.upsert_memory(f"alpha bravo charlie late {i}", category="keep")
                for i in range(6)
            ]
            conn = sqlite3.connect(str(tmp_path / "h2.db"))
            try:
                for doc_id in late:
                    conn.execute(
                        "UPDATE doc_vectors SET vector = 'not json'"
                        " WHERE doc_id = ?",
                        (doc_id,),
                    )
                conn.commit()
            finally:
                conn.close()
            results = mem2.search(QUERY, limit=10)
            assert {r["id"] for r in results} == set(first)
            assert mem2.last_search_stats["candidates_scored"] == 6
        finally:
            mem2.close()
    finally:
        mem.close()


def test_encrypted_store_searches_identically(tmp_path):
    plain = _huginn(tmp_path, name="plain.db")
    sealed = _huginn(
        tmp_path,
        name="sealed.db",
        store_encryption=True,
        encryption_passphrase="rm062-parity-passphrase",
    )
    try:
        _corpus(plain, count=120)
        _corpus(sealed, count=120)
        for kwargs in (
            {},
            {"category": "cat1"},
            {"min_importance": 8},
            {"category": "cat2", "min_importance": 5},
        ):
            expected = [
                {"id": r["id"], "score": r["score"]}
                for r in plain.search(QUERY, limit=10, **kwargs)
            ]
            got = [
                {"id": r["id"], "score": r["score"]}
                for r in sealed.search(QUERY, limit=10, **kwargs)
            ]
            assert got == expected
            assert sealed.last_search_stats == plain.last_search_stats
    finally:
        plain.close()
        sealed.close()


def test_gate_script_shape_and_small_run(tmp_path, monkeypatch):
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    spec = importlib.util.spec_from_file_location("huginn_vector_scan", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.DOCS_API == 10000
    assert module.DOCS_SCALE == 100000
    assert module.SCALE_CAP == 200000
    assert module.VECTOR_DIM == 384
    record = module.run_vector_scan(n_api=120, n_scale=300, repeat_api=2, repeat_scale=2)
    assert record["package"] == "huginn"
    assert record["kind"] == "vector_scan"
    assert record["details"]["api"]["n_docs"] == 120
    assert record["details"]["scale"]["n_docs"] == 300
    for section in ("api", "scale"):
        for query_stats in record["details"][section]["queries"].values():
            stats = query_stats["stats"]
            assert stats["candidates_total"] == record["details"][section]["n_docs"]
            assert stats["candidates_scored"] <= stats["candidates_total"]


def test_committed_gate_record_shape():
    record = json.loads(COMMITTED.read_text())
    assert record["package"] == "huginn"
    assert record["kind"] == "vector_scan"
    for key in (
        "recorded_at", "machine", "system", "platform", "node",
        "cpu_count", "load_avg", "python_version", "sqlite_version",
    ):
        assert key in record["environment"], f"environment block missing {key}"
    details = record["details"]
    assert details["api"]["n_docs"] == 10000
    assert details["scale"]["n_docs"] == 100000
    assert details["scale"]["config_overrides"] == {"max_search_candidates": 200000}
    for key, value in record["results_ms"].items():
        assert value >= 0, key


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
