# Query plans (RM-067)

`EXPLAIN QUERY PLAN` proofs for the hot queries of both
packages. The pins live in `tests/test_query_plans.py` in
each package and run against a store built through the
public API, read on a fresh raw connection (the RM-058
pattern). The law of this slice: **a query that must ride
an index names that index in its pinned plan, so a schema
change that drops the index fails the suites loudly** —
each suite also carries a sensitivity test that drops the
index in a scratch copy and proves the plan changes.
Plans below are quoted from a probe run on seeded stores
(50 nodes / 50 documents) on SQLite 3.45.1; plan *shape*
(the index named, SEARCH vs SCAN, temp b-tree presence)
is the pinned contract, not the probe's exact wording
beyond those shapes.

## Muninn

| Query (caller) | Plan | Verdict |
|---|---|---|
| `SELECT * FROM nodes WHERE id = ?` (`get_node`) | `SEARCH nodes USING INTEGER PRIMARY KEY (rowid=?)` | key search |
| `get_associations` ordered read | `SEARCH hebbian_connections USING COVERING INDEX idx_conn_a_strength (memory_a_id=? AND strength>?)` | covering index, no temp b-tree (the RM-058 win, re-pinned here) |
| spread-activation frontier chunk (`memory_a_id IN (...)`) | `SEARCH ... USING COVERING INDEX idx_conn_a_strength` + `USE TEMP B-TREE FOR RIGHT PART OF ORDER BY` | index rides; the second sort key is finished by a temp b-tree over one chunk (≤500 ids) — accepted, stated |
| pair existence (`memory_a_id = ? AND memory_b_id = ?`) | `SEARCH hebbian_connections USING COVERING INDEX sqlite_autoindex_hebbian_connections_1` | table primary key |
| `SELECT COUNT(*) FROM activation_log WHERE memory_id = ?` (`activation_count`) | `SEARCH activation_log USING COVERING INDEX idx_activation_memory (memory_id=?)` | index |
| node_activation counter read | `SEARCH node_activation USING INTEGER PRIMARY KEY (rowid=?)` | key search |
| heal counter reconciliation (`GROUP BY memory_id` over `activation_log`) | `SCAN activation_log USING INDEX idx_activation_memory` | index supplies the grouping order — no temp b-tree |
| forget's edge delete (`memory_a_id = ? OR memory_b_id = ?`) | multi-index OR: PK index for the a-side, `idx_conn_b` for the b-side | both directions indexed |
| decay/consolidate chunk paging (`rowid > ?`) | `SEARCH hebbian_connections USING INTEGER PRIMARY KEY (rowid>?)` | key search (RM-064) |
| idempotent-store lookup (`content_hash, category, path`) | `SEARCH nodes USING COVERING INDEX sqlite_autoindex_nodes_1` | the UNIQUE constraint's index |
| `retrieve`'s filtered scan | `SCAN nodes` | **deliberate scan** — arbitrary filter combinations, bounded by `max_nodes`; pinned as a scan so an index added later is a deliberate pin update |
| `get_by_path` (`WHERE path = ?`) | `SCAN nodes` | **deliberate scan** — same bound, same reasoning; a path index is future work only if a profile ever shows pain here |

## Huginn (local backend)

| Query (caller) | Plan | Verdict |
|---|---|---|
| `SELECT * FROM documents WHERE id = ?` (`get`) | `SEARCH documents USING INTEGER PRIMARY KEY (rowid=?)` | key search |
| dedupe lookup (`content_hash = ? AND category = ?`) | `SEARCH documents USING COVERING INDEX sqlite_autoindex_documents_1` | the UNIQUE constraint's index |
| posting lists (`doc_terms WHERE term IN (...)`) | `SEARCH doc_terms USING INDEX idx_terms_term (term=?)` (the DISTINCT form adds `USE TEMP B-TREE FOR DISTINCT`) | term index — the search hot path |
| candidate term fetch (`doc_terms WHERE doc_id IN (...)`) | `SEARCH doc_terms USING COVERING INDEX sqlite_autoindex_doc_terms_1 (doc_id=?)` | table primary key (RM-061) |
| per-document terms (`WHERE doc_id = ?`) | `SEARCH doc_terms USING COVERING INDEX sqlite_autoindex_doc_terms_1` | table primary key |
| doc frequencies (`corpus_stats WHERE term IN (...)`) | `SEARCH corpus_stats USING INDEX sqlite_autoindex_corpus_stats_1 (term=?)` | table primary key |
| filtered document fetch (`id IN (...) AND category = ?`, RM-062) | `SEARCH documents USING INTEGER PRIMARY KEY (rowid=?)` | key search |
| vector survivors fetch (`doc_vectors WHERE doc_id IN (...)`, RM-062) | `SEARCH doc_vectors USING INTEGER PRIMARY KEY (rowid=?)` | key search |
| vector cap (`SELECT doc_id FROM doc_vectors ORDER BY doc_id LIMIT ?`, RM-062) | `SCAN doc_vectors`, no temp b-tree | **deliberate scan** — `doc_id` is the rowid, so the scan already walks in the required order and stops at the cap |
| vector count (`SELECT COUNT(*) FROM doc_vectors`) | `SCAN doc_vectors` | **deliberate scan** — a count over the primary-key table |

## What is not pinned, and why

Write statements (`INSERT`/`UPDATE` by key) are not
plan-pinned: their lookup side is the same key searches
above, and SQLite reports no plan detail for them beyond
it. `stats()`/`health()` count queries are full-table
counts by definition. Qdrant-backend queries are the
server's own plans — out of scope, as in RM-053.
