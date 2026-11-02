"""RM-061 — Huginn candidate generation: posting-list pruning.

The local TF-IDF search used to fetch every candidate's full
term set and score it. This slice narrows the candidates from
the query terms' posting lists first: from the postings alone,
each candidate's dot product with the query is exact and its
full vector norm is bounded from below (the posting-only
sub-vector's norm plus the least the remaining terms can
contribute, from the corpus-minimum idf and the candidate's
total token count), giving a true upper bound on its cosine
score. Candidates are fully scored best-bound-first in
batches; once ``limit`` exact scores stand, a remaining
candidate whose bound cannot beat — or tie-and-outrank by
doc id — the limit-th score is pruned without its term set
ever being fetched.

The claim that matters is EXACTNESS: the pruned search
returns the unpruned search's results. These tests prove it
against a brute-force reference computed from the store's
raw tables (the gate script
``scripts/candidate_pruning.py`` re-proves it inside every
run, on the benchmark corpus and a distinct-document corpus,
before quoting any timing):

* parity on the RM-020 benchmark corpus (fixed queries,
  plus a category-filtered query);
* parity on a randomized corpus across limits, category
  filters and importance floors;
* pruning genuinely prunes on a crafted strong/weak corpus,
  and composes with the RM-053 candidate cap;
* exact ties are never pruned (identical documents are all
  fully scored; the lowest ids win the tie-break);
* the stats record carries ``candidates_pruned`` (0 on the
  vector road, which does not prune);
* an encrypted store (RM-049) prunes identically.

Record: ``docs/CANDIDATE_PRUNING.md``.
"""

import importlib.util
import json
import random
import sqlite3
from pathlib import Path

import pytest

from huginn import HuginnMemory
from huginn.config import HuginnConfig
from huginn.text import cosine, sparse_tfidf, term_counts, tokenize

PKG = Path(__file__).parent.parent
SCRIPT = PKG / "scripts" / "candidate_pruning.py"
COMMITTED = PKG / "scripts" / "candidate_pruning.json"


def _huginn(tmp_path, name="h.db", **overrides):
    config = HuginnConfig(
        backend="local",
        local_db_path=str(tmp_path / name),
        **overrides,
    )
    return HuginnMemory(config)


