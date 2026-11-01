"""RM-016 — SQLite runtime version pinning for muninn.

``health()`` records the SQLite runtime version
(``sqlite3.sqlite_version`` — the library the store actually
runs on), so a WAL or behaviour difference can always be
traced to the runtime that produced it. The documented
minimum WAL-safe version (docs/SQLITE_RUNTIME.md) is 3.7.0,
the release that introduced the WAL journal mode both raven
stores use.
"""

import sqlite3

from muninn import HebbianMemory
from muninn.config import MuninnConfig

MINIMUM_WAL_SAFE = (3, 7, 0)


def _version_tuple(text):
    return tuple(int(part) for part in text.split(".")[:3])


def test_health_carries_sqlite_version(tmp_path):
    m = HebbianMemory(MuninnConfig(db_path=str(tmp_path / "m.db")))
    try:
        assert m.health()["sqlite_version"] == sqlite3.sqlite_version
    finally:
        m.close()


def test_sqlite_version_is_a_dotted_triple_at_or_above_minimum(tmp_path):
    m = HebbianMemory(MuninnConfig(db_path=str(tmp_path / "m.db")))
    try:
        version = _version_tuple(m.health()["sqlite_version"])
        assert version >= MINIMUM_WAL_SAFE
    finally:
        m.close()


def test_health_sqlite_version_read_is_pure(tmp_path):
    m = HebbianMemory(MuninnConfig(db_path=str(tmp_path / "m.db")))
    try:
        m.remember("runes and ravens", category="lore")
        before = m.stats()
        m.health()
        m.health()
        assert m.stats() == before
    finally:
        m.close()
