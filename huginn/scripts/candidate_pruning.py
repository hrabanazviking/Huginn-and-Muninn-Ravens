"""Huginn candidate pruning — RM-061 gate script.

Run: python scripts/candidate_pruning.py [--output candidate_pruning.json]

What it does:
- Seeds two fresh local stores and measures the fixed search
  workload on each, ``REPEAT`` timed searches per query, the
  median reported:
  * ``benchmark`` — the RM-020 benchmark corpus
    (``scripts/benchmark.py``'s formula documents, 5,000 docs,
    categories ``cat{i % 10}``) with the corpus's own four
    fixed queries at ``limit=10``, plus one category-filtered
    query;
  * ``distinct`` — a deterministic distinct-document corpus
    (``DOCS_DISTINCT`` documents of 20-79 synthetic terms
    each over a ``DISTINCT_VOCAB``-term vocabulary; the
    RM-057 atlas could only measure the
    benchmark corpus's 23 distinct documents, so search cost
    over distinct documents was NOT measured — this corpus
    closes that measurement gap for the local search) with
    three fixed queries at ``limit=10``.
- Inside every run, before any timing is quoted, each query's
  result is verified against a brute-force reference computed
  from the store's raw tables (every candidate's full term
  set scored with ``huginn.text``'s own TF-IDF/cosine): the
  pruned search must return exactly the reference's ids, in
  order, with exactly its scores. A mismatch raises instead
  of recording timings for a different search.
- The record carries the RM-006 environment block, the
  RM-020 corpus block for the benchmark corpus, the distinct
  corpus's parameters, and per query the
  ``last_search_stats`` accounting (candidates offered /
  scored / pruned — ``candidates_pruned`` reads 0 on a tree
  without RM-061, where the field does not exist yet).

Class: BENCH + UNIT (the parity check). This script is the
RM-061 acceptance gate: run unchanged on the pre- and
post-slice trees, it produces the before/after numbers.
Numbers on a loaded machine are indicative, not absolutes —
the environment block says so. Stores live on tmpfs (the
RM-005 storage class); local backend only, nothing external
is touched; a live Qdrant round-trip stays NOT PROVEN.
"""

import argparse
import json
import sqlite3
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import benchmark as _bench  # noqa: E402  (sibling script, path set above)

REPEAT = 15

DOCS_BENCHMARK = 5000
QUERIES_BENCHMARK = (
    "raven wisdom tree",
    "sword fire storm",
    "ship sea song",
    "wolf eye memory",
)
FILTERED_QUERY = "raven wisdom tree"
FILTERED_CATEGORY = "cat3"

DOCS_DISTINCT = 10000
DISTINCT_VOCAB = 1024
DISTINCT_DOC_WORDS = "20 + (i * 13) % 60"
QUERIES_DISTINCT = (
    "term100 term200 term37",
    "term5 term999 term300",
    "term248 term17 term800",
)

LIMIT = 10


def distinct_text(i):
    """One distinct-corpus document: a pure formula of the
    index (no randomness anywhere). The length varies with
    the index (20-79 tokens) and the term formula is
    quadratic in the position, so documents genuinely differ
    from each other — in content, in length, and in how
    strongly any query term speaks in them."""
    length = 20 + (i * 13) % 60
    return " ".join(
        f"term{(i * 7919 + j * 104729 + j * j * 31 + i * j * 7) % DISTINCT_VOCAB}"
        for j in range(length)
    )


