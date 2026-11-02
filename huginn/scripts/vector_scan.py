"""Huginn vector scan — RM-062 gate script.

Run: python scripts/vector_scan.py [--output vector_scan.json]
     (set TMPDIR to a filesystem that can hold a ~0.75 GB
     store for the scale corpus — /var/tmp on the build VM)

What it does:
- Seeds two fresh local stores in embedder mode
  (``embedder="hashing"``, the shipped default
  ``vector_dim=384``) and measures the fixed vector-search
  workload on each — an unfiltered search, a category-filtered
  search (``cat3``, one tenth of the store) and an
  importance-filtered search (``min_importance=9``, two
  tenths) — ``REPEAT`` timed searches per query, the median
  reported:
  * ``api`` — ``DOCS_API`` documents of the RM-061
    distinct-document corpus, seeded through the public
    ``upsert_memory`` API (categories ``cat{i % 10}``,
    importance ``(i % 10) + 1``), under the shipped default
    ``max_search_candidates=10000``;
  * ``scale`` — ``DOCS_SCALE`` documents, seeded by direct
    construction: the store file is created by a real open,
    then the ``documents`` + ``doc_vectors`` rows are
    inserted in one transaction (same content-hash function
    and the hashing embedder's own vectors the upsert road
    would store; the term index is intentionally left empty
    — the vector road never reads it, and a TF-IDF search on
    this store would find nothing). Seeding through the
    public API at this scale costs ~6 ms per document of
    per-call commit + term indexing that this slice does not
    measure; the *search* under measurement runs entirely
    through the public API on a real store file either way.
    The corpus texts carry a per-index ``marker{i}`` token
    so all ``DOCS_SCALE`` documents are genuinely distinct
    (the RM-061 formula alone repeats with a period below
    this scale). The store is opened with
    ``max_search_candidates=200000`` — a recorded override,
    because the shipped 10,000 ceiling would cap the scan at
    10k candidates by design (RM-053) and the roadmap asks
    for the scan itself measured at 100k documents.
- Inside every run, before any timing is quoted, each
  query's result is verified against a brute-force reference
  computed by streaming the store's raw tables (every stored
  vector decoded once, the RM-053 cap and the
  category/importance filters applied in the reference's own
  code, scored with ``huginn.text``'s dense cosine): the
  backend search must return exactly the reference's ids, in
  order, with exactly its scores. A mismatch raises instead
  of recording timings for a different search.
- The record carries the RM-006 environment block, the
  RM-020 corpus block for the api corpus, the scale corpus's
  parameters + store size, the seed method per corpus, and
  per query the ``last_search_stats`` accounting
  (candidates offered / scored — ``candidates_total`` on a
  tree without the RM-062 prefilter still counts every
  stored vector, because the old road fetched them all).

Class: BENCH + UNIT (the parity check). This script is the
RM-062 acceptance gate: run unchanged on the pre- and
post-slice trees, it produces the before/after numbers.
Numbers on a loaded machine are indicative, not absolutes —
the environment block says so. Stores live on tmpfs (the
RM-005 storage class); local backend only, nothing external
is touched; a live Qdrant round-trip and the
sentence-transformers path stay NOT PROVEN.
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

DOCS_API = 10000
DOCS_SCALE = 100000
SCALE_CAP = 200000
VECTOR_DIM = 384
REPEAT_API = 5
REPEAT_SCALE = 3
LIMIT = 10
QUERY = "term100 term200 term37"
CATEGORY = "cat3"
MIN_IMPORTANCE = 9

# (name, search kwargs) — the fixed workload, both corpora.
WORKLOAD = (
    ("unfiltered", {}),
    ("category", {"category": CATEGORY}),
    ("importance", {"min_importance": MIN_IMPORTANCE}),
)

SEED_TS = "2026-01-01T00:00:00+00:00"
_SEED_BATCH = 5000


def distinct_text(i):
    """The RM-061 distinct-corpus document formula (kept
    byte-identical so the api corpus is the corpus RM-061
    measured): 20-79 tokens over a 1,024-term vocabulary,
    quadratic in the position."""
    length = 20 + (i * 13) % 60
    return " ".join(
        f"term{(i * 7919 + j * 104729 + j * j * 31 + i * j * 7) % 1024}"
        for j in range(length)
    )


def scale_text(i):
    """One scale-corpus document: the RM-061 formula plus a
    per-index marker token, so documents stay genuinely
    distinct at 100k (the bare formula repeats)."""
    return distinct_text(i) + f" marker{i}"


def _reference_searches(db_path, query_vec, cap):
    """Brute-force vector search over the store's raw tables,
    for every workload entry in one streaming pass: every
    stored vector decoded once, cap (lowest ids) then
    category/importance filters applied here — independently
    of the backend's search code. Returns {name: [{id, score}]}.
    """
    from huginn.text import dense_cosine

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        docs = {
            int(r[0]): (r[1], int(r[2]))
            for r in conn.execute(
                "SELECT id, category, importance FROM documents"
            ).fetchall()
        }
        scored = {name: [] for name, _ in WORKLOAD}
        rows = conn.execute(
            "SELECT doc_id, vector FROM doc_vectors ORDER BY doc_id"
        )
        seen = 0
        for doc_id, vector_text in rows:
            if seen >= cap:
                break
            seen += 1
            doc_id = int(doc_id)
            if doc_id not in docs:
                continue
            category, importance = docs[doc_id]
            vector = json.loads(vector_text)
            for name, kwargs in WORKLOAD:
                if kwargs.get("category") and category != kwargs["category"]:
                    continue
                if importance < kwargs.get("min_importance", 1):
                    continue
                score = dense_cosine(query_vec, vector)
                if score > 0.0:
                    scored[name].append((score, doc_id))
        out = {}
        for name, pairs in scored.items():
            pairs.sort(key=lambda item: (-item[0], item[1]))
            out[name] = [
                {"id": doc_id, "score": score}
                for score, doc_id in pairs[:LIMIT]
            ]
        return out
    finally:
        conn.close()


def _verify_parity(mem, db_path, cap):
    """Every workload search through the facade, checked
    exactly (ids in order, scores bit-for-bit) against the
    brute-force reference. Returns {name: stats record}."""
    from huginn.text import HashingEmbedder

    query_vec = HashingEmbedder(VECTOR_DIM).embed(QUERY)
    reference = _reference_searches(db_path, query_vec, cap)
    stats = {}
    for name, kwargs in WORKLOAD:
        results = mem.search(QUERY, limit=LIMIT, **kwargs)
        got = [{"id": r["id"], "score": r["score"]} for r in results]
        if got != reference[name]:
            raise AssertionError(
                f"parity failure for {name} search:\n"
                f"  search:    {got}\n  reference: {reference[name]}"
            )
        stats[name] = dict(mem.last_search_stats)
    return stats


def _timed_searches(mem, kwargs, repeat):
    times = []
    for _ in range(repeat):
        start = time.perf_counter()
        mem.search(QUERY, limit=LIMIT, **kwargs)
        times.append((time.perf_counter() - start) * 1000)
    return statistics.median(times)


def _run_workload(mem, db_path, cap, repeat, label):
    stats = _verify_parity(mem, db_path, cap)
    per_query = {}
    medians = []
    for name, kwargs in WORKLOAD:
        median = _timed_searches(mem, kwargs, repeat)
        medians.append(median)
        per_query[name] = {"median_ms": median, "stats": stats[name]}
        s = stats[name]
        print(
            f"[{label}] search({name}) x{repeat}: median {median:9.2f} ms"
            f"  (total {s['candidates_total']}, scored {s['candidates_scored']},"
            f" capped {s['capped']})"
        )
    return {"queries": per_query, "median_ms": statistics.median(medians)}


def _run_api_corpus(n_docs, repeat):
    from huginn import HuginnConfig, HuginnMemory

    texts = [distinct_text(i) for i in range(n_docs)]
    tmp = tempfile.mkdtemp(prefix="huginn-vscan-api-")
    db_path = str(Path(tmp) / "vscan.db")
    mem = HuginnMemory(
        HuginnConfig(
            backend="local", local_db_path=db_path,
            embedder="hashing", auto_backup=False,
        )
    )
    try:
        for i, text in enumerate(texts):
            mem.upsert_memory(
                content=text, category=f"cat{i % 10}", importance=(i % 10) + 1
            )
        entry = _run_workload(mem, db_path, mem.config.max_search_candidates,
                              repeat, "api")
        entry["n_docs"] = mem.health()["documents"]
        entry["corpus"] = _bench.corpus_block(texts)
        entry["seed"] = "public upsert_memory API"
        entry["config_overrides"] = {}
        entry["store_bytes"] = Path(db_path).stat().st_size
        return entry
    finally:
        mem.close()


def _run_scale_corpus(n_docs, repeat):
    from huginn import HuginnConfig, HuginnMemory
    from huginn.local_backend import _content_hash
    from huginn.text import HashingEmbedder

    tmp = tempfile.mkdtemp(prefix="huginn-vscan-scale-")
    db_path = str(Path(tmp) / "vscan.db")
    config = HuginnConfig(
        backend="local", local_db_path=db_path,
        embedder="hashing", auto_backup=False,
        max_search_candidates=SCALE_CAP,
    )
    # Create the store through a real open, then construct the
    # rows directly (see the module docstring for why, and for
    # exactly what this seed does and does not build).
    mem = HuginnMemory(config)
    mem.health()
    mem.close()
    embedder = HashingEmbedder(VECTOR_DIM)
    conn = sqlite3.connect(db_path)
    try:
        doc_id = 0
        for start in range(0, n_docs, _SEED_BATCH):
            doc_rows = []
            vec_rows = []
            for i in range(start, min(start + _SEED_BATCH, n_docs)):
                text = scale_text(i)
                category = f"cat{i % 10}"
                doc_id += 1
                doc_rows.append((
                    doc_id, text, _content_hash(text, category), category,
                    (i % 10) + 1, "[]", 0.0, SEED_TS, SEED_TS,
                ))
                vec_rows.append((doc_id, json.dumps(embedder.embed(text))))
            conn.executemany(
                "INSERT INTO documents"
                " (id, content, content_hash, category, importance, tags,"
                "  emotional_valence, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                doc_rows,
            )
            conn.executemany(
                "INSERT INTO doc_vectors (doc_id, vector) VALUES (?, ?)",
                vec_rows,
            )
        conn.commit()
    finally:
        conn.close()
    mem = HuginnMemory(config)
    try:
        entry = _run_workload(mem, db_path, SCALE_CAP, repeat, "scale")
        entry["n_docs"] = mem.health()["documents"]
        entry["corpus"] = {
            "generator": "scale_text(i): RM-061 distinct_text(i)"
            " + ' marker{i}' token",
            "distinct_documents": n_docs,
        }
        entry["seed"] = (
            "direct construction: documents + doc_vectors rows in one"
            " transaction (hashing embedder vectors, upsert content"
            " hashes); term index intentionally empty"
        )
        entry["config_overrides"] = {"max_search_candidates": SCALE_CAP}
        entry["store_bytes"] = Path(db_path).stat().st_size
        return entry
    finally:
        mem.close()


def run_vector_scan(
    n_api=DOCS_API, n_scale=DOCS_SCALE,
    repeat_api=REPEAT_API, repeat_scale=REPEAT_SCALE,
):
    """Seed both corpora, verify parity, measure; return the
    full record. Sizes are parameters so tests can run the
    same shape small."""
    api_entry = _run_api_corpus(n_api, repeat_api)
    scale_entry = _run_scale_corpus(n_scale, repeat_scale)
    return {
        "package": "huginn",
        "schema": 1,
        "kind": "vector_scan",
        "environment": _bench.environment_block(),
        "results_ms": {
            "api_unfiltered": api_entry["queries"]["unfiltered"]["median_ms"],
            "api_category": api_entry["queries"]["category"]["median_ms"],
            "api_importance": api_entry["queries"]["importance"]["median_ms"],
            "scale_unfiltered": scale_entry["queries"]["unfiltered"]["median_ms"],
            "scale_category": scale_entry["queries"]["category"]["median_ms"],
            "scale_importance": scale_entry["queries"]["importance"]["median_ms"],
        },
        "details": {
            "limit": LIMIT,
            "query": QUERY,
            "category": CATEGORY,
            "min_importance": MIN_IMPORTANCE,
            "vector_dim": VECTOR_DIM,
            "embedder": "hashing",
            "api": api_entry,
            "scale": scale_entry,
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None,
                        help="write the JSON record to this path")
    args = parser.parse_args(argv)
    record = run_vector_scan()
    env = record["environment"]
    print("environment:")
    for key in (
        "recorded_at", "machine", "system", "platform", "node",
        "cpu_count", "load_avg", "python_version", "sqlite_version",
    ):
        print(f"  {key}: {env[key]}")
    print("medians (ms):")
    for key, value in record["results_ms"].items():
        print(f"  {key}: {value:.2f}")
    if args.output is not None:
        args.output.write_text(json.dumps(record, indent=2) + "\n")
        print(f"record written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
