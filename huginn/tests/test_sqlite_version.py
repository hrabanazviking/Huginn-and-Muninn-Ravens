"""RM-016 — SQLite runtime version pinning for huginn.

``health()`` on the local (SQLite) backend records the SQLite
runtime version (``sqlite3.sqlite_version`` — the library the
store actually runs on), and the facade passes it through, so
a WAL or behaviour difference can always be traced to the
runtime that produced it. The documented minimum WAL-safe
version (docs/SQLITE_RUNTIME.md) is 3.7.0, the release that
introduced the WAL journal mode both raven stores use. The
Qdrant backend runs no SQLite, so its health carries no
``sqlite_version`` — that road stays as documented, and a
live Qdrant round-trip is still NOT PROVEN.
"""

import sqlite3

from huginn import HuginnConfig, HuginnMemory

MINIMUM_WAL_SAFE = (3, 7, 0)


def _version_tuple(text):
    return tuple(int(part) for part in text.split(".")[:3])


def _local(tmp_path):
    return HuginnMemory(
        HuginnConfig(backend="local", local_db_path=str(tmp_path / "h.db"))
    )


def test_health_carries_sqlite_version(tmp_path):
    h = _local(tmp_path)
    try:
        assert h.health()["sqlite_version"] == sqlite3.sqlite_version
    finally:
        h.close()


def test_sqlite_version_is_a_dotted_triple_at_or_above_minimum(tmp_path):
    h = _local(tmp_path)
    try:
        version = _version_tuple(h.health()["sqlite_version"])
        assert version >= MINIMUM_WAL_SAFE
    finally:
        h.close()


def test_health_sqlite_version_read_is_pure(tmp_path):
    h = _local(tmp_path)
    try:
        h.upsert_memory(content="runes and ravens fly at dawn")
        before = h.health()
        h.health()
        assert h.health() == before
    finally:
        h.close()
