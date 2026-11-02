"""RM-010 — Slice-log pin for huginn.

``docs/SLICE_LOG.md`` is the roadmap's permanent evidence
record: every banked slice appends an entry with its honesty
class and banking commit, in the same commit that banks it.
This test pins the entries for the slices banked so far, so the
log cannot silently lose one. When a later slice banks, it
appends its entry and extends EXPECTED in both packages' copies
of this test in the same commit. Skips outside a repo checkout.
"""

import re
from pathlib import Path

import pytest

EXPECTED = [f"RM-{n:03d}" for n in range(1, 46)]  # RM-001..RM-045


@pytest.fixture(scope="module")
def slice_log():
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "docs" / "SLICE_LOG.md"
        if candidate.is_file() and (parent / "RAVENS_ROADMAP_2026-10-31.md").is_file():
            return candidate.read_text()
    pytest.skip("not running inside a repo checkout (no docs/SLICE_LOG.md)")


def _entries(text):
    blocks = {}
    parts = re.split(r"^## (RM-\d{3}) — ", text, flags=re.M)
    # parts: [prelude, id, body, id, body, ...]
    for i in range(1, len(parts), 2):
        blocks[parts[i]] = parts[i + 1]
    return blocks


def test_every_banked_slice_has_an_entry(slice_log):
    blocks = _entries(slice_log)
    for slice_id in EXPECTED:
        assert slice_id in blocks, f"SLICE_LOG.md has no entry for {slice_id}"


def test_every_entry_carries_class_and_commit(slice_log):
    blocks = _entries(slice_log)
    for slice_id in EXPECTED:
        body = blocks[slice_id]
        assert "**Class:**" in body, f"{slice_id} entry has no Class field"
        assert "**Commit:**" in body, f"{slice_id} entry has no Commit field"
