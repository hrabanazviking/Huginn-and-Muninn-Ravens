"""RM-040 — SQL-injection audit battery, muninn (TH-01).

Two proofs, one law: **no caller value ever reaches SQL as
syntax.**

* The hostile battery: contents, categories, tags, metadata,
  paths, filter arguments, activation sources and update
  values carrying quotes, ``'; DROP TABLE`` payloads, comment
  markers, LIKE wildcards and unicode look-alikes are stored
  and retrieved **verbatim**, every table survives, and a
  filter carrying an injection payload matches nothing it
  should not (``' OR '1'='1`` is a literal string here, never
  a tautology). ``update()``'s one interpolated surface —
  column names — is proven closed: a hostile field *name*
  is a typed refusal, never SQL.
* The source audit: every ``execute`` / ``executemany`` /
  ``executescript`` call site in ``src/muninn`` is classified
  from its AST. A site is a string constant, one of the two
  pinned f-string templates (the ``int()``-cast
  ``busy_timeout`` PRAGMA; ``update()``'s assignments, whose
  keys come only from the validated allow-list — see
  ``docs/SQL_INJECTION_AUDIT.md``), or one of the three
  pinned variable sites (``schema_sql``, the static
  ``SCHEMA_SQL``; ``sql`` in the timestamp seed loop, drawn
  from a tuple of constants; ``sql`` in ``retrieve``, built
  from a constant base plus constant fragments with every
  value in the parameter list). Any new shape fails here
  until the audit is re-run and this pin updated.
"""

import ast
from pathlib import Path

import pytest

from muninn import HebbianMemory
from muninn.config import MuninnConfig
from muninn.errors import MuninnValidationError

HOSTILE_CONTENTS = [
    "'; DROP TABLE nodes; --",
    "Robert'); DROP TABLE nodes;--",
    "' OR '1'='1",
    '" OR 1=1 --',
    "a'; DELETE FROM nodes WHERE 1=1; --",
    "x' UNION SELECT * FROM sqlite_master --",
    "''' \"\"\" ;;; ---",
    "\\'; DROP TABLE hebbian_connections; \\",
    "line one\n'; DROP TABLE activation_log;\n-- tail",
    "’； DROP TABLE nodes; --",  # curly quote + fullwidth semicolon
    "‮'; DROP TABLE nodes; --",  # RTL override before the payload
    "100% _sure 'quoted'",
]

HOSTILE_CATEGORY = "x'; DROP TABLE nodes; --"
HOSTILE_TAG = "'; drop table nodes; --"  # tags are lower-cased + 64-capped by design


@pytest.fixture()
def mem(tmp_path):
    m = HebbianMemory(MuninnConfig(db_path=str(tmp_path / "m.db")))
    yield m
    m.close()


def _tables_intact(mem):
    stats = mem.stats()
    health = mem.health()
    assert health["status"] == "healthy"
    assert health["integrity"] == "ok"
    return stats


def test_hostile_contents_stored_and_retrieved_verbatim(mem):
    ids = [mem.remember(payload) for payload in HOSTILE_CONTENTS]
    assert len(set(ids)) == len(HOSTILE_CONTENTS)
    for node_id, payload in zip(ids, HOSTILE_CONTENTS, strict=True):
        assert mem.get_node(node_id).content == payload
    stats = _tables_intact(mem)
    assert stats["total_nodes"] == len(HOSTILE_CONTENTS)
    # The store still works for ordinary traffic afterwards.
    plain = mem.remember("an ordinary memory")
    assert mem.get_node(plain).content == "an ordinary memory"


def test_hostile_category_tag_metadata_and_path_round_trip(mem):
    node_id = mem.remember(
        "filed under hostile labels",
        category=HOSTILE_CATEGORY,
        path="a';drop/b",
        tags=[HOSTILE_TAG],
        metadata={"k'; drop": "v'; DROP TABLE nodes; --"},
    )
    node = mem.get_node(node_id)
    assert node.memory_type == HOSTILE_CATEGORY
    assert node.path == "a';drop/b"
    assert node.tags == [HOSTILE_TAG]
    assert node.metadata == {"k'; drop": "v'; DROP TABLE nodes; --"}
    assert [n.id for n in mem.get_by_path("a';drop/b")] == [node_id]
    assert [n.id for n in mem.retrieve(category=HOSTILE_CATEGORY)] == [node_id]
    assert [n.id for n in mem.retrieve(tags=[HOSTILE_TAG])] == [node_id]
    _tables_intact(mem)


