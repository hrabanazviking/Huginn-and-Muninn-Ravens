"""RM-028 — Pathological node paths for muninn.

Node paths are store-internal hierarchical labels (``/``-separated),
never filesystem paths. This suite pins the defined behaviour from
docs/PATHOLOGICAL_PATHS.md:

* every spelling of one logical path normalises to one stored
  path — empty segments, ``.`` segments, leading/trailing slashes
  collapse; ``..`` climbs one level and clamps at the root (a store
  path cannot escape its own root);
* only ``/`` separates segments — backslashes and unicode
  look-alike separators are ordinary segment characters;
* ``%`` / ``_`` / ``\\`` inside a segment are literal characters,
  never LIKE wildcards, in every prefix read;
* paths are strings with two ceilings — at most 64 segments and
  at most 2048 UTF-8 bytes once normalised — and a violation, or a
  non-string path, is a typed ``MuninnValidationError`` raised
  before any write.
"""

import pytest

from muninn import HebbianMemory, MuninnValidationError
from muninn.config import MuninnConfig


def _mem(tmp_path, name="m.db"):
    return HebbianMemory(MuninnConfig(db_path=str(tmp_path / name)))


def test_dotdot_climbs_and_clamps_at_root(tmp_path):
    m = _mem(tmp_path)
    a = m.remember("climber", path="a/b/../c")
    assert m.get_node(a).path == "a/c"
    b = m.remember("rooted", path="../x")
    assert m.get_node(b).path == "x"
    c = m.remember("overclimber", path="a/../../y")
    assert m.get_node(c).path == "y"
    m.close()


def test_empty_segments_dots_and_slashes_collapse(tmp_path):
    m = _mem(tmp_path)
    first = m.remember("one logical path", path="a//b/")
    for spelling in ("/a/b", "a/./b", "a/b", "//a///b//"):
        again = m.remember("one logical path", path=spelling)
        assert again == first, f"spelling {spelling!r} forked the node"
    assert m.get_node(first).path == "a/b"
    m.close()


def test_root_spellings_are_all_the_root(tmp_path):
    m = _mem(tmp_path)
    first = m.remember("at the root", path="")
    for spelling in ("/", "//", ".", "..", "./..", "/./"):
        assert m.remember("at the root", path=spelling) == first
    assert m.get_node(first).path == ""
    m.close()


def test_write_and_read_spellings_agree(tmp_path):
    m = _mem(tmp_path)
    nid = m.remember("findable", path="a//b/")
    assert [n.id for n in m.get_by_path("a/b")] == [nid]
    assert [n.id for n in m.get_by_path("/a/b/")] == [nid]
    assert [n.id for n in m.retrieve(path="a//")] == [nid]
    children = m.get_children("a/")
    assert [n.id for n in children["a/b"]] == [nid]
    m.close()


def test_move_and_update_normalise(tmp_path):
    m = _mem(tmp_path)
    nid = m.remember("mover", path="start")
    assert m.move(nid, "x/../y/") is True
    assert m.get_node(nid).path == "y"
    assert m.update(nid, path="p//q") is True
    assert m.get_node(nid).path == "p/q"
    m.close()


def test_non_string_paths_are_typed_errors(tmp_path):
    m = _mem(tmp_path)
    nid = m.remember("anchored", path="a")
    before = m.stats()
    for bad in (123, None, ["a"], b"a/b", 1.5):
        with pytest.raises(MuninnValidationError):
            m.remember("nope", path=bad)
        with pytest.raises(MuninnValidationError):
            m.get_by_path(bad)
        with pytest.raises(MuninnValidationError):
            m.get_children(bad)
        with pytest.raises(MuninnValidationError):
            m.move(nid, bad)
    assert m.stats() == before
    assert m.get_node(nid).path == "a"
    m.close()


def test_depth_ceiling_boundary(tmp_path):
    m = _mem(tmp_path)
    legal = "/".join(["a"] * 64)
    nid = m.remember("deep but legal", path=legal)
    assert m.get_node(nid).path == legal
    before = m.stats()
    with pytest.raises(MuninnValidationError):
        m.remember("too deep", path="/".join(["a"] * 65))
    assert m.stats() == before
    m.close()


def test_byte_ceiling_counts_utf8_bytes(tmp_path):
    m = _mem(tmp_path)
    at = "é" * 1024  # 2048 UTF-8 bytes exactly
    nid = m.remember("at the ceiling", path=at)
    assert m.get_node(nid).path == at
    before = m.stats()
    with pytest.raises(MuninnValidationError):
        m.remember("over the ceiling", path="x" * 2049)
    with pytest.raises(MuninnValidationError):
        m.remember("over by bytes", path="é" * 1025)  # 2050 bytes
    assert m.stats() == before
    m.close()


def test_backslash_and_unicode_separators_are_ordinary(tmp_path):
    m = _mem(tmp_path)
    backslashed = m.remember("windowsy", path=r"a\b")
    fullwidth = m.remember("fullwidth", path="a／b")  # U+FF0F
    assert m.get_node(backslashed).path == r"a\b"
    assert m.get_node(fullwidth).path == "a／b"
    # Neither is a child of "a": each is a single root-level segment.
    assert m.get_children("a") == {}
    tree = m.get_tree_structure()
    assert r"a\b" in tree and "a／b" in tree
    m.close()


def test_like_wildcards_in_segments_are_literal(tmp_path):
    m = _mem(tmp_path)
    under = m.remember("under", path="a_b/c")
    m.remember("other", path="aXb/c")
    children = m.get_children("a_b")
    assert list(children) == ["a_b/c"]
    assert [n.id for n in children["a_b/c"]] == [under]
    assert [n.id for n in m.retrieve(path="a_b")] == [under]
    pct = m.remember("percent", path="100%/x")
    assert [n.id for n in m.get_children("100%")["100%/x"]] == [pct]
    assert m.get_children("100") == {}
    m.close()


def test_get_children_of_root_returns_every_pathed_node(tmp_path):
    m = _mem(tmp_path)
    m.remember("root node", path="")
    a = m.remember("level one", path="a")
    b = m.remember("level two", path="a/b")
    children = m.get_children("")
    assert [n.id for n in children["a"]] == [a]
    assert [n.id for n in children["a/b"]] == [b]
    assert "" not in children
    m.close()


def test_deep_legal_nesting_round_trips(tmp_path):
    m = _mem(tmp_path)
    deep = "/".join(f"level{i}" for i in range(64))
    nid = m.remember("deep", path=deep)
    assert [n.id for n in m.get_by_path(deep)] == [nid]
    parent = "/".join(f"level{i}" for i in range(63))
    assert [n.id for n in m.get_children(parent)[deep]] == [nid]
    m.close()