def _reference(db_path, query_text, *, limit, category=None, min_importance=1, cap=10000):
    """The unpruned search, computed from the raw tables:
    every candidate's full term set scored with the package's
    own TF-IDF/cosine, the RM-053 cap (lowest ids) and the
    category/importance filters applied exactly as the
    backend applies them."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        total_docs = int(conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0])
        q_counts = term_counts(tokenize(query_text))
        if not q_counts or total_docs == 0:
            return [], 0
        placeholders = ",".join("?" * len(q_counts))
        candidate_ids = sorted(
            int(r[0])
            for r in conn.execute(
                f"SELECT DISTINCT doc_id FROM doc_terms WHERE term IN ({placeholders})",
                list(q_counts),
            ).fetchall()
        )
        candidates_total = len(candidate_ids)
        candidate_ids = candidate_ids[:cap]
        if not candidate_ids:
            return [], candidates_total
        ph = ",".join("?" * len(candidate_ids))
        sql = f"SELECT id, category, importance FROM documents WHERE id IN ({ph})"
        keep = {}
        for doc_id, cat, imp in conn.execute(sql, candidate_ids).fetchall():
            if category and cat != category:
                continue
            if min_importance > 1 and imp < min_importance:
                continue
            keep[int(doc_id)] = True
        if not keep:
            return [], candidates_total
        kept_ids = sorted(keep)
        ph = ",".join("?" * len(kept_ids))
        per_doc = {}
        all_terms = set(q_counts)
        for doc_id, term, tf in conn.execute(
            f"SELECT doc_id, term, tf FROM doc_terms WHERE doc_id IN ({ph})"
            " ORDER BY doc_id, term",
            kept_ids,
        ).fetchall():
            per_doc.setdefault(int(doc_id), {})[term] = int(tf)
            all_terms.add(term)
        tph = ",".join("?" * len(all_terms))
        df = {
            r[0]: int(r[1])
            for r in conn.execute(
                f"SELECT term, doc_freq FROM corpus_stats WHERE term IN ({tph})",
                list(all_terms),
            ).fetchall()
        }
        query_vec = sparse_tfidf(q_counts, df, total_docs)
        scored = []
        for doc_id, counts in per_doc.items():
            score = cosine(query_vec, sparse_tfidf(counts, df, total_docs))
            if score > 0.0:
                scored.append((score, doc_id))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [{"id": d, "score": s} for s, d in scored[:limit]], candidates_total
    finally:
        conn.close()


def _assert_parity(mem, db_path, query, **kwargs):
    limit = kwargs.get("limit", 10)
    results = mem.search(query, **kwargs)
    expected, candidates_total = _reference(
        db_path,
        query,
        limit=limit,
        category=kwargs.get("category"),
        min_importance=kwargs.get("min_importance", 1),
        cap=mem.config.max_search_candidates,
    )
    got = [{"id": r["id"], "score": r["score"]} for r in results]
    assert got == expected
    stats = mem.last_search_stats
    assert stats["candidates_total"] == candidates_total
    return stats


def _load_benchmark_module():
    spec = importlib.util.spec_from_file_location(
        "huginn_benchmark_for_pruning", PKG / "scripts" / "benchmark.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parity_on_the_benchmark_corpus(tmp_path):
    bench = _load_benchmark_module()
    mem = _huginn(tmp_path)
    try:
        for i, text in enumerate(bench.corpus_texts(600)):
            mem.upsert_memory(content=text, category=f"cat{i % 10}", importance=5)
        db_path = str(tmp_path / "h.db")
        for query in (
            "raven wisdom tree",
            "sword fire storm",
            "ship sea song",
            "wolf eye memory",
        ):
            _assert_parity(mem, db_path, query, limit=10)
            _assert_parity(mem, db_path, query, limit=3)
        _assert_parity(mem, db_path, "raven wisdom tree", limit=10, category="cat3")
    finally:
        mem.close()


def test_parity_on_a_randomized_corpus(tmp_path):
    rng = random.Random(20261031)
    vocab = [f"word{i}" for i in range(300)]
    mem = _huginn(tmp_path)
    try:
        for i in range(400):
            words = [rng.choice(vocab) for _ in range(rng.randint(5, 60))]
            mem.upsert_memory(
                content=" ".join(words),
                category=f"cat{i % 3}",
                importance=rng.randint(1, 10),
            )
        db_path = str(tmp_path / "h.db")
        for _ in range(8):
            query = " ".join(rng.choice(vocab) for _ in range(rng.randint(1, 4)))
            _assert_parity(mem, db_path, query, limit=rng.choice([1, 3, 10, 50]))
        _assert_parity(mem, db_path, "word1 word2", limit=10, category="cat1")
        _assert_parity(mem, db_path, "word3 word4 word5", limit=10, min_importance=8)
        _assert_parity(
            mem, db_path, "word7", limit=5, category="cat2", min_importance=5
        )
    finally:
        mem.close()


def _strong_weak_corpus(mem, strong=30, weak=300):
    filler = " ".join(f"filler{i}" for i in range(60))
    for i in range(strong):
        mem.upsert_memory(
            content=f"alpha bravo charlie alpha bravo charlie saga {i}",
            category="strong",
        )
    for i in range(weak):
        mem.upsert_memory(content=f"alpha {filler} token{i}", category="weak")


def test_pruning_actually_prunes_and_stays_exact(tmp_path):
    mem = _huginn(tmp_path)
    try:
        _strong_weak_corpus(mem)
        stats = _assert_parity(mem, str(tmp_path / "h.db"), "alpha bravo charlie", limit=10)
        assert stats["candidates_total"] == 330
        assert stats["candidates_pruned"] > 0
        assert stats["candidates_scored"] < stats["candidates_total"]
    finally:
        mem.close()


def test_pruning_composes_with_the_candidate_cap(tmp_path):
    mem = _huginn(tmp_path, max_search_candidates=50)
    try:
        _strong_weak_corpus(mem)
        stats = _assert_parity(mem, str(tmp_path / "h.db"), "alpha bravo charlie", limit=10)
        assert stats["candidates_total"] == 330
        assert stats["capped"] is True
        assert stats["candidates_scored"] <= 50
    finally:
        mem.close()


def test_exact_ties_are_never_pruned(tmp_path):
    mem = _huginn(tmp_path)
    try:
        for i in range(100):
            mem.upsert_memory(
                content="alpha bravo charlie delta echo", category=f"tie{i}"
            )
        results = mem.search("alpha bravo", limit=10)
        assert [r["id"] for r in results] == list(range(1, 11))
        assert len({r["score"] for r in results}) == 1
        stats = mem.last_search_stats
        # Every tied candidate was fully scored: a bound that
        # merely ties the limit-th score never excuses a
        # candidate that could win the id tie-break, and the
        # bound's safety factor keeps exact ties scored.
        assert stats["candidates_pruned"] == 0
        assert stats["candidates_scored"] == 100
    finally:
        mem.close()


def test_vector_road_records_zero_pruned(tmp_path):
    mem = _huginn(tmp_path, embedder="hashing")
    try:
        for i in range(20):
            mem.upsert_memory(f"alpha bravo tale {i}", category="lore")
        mem.search("alpha", limit=5)
        stats = mem.last_search_stats
        assert stats["candidates_pruned"] == 0
        assert stats["candidates_scored"] <= 20
    finally:
        mem.close()


def test_encrypted_store_prunes_identically(tmp_path):
    plain = _huginn(tmp_path, name="plain.db")
    sealed = _huginn(
        tmp_path,
        name="sealed.db",
        store_encryption=True,
        encryption_passphrase="rm061-parity-passphrase",
    )
    try:
        _strong_weak_corpus(plain)
        _strong_weak_corpus(sealed)
        for query in ("alpha bravo charlie", "alpha"):
            expected = [
                {"id": r["id"], "score": r["score"]}
                for r in plain.search(query, limit=10)
            ]
            got = [
                {"id": r["id"], "score": r["score"]}
                for r in sealed.search(query, limit=10)
            ]
            assert got == expected
            if query == "alpha bravo charlie":
                # The three-term search prunes on the sealed
                # store exactly as on the plain one. (The
                # one-term "alpha" search prunes nothing on
                # either: alpha is in every document, so its
                # idf — and every score — is tiny and no bound
                # falls below the limit-th score.)
                assert sealed.last_search_stats["candidates_pruned"] > 0
                assert (
                    sealed.last_search_stats["candidates_pruned"]
                    == plain.last_search_stats["candidates_pruned"]
                )
    finally:
        plain.close()
        sealed.close()


def test_gate_script_shape_and_small_run(tmp_path, monkeypatch):
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    spec = importlib.util.spec_from_file_location("huginn_candidate_pruning", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.DOCS_BENCHMARK == 5000
    assert module.DOCS_DISTINCT == 10000
    assert module.LIMIT == 10
    record = module.run_candidate_pruning(n_benchmark=150, n_distinct=200, repeat=2)
    assert record["package"] == "huginn"
    assert record["kind"] == "candidate_pruning"
    for section in ("benchmark", "distinct"):
        entry = record["details"][section]
        for query_stats in entry["queries"].values():
            stats = query_stats["stats"]
            assert stats["candidates_total"] >= stats["candidates_scored"]


def test_committed_gate_record_shape():
    record = json.loads(COMMITTED.read_text())
    assert record["package"] == "huginn"
    assert record["kind"] == "candidate_pruning"
    for key in (
        "recorded_at", "machine", "system", "platform", "node",
        "cpu_count", "load_avg", "python_version", "sqlite_version",
    ):
        assert key in record["environment"], f"environment block missing {key}"
    details = record["details"]
    assert details["benchmark"]["n_docs"] == 5000
    assert details["distinct"]["n_docs"] == 10000
    for section in ("benchmark", "distinct"):
        for query_stats in details[section]["queries"].values():
            stats = query_stats["stats"]
            assert "candidates_pruned" in stats
    assert record["results_ms"]["benchmark_search"] >= 0
    assert record["results_ms"]["distinct_search"] >= 0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
