"""RM-055 — Secure-defaults pins for muninn.

TH-15 (unsafe defaults) is answered by one recorded review
of every config default — `docs/SECURE_DEFAULTS.md` — and
pinned here so the review cannot silently rot: the exact
default of every field, the field set itself (a new field
fails until it has been reviewed and recorded), the off/on
posture of the security flags, and the rule that the
record and the guide name every field. No default changed
in RM-055; the passes against older trees are exactly the
defaults that were already reviewed-safe, and the failures
are the record/guide pins. When the suite runs against an
installed package outside a repo checkout the document
tests skip (the RM-007 pattern).
"""

import dataclasses
from pathlib import Path

import pytest

from muninn.config import MuninnConfig

EXPECTED_DEFAULTS = {
    "db_path": "~/.hermes/memory/muninn_hebbian.db",
    "learning_rate": 0.1,
    "decay_half_life_days": 30.0,
    "confidence_half_life_days": 90.0,
    "prune_threshold": 0.01,
    "consolidation_threshold": 0.8,
    "busy_timeout_ms": 5000,
    "backup_keep": 3,
    "auto_backup": True,
    "max_nodes": 20000,
    "max_content_bytes": 1048576,
    "max_metadata_bytes": 65536,
    "strict_path_safety": False,
    "debug_log_content": False,
    "store_encryption": False,
    "encryption_passphrase": None,
    "integrity_attestation": False,
    "integrity_passphrase": None,
    "max_spread_candidates": 100000,
    "cache_size": 0,
}


def _repo_root():
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "RAVENS_ROADMAP_2026-10-31.md").is_file():
            return parent
    return None


@pytest.fixture(scope="module")
def root():
    found = _repo_root()
    if found is None:
        pytest.skip("not running inside a repo checkout")
    return found


def test_every_config_default_is_the_reviewed_one():
    fields = {f.name for f in dataclasses.fields(MuninnConfig)}
    assert fields == set(EXPECTED_DEFAULTS), (
        "config field set changed — a new field must be "
        "reviewed in docs/SECURE_DEFAULTS.md (RM-055) in the "
        "same slice that adds it"
    )
    config = MuninnConfig()
    for name, expected in EXPECTED_DEFAULTS.items():
        assert getattr(config, name) == expected, (
            f"default of {name} changed — a default change "
            "must re-run the RM-055 review and update the "
            "record and the guides in the same commit"
        )


def test_dangerous_capabilities_are_off_by_default():
    config = MuninnConfig()
    assert config.debug_log_content is False
    assert config.store_encryption is False
    assert config.integrity_attestation is False
    # strict_path_safety=False is the one compatibility-kept
    # convenience default; its judgement is recorded, and
    # the pin here keeps the keep deliberate.
    assert config.strict_path_safety is False


def test_safety_positive_defaults_are_on():
    config = MuninnConfig()
    assert config.auto_backup is True
    assert config.backup_keep == 3


def test_no_secret_is_invented_by_default():
    config = MuninnConfig()
    assert config.encryption_passphrase is None
    assert config.integrity_passphrase is None
    text = repr(config)
    assert "encryption_passphrase" not in text
    assert "integrity_passphrase" not in text


def test_waits_and_ceilings_are_bounded_by_default():
    config = MuninnConfig()
    assert config.busy_timeout_ms > 0
    assert config.max_nodes >= 1
    assert config.max_content_bytes >= 1
    assert config.max_metadata_bytes >= 1
    assert config.max_spread_candidates >= 1
    assert config.cache_size >= 0


def test_review_record_names_every_field(root):
    record = (root / "docs" / "SECURE_DEFAULTS.md").read_text()
    assert "TH-15" in record
    assert "RM-055" in record
    for name in EXPECTED_DEFAULTS:
        assert f"`{name}`" in record, (
            f"secure-defaults record does not judge {name!r}"
        )


def test_guide_names_every_field(root):
    guide = (root / "docs" / "MUNINN_GUIDE.md").read_text()
    for name in EXPECTED_DEFAULTS:
        assert f"`{name}`" in guide, (
            f"Muninn guide does not name config field {name!r}"
        )
