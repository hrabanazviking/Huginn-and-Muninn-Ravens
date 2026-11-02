# Dependency Hygiene — RM-052 (TH-12)

Part IV — Security. This slice closes the two gaps the threat
model (RM-039) recorded under **TH-12** — *dependency compromise
or rot*: "Core installs are dependency-free and extras are
bounded, but there is no lockfile example and no vulnerability
scan in CI." Both gaps are closed here, and the slice's own scan
found and fixed a live instance of the threat on the way.

## The inventory (audited at this slice, both packages)

Core installs are dependency-free — `project.dependencies` is
empty in both pyprojects, and that emptiness is now test-pinned.
Everything either package declares, in full:

| Where | Requirement | Bound |
|---|---|---|
| both build-system | setuptools | `>=68,<82` |
| muninn extra `encryption` | cryptography | `>=42,<51` |
| huginn extra `encryption` | cryptography | `>=42,<51` |
| huginn extra `qdrant` | qdrant-client | `>=1.9,<2` |
| huginn extra `embeddings` | sentence-transformers | `>=2.2,<6` |
| both extra `dev` | pytest | `>=7,<10` (raised by this slice — below) |
| both extra `dev` | ruff | `>=0.6,<1` |
| both extra `dev` | mypy | `>=1.11,<2` |
| both extra `dev` | coverage | `>=7,<8` |

The rule, now pinned by `tests/test_dependency_hygiene.py` in
both packages: **every** declared requirement — build-system,
core, and every extra — carries a `>=floor,<ceiling` bound, and
none is a direct reference (no `@`, no URL, no VCS path). A new
dependency declared without a bound fails both suites until it
is bounded and this inventory is updated.

## The founding discovery: PYSEC-2026-1845

Building this slice's scan and running it locally over the
RM-051-era development environment found a live vulnerability:

- **pytest 8.4.2** — the newest release the old dev bound
  `pytest>=7,<9` allowed — carries **PYSEC-2026-1845**: "pytest
  through 9.0.2 on UNIX relies on directories with the
  `/tmp/pytest-of-{user}` name pattern, which allows local
  users to cause a denial of service or possibly gain
  privileges." Fixed in **9.0.3** — a release the `<9` ceiling
  made unreachable. pip-audit reported 2 rows for the one
  package / one advisory.
- The runtime closure (below) scanned clean in the same run:
  no known vulnerabilities.

Per the never-leave-a-bug rule the bound was fixed in this
slice, not filed: both pyprojects' dev extra and the CI install
line now read `pytest>=7,<10` (floor unchanged), and
`docs/INTEGRATION.md`'s statement of the bound was corrected to
match. Re-verified after the fix: the environment was upgraded
to pytest 9.2.0 and pip-audit over the full installed
environment (runtime + dev + pip-audit's own tree) reported
**no known vulnerabilities**; both suites run green under
pytest 9.2.0 (counts in the slice log). A hygiene test pins the
lesson: the dev bound must satisfy the fixed version 9.0.3, in
both pyprojects and in CI, so the ceiling can never again sit
below a security fix for a tool the suites run as.

## The lockfile example

`docs/examples/requirements-lock.example.txt` is a worked
example of the deployment road: the exact-version closure pip
resolved for `muninn[encryption]` + `huginn[encryption,qdrant]`
on CPython 3.12.3 / Linux x86-64, frozen 2026-11-02 with
`pip freeze` from the slice's own verification venv (23 pins;
the two ravens themselves omitted — they are this repo). Its
header records the provenance and the two deliberate exclusions:
the `embeddings` extra (a torch-scale tree; a host that uses it
freezes it by the same road) and the `dev` extra
(development-only, frozen per checkout, never deployed).

The road for a real deployment:

```bash
pip install "./muninn[encryption]" "./huginn[encryption,qdrant]"
pip freeze > requirements.lock      # on YOUR Python + platform
pip-audit -r requirements.lock      # scan before deploying
pip install -r requirements.lock    # reproduce the frozen set
```

An example is not a lock for your machine: platform wheels
differ, so re-freeze on the deployment Python and platform, and
treat any pin in the example that no longer resolves or scans
clean as a signal to re-freeze, not to force the example in.
Tests pin that the example's direct-extra pins (cryptography,
qdrant-client) satisfy the declared bounds above. For
hash-checked installs, generate hashes at freeze time on the
deployment machine (`pip hash` / `--generate-hashes` tooling)
— hashes are platform artefacts and are deliberately not
shipped in the example.

## The vulnerability scan in CI

`.github/workflows/ci.yml` gains a `dependency-scan` job
(RM-052), inside the same manual-only workflow (RM-002's law is
unchanged — nothing fires automatically):

1. Install **pip-audit** under the dependency law:
   `pip-audit>=2.7,<3` (2.10.1 at this slice).
2. Scan the lockfile example:
   `pip_audit -r docs/examples/requirements-lock.example.txt`.
3. Install both packages with their runtime + dev extras
   (`encryption`, `qdrant`, `dev`; `embeddings` excluded for the
   torch-scale reason stated in the workflow) and scan the
   installed environment: `python -m pip_audit`.
   pip-audit skips the two ravens themselves (not published to
   PyPI — "could not be audited"), which is expected: the scan
   covers everything they *pull in*, and the ravens' own code is
   what the rest of the workflow tests.

A finding fails the job (pip-audit exits non-zero) — that is
the step doing its job, as it did locally for PYSEC-2026-1845.

## Honesty ledger

- The local scans quoted above were **actually run** at this
  slice (pip-audit 2.10.1 against the OSV service, 2026-11-02):
  runtime closure clean before the fix; dev environment flagged
  before the fix and clean after it. Tool output is the
  evidence; the numbers live in the slice log.
- A **GitHub-hosted run** of the new job is **NOT PROVEN** —
  the workflow is manual-only and has never been dispatched
  (the RM-002 position, unchanged).
- A lockfile freezes versions, not virtue: a compromised
  release inside a bound is caught only when an advisory
  exists and the scan runs. The scan is a standing step, not a
  one-time proof; TH-12's register state is re-checked at the
  RM-056 part gate.
- Live Qdrant and the sentence-transformers path stay
  **NOT PROVEN**, as throughout Part IV.
