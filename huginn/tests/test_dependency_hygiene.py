"""RM-052 — Dependency-hygiene pins for huginn.

TH-12 (dependency compromise or rot) is answered three ways, and
each answer is pinned here so it cannot quietly rot: every
requirement either package declares carries a `>=floor,<ceiling`
bound and no direct reference; a worked lockfile example lives in
`docs/examples/` with exact pins that satisfy the declared bounds
for the direct extras; and the manual CI carries a bounded
pip-audit vulnerability-scan job over that example and over an
installed runtime + dev environment. The record is
`docs/DEPENDENCY_HYGIENE.md`. When the suite runs against an
installed package outside a repo checkout there is nothing to pin
and the tests skip (the RM-007 pattern).
"""

import re
import tomllib
from pathlib import Path

import pytest

_REQ_RE = re.compile(r"^([A-Za-z0-9_.-]+)\s*(.*)$")
_PIN_RE = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s;]+)$")


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


def _pyproject(root, package):
    text = (root / package / "pyproject.toml").read_text()
    return tomllib.loads(text)


def _all_requirements(data):
    reqs = list(data["build-system"]["requires"])
    reqs.extend(data["project"].get("dependencies", []))
    for extra in data["project"].get("optional-dependencies", {}).values():
        reqs.extend(extra)
    return reqs


def _version_tuple(text):
    parts = []
    for chunk in text.split("."):
        digits = re.match(r"\d+", chunk)
        parts.append(int(digits.group()) if digits else 0)
    return tuple(parts)


def _satisfies(version, spec):
    vt = _version_tuple(version)
    for clause in spec.split(","):
        clause = clause.strip()
        if clause.startswith(">="):
            if vt < _version_tuple(clause[2:]):
                return False
        elif clause.startswith("<"):
            if not vt < _version_tuple(clause[1:]):
                return False
        else:
            return False
    return True


def test_core_installs_are_dependency_free(root):
    for package in ("muninn", "huginn"):
        data = _pyproject(root, package)
        assert data["project"]["dependencies"] == [], (
            f"{package} core gained a runtime dependency"
        )


def test_every_declared_requirement_is_bounded(root):
    for package in ("muninn", "huginn"):
        for req in _all_requirements(_pyproject(root, package)):
            assert "@" not in req and "://" not in req, (
                f"{package}: direct reference is not a bound: {req!r}"
            )
            match = _REQ_RE.match(req)
            assert match, f"{package}: unparseable requirement {req!r}"
            spec = match.group(2)
            assert ">=" in spec and "<" in spec, (
                f"{package}: requirement lacks a >=floor,<ceiling bound: {req!r}"
            )


def test_pytest_bound_reaches_the_pysec_2026_1845_fix(root):
    # RM-052's founding discovery: pip-audit found pytest 8.4.2 —
    # the newest the old >=7,<9 bound allowed — carrying
    # PYSEC-2026-1845, fixed only in 9.0.3. The dev bound must
    # reach a fixed release, in both packages and in CI.
    for package in ("muninn", "huginn"):
        dev = _pyproject(root, package)["project"]["optional-dependencies"]["dev"]
        spec = next(r for r in dev if r.startswith("pytest")).split("pytest", 1)[1]
        assert _satisfies("9.0.3", spec), f"{package}: dev bound excludes the fix: {spec}"
    workflow = (root / ".github" / "workflows" / "ci.yml").read_text()
    assert '"pytest>=7,<10"' in workflow, "CI installs pytest under the old bound"


def test_lockfile_example_is_exact_pins(root):
    path = root / "docs" / "examples" / "requirements-lock.example.txt"
    assert path.is_file(), "lockfile example is missing"
    pins = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = _PIN_RE.match(line)
        assert match, f"lockfile example line is not an exact pin: {line!r}"
        pins[match.group(1).lower()] = match.group(2)
    assert len(pins) >= 20, f"lockfile example shrank to {len(pins)} pins"


def test_lockfile_pins_satisfy_the_declared_bounds(root):
    path = root / "docs" / "examples" / "requirements-lock.example.txt"
    pins = {}
    for line in path.read_text().splitlines():
        match = _PIN_RE.match(line.strip())
        if match:
            pins[match.group(1).lower()] = match.group(2)
    declared = {}
    for package in ("muninn", "huginn"):
        for req in _all_requirements(_pyproject(root, package)):
            match = _REQ_RE.match(req)
            declared[match.group(1).lower()] = match.group(2)
    for direct in ("cryptography", "qdrant-client"):
        assert direct in pins, f"lockfile example does not pin {direct}"
        assert _satisfies(pins[direct], declared[direct]), (
            f"lockfile pin {direct}=={pins[direct]} violates the declared "
            f"bound {declared[direct]}"
        )


def test_ci_carries_the_vulnerability_scan(root):
    workflow = (root / ".github" / "workflows" / "ci.yml").read_text()
    assert "dependency-scan:" in workflow, "CI has no dependency-scan job"
    assert '"pip-audit>=2.7,<3"' in workflow, "pip-audit itself is not bounded"
    assert "pip_audit -r docs/examples/requirements-lock.example.txt" in workflow, (
        "CI does not scan the lockfile example"
    )
    assert "python -m pip_audit" in workflow, "CI does not scan an installed environment"


def test_record_doc_names_threat_finding_and_limits(root):
    doc = (root / "docs" / "DEPENDENCY_HYGIENE.md").read_text()
    for marker in ("TH-12", "PYSEC-2026-1845", "requirements-lock.example", "NOT PROVEN"):
        assert marker in doc, f"dependency-hygiene record does not name {marker!r}"
