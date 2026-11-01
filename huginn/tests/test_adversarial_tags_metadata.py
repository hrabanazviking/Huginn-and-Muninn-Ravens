"""RM-036 — Adversarial tags, huginn.

The twin of muninn's slice (see that file for the full
statement). Huginn memories carry no caller metadata, so the
adversarial annotation surface here is the tags list itself.
Before this slice (measured by probe against the RM-035
packages):

- a tags list of 200,000 entries was accepted without bound,
  however large its stored form grew;
- a tag element nested 50,000 containers deep escaped
  ``upsert_memory`` as a raw ``RecursionError`` from the
  ``repr`` produced by the facade's ``str()`` coercion.

Defined now (docs/ADVERSARIAL_TAGS_METADATA.md), enforced in
the facade before any backend is touched, so the policy holds
on the local and Qdrant backends alike:

- one iterative depth bound, ``_MAX_STRUCTURE_DEPTH`` (100
  containers), over every tag element: deeper is the typed
  refusal ``tags nesting depth exceeds maximum of 100``;
- the RM-027 size ceiling applied uniformly: the cleaned tags
  list, measured as its JSON form in UTF-8 bytes (the form
  the local backend stores), must fit ``max_content_bytes``;
- a self-referential tag element keeps rendering through
  ``repr``'s ellipsis, as it always has;
- every refusal lands before any write: counts unchanged,
  the store keeps working.
"""

import json

import pytest

from huginn import HuginnMemory
from huginn.config import HuginnConfig
from huginn.errors import HuginnValidationError

DEPTH_MSG = "nesting depth exceeds maximum of 100"


@pytest.fixture()
def mem(tmp_path):
    h = HuginnMemory(
        HuginnConfig(backend="local", local_db_path=str(tmp_path / "h.db"))
    )
    yield h
    h.close()


def _deep_list(depth):
    root = cur = []
    for _ in range(depth):
        nxt = []
        cur.append(nxt)
        cur = nxt
    return root


def _tight(tmp_path, **overrides):
    return HuginnMemory(
        HuginnConfig(
            backend="local",
            local_db_path=str(tmp_path / "tight.db"),
            **overrides,
        )
    )


def test_deep_tag_element_refused_not_recursion_error(mem):
    with pytest.raises(HuginnValidationError, match="tags " + DEPTH_MSG):
        mem.upsert_memory("dtag", tags=[_deep_list(50_000)])
    assert mem.stats()["documents"] == 0


def test_tag_element_at_depth_bound_is_stored(mem):
    doc_id = mem.upsert_memory("bounded", tags=[_deep_list(99)])
    assert mem.get(doc_id)["tags"] == [str(_deep_list(99))]


def test_circular_tag_element_renders_with_ellipsis(mem):
    circular = []
    circular.append(circular)
    doc_id = mem.upsert_memory("ctag", tags=[circular])
    assert mem.get(doc_id)["tags"] == ["[[...]]"]


def test_shared_substructure_is_not_circular(mem):
    shared = [1, 2, 3]
    doc_id = mem.upsert_memory("dag", tags=[[shared, shared]])
    assert mem.get(doc_id)["tags"] == [str([shared, shared])]


def test_tags_at_ceiling_are_stored(tmp_path):
    h = _tight(tmp_path, max_content_bytes=64)
    tags = ["a" * 15, "b" * 15, "c" * 15]
    assert len(json.dumps(tags).encode("utf-8")) <= 64
    doc_id = h.upsert_memory("fits", tags=tags)
    assert h.get(doc_id)["tags"] == tags
    h.close()


def test_tags_above_ceiling_refused_typed_without_a_write(tmp_path):
    h = _tight(tmp_path, max_content_bytes=64)
    h.upsert_memory("seed")
    tags = ["t" * 30, "u" * 30]
    size = len(json.dumps(tags).encode("utf-8"))
    assert size > 64
    with pytest.raises(
        HuginnValidationError,
        match=rf"tags size {size} bytes exceeds max_content_bytes \(64 bytes\)",
    ):
        h.upsert_memory("too many tags", tags=tags)
    assert h.stats()["documents"] == 1
    h.close()


def test_enormous_tag_count_refused_under_default_ceiling(mem):
    with pytest.raises(HuginnValidationError, match="tags size .* exceeds"):
        mem.upsert_memory("flood", tags=[f"t{i}" for i in range(200_000)])
    assert mem.stats()["documents"] == 0
    # the store keeps working after the refusal
    assert mem.upsert_memory("still alive") is not None
