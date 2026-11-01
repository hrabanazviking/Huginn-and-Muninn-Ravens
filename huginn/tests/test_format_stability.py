"""RM-022 — Store-format stability promise pin for huginn.

docs/FORMAT_STABILITY.md is the promise: which files, tables
and meta keys are contractual, and the migration rule each
carries. These tests pin the review against the code: every
table and index in the RM-004 golden schema must be named in
the document, along with the meta key, the backup file shape
and the Qdrant collection name — a format element added to
the schema without a promise update fails here. When the
suite runs against an installed package outside a repo
checkout there is no document to pin and the tests skip
(the RM-007 pattern).
"""

from pathlib import Path

import pytest

GOLDEN = Path(__file__).parent / "golden_schema.txt"


def _doc_text():
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "docs" / "FORMAT_STABILITY.md"
        if candidate.is_file():
            return candidate.read_text()
    return None


@pytest.fixture(scope="module")
def doc():
    text = _doc_text()
    if text is None:
        pytest.skip("not running inside a repo checkout (no FORMAT_STABILITY.md)")
    return text


def _golden_names(kind):
    names = []
    for line in GOLDEN.read_text().splitlines():
        parts = line.split("|")
        if len(parts) >= 2 and parts[0] == kind:
            names.append(parts[1])
    return names


def test_every_golden_table_is_named_in_the_promise(doc):
    tables = _golden_names("table")
    assert tables, "golden schema has no tables to pin"
    for table in tables:
        assert table in doc, f"FORMAT_STABILITY.md does not name table {table}"


def test_every_golden_index_and_the_meta_keys_are_named(doc):
    for index in _golden_names("index"):
        assert index in doc, f"FORMAT_STABILITY.md does not name index {index}"
    assert "schema_version" in doc
    assert ".bak-" in doc, "FORMAT_STABILITY.md does not name the backup files"
    assert "huginn_memories" in doc, "the Qdrant collection is not named"
