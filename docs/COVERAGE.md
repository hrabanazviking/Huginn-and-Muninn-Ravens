# Coverage Floor (RM-009)

Line coverage for both packages, measured 2026-10-31 on this
tree (the v1.0.0 logic, post-RM-008) with coverage.py 7.17.0:

| Package | Statements | Missed | Line coverage | Floor |
|---|---|---|---|---|
| muninn | 661 | 74 | **88.80%** | 88 |
| huginn | 883 | 99 | **88.79%** | 88 |

The floor in each package's `pyproject.toml`
(`[tool.coverage.report] fail_under`) is the measured level
rounded down to a whole percent. `coverage report` exits
non-zero below it — proven by re-running the muninn report
against a scratch `fail_under = 99`, which fails with
`Coverage failure: total of 88.80 is less than fail-under=99.00`.
The manual CI runs both coverage steps on every dispatch, and
`tests/test_coverage_floor.py` in both packages pins the floor,
the measured package and the bounded tool (`coverage>=7,<8`,
dev extra only). Later slices ratchet the floor up; it never
moves down without the measurement being re-taken and recorded.

## How it was measured

Per package, from the package directory, tests importing the
package from `src/`:

```sh
pip install "coverage>=7,<8"
(cd muninn && PYTHONPATH=src coverage run -m pytest tests -q && coverage report)
(cd huginn && PYTHONPATH=src coverage run -m pytest tests -q && coverage report)
```

Suites under coverage: muninn **61 passed**, huginn **52
passed** (the RM-008 counts plus this slice's three pins each).

## The reports (verbatim, 2026-10-31)

```
Name                     Stmts   Miss   Cover   Missing
-------------------------------------------------------
src/muninn/__init__.py       5      0 100.00%
src/muninn/_db.py          120     17  85.83%   66-67, 86, 102-104, 116-119, 127, 134-135, 142, 197-199
src/muninn/config.py        38      9  76.32%   61, 63, 65, 67, 69, 71, 73, 75, 77
src/muninn/core.py         493     48  90.26%   121, 129, 142-143, 191, 194, 225, 227-229, 272, 275, 378-387, 399-405, 453, 494, 496, 515-518, 551, 599, 622, 653-654, 670, 832-835, 839, 845, 851, 853, 861-863, 901, 1018, 1058-1059, 1109, 1150
src/muninn/errors.py         5      0 100.00%
-------------------------------------------------------
TOTAL                      661     74  88.80%
```

```
Name                           Stmts   Miss   Cover   Missing
-------------------------------------------------------------
src/huginn/__init__.py             5      0 100.00%
src/huginn/_db.py                119     17  85.71%   54-55, 70, 86-88, 98-101, 108, 115-116, 123, 172-174
src/huginn/config.py              42      9  78.57%   67, 69, 71, 73, 75, 77, 79, 81, 83
src/huginn/core.py               270     27  90.00%   85, 98, 155, 163, 172, 174, 191-193, 208-210, 214, 233-234, 314, 360-361, 375, 378, 384, 402-403, 419, 430, 449, 452, 472
src/huginn/errors.py               6      0 100.00%
src/huginn/local_backend.py      210     13  93.81%   104, 110, 171, 214, 250, 266, 312-313, 343, 365, 379, 441-442
src/huginn/qdrant_backend.py     154     17  88.96%   55, 106-107, 150-151, 166, 172-173, 188-189, 219, 254-262, 275-276, 293
src/huginn/text.py                77     16  79.22%   58, 65, 76, 78, 85, 131-141, 144-145, 150, 157
-------------------------------------------------------------
TOTAL                            883     99  88.79%
```

## What the missed lines are (read from the Missing column)

- **Config validation branches** (both `config.py` files,
  ~76–79%): the per-field illegal-value raises. Each validator
  has some values exercised and some not — the natural first
  ratchet target.
- **`_db.py` healing paths** (~86% both): backup-rotation and
  corruption-recovery branches that the robustness suites hit
  only partly.
- **huginn `text.py` 131–141**: the sentence-transformers
  embedder body — that path stays **NOT PROVEN** (the extra has
  never run live), so its lines are uncovered by definition
  until a LIVE slice runs it.
- **huginn `qdrant_backend.py`**: live-client paths the fake
  cannot reach (a live Qdrant round-trip likewise stays
  NOT PROVEN).
- **muninn `core.py` 670** and **huginn `local_backend.py`
  250/266**: the RM-008 loud `lastrowid is None` guards —
  unreachable by construction, kept loud on purpose; they count
  as missed lines and the floor already absorbs them.

A GitHub-hosted run of the new CI steps is NOT PROVEN — the
workflow has never been dispatched (RM-002 posture); the local
runs above are the evidence.
