"""RM-038 — Part III gate pin for huginn.

docs/PART_III_EVIDENCE.md is the part gate: the evidence
bundle and slice check-off for RM-025..RM-038. These tests
pin that the bundle exists inside the repo, names every
Part III slice, and files every FAULT result the roadmap's
gate calls for (disk-full, read-only filesystem,
partial-file states). When the suite runs against an
installed package outside a repo checkout there is no
bundle to pin and the tests skip (the RM-007 pattern).
"""

from pathlib import Path

import pytest

PART_III_SLICES = [f"RM-{n:03d}" for n in range(25, 39)]


def _doc_text():
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "docs" / "PART_III_EVIDENCE.md"
        if candidate.is_file():
            return candidate.read_text()
    return None


@pytest.fixture(scope="module")
def doc():
    text = _doc_text()
    if text is None:
        pytest.skip("not running inside a repo checkout (no PART_III_EVIDENCE.md)")
    return text


def test_bundle_names_every_part_iii_slice(doc):
    for slice_id in PART_III_SLICES:
        assert slice_id in doc, f"evidence bundle does not name {slice_id}"


def test_bundle_files_every_fault_result(doc):
    for marker in ("DISK_FULL.md", "READONLY_FILESYSTEM.md", "PARTIAL_FILE_STATES.md", "FAULT"):
        assert marker in doc, f"evidence bundle is missing {marker!r}"
    assert "NOT PROVEN" in doc, "the honesty ledger must ride with the gate"
