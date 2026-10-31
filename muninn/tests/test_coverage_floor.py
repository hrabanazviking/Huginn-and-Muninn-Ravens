"""RM-009 — Coverage floor pin for muninn.

Line coverage was measured on the v1.0.0 logic (post-RM-008 tree)
at 88.80%; the floor in this package's ``pyproject.toml`` is that
measurement rounded down to a whole percent (88), enforced by
``coverage report`` in the manual CI. This test pins the floor,
the measured package, and the bounded tool so a later edit cannot
silently lower any of them. Skips outside a repo checkout.
"""

import re
import tomllib
from pathlib import Path

import pytest

FLOOR = 88


@pytest.fixture(scope="module")
def pyproject():
    path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    if not path.is_file():
        pytest.skip("not running inside a repo checkout (no pyproject.toml)")
    return tomllib.loads(path.read_text())


@pytest.fixture(scope="module")
def workflow():
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / ".github" / "workflows" / "ci.yml"
        if candidate.is_file():
            return candidate.read_text()
    pytest.skip("not running inside a repo checkout (no ci.yml found)")


def test_coverage_floor_is_pinned(pyproject):
    coverage = pyproject["tool"]["coverage"]
    assert coverage["run"]["source_pkgs"] == ["muninn"]
    assert coverage["report"]["fail_under"] == FLOOR


def test_coverage_tool_is_bounded(pyproject):
    dev = pyproject["project"]["optional-dependencies"]["dev"]
    assert "coverage>=7,<8" in dev


def test_ci_enforces_the_floor(workflow):
    assert re.search(r"Coverage muninn \(RM-009 floor", workflow)
    assert "python -m coverage report" in workflow
