"""RM-036 — Adversarial tags/metadata, muninn.

The shapes a hostile or careless caller hands the annotation
payload: metadata and JSON content nested thousands of
containers deep, self-referential structures, and tags lists
of enormous length. Before this slice (measured by probe
against the RM-035 packages):

- metadata or content nested 5,000 deep escaped ``remember``
  as a raw ``RecursionError`` — from the recursive RM-034
  surrogate walk or from ``json.dumps`` itself;
- a tags list of 200,000 entries was accepted without bound,
  however large its stored form grew.

Defined now (docs/ADVERSARIAL_TAGS_METADATA.md):

- one iterative depth bound, ``_MAX_STRUCTURE_DEPTH`` (100
  containers), checked before every recursive walk, over
  JSON-shaped content, metadata (``remember`` and ``update``)
  and every tag element (``remember``, ``update`` and the
  ``retrieve`` filter): deeper is the typed refusal
  ``{field} nesting depth exceeds maximum of 100``;
- the RM-027 size ceilings applied uniformly: the stored
  (cleaned) tags list, measured as its JSON form in UTF-8
  bytes, must fit ``max_metadata_bytes`` — the annotation
  ceiling that already bounds metadata;
- self-referential content/metadata keep their established
  typed serializability refusals (the depth walk does not
  descend into a container already on its path; ``json.dumps``
  refuses the cycle), and a self-referential tag element keeps
  rendering through ``repr``'s ellipsis, as it always has;
- every refusal lands before any write: counts unchanged,
  the store keeps working.
"""

import json

import pytest

from muninn import HebbianMemory
from muninn.config import MuninnConfig
from muninn.errors import MuninnValidationError

DEPTH_MSG = "nesting depth exceeds maximum of 100"


def _mem(tmp_path, name="m.db", **overrides):
    return HebbianMemory(MuninnConfig(db_path=str(tmp_path / name), **overrides))


def _deep_dict(depth):
    root = cur = {}
    for _ in range(depth):
        cur["a"] = {}
        cur = cur["a"]
    return root


def _deep_list(depth):
    root = cur = []
    for _ in range(depth):
        nxt = []
        cur.append(nxt)
        cur = nxt
    return root


def _count(m):
    return m.stats()["total_nodes"]


# ─── depth: metadata ──────────────────────────────────────────────


def test_metadata_at_depth_bound_is_stored(tmp_path):
    m = _mem(tmp_path)
    node_id = m.remember("at bound", metadata=_deep_dict(99))
    assert m.get_node(node_id).metadata == _deep_dict(99)
    m.close()


def test_metadata_above_depth_bound_refused_typed(tmp_path):
    m = _mem(tmp_path)
    m.remember("seed")
    with pytest.raises(MuninnValidationError, match="metadata " + DEPTH_MSG):
        m.remember("too deep", metadata=_deep_dict(101))
    assert _count(m) == 1
    m.close()


def test_metadata_thousands_deep_refused_not_recursion_error(tmp_path):
    m = _mem(tmp_path)
    with pytest.raises(MuninnValidationError, match=DEPTH_MSG):
        m.remember("abyss", metadata=_deep_dict(5000))
    assert _count(m) == 0
    m.close()


def test_update_metadata_above_depth_bound_refused_typed(tmp_path):
    m = _mem(tmp_path)
    node_id = m.remember("victim", metadata={"a": 1})
    with pytest.raises(MuninnValidationError, match="metadata " + DEPTH_MSG):
        m.update(node_id, metadata=_deep_dict(5000))
    assert m.get_node(node_id).metadata == {"a": 1}
    m.close()


# ─── depth: JSON-shaped content ───────────────────────────────────


def test_content_at_depth_bound_is_stored(tmp_path):
    m = _mem(tmp_path)
    node_id = m.remember(_deep_list(99))
    assert m.get_node(node_id).content == _deep_list(99)
    m.close()