def _reference_search(db_path, query_text, *, limit, category=None):
    """Brute-force TF-IDF search over the store's raw tables:
    every candidate's full term set, scored with the package's
    own ``sparse_tfidf`` / ``cosine`` — the unpruned road,
    computed independently of the backend's search code."""
    from huginn.text import cosine, sparse_tfidf, term_counts, tokenize

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        total_docs = int(
            conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        )
        q_counts = term_counts(tokenize(query_text))
        if not q_counts or total_docs == 0:
            return []
        placeholders = ",".join("?" * len(q_counts))
        candidate_ids = sorted(
            int(r[0])
            for r in conn.execute(
                f"SELECT DISTINCT doc_id FROM doc_terms WHERE term IN ({placeholders})",
                list(q_counts),
            ).fetchall()
        )
        if category:
            candidate_ids = [
                doc_id
                for doc_id in candidate_ids
                if conn.execute(
                    "SELECT category FROM documents WHERE id = ?", (doc_id,)
                ).fetchone()[0]
                == category
            ]
        if not candidate_ids:
            return []
        ph = ",".join("?" * len(candidate_ids))
        per_doc = {}
        all_terms = set(q_counts)
        for doc_id, term, tf in conn.execute(
            f"SELECT doc_id, term, tf FROM doc_terms WHERE doc_id IN ({ph})"
            " ORDER BY doc_id, term",
            candidate_ids,
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
        return [
            {"id": doc_id, "score": score} for score, doc_id in scored[:limit]
        ]
    finally:
        conn.close()


def _verify_parity(mem, db_path, query_text, *, category=None):
    """One search through the facade, checked exactly (ids in
    order, scores bit-for-bit) against the brute-force
    reference. Returns the facade's stats record."""
    results = mem.search(query_text, limit=LIMIT, category=category)
    reference = _reference_search(
        db_path, query_text, limit=LIMIT, category=category
    )
    got = [{"id": r["id"], "score": r["score"]} for r in results]
    if got != reference:
        raise AssertionError(
            f"parity failure for query {query_text!r} category={category!r}:\n"
            f"  search:    {got}\n  reference: {reference}"
        )
    return dict(mem.last_search_stats)


def _timed_searches(mem, query_text, *, category=None, repeat=REPEAT):
    times = []
    for _ in range(repeat):
        start = time.perf_counter()
        mem.search(query_text, limit=LIMIT, category=category)
        times.append((time.perf_counter() - start) * 1000)
    return statistics.median(times)


def _run_corpus(name, texts, queries, filtered, seed, repeat=REPEAT):
    from huginn import HuginnConfig, HuginnMemory

    tmp = tempfile.mkdtemp(prefix=f"huginn-pruning-{name}-")
    db_path = str(Path(tmp) / "pruning.db")
    mem = HuginnMemory(
        HuginnConfig(backend="local", local_db_path=db_path, auto_backup=False)
    )
    try:
        seed(mem, texts)
        per_query = {}
        medians = []
        for query in queries:
            stats = _verify_parity(mem, db_path, query)
            median = _timed_searches(mem, query, repeat=repeat)
            medians.append(median)
            per_query[query] = {"median_ms": median, "stats": stats}
            print(
                f"[{name}] search({query!r}) x{repeat}: median {median:8.2f} ms"
                f"  (total {stats['candidates_total']},"
                f" scored {stats['candidates_scored']},"
                f" pruned {stats.get('candidates_pruned', 0)})"
            )
        entry = {"queries": per_query, "median_ms": statistics.median(medians)}
        if filtered is not None:
            query, category = filtered
            stats = _verify_parity(mem, db_path, query, category=category)
            median = _timed_searches(mem, query, category=category, repeat=repeat)
            entry["filtered"] = {
                "query": query,
                "category": category,
                "median_ms": median,
                "stats": stats,
            }
            print(
                f"[{name}] search({query!r}, category={category!r}) x{repeat}:"
                f" median {median:8.2f} ms"
                f"  (total {stats['candidates_total']},"
                f" scored {stats['candidates_scored']},"
                f" pruned {stats.get('candidates_pruned', 0)})"
            )
        return entry
    finally:
        mem.close()


def run_candidate_pruning(
    n_benchmark=DOCS_BENCHMARK, n_distinct=DOCS_DISTINCT, repeat=REPEAT
):
    """Seed both corpora, verify parity, measure; return the
    full record. Sizes are parameters so tests can run the
    same shape small."""
    bench_texts = _bench.corpus_texts(n_benchmark)

    def seed_benchmark(mem, texts):
        for i, text in enumerate(texts):
            mem.upsert_memory(content=text, category=f"cat{i % 10}", importance=5)

    benchmark_entry = _run_corpus(
        "benchmark",
        bench_texts,
        QUERIES_BENCHMARK,
        (FILTERED_QUERY, FILTERED_CATEGORY),
        seed_benchmark,
        repeat=repeat,
    )
    benchmark_entry["corpus"] = _bench.corpus_block(bench_texts)
    benchmark_entry["n_docs"] = n_benchmark

    distinct_texts = [distinct_text(i) for i in range(n_distinct)]

    def seed_distinct(mem, texts):
        for text in texts:
            mem.upsert_memory(content=text, category="distinct", importance=5)

    distinct_entry = _run_corpus(
        "distinct", distinct_texts, QUERIES_DISTINCT, None, seed_distinct,
        repeat=repeat,
    )
    distinct_entry["corpus"] = {
        "generator": "distinct_text(i): 20 + (i*13) % 60 tokens of"
        " term[(i*7919 + j*104729 + j*j*31 + i*j*7) % 1024]",
        "vocab": DISTINCT_VOCAB,
        "doc_words": DISTINCT_DOC_WORDS,
        "distinct_documents": len(set(distinct_texts)),
    }
    distinct_entry["n_docs"] = n_distinct

    return {
        "package": "huginn",
        "schema": 1,
        "kind": "candidate_pruning",
        "environment": _bench.environment_block(),
        "results_ms": {
            "benchmark_search": benchmark_entry["median_ms"],
            "distinct_search": distinct_entry["median_ms"],
        },
        "details": {
            "limit": LIMIT,
            "repeat": repeat,
            "benchmark": benchmark_entry,
            "distinct": distinct_entry,
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None,
                        help="write the JSON record to this path")
    args = parser.parse_args(argv)
    record = run_candidate_pruning()
    env = record["environment"]
    print("environment:")
    for key in (
        "recorded_at", "machine", "system", "platform", "node",
        "cpu_count", "load_avg", "python_version", "sqlite_version",
    ):
        print(f"  {key}: {env[key]}")
    print(
        "medians: benchmark "
        f"{record['results_ms']['benchmark_search']:.2f} ms, distinct "
        f"{record['results_ms']['distinct_search']:.2f} ms"
    )
    if args.output is not None:
        args.output.write_text(json.dumps(record, indent=2) + "\n")
        print(f"record written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
