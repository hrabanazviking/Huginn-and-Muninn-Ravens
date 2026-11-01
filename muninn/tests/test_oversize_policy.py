"""RM-027 — Oversize content policy, muninn.

Before this slice both content and metadata were accepted at
any size. Now each carries an explicit, configurable ceiling
(``MuninnConfig.max_content_bytes`` /
``max_metadata_bytes``): content is measured in UTF-8 bytes of
the stored text (the raw string, or its JSON serialization
for non-string content), metadata in UTF-8 bytes of its
serialized JSON form. Above the ceiling the write is refused
with a typed :class:`MuninnValidationError` before anything is
stored; at and below it, the write lands exactly as before.

Acceptance, per the roadmap: boundary tests at, above and
below the ceiling — for both ceilings, on both write paths
(``remember`` and ``update``).
"""

import json

import pytest

from muninn import HebbianMemory
from muninn.config import MuninnConfig
from muninn.errors import MuninnConfigurationError, MuninnValidationError


def _mem(tmp_path, name="m.db", **overrides):
    return HebbianMemory(
        MuninnConfig(db_path=str(tmp_path / name), **overrides)
    )


def test_default_ceilings_are_the_documented_values():
    cfg = MuninnConfig(db_path="x.db")
    assert cfg.max_content_bytes == 1048576  # 1 MiB
    assert cfg.max_metadata_bytes == 65536  # 64 KiB


def test_content_below_and_at_ceiling_is_stored(tmp_path):
    m = _mem(tmp_path, max_content_bytes=16)
    below = m.remember("a" * 15)
    at = m.remember("b" * 16)
    assert m.get_node(below).content == "a" * 15
    assert m.get_node(at).content == "b" * 16
    m.close()


def test_content_above_ceiling_refused_without_a_write(tmp_path):
    m = _mem(tmp_path, max_content_bytes=16)
    m.remember("seed")
    before = m.stats()["total_nodes"]
    with pytest.raises(MuninnValidationError) as excinfo:
        m.remember("c" * 17)
    assert str(excinfo.value) == (
        "content size 17 bytes exceeds max_content_bytes (16 bytes)"
    )
    assert m.stats()["total_nodes"] == before
    # the store still works after the refusal
    ok = m.remember("after")
    assert m.get_node(ok).content == "after"
    m.close()


def test_content_size_counts_utf8_bytes_not_characters(tmp_path):
    # "é" is 2 bytes in UTF-8: five of them cost 10 bytes.
    m = _mem(tmp_path, "tight.db", max_content_bytes=9)
    with pytest.raises(MuninnValidationError):
        m.remember("é" * 5)
    m.close()
    m = _mem(tmp_path, "exact.db", max_content_bytes=10)
    node_id = m.remember("é" * 5)
    assert m.get_node(node_id).content == "é" * 5
    m.close()


def test_json_content_is_measured_as_its_serialized_text(tmp_path):
    content = {"a": "12345678"}
    serialized = json.dumps(content, sort_keys=True)
    size = len(serialized.encode("utf-8"))
    m = _mem(tmp_path, "at.db", max_content_bytes=size)
    node_id = m.remember(content)
    assert m.get_node(node_id).content == content
    m.close()
    m = _mem(tmp_path, "over.db", max_content_bytes=size - 1)
    with pytest.raises(MuninnValidationError):
        m.remember(content)
    m.close()


def test_metadata_below_at_and_above_ceiling(tmp_path):
    metadata = {"k": "x" * 10}
    size = len(json.dumps(metadata, sort_keys=True).encode("utf-8"))
    m = _mem(tmp_path, "at.db", max_metadata_bytes=size)
    node_id = m.remember("meta", metadata=metadata)
    assert m.get_node(node_id).metadata == metadata
    m.close()
    m = _mem(tmp_path, "over.db", max_metadata_bytes=size - 1)
    with pytest.raises(MuninnValidationError) as excinfo:
        m.remember("meta", metadata=metadata)
    assert str(excinfo.value) == (
        f"metadata size {size} bytes exceeds "
        f"max_metadata_bytes ({size - 1} bytes)"
    )
    assert m.stats()["total_nodes"] == 0
    m.close()


def test_update_paths_enforce_both_ceilings(tmp_path):
    m = _mem(tmp_path, max_content_bytes=16, max_metadata_bytes=16)
    node_id = m.remember("orig", metadata={"k": 1})
    with pytest.raises(MuninnValidationError):
        m.update(node_id, content="z" * 17)
    with pytest.raises(MuninnValidationError):
        m.update(node_id, metadata={"k": "x" * 32})
    node = m.get_node(node_id)
    assert node.content == "orig"
    assert node.metadata == {"k": 1}
    # at-ceiling updates still land
    assert m.update(node_id, content="z" * 16)
    assert m.get_node(node_id).content == "z" * 16
    m.close()


def test_ceiling_config_values_are_validated(tmp_path):
    for field in ("max_content_bytes", "max_metadata_bytes"):
        for bad in (0, -3, "big", float("nan"), None, []):
            with pytest.raises(MuninnConfigurationError):
                MuninnConfig(db_path=str(tmp_path / "c.db"), **{field: bad})
    # the frozen-config road to a variant re-validates (RM-017)
    from dataclasses import replace

    cfg = MuninnConfig(db_path=str(tmp_path / "c.db"))
    small = replace(cfg, max_content_bytes=8)
    assert small.max_content_bytes == 8
    with pytest.raises(MuninnConfigurationError):
        replace(cfg, max_metadata_bytes=0)
