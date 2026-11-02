"""RM-040 — SQL-injection audit battery, huginn (TH-01).

Two proofs, one law: **no caller value ever reaches SQL as
syntax** (local backend; the Qdrant backend issues no SQL).

* The hostile battery: contents, categories and tags carrying
  quotes, ``'; DROP TABLE`` payloads, comment markers and
  unicode look-alikes are stored and retrieved **verbatim**,
  every table survives, and a search carrying an injection
  payload — above all as its category filter — matches
  nothing it should not (``' OR '1'='1`` is a literal string
  here, never a tautology). The ``IN (?,?,…)`` placeholder
  strings are exercised at width: a many-term hostile query
  still binds every term as a value.
* The source audit: every ``execute`` / ``executemany`` /
  ``executescript`` call site in ``src/huginn`` is classified
  from its AST. A site is a string constant, one of the four
  pinned f-string templates (the ``int()``-cast
  ``busy_timeout`` PRAGMA; the three ``IN`` placeholder
  strings, each built from ``len()`` of a value collection
  and nothing else), or one of the two pinned variable sites
  (``schema_sql``, the static ``SCHEMA_SQL``; ``sql`` in
  ``_candidate_docs_locked``, built from a constant base plus
  constant filter fragments with every value in the
  parameter list). Any new shape fails here until the audit
  is re-run and this pin updated — see
  ``docs/SQL_INJECTION_AUDIT.md``.
"""

import ast
from pathlib import Path

import pytest

from huginn import HuginnConfig, HuginnMemory

HOSTILE_CONTENTS = [
    "zebra '; DROP TABLE documents; --",
    "zebra Robert'); DROP TABLE documents;--",
    "zebra ' OR '1'='1",
    'zebra " OR 1=1 --',
    "zebra a'; DELETE FROM documents WHERE 1=1; --",
    "zebra x' UNION SELECT * FROM sqlite_master --",
    "zebra ''' \"\"\" ;;; ---",
    "zebra \\'; DROP TABLE doc_terms; \\",
    "zebra line one\n'; DROP TABLE corpus_stats;\n-- tail",
    "zebra ’； DROP TABLE documents; --",  # curly quote + fullwidth ;
    "zebra ‮'; DROP TABLE documents; --",  # RTL override before payload
]

HOSTILE_CATEGORY = "x'; DROP TABLE documents; --"
HOSTILE_TAG = "'; DROP TABLE documents; --"


@pytest.fixture()
def mem(tmp_path):
    m = HuginnMemory(
        HuginnConfig(backend="local", local_db_path=str(tmp_path / "h.db"))
    )
    yield m
    m.close()


def _tables_intact(mem):
    health = mem.health()
    assert health["status"] == "healthy"
    assert health["integrity"] == "ok"
    return health


def test_hostile_contents_stored_and_retrieved_verbatim(mem):
    ids = [mem.upsert_memory(payload) for payload in HOSTILE_CONTENTS]
    assert len(set(ids)) == len(HOSTILE_CONTENTS)
    for doc_id, payload in zip(ids, HOSTILE_CONTENTS, strict=True):
        assert mem.get(doc_id)["content"] == payload
    health = _tables_intact(mem)
    assert health["documents"] == len(HOSTILE_CONTENTS)
    plain = mem.upsert_memory("zebra an ordinary memory")
    assert mem.get(plain)["content"] == "zebra an ordinary memory"


def test_hostile_category_and_tags_round_trip(mem):
    doc_id = mem.upsert_memory(
        "zebra filed under hostile labels",
        category=HOSTILE_CATEGORY,
        tags=[HOSTILE_TAG],
    )
    doc = mem.get(doc_id)
    assert doc["category"] == HOSTILE_CATEGORY
    assert doc["tags"] == [HOSTILE_TAG]
    found = mem.search("zebra", category=HOSTILE_CATEGORY)
    assert [d["id"] for d in found] == [doc_id]
    _tables_intact(mem)


def test_injection_category_filter_matches_nothing_it_should_not(mem):
    mem.upsert_memory("zebra a perfectly ordinary fact", category="general")
    mem.upsert_memory("zebra another ordinary fact", category="general")
    assert mem.search("zebra", category="' OR '1'='1") == []
    assert mem.search("zebra", category="general' OR '1'='1' --") == []
    health = _tables_intact(mem)
    assert health["documents"] == 2


def test_hostile_query_terms_are_values_not_syntax(mem):
    doc_id = mem.upsert_memory("zebra quokka wombat nugget")
    found = mem.search("zebra '; DROP TABLE documents; --")
    assert [d["id"] for d in found] == [doc_id]
    wide = " ".join(f"term{i}" for i in range(50)) + " zebra"
    found = mem.search(wide)
    assert [d["id"] for d in found] == [doc_id]
    health = _tables_intact(mem)
    assert health["documents"] == 1


def test_explicit_id_upsert_with_hostile_content(mem):
    payload = "zebra '; DROP TABLE documents; --"
    doc_id = mem.upsert_memory(payload, memory_id=4242)
    assert doc_id == 4242
    assert mem.get(doc_id)["content"] == payload
    _tables_intact(mem)


