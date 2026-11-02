"""RM-055 — Secure-defaults pins for huginn.

TH-15 (unsafe defaults) is answered by one recorded review
of every config default — `docs/SECURE_DEFAULTS.md` — and
pinned here so the review cannot silently rot: the exact
default of every field, the field set itself (a new field
fails until it has been reviewed and recorded), the off/on
posture of the security flags, the default transport
posture (loopback plaintext accepted, remote plaintext
refused at construction), and the rule that the record
and the guide name every field. No default changed in
RM-055; the passes against older trees are exactly the
defaults that were already reviewed-safe, and the failures
are the record/guide pins. When the suite runs against an
installed package outside a repo checkout the document
tests skip (the RM-007 pattern).
"""

import dataclasses
from pathlib import Path

import pytest

from huginn.config import HuginnConfig
from huginn.errors import HuginnConfigurationError

EXPECTED_DEFAULTS = {
    "backend": "auto",
    "qdrant_url": "http://localhost:6333",
    "qdrant_api_key": None,
    "collection_name": "huginn_memories",
    "local_db_path": "~/.hermes/memory/huginn_local.db",
    "embedder": "tfidf",
    "vector_dim": 384,
    "st_model": "all-MiniLM-L6-v2",
    "qdrant_timeout": 2.0,
    "busy_timeout_ms": 5000,
    "backup_keep": 3,
    "auto_backup": True,
    "max_content_bytes": 1048576,
    "strict_path_safety": False,
    "debug_log_content": False,
    "allow_insecure_http": False,
    "store_encryption": False,
    "encryption_passphrase": None,
    "max_search_candidates": 10000,
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
    fields = {f.name for f in dataclasses.fields(HuginnConfig)}
    assert fields == set(EXPECTED_DEFAULTS), (
        "config field set changed — a new field must be "
        "reviewed in docs/SECURE_DEFAULTS.md (RM-055) in the "
        "same slice that adds it"
    )
    config = HuginnConfig()
    for name, expected in EXPECTED_DEFAULTS.items():
        assert getattr(config, name) == expected, (
            f"default of {name} changed — a default change "
            "must re-run the RM-055 review and update the "
            "record and the guides in the same commit"
        )


def test_dangerous_capabilities_are_off_by_default():
    config = HuginnConfig()
    assert config.allow_insecure_http is False
    assert config.debug_log_content is False
    assert config.store_encryption is False
    # strict_path_safety=False is the one compatibility-kept
    # convenience default; its judgement is recorded, and
    # the pin here keeps the keep deliberate.
    assert config.strict_path_safety is False


def test_safety_positive_defaults_are_on():
    config = HuginnConfig()
    assert config.auto_backup is True
    assert config.backup_keep == 3


def test_no_secret_is_invented_by_default():
    config = HuginnConfig()
    assert config.qdrant_api_key is None
    assert config.encryption_passphrase is None
    text = repr(config)
    assert "qdrant_api_key" not in text
    assert "encryption_passphrase" not in text


def test_waits_and_ceilings_are_bounded_by_default():
    config = HuginnConfig()
    assert config.qdrant_timeout > 0
    assert config.busy_timeout_ms > 0
    assert config.max_content_bytes >= 1
    assert config.max_search_candidates >= 1


def test_default_transport_posture_confines_plaintext_to_loopback():
    # The default URL is loopback http and is accepted; the
    # same default posture refuses remote plaintext at
    # construction (RM-045), and the default embedder needs
    # no network and no model download.
    config = HuginnConfig()
    assert config.qdrant_url == "http://localhost:6333"
    assert config.embedder == "tfidf"
    with pytest.raises(HuginnConfigurationError):
        HuginnConfig(qdrant_url="http://qdrant.example.com:6333")


def test_review_record_names_every_field(root):
    record = (root / "docs" / "SECURE_DEFAULTS.md").read_text()
    assert "TH-15" in record
    assert "RM-055" in record
    for name in EXPECTED_DEFAULTS:
        assert f"`{name}`" in record, (
            f"secure-defaults record does not judge {name!r}"
        )


def test_guide_names_every_field(root):
    guide = (root / "docs" / "HUGINN_GUIDE.md").read_text()
    for name in EXPECTED_DEFAULTS:
        assert f"`{name}`" in guide, (
            f"Huginn guide does not name config field {name!r}"
        )
