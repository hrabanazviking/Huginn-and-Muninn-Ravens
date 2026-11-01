"""RM-034 — Unicode & encoding gauntlet, huginn.

The twin of muninn's gauntlet (see that file for the full
statement): valid Unicode — RTL scripts, emoji ZWJ sequences,
combining marks, astral-plane characters — is stored and
returned verbatim, never normalised; a lone surrogate
(U+D800–U+DFFF, unencodable in UTF-8 and unholdable by JSON /
SQLite honestly) is refused with ``HuginnValidationError``
(``… must not contain lone surrogates``) in the facade, before
any backend is touched, so the policy holds on the local and
Qdrant backends alike. Before this slice a surrogate content
string escaped as a raw ``UnicodeEncodeError`` from the size
check, a surrogate category died at the SQLite bind, a
surrogate tag was silently stored as a JSON escape, and a
surrogate query silently searched for nothing.

``fly`` keeps its ancestor discipline: a refused query comes
home as an error flight naming the refusal, never a raise.
"""

import pytest

from huginn import HuginnMemory, semantic_search
from huginn.config import HuginnConfig
from huginn.errors import HuginnValidationError

ARABIC = "مرحبا بالعالم، هذه ذاكرة قوية"
HEBREW = "שלום עולם, זיכרון חזק"
FAMILY = "👨\u200d👩\u200d👧\u200d👦 family memory gathering"
DECOMPOSED = "cafe\u0301 memory note"
COMPOSED = "caf\u00e9 memory note"
ASTRAL = "𝄞 music and 𐍈 letters memory"


@pytest.fixture()
def mem(tmp_path):
    h = HuginnMemory(
        HuginnConfig(backend="local", local_db_path=str(tmp_path / "h.db"))
    )
    yield h
    h.close()


# ─── the welcome half ─────────────────────────────────────────────


def test_rtl_content_round_trips_and_searches(mem):
    a = mem.upsert_memory(ARABIC)
    b = mem.upsert_memory(HEBREW)
    assert mem.get(a)["content"] == ARABIC
    assert mem.get(b)["content"] == HEBREW
    hits = mem.search("ذاكرة")
    assert [hit["id"] for hit in hits] == [a]


def test_emoji_zwj_content_round_trips_verbatim(mem):
    doc_id = mem.upsert_memory(FAMILY)
    assert mem.get(doc_id)["content"] == FAMILY
    hits = mem.search("family")
    assert [hit["id"] for hit in hits] == [doc_id]


def test_combining_marks_are_not_normalised(mem):
    a = mem.upsert_memory(DECOMPOSED)
    b = mem.upsert_memory(COMPOSED)
    assert a != b
    assert mem.get(a)["content"] == DECOMPOSED
    assert mem.get(b)["content"] == COMPOSED


def test_astral_plane_characters_are_not_lone_surrogates(mem):
    doc_id = mem.upsert_memory(ASTRAL)
    assert mem.get(doc_id)["content"] == ASTRAL


# ─── the refusal half ─────────────────────────────────────────────


def test_lone_surrogate_content_rejected_and_writes_nothing(mem):
    mem.upsert_memory("one clean memory")
    before = mem.health()["documents"]
    for bad in ("\ud800", "bad \udcff memory", "end \udfff"):
        with pytest.raises(HuginnValidationError) as excinfo:
            mem.upsert_memory(bad)
        assert "lone surrogates" in str(excinfo.value)
    assert mem.health()["documents"] == before


def test_lone_surrogate_category_and_tag_rejected(mem):
    with pytest.raises(HuginnValidationError):
        mem.upsert_memory("clean memory", category="cat\ud800")
    with pytest.raises(HuginnValidationError):
        mem.upsert_memory("clean memory", tags=["bad \ud800"])
    with pytest.raises(HuginnValidationError):
        mem.search("clean", category="cat\ud800")
    assert mem.health()["documents"] == 0


def test_lone_surrogate_search_query_rejected(mem):
    mem.upsert_memory("a clean memory")
    with pytest.raises(HuginnValidationError):
        mem.search("bad \ud800")


def test_lone_surrogate_analysis_and_semantic_search_rejected(mem):
    with pytest.raises(HuginnValidationError):
        mem.analyze_query("bad \ud800")
    with pytest.raises(HuginnValidationError):
        semantic_search("bad \ud800", ["a good memory"])
    with pytest.raises(HuginnValidationError):
        semantic_search("memory", ["a bad \ud800 document"])


def test_lone_surrogate_fly_comes_home_as_error_flight(mem):
    flight = mem.fly("bad \ud800")
    assert flight.results == []
    assert flight.error is not None
    assert "lone surrogates" in flight.error


def test_lone_surrogate_multi_hop_rejected(mem):
    with pytest.raises(HuginnValidationError):
        mem.multi_hop_retrieve("bad \ud800")