# ─── the source audit pin ────────────────────────────────────────

EXPECTED_FSTR_TEMPLATES = {
    "PRAGMA busy_timeout={int(busy_timeout_ms)}",
    "SELECT DISTINCT doc_id FROM doc_terms WHERE term IN ({placeholders})",
    "SELECT doc_id, term, tf FROM doc_terms WHERE doc_id IN ({ph})",
    "SELECT term, doc_freq FROM corpus_stats WHERE term IN ({tph})",
    # RM-061: the posting-list read — query terms x candidate
    # ids, both placeholder lists built from len() of a value
    # collection, every value bound.
    "SELECT doc_id, term, tf FROM doc_terms WHERE term IN ({tph})"
    " AND doc_id IN ({ph})",
    # RM-061: the per-candidate total-token aggregate the
    # pruning bound reads (same IN placeholder discipline).
    "SELECT doc_id, SUM(tf) FROM doc_terms WHERE doc_id IN ({ph})"
    " GROUP BY doc_id",
}
# Every SQL-shaped f-string anywhere in the source (the
# _candidate_docs_locked base reaches execute() via the
# pinned `sql` variable, so it is pinned here too).
EXPECTED_SQL_JOINED_ANYWHERE = EXPECTED_FSTR_TEMPLATES | {
    "SELECT * FROM documents WHERE id IN ({placeholders})",
}
EXPECTED_NAME_SITES = {"schema_sql": 1, "sql": 1, "count_sql": 1}
# RM-049: +3 sites — the _crypto probe's meta select + the
# named count_sql it runs, and the encryption-header insert in
# the local backend (all constant SQL; the count arrives as a
# named constant from the caller, never built from values).
# RM-051: +8 sites — the secure-forget purge machinery in
# _db.py: the secure_delete pragma read + set + three-way
# restore, and the two wal_checkpoint(TRUNCATE) + VACUUM
# purge stages (all constant SQL, no values at all).
# RM-061: +4 sites net — the candidate-pruning search road
# in local_backend: the query-term doc_freq lookup, the
# corpus-max doc_freq constant, the total-token aggregate
# and the posting-list read (new templates above), and one
# added per-batch doc_freq lookup reusing the pinned IN
# template; the old road's single full-term fetch and
# all-terms doc_freq lookup are the per-batch fetches,
# evolved, not additions.
EXPECTED_SITE_TOTAL = 57


def _source_dir():
    here = Path(__file__).resolve()
    for parent in here.parents:
        for candidate in (
            parent / "src" / "huginn",
            parent / "huginn" / "src" / "huginn",
        ):
            root = candidate
            while root.parent != root and not (
                root / "RAVENS_ROADMAP_2026-10-31.md"
            ).is_file():
                root = root.parent
            if candidate.is_dir() and (root / "RAVENS_ROADMAP_2026-10-31.md").is_file():
                return candidate
    return None


def _audit_sites():
    src = _source_dir()
    if src is None:
        pytest.skip("not running inside a repo checkout (no src/huginn)")
    sites = []
    for path in sorted(src.rglob("*.py")):
        text = path.read_text()
        for node in ast.walk(ast.parse(text)):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in ("execute", "executemany", "executescript"):
                continue
            arg = node.args[0] if node.args else None
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                sites.append(("const", arg.value))
            elif isinstance(arg, ast.JoinedStr):
                template = "".join(
                    str(v.value)
                    if isinstance(v, ast.Constant)
                    else "{" + str(ast.get_source_segment(text, v.value)) + "}"
                    for v in arg.values
                )
                sites.append(("fstr", template))
            elif isinstance(arg, ast.Name):
                sites.append(("name", arg.id))
            else:
                sites.append(("other", ast.dump(arg)[:80]))
    return sites


def test_every_sql_site_is_constant_or_a_pinned_closed_shape():
    sites = _audit_sites()
    assert len(sites) == EXPECTED_SITE_TOTAL
    assert [s for s in sites if s[0] == "other"] == []
    fstr_templates = {template for kind, template in sites if kind == "fstr"}
    assert fstr_templates == EXPECTED_FSTR_TEMPLATES
    names = {}
    for kind, name in sites:
        if kind == "name":
            names[name] = names.get(name, 0) + 1
    assert names == EXPECTED_NAME_SITES


_SQL_KEYWORDS = ("SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "PRAGMA")


def test_no_other_sql_shaped_fstring_exists_anywhere():
    src = _source_dir()
    if src is None:
        pytest.skip("not running inside a repo checkout")
    found = set()
    for path in sorted(src.rglob("*.py")):
        text = path.read_text()
        for node in ast.walk(ast.parse(text)):
            if not isinstance(node, ast.JoinedStr):
                continue
            template = "".join(
                str(v.value)
                if isinstance(v, ast.Constant)
                else "{" + str(ast.get_source_segment(text, v.value)) + "}"
                for v in node.values
            )
            if any(kw in template for kw in _SQL_KEYWORDS):
                found.add(template)
    assert found == EXPECTED_SQL_JOINED_ANYWHERE
