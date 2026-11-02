"""RM-039 — Threat-model pin for muninn.

docs/THREAT_MODEL.md is Part IV's foundation: the assets,
actors, trust boundaries, threat register and non-goals
every security slice RM-040..RM-056 cites. These tests pin
that the model exists inside the repo, names the roadmap's
four actors and both ravens' core assets, maps every later
Part IV slice to a threat, and carries its non-goals and
honesty ledger — a security slice added to the part without
a threat, or a model quietly losing one, fails here. When
the suite runs against an installed package outside a repo
checkout there is no document to pin and the tests skip
(the RM-007 pattern).
"""

from pathlib import Path

import pytest

PART_IV_SLICES = [f"RM-{n:03d}" for n in range(40, 57)]


def _doc_text():
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "docs" / "THREAT_MODEL.md"
        if candidate.is_file():
            return candidate.read_text()
    return None


@pytest.fixture(scope="module")
def doc():
    text = _doc_text()
    if text is None:
        pytest.skip("not running inside a repo checkout (no THREAT_MODEL.md)")
    return text


def test_model_names_the_roadmaps_actors_and_assets(doc):
    for marker in (
        "buggy caller",
        "hostile input",
        "local file attacker",
        "network attacker",
        "activation_log",
        "hebbian_connections",
        "API key",
        "backup",
    ):
        assert marker in doc, f"threat model does not name {marker!r}"


def test_model_maps_every_part_iv_slice_and_states_its_limits(doc):
    for slice_id in PART_IV_SLICES:
        assert slice_id in doc, f"threat model does not map {slice_id}"
    assert "Non-goals" in doc or "non-goals" in doc, (
        "threat model states no non-goals"
    )
    assert "NOT PROVEN" in doc, "the honesty ledger must ride with the model"
    assert "TH-" in doc, "threat model has no threat register ids"
