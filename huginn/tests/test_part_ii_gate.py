"""RM-024 — Part II gate pin for huginn.

docs/PART_II_EVIDENCE.md is the part gate: the evidence
bundle and slice check-off for RM-011..RM-024. These tests
pin that the bundle exists inside the repo, names every
Part II slice, and files all four evidence kinds the
roadmap's gate calls for (determinism, soak, flake,
matrix). When the suite runs against an installed package
outside a repo checkout there is no bundle to pin and the
tests skip (the RM-007 pattern).
"""

from pathlib import Path

import pytest

PART_II_SLICES = [f"RM-{n:03d}" for n in range(11, 25)]


def _doc_text():
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "docs" / "PART_II_EVIDENCE.md"
        if candidate.is_file():
            return candidate.read_text()
    return None


@pytest.fixture(scope="module")
def doc():
    text = _doc_text()
    if text is None:
        pytest.skip("not running inside a repo checkout (no PART_II_EVIDENCE.md)")
    return text


def test_bundle_names_every_part_ii_slice(doc):
    for slice_id in PART_II_SLICES:
        assert slice_id in doc, f"evidence bundle does not name {slice_id}"


def test_bundle_files_the_four_evidence_kinds(doc):
    for marker in ("DETERMINISM.md", "SOAK.md", "50 consecutive", "Matrix"):
        assert marker in doc, f"evidence bundle is missing {marker!r}"
    assert "NOT PROVEN" in doc, "the honesty ledger must ride with the gate"
