"""RM-034 — Unicode & encoding gauntlet, muninn.

Two halves, one law:

* **Valid Unicode is welcome, verbatim.** RTL scripts, emoji
  ZWJ sequences, combining marks, astral-plane characters —
  stored and returned exactly as given, never normalised,
  never folded: the decomposed and precomposed spellings of
  the same word are two different memories.
* **Lone surrogates are refused, typed.** A Python string can
  hold an unpaired surrogate (U+D800–U+DFFF) that UTF-8,
  JSON and SQLite cannot hold honestly. Before this slice such
  a value escaped as a raw ``UnicodeEncodeError`` from a hash
  or size ``.encode()``, died at the SQLite bind, or — worst —
  was silently stored as a JSON ``\\udXXX`` escape in tags /
  metadata / JSON content and came back as a string no other
  system can encode. Now every text that enters the store is
  checked first and refused with ``MuninnValidationError``
  (``… must not contain lone surrogates``), before any write.
"""

import pytest

from muninn import HebbianMemory
from muninn.config import MuninnConfig
from muninn.errors import MuninnValidationError

ARABIC = "مرحبا بالعالم، هذه ذاكرة"
HEBREW = "שלום עולם, זיכרון חזק"
FAMILY = "👨\u200d👩\u200d👧\u200d👦 gathering at the longhouse"
TECHNOLOGIST = "👩🏽\u200d💻 writes the runes"
DECOMPOSED = "cafe\u0301 society"  # e + combining acute
COMPOSED = "caf\u00e9 society"  # single precomposed é
ASTRAL = "𝄞 and 𐍈 are single code points"

SURROGATES = ["\ud800", "\udcff", "bad \ud800 end", "end \udfff", "\ud83d alone"]


@pytest.fixture()
def mem(tmp_path):
    m = HebbianMemory(MuninnConfig(db_path=str(tmp_path / "m.db")))
    yield m
    m.close()


# ─── the welcome half ─────────────────────────────────────────────


def test_rtl_content_round_trips_verbatim(mem):
    a = mem.remember(ARABIC)
    b = mem.remember(HEBREW)
    assert mem.get_node(a).content == ARABIC
    assert mem.get_node(b).content == HEBREW
    found = mem.retrieve(query="ذاكرة")
    assert [n.id for n in found] == [a]


def test_emoji_zwj_sequences_round_trip_verbatim(mem):
    a = mem.remember(FAMILY)
    b = mem.remember(TECHNOLOGIST)
    assert mem.get_node(a).content == FAMILY
    assert mem.get_node(b).content == TECHNOLOGIST


def test_combining_marks_are_not_normalised(mem):
    a = mem.remember(DECOMPOSED)
    b = mem.remember(COMPOSED)
    # No NFC/NFD folding anywhere: two spellings, two memories.
    assert a != b
    assert mem.get_node(a).content == DECOMPOSED
    assert mem.get_node(b).content == COMPOSED
    assert mem.get_node(a).content != mem.get_node(b).content


def test_astral_plane_characters_are_not_lone_surrogates(mem):
    node_id = mem.remember(ASTRAL)
    assert mem.get_node(node_id).content == ASTRAL


def test_unicode_path_tags_metadata_category_round_trip(mem):
    node_id = mem.remember(
        "filed under unicode",
        category="ذكريات",
        path="أرشيف/عائلة",
        tags=["عائلة", "👨\u200d👩\u200d👧\u200d👦"],
        metadata={"note": "café \u0301 vs café", "emoji": "👩🏽\u200d💻"},
    )
    node = mem.get_node(node_id)
    assert node.path == "أرشيف/عائلة"
    assert node.memory_type == "ذكريات"
    assert node.tags == ["عائلة", "👨\u200d👩\u200d👧\u200d👦"]
    assert node.metadata["note"] == "café \u0301 vs café"
    assert node.metadata["emoji"] == "👩🏽\u200d💻"
    by_path = mem.get_by_path("أرشيف/عائلة")
    assert [n.id for n in by_path] == [node_id]


# ─── the refusal half ─────────────────────────────────────────────


@pytest.mark.parametrize("bad", SURROGATES)
def test_lone_surrogate_content_rejected_typed_and_writes_nothing(mem, bad):
    before = mem.stats()["total_nodes"]
    with pytest.raises(MuninnValidationError) as excinfo:
        mem.remember(bad)
    assert "lone surrogates" in str(excinfo.value)
    assert mem.stats()["total_nodes"] == before


def test_lone_surrogate_json_content_rejected(mem):
    for bad in (
        {"k": "v \ud800"},
        {"\ud800": "v"},
        ["ok", {"deep": ["x\udcff"]}],
        ("tuple \ud800",),
    ):
        with pytest.raises(MuninnValidationError):
            mem.remember(bad)
    assert mem.stats()["total_nodes"] == 0


def test_lone_surrogate_metadata_rejected(mem):
    for bad_meta in (
        {"k": "v \ud800"},
        {"\ud800": "v"},
        {"nested": {"list": ["x\udcff"]}},
    ):
        with pytest.raises(MuninnValidationError):
            mem.remember("clean content", metadata=bad_meta)
    assert mem.stats()["total_nodes"] == 0


def test_lone_surrogate_tag_rejected(mem):
    with pytest.raises(MuninnValidationError):
        mem.remember("clean content", tags=["fine", "bad \ud800"])
    assert mem.stats()["total_nodes"] == 0


def test_lone_surrogate_path_rejected_on_write_and_read(mem):
    with pytest.raises(MuninnValidationError):
        mem.remember("clean content", path="a/\ud800")
    with pytest.raises(MuninnValidationError):
        mem.get_by_path("a/\ud800")
    with pytest.raises(MuninnValidationError):
        mem.get_children("\ud800")
    assert mem.stats()["total_nodes"] == 0


def test_lone_surrogate_category_rejected(mem):
    with pytest.raises(MuninnValidationError):
        mem.remember("clean content", category="cat\ud800")
    assert mem.stats()["total_nodes"] == 0


def test_lone_surrogate_update_rejected_and_node_unchanged(mem):
    node_id = mem.remember("original content", metadata={"k": "v"})
    for kwargs in (
        {"content": "new \ud800"},
        {"metadata": {"k": "v \ud800"}},
        {"tags": ["t\ud800"]},
        {"path": "p/\ud800"},
        {"category": "c\ud800"},
    ):
        with pytest.raises(MuninnValidationError):
            mem.update(node_id, **kwargs)
    node = mem.get_node(node_id)
    assert node.content == "original content"
    assert node.metadata == {"k": "v"}
    assert node.path == ""


def test_lone_surrogate_retrieve_query_rejected(mem):
    mem.remember("something clean")
    with pytest.raises(MuninnValidationError):
        mem.retrieve(query="bad \ud800")
    with pytest.raises(MuninnValidationError):
        mem.retrieve(tags=["t\ud800"])
