"""RM-056 — Part IV gate pin for muninn.

docs/PART_IV_EVIDENCE.md is the part gate: the evidence
bundle and slice check-off for RM-039..RM-056. These tests
pin that the bundle exists inside the repo, names every
Part IV slice, files every FAULT result the roadmap's
gate calls for (store encryption build, integrity
attestation, secure forget), and that the threat model
carries the gate's re-review with its register updated.
When the suite runs against an installed package outside
a repo checkout there is no bundle to pin and the tests
skip (the RM-007 pattern).
"""

from pathlib import Path

import pytest

PART_IV_SLICES = [f"RM-{n:03d}" for n in range(39, 57)]


def _doc_text(name):
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "docs" / name
        if candidate.is_file():
            return candidate.read_text()
    return None


@pytest.fixture(scope="module")
def doc():
    text = _doc_text("PART_IV_EVIDENCE.md")
    if text is None:
        pytest.skip("not running inside a repo checkout (no PART_IV_EVIDENCE.md)")
    return text


def test_bundle_names_every_part_iv_slice(doc):
    for slice_id in PART_IV_SLICES:
        assert slice_id in doc, f"evidence bundle does not name {slice_id}"


def test_bundle_files_every_fault_result(doc):
    for marker in ("STORE_ENCRYPTION.md", "INTEGRITY_ATTESTATION.md", "SECURE_FORGET.md", "FAULT"):
        assert marker in doc, f"evidence bundle is missing {marker!r}"
    assert "NOT PROVEN" in doc, "the honesty ledger must ride with the gate"


def test_threat_model_carries_the_gate_re_review(doc):
    model = _doc_text("THREAT_MODEL.md")
    if model is None:
        pytest.skip("not running inside a repo checkout (no THREAT_MODEL.md)")
    assert "RM-056 re-review" in model, "threat model carries no RM-056 re-review"
    assert "RM-056 update" in model, "threat model register states were not updated at the gate"