def test_injection_filter_matches_nothing_it_should_not(mem):
    mem.remember("a perfectly ordinary fact", category="general")
    mem.remember("another ordinary fact", category="general")
    assert mem.retrieve(category="' OR '1'='1") == []
    assert mem.retrieve(query="'; DROP TABLE nodes; --") == []
    assert mem.retrieve(path="' OR '1'='1") == []
    stats = _tables_intact(mem)
    assert stats["total_nodes"] == 2


def test_like_wildcards_in_path_filter_are_literal(mem):
    pct = mem.remember("under the percent path", path="a%b/c")
    mem.remember("under the axb path", path="axb/c")
    found = mem.retrieve(path="a%b")
    assert [n.id for n in found] == [pct]
    _tables_intact(mem)


def test_hostile_activation_source_is_a_value_not_syntax(mem):
    node_id = mem.remember("to be activated")
    mem.activate(node_id, source="'; DROP TABLE activation_log; --")
    assert mem.activation_count(node_id) == 1
    _tables_intact(mem)


def test_update_value_injection_is_stored_verbatim(mem):
    node_id = mem.remember("before update")
    payload = "'; DROP TABLE nodes; --"
    assert mem.update(node_id, content=payload) is True
    assert mem.get_node(node_id).content == payload
    _tables_intact(mem)


def test_update_field_name_injection_is_refused_typed(mem):
    node_id = mem.remember("untouched by field-name injection")
    with pytest.raises(MuninnValidationError):
        mem.update(node_id, **{"path = 'pwned', content = 'x": "y"})
    with pytest.raises(MuninnValidationError):
        mem.update(node_id, **{"content; DROP TABLE nodes; --": "y"})
    node = mem.get_node(node_id)
    assert node.content == "untouched by field-name injection"
    assert node.path == ""
    _tables_intact(mem)


# ─── the source audit pin ────────────────────────────────────────

EXPECTED_FSTR_TEMPLATES = {
    "PRAGMA busy_timeout={int(busy_timeout_ms)}",
    "UPDATE nodes SET {assignments} WHERE id = ?",
    # RM-058: spread_activation's batched frontier query — the
    # only interpolated value is the generated placeholder list
    # (question marks only); every id still travels as a bound
    # parameter. This replaces the per-node constant SELECT, so
    # the site total below is unchanged.
    "SELECT memory_a_id, memory_b_id, strength FROM hebbian_connections"
    " WHERE memory_a_id IN ({placeholders}) AND strength >= ?"
    " ORDER BY memory_a_id ASC, memory_b_id ASC",
}
# Every SQL-shaped f-string anywhere in the source is one of
# the execute-site templates above (no SQL is built into a
# variable through an f-string in muninn).
EXPECTED_SQL_JOINED_ANYWHERE = EXPECTED_FSTR_TEMPLATES
EXPECTED_NAME_SITES = {"schema_sql": 1, "sql": 2, "count_sql": 1}
# RM-049: +3 sites — the _crypto probe's meta select + the
# named count_sql it runs, and the encryption-header insert in
# core (all constant SQL; the count arrives as a named constant
# from the caller, never built from values).
# RM-050: +5 sites — the _attest recompute select + meta
# select, and core's bootstrap select + header insert + the
# per-activation head executemany (all constant SQL).
# RM-051: +8 sites — the secure-forget purge machinery in
# _db.py: the secure_delete pragma read + set + three-way
# restore, and the two wal_checkpoint(TRUNCATE) + VACUUM
# purge stages (all constant SQL, no values at all).
EXPECTED_SITE_TOTAL = 97


def _source_dir():
    here = Path(__file__).resolve()
    for parent in here.parents:
        for candidate in (
            parent / "src" / "muninn",
            parent / "muninn" / "src" / "muninn",
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
        pytest.skip("not running inside a repo checkout (no src/muninn)")
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