def test_content_thousands_deep_refused_not_recursion_error(tmp_path):
    m = _mem(tmp_path)
    with pytest.raises(MuninnValidationError, match="content " + DEPTH_MSG):
        m.remember(_deep_list(5000))
    assert _count(m) == 0
    # the store keeps working after the refusal
    assert m.remember("still alive") is not None
    m.close()


# ─── self-referential structures keep their established refusals ──


def test_circular_metadata_refused_as_not_serializable(tmp_path):
    m = _mem(tmp_path)
    circular = {}
    circular["loop"] = circular
    with pytest.raises(MuninnValidationError, match="metadata must be JSON-serializable"):
        m.remember("circ", metadata=circular)
    assert _count(m) == 0
    m.close()


def test_circular_content_refused_as_not_serializable(tmp_path):
    m = _mem(tmp_path)
    circular = []
    circular.append(circular)
    with pytest.raises(
        MuninnValidationError, match="content must be a string or JSON-serializable"
    ):
        m.remember(circular)
    assert _count(m) == 0
    m.close()


def test_shared_substructure_is_not_circular(tmp_path):
    m = _mem(tmp_path)
    shared = {"x": [1, 2, 3]}
    node_id = m.remember("dag", metadata={"a": shared, "b": shared})
    assert m.get_node(node_id).metadata == {"a": shared, "b": shared}
    m.close()


def test_circular_tag_element_renders_with_ellipsis(tmp_path):
    m = _mem(tmp_path)
    circular = []
    circular.append(circular)
    node_id = m.remember("ctag", tags=[circular])
    assert m.get_node(node_id).tags == ["[[...]]"]
    m.close()


# ─── adversarial tag elements ─────────────────────────────────────


def test_deep_tag_element_refused_not_recursion_error(tmp_path):
    m = _mem(tmp_path)
    with pytest.raises(MuninnValidationError, match="tags " + DEPTH_MSG):
        m.remember("dtag", tags=[_deep_list(5000)])
    assert _count(m) == 0
    m.close()


def test_deep_tag_filter_refused_in_retrieve(tmp_path):
    m = _mem(tmp_path)
    m.remember("seed", tags=["one"])
    with pytest.raises(MuninnValidationError, match="tags " + DEPTH_MSG):
        m.retrieve(tags=[_deep_list(5000)])
    m.close()


# ─── enormous tags: the RM-027 ceiling applied uniformly ──────────


def test_tags_at_ceiling_are_stored(tmp_path):
    m = _mem(tmp_path, max_metadata_bytes=64)
    tags = ["a" * 15, "b" * 15, "c" * 15]
    assert len(json.dumps(tags).encode("utf-8")) <= 64
    node_id = m.remember("fits", tags=tags)
    assert m.get_node(node_id).tags == tags
    m.close()


def test_tags_above_ceiling_refused_typed_without_a_write(tmp_path):
    m = _mem(tmp_path, max_metadata_bytes=64)
    m.remember("seed")
    tags = ["t" * 30, "u" * 30]
    size = len(json.dumps(tags).encode("utf-8"))
    assert size > 64
    with pytest.raises(
        MuninnValidationError,
        match=rf"tags size {size} bytes exceeds max_metadata_bytes \(64 bytes\)",
    ):
        m.remember("too many tags", tags=tags)
    assert _count(m) == 1
    m.close()


def test_enormous_tag_count_refused_under_default_ceiling(tmp_path):
    m = _mem(tmp_path)
    with pytest.raises(MuninnValidationError, match="tags size .* exceeds"):
        m.remember("flood", tags=[f"t{i}" for i in range(200_000)])
    assert _count(m) == 0
    m.close()


def test_update_tags_above_ceiling_refused_typed(tmp_path):
    m = _mem(tmp_path, max_metadata_bytes=64)
    node_id = m.remember("victim", tags=["small"])
    with pytest.raises(MuninnValidationError, match="tags size .* exceeds"):
        m.update(node_id, tags=["t" * 30, "u" * 30])
    assert m.get_node(node_id).tags == ["small"]
    m.close()
