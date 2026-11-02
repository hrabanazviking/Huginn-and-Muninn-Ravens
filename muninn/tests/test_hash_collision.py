"""RM-047 — Hash-collision honesty for muninn.

Threat TH-08 (docs/THREAT_MODEL.md): Muninn's idempotent
store keys identity on (content_hash, category, path). The
hash is SHA-256, so a natural collision is implausible — but
the pre-slice code trusted the hash alone: the fallback after
``INSERT OR IGNORE`` fetched the existing row's id and
returned it, whatever content that row actually held. Two
different memories under one hash would have silently become
one memory.

The fix is a length+content double check on that fallback:
the stored text's length, the stored text itself, and its
kind (string vs JSON) must equal the incoming values before
the existing id is returned; anything else raises
``MuninnValidationError`` naming only the existing id, and
the existing node is left untouched.

SHA-256 cannot be collided on demand, so the collisions are
forced the way the roadmap's acceptance names: an injected
hash function. ``muninn.core._content_hash`` — the one hash
function the store path uses — is replaced with a constant,
so every content hashes alike. A planted-row test covers the
same refusal without injection (a row whose hash was forged
by raw SQL, the tamper shape).
"""

import hashlib

import pytest

import muninn.core
from muninn import HebbianMemory
from muninn.config import MuninnConfig
from muninn.errors import MuninnValidationError

FORCED_HASH = "f" * 64


@pytest.fixture
def forced_hash(monkeypatch):
    # raising=False: against a pre-RM-047 package (which has no
    # such seam) the fixture installs the name harmlessly and
    # the tests then fail on the merging behaviour itself —
    # the negation evidence this slice records.
    monkeypatch.setattr(
        muninn.core,
        "_content_hash",
        lambda text, is_json: FORCED_HASH,
        raising=False,
    )


def _memory(tmp_path):
    return HebbianMemory(MuninnConfig(db_path=str(tmp_path / "m.db")))


def test_forced_collision_different_length_is_refused(forced_hash, tmp_path):
    m = _memory(tmp_path)
    try:
        first = m.remember("short")
        with pytest.raises(MuninnValidationError) as caught:
            m.remember("a much longer different memory")
        assert str(caught.value) == (
            "content hash collision: a different memory already "
            f"holds this content hash (id {first}); refusing to merge"
        )
        # The existing memory is untouched and alone.
        assert m.get_node(first).content == "short"
        assert m.stats()["total_nodes"] == 1
    finally:
        m.close()


def test_forced_collision_same_length_is_refused(forced_hash, tmp_path):
    m = _memory(tmp_path)
    try:
        first = m.remember("alpha")
        # Same length, same forced hash, different content:
        # length alone would pass this pair — the exact-content
        # half of the double check is what refuses it.
        with pytest.raises(MuninnValidationError):
            m.remember("alphe")
        assert m.get_node(first).content == "alpha"
        assert m.stats()["total_nodes"] == 1
    finally:
        m.close()


def test_true_duplicate_under_forced_hash_still_merges(forced_hash, tmp_path):
    m = _memory(tmp_path)
    try:
        first = m.remember("same words", importance=5)
        again = m.remember("same words", importance=9)
        assert again == first
        assert m.stats()["total_nodes"] == 1
    finally:
        m.close()


def test_forced_hash_different_category_is_not_a_collision(
    forced_hash, tmp_path
):
    m = _memory(tmp_path)
    try:
        a = m.remember("shared text", category="fact")
        b = m.remember("other text", category="note")
        # The identity key includes the category, so the forced
        # hash alone never merges across it.
        assert a != b
        assert m.stats()["total_nodes"] == 2
    finally:
        m.close()


def test_forced_hash_different_path_is_not_a_collision(forced_hash, tmp_path):
    m = _memory(tmp_path)
    try:
        a = m.remember("shared text", path="a")
        b = m.remember("other text", path="b")
        assert a != b
        assert m.stats()["total_nodes"] == 2
    finally:
        m.close()


def test_forced_collision_string_vs_json_kind_is_refused(
    forced_hash, tmp_path
):
    m = _memory(tmp_path)
    try:
        # The stored texts are identical ('["a"]'); only the
        # kind differs (a literal string vs a JSON list). The
        # double check compares the kind too.
        first = m.remember('["a"]')
        with pytest.raises(MuninnValidationError):
            m.remember(["a"])
        assert m.get_node(first).content == '["a"]'
    finally:
        m.close()


def test_planted_row_with_forged_hash_is_refused(tmp_path):
    m = _memory(tmp_path)
    try:
        victim = "the incoming memory"
        real_hash = hashlib.sha256(("s:" + victim).encode()).hexdigest()
        conn = m._get_conn()
        conn.execute(
            "INSERT INTO nodes (content, content_is_json, content_hash,"
            " path, category, importance, emotional_valence, tags,"
            " metadata, created_at, updated_at)"
            " VALUES (?, 0, ?, '', 'general', 5, 0.0, '[]', '{}',"
            " '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')",
            ("planted different content", real_hash),
        )
        conn.commit()
        with pytest.raises(MuninnValidationError) as caught:
            m.remember(victim)
        assert "refusing to merge" in str(caught.value)
        assert "planted different content" not in str(caught.value)
        assert m.stats()["total_nodes"] == 1
    finally:
        m.close()


def test_real_hashes_still_dedupe_without_injection(tmp_path):
    m = _memory(tmp_path)
    try:
        a = m.remember("ordinary memory")
        b = m.remember("ordinary memory")
        c = m.remember("another memory")
        assert a == b != c
        assert m.stats()["total_nodes"] == 2
    finally:
        m.close()
