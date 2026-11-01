"""RM-017 — Config immutability for huginn.

``HuginnConfig`` is frozen after validation: a caller mutating the
dataclass mid-flight cannot change a live store's behaviour (most
pointedly, cannot flip its backend). The road to a different
configuration is ``dataclasses.replace``, which builds a new,
re-validated config — the constructor's ``**overrides`` already
take that road and must leave the caller's config untouched.
"""

import dataclasses

import pytest

from huginn import HuginnConfig, HuginnMemory
from huginn.errors import HuginnConfigurationError


def _cfg(tmp_path, **overrides):
    base = {"backend": "local", "local_db_path": str(tmp_path / "h.db")}
    base.update(overrides)
    return HuginnConfig(**base)


def test_config_fields_cannot_be_assigned(tmp_path):
    cfg = _cfg(tmp_path)
    for field, value in [
        ("backend", "qdrant"),
        ("local_db_path", str(tmp_path / "other.db")),
        ("qdrant_api_key", "secret"),
        ("embedder", "hashing"),
    ]:
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(cfg, field, value)
    assert cfg.backend == "local"
    assert cfg.qdrant_api_key is None


def test_mutation_attempt_cannot_flip_a_live_store_backend(tmp_path):
    cfg = _cfg(tmp_path)
    h = HuginnMemory(cfg)
    try:
        with pytest.raises(dataclasses.FrozenInstanceError):
            cfg.backend = "qdrant"
        assert h.health()["backend"] == "local"
        assert h.config.backend == "local"
    finally:
        h.close()


def test_replace_builds_a_new_config_and_leaves_the_original(tmp_path):
    cfg = _cfg(tmp_path)
    changed = dataclasses.replace(cfg, embedder="hashing")
    assert changed is not cfg
    assert changed.embedder == "hashing"
    assert cfg.embedder == "tfidf"


def test_replace_revalidates(tmp_path):
    cfg = _cfg(tmp_path)
    with pytest.raises(HuginnConfigurationError):
        dataclasses.replace(cfg, backend="bogus")
    with pytest.raises(HuginnConfigurationError):
        dataclasses.replace(cfg, vector_dim=1)


def test_constructor_overrides_do_not_mutate_the_callers_config(tmp_path):
    cfg = _cfg(tmp_path, embedder="tfidf")
    h = HuginnMemory(cfg, embedder="hashing")
    try:
        assert h.config.embedder == "hashing"
        assert cfg.embedder == "tfidf"
    finally:
        h.close()
