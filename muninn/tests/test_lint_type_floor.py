"""RM-008 — Lint/type floor pin for muninn.

The floor lives in this package's ``pyproject.toml``: a ruff rule
set (E, W, F, I, UP, B, SIM, C4 at line-length 100, target py311)
and a mypy ratchet level (every def typed, untyped bodies checked,
no Any returns, no implicit Optional). This test pins that config
so a later edit cannot silently lower the floor — raising it is
the ratchet's job and is recorded in docs/LINT_AND_TYPES.md.
Skips outside a repo checkout, like the RM-007 matrix pin.
"""

import re
import tomllib
from pathlib import Path

import pytest

RUFF_FLOOR = {"E", "W", "F", "I", "UP", "B", "SIM", "C4"}
MYPY_RATCHET = (
    "disallow_untyped_defs",
    "disallow_incomplete_defs",
    "check_untyped_defs",
    "warn_return_any",
    "no_implicit_optional",
)


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


def test_ruff_floor_is_pinned(pyproject):
    ruff = pyproject["tool"]["ruff"]
    assert set(ruff["lint"]["select"]) == RUFF_FLOOR
    assert ruff["line-length"] == 100
    assert ruff["target-version"] == "py311"


def test_mypy_ratchet_level_is_pinned(pyproject):
    mypy = pyproject["tool"]["mypy"]
    assert mypy["python_version"] == "3.11"
    for flag in MYPY_RATCHET:
        assert mypy[flag] is True, f"mypy ratchet flag lowered: {flag}"


def test_dev_tools_are_bounded(pyproject):
    dev = pyproject["project"]["optional-dependencies"]["dev"]
    assert "ruff>=0.6,<1" in dev
    assert "mypy>=1.11,<2" in dev


def test_ci_runs_the_floor(workflow):
    assert re.search(r"ruff check muninn/src", workflow)
    assert re.search(r"ruff check huginn/src", workflow)
    assert workflow.count("python -m mypy src/") == 2
