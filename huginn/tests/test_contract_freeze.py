"""RM-003 — Contract freeze (golden) tests for huginn.

Pins the exact Bifröst call shapes and result keys of BUILD_NOTES §1
(hrabanazviking/bifrost @ b66e98cc) as data, so no later slice can drift
the contract unknowingly: a deliberate signature or result-key change
fails this suite until the golden data below is updated on purpose —
in the same commit as the contract change, with the Bifröst
re-verification the roadmap requires for API changes.

Behavioural exercise of the same calls lives in test_contract.py; this
file pins their *shape*.
"""

import inspect

from huginn import HuginnConfig, HuginnMemory


def _shape(fn):
    """(name, kind, repr(default)) per parameter, excluding self."""
    out = []
    for p in inspect.signature(fn).parameters.values():
        if p.name == "self":
            continue
        default = "<required>" if p.default is inspect.Parameter.empty else repr(p.default)
        out.append((p.name, p.kind.name, default))
    return out


# Golden signatures — BUILD_NOTES §1.3. Update ONLY deliberately.
GOLDEN_SIGNATURES = {
    "__init__": [
        ("config", "POSITIONAL_OR_KEYWORD", "None"),
        ("overrides", "VAR_KEYWORD", "<required>"),
    ],
    "upsert_memory": [
        ("content", "POSITIONAL_OR_KEYWORD", "<required>"),
        ("category", "POSITIONAL_OR_KEYWORD", "'general'"),
        ("importance", "POSITIONAL_OR_KEYWORD", "5"),
        ("tags", "POSITIONAL_OR_KEYWORD", "None"),
        ("emotional_valence", "POSITIONAL_OR_KEYWORD", "0.0"),
        ("memory_id", "KEYWORD_ONLY", "None"),
    ],
    "search": [
        ("query_text", "POSITIONAL_OR_KEYWORD", "<required>"),
        ("limit", "POSITIONAL_OR_KEYWORD", "10"),
        ("category", "POSITIONAL_OR_KEYWORD", "None"),
        ("min_importance", "POSITIONAL_OR_KEYWORD", "1"),
    ],
    "health": [],
    "close": [],
}


def test_golden_signatures():
    for name, golden in GOLDEN_SIGNATURES.items():
        actual = _shape(getattr(HuginnMemory, name))
        assert actual == golden, (
            f"HuginnMemory.{name} signature drifted from the frozen "
            f"Bifröst contract: {actual} != {golden}. If this change is "
            "deliberate, update the golden data and re-run the Bifröst "
            "contract verification before banking."
        )


def test_golden_result_keys(tmp_path):
    h = HuginnMemory(
        HuginnConfig(backend="local", local_db_path=str(tmp_path / "h.db"))
    )
    try:
        h.upsert_memory(
            content="runes and ravens fly at dawn", category="lore",
            importance=7, tags=["rune"], emotional_valence=0.2,
        )
        results = h.search(query_text="runes ravens")
        assert results, "search must find the stored document"
        # Bifröst reads exactly these keys from every search result.
        assert set(results[0]) == {
            "id", "content", "category", "importance", "tags",
            "emotional_valence", "score",
        }
        assert set(h.health()) == {
            "backend", "backend_configured", "db_path", "documents",
            "embedder", "integrity", "recovered_from_backup",
            "sqlite_version", "status", "vocabulary",
        }
    finally:
        h.close()
