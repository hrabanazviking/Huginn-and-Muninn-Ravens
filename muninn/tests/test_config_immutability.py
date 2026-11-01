"""RM-017 — Config immutability for muninn.

``MuninnConfig`` is frozen after validation: a caller mutating the
dataclass mid-flight cannot change a live store's behaviour. The
road to a different configuration is ``dataclasses.replace``,
which builds a new, re-validated config — the constructor's
``**overrides`` already take that road and must leave the caller's
config untouched.
"""

import dataclasses

import pytest

from muninn import HebbianMemory
from muninn.config import MuninnConfig
from muninn.errors import MuninnConfigurationError


def _cfg(tmp_path, **overrides):
    return MuninnConfig(db_path=str(tmp_path / "m.db"), **overrides)


def test_config_fields_cannot_be_assigned(tmp_path):
    cfg = _cfg(tmp_path)
    for field, value in [
        ("db_path", str(tmp_path / "other.db")),
        ("learning_rate", 0.9),
        ("max_nodes", 5),
        ("auto_backup", False),
    ]:
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(cfg, field, value)
    assert cfg.learning_rate == 0.1
    assert cfg.max_nodes == 20000


def test_mutation_attempt_cannot_change_a_live_store(tmp_path):
    cfg = _cfg(tmp_path, learning_rate=0.1)
    m = HebbianMemory(cfg)
    try:
        with pytest.raises(dataclasses.FrozenInstanceError):
            cfg.learning_rate = 1.0
        m.activate_batch([1, 2])
        # First wiring starts at exactly the configured learning
        # rate — the attempted 1.0 never reached the store.
        assert m.get_associations(1)[0]["strength"] == pytest.approx(0.1)
        assert m.config.learning_rate == 0.1
    finally:
        m.close()


def test_replace_builds_a_new_config_and_leaves_the_original(tmp_path):
    cfg = _cfg(tmp_path)
    changed = dataclasses.replace(cfg, learning_rate=0.5)
    assert changed is not cfg
    assert changed.learning_rate == 0.5
    assert cfg.learning_rate == 0.1


def test_replace_revalidates(tmp_path):
    cfg = _cfg(tmp_path)
    with pytest.raises(MuninnConfigurationError):
        dataclasses.replace(cfg, learning_rate=2.0)
    with pytest.raises(MuninnConfigurationError):
        dataclasses.replace(cfg, max_nodes=0)


def test_constructor_overrides_do_not_mutate_the_callers_config(tmp_path):
    cfg = _cfg(tmp_path, learning_rate=0.1)
    m = HebbianMemory(cfg, learning_rate=0.5)
    try:
        assert m.config.learning_rate == 0.5
        assert cfg.learning_rate == 0.1
    finally:
        m.close()
