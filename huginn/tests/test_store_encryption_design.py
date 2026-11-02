"""RM-048 — Store-encryption design pin for huginn.

RM-048 is a design slice: its output is the decision
record ``docs/STORE_ENCRYPTION.md``, and RM-049 builds
what it specifies. These tests pin that the record
exists inside the repo, judges the roadmap's three
candidates against the roadmap's two constraints
(stdlib-first and the shared-schema law), records the
decision and the rejected options, and carries the
build specification RM-049 implements — config flag,
bounded extra, key hierarchy, open-time key proof, and
the per-package transform list, including Huginn's
token index and stored vectors — plus its honesty
limits (what stays plaintext, what stays NOT PROVEN).
A later edit that quietly reverses the decision or
drops the spec fails here. When the suite runs against
an installed package outside a repo checkout there is
no document to pin and the tests skip (the RM-007
pattern).
"""

from pathlib import Path

import pytest


def _doc_text():
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "docs" / "STORE_ENCRYPTION.md"
        if candidate.is_file():
            return candidate.read_text()
    return None


@pytest.fixture(scope="module")
def doc():
    text = _doc_text()
    if text is None:
        pytest.skip("not running inside a repo checkout (no STORE_ENCRYPTION.md)")
    return text


def test_record_judges_all_three_candidates_against_both_constraints(doc):
    for marker in (
        "SQLCipher",
        "envelope encryption",
        "Filesystem encryption",
        "stdlib-first",
        "shared-schema law",
        "TH-09",
        "activation_log",
        "hebbian_connections",
    ):
        assert marker in doc, f"design record does not cover {marker!r}"


def test_record_states_the_decision_and_the_rm049_spec(doc):
    for marker in (
        "RM-049 builds candidate B",
        "store_encryption: bool = False",
        "encryption_passphrase",
        "cryptography>=42,<51",
        "AES-256-GCM",
        "PBKDF2-HMAC-SHA256",
        "key-check value",
        "enc:v1:",
        "keyed lookup tag",
        "doc_terms.term",
        "doc_vectors.vector",
        "NOT PROVEN",
    ):
        assert marker in doc, f"design record does not specify {marker!r}"
