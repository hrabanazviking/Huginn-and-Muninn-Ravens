"""RM-007 — Test-matrix pin for huginn.

The manual CI must run both suites under Python 3.11, 3.12 and
3.13 (the versions huginn's ``requires-python = ">=3.11"`` promises),
and it must stay manual-only (RM-002). This test reads the real
workflow file from the repo checkout and pins both facts, so a
later edit cannot silently shrink the matrix or add an automatic
trigger. When the suite runs against an installed package outside
a repo checkout (the RM-001 neutral-cwd method) there is no
workflow file to pin and the test skips.
"""

import re
from pathlib import Path

import pytest

EXPECTED_VERSIONS = ("3.11", "3.12", "3.13")


def _workflow_text():
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / ".github" / "workflows" / "ci.yml"
        if candidate.is_file():
            return candidate.read_text()
    return None


@pytest.fixture(scope="module")
def workflow():
    text = _workflow_text()
    if text is None:
        pytest.skip("not running inside a repo checkout (no ci.yml found)")
    return text


def test_ci_matrix_covers_all_supported_pythons(workflow):
    match = re.search(r"python-version:\s*\[([^\]]*)\]", workflow)
    assert match, "workflow has no python-version matrix list"
    listed = set(re.findall(r'"(\d+\.\d+)"', match.group(1)))
    for version in EXPECTED_VERSIONS:
        assert version in listed, f"CI matrix is missing Python {version}"


def test_ci_matrix_keeps_fail_fast_off(workflow):
    # One version's failure must never hide another version's result.
    assert re.search(r"fail-fast:\s*false", workflow)


def test_ci_stays_manual_only(workflow):
    # RM-002 guard, re-pinned here: the only trigger is dispatch.
    on_block = re.search(r"^on:\n((?:^[ \t]+.*\n)+)", workflow, re.M)
    assert on_block, "workflow has no 'on:' trigger block"
    assert "workflow_dispatch:" in on_block.group(1)
    for trigger in ("push:", "pull_request:", "schedule:"):
        assert trigger not in on_block.group(1), trigger
