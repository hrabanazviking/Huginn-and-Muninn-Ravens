"""RM-027 — Oversize content policy, huginn.

Before this slice content was accepted at any size. Now it
carries an explicit, configurable ceiling
(``HuginnConfig.max_content_bytes``), measured in UTF-8 bytes
of the content. Above the ceiling the write is refused with a
typed :class:`HuginnValidationError` in the facade — before
any backend is touched, so the policy holds identically on
the local and Qdrant backends. At and below the ceiling the
write lands exactly as before.

(Huginn memories carry no caller metadata argument, so there
is no metadata ceiling in this package; Muninn's config
carries both ceilings.)

Acceptance, per the roadmap: boundary tests at, above and
below the ceiling.
"""

import pytest

from huginn import HuginnConfig, HuginnMemory
from huginn.errors import HuginnConfigurationError, HuginnValidationError


def _mem(tmp_path, name="h.db", **overrides):
    return HuginnMemory(
        HuginnConfig(
            backend="local",
            local_db_path=str(tmp_path / name),
            **overrides,
        )
    )


def test_default_ceiling_is_the_documented_value():
    cfg = HuginnConfig()
    assert cfg.max_content_bytes == 1048576  # 1 MiB


def test_content_below_and_at_ceiling_is_stored(tmp_path):
    h = _mem(tmp_path, max_content_bytes=16)
    below = h.upsert_memory("a" * 15)
    at = h.upsert_memory("b" * 16)
    assert h.get(below)["content"] == "a" * 15
    assert h.get(at)["content"] == "b" * 16
    h.close()


def test_content_above_ceiling_refused_without_a_write(tmp_path):
    h = _mem(tmp_path, max_content_bytes=16)
    h.upsert_memory("seed")
    before = h.health()["documents"]
    with pytest.raises(HuginnValidationError) as excinfo:
        h.upsert_memory("c" * 17)
    assert str(excinfo.value) == (
        "content size 17 bytes exceeds max_content_bytes (16 bytes)"
    )
    assert h.health()["documents"] == before
    # the store still works after the refusal
    ok = h.upsert_memory("after")
    assert h.get(ok)["content"] == "after"
    h.close()


def test_content_size_counts_utf8_bytes_not_characters(tmp_path):
    # "é" is 2 bytes in UTF-8: five of them cost 10 bytes.
    h = _mem(tmp_path, "tight.db", max_content_bytes=9)
    with pytest.raises(HuginnValidationError):
        h.upsert_memory("é" * 5)
    h.close()
    h = _mem(tmp_path, "exact.db", max_content_bytes=10)
    doc_id = h.upsert_memory("é" * 5)
    assert h.get(doc_id)["content"] == "é" * 5
    h.close()


def test_ceiling_config_values_are_validated(tmp_path):
    for bad in (0, -3, "big", float("nan"), None, []):
        with pytest.raises(HuginnConfigurationError):
            HuginnConfig(
                backend="local",
                local_db_path=str(tmp_path / "c.db"),
                max_content_bytes=bad,
            )
    # the frozen-config road to a variant re-validates (RM-017)
    from dataclasses import replace

    cfg = HuginnConfig(
        backend="local", local_db_path=str(tmp_path / "c.db")
    )
    small = replace(cfg, max_content_bytes=8)
    assert small.max_content_bytes == 8
    with pytest.raises(HuginnConfigurationError):
        replace(cfg, max_content_bytes=0)
