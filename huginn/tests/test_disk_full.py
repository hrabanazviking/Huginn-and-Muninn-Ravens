"""RM-029 — Disk-full behaviour for huginn.

The fault is injected with the real engine, not a mock:
``PRAGMA max_page_count`` is clamped to the local store's
current page count, so the next write that needs a new page
gets SQLite's own SQLITE_FULL — the same ``database or disk is
full`` error a full filesystem produces. This suite pins the
RM-029 contract for the local backend (the Qdrant backend
already translates its failures into ``HuginnBackendError``):

* a write against a full store surfaces as a typed
  ``HuginnStorageError`` naming the operation — never a raw
  ``sqlite3.Error``;
* the failed call is rolled back: an upsert that had already
  de-indexed the old document before the failing statement
  leaves the old document fully intact, and nothing partial
  leaks into a later commit;
* the store stays open and consistent in the same session, and
  after close/reopen: prior data intact, integrity ok, and
  writes succeed again once space returns (the cap is lifted).
"""

import sqlite3

import pytest

from huginn import HuginnConfig, HuginnMemory
from huginn.errors import HuginnStorageError

BIG = "x" * 200_000  # under the 1 MiB content ceiling, far over one page


def _mem(tmp_path, name="h.db"):
    return HuginnMemory(
        HuginnConfig(backend="local", local_db_path=str(tmp_path / name))
    )


def _conn(h):
    return h._ensure_backend()._conn


def _cap_growth(h):
    conn = _conn(h)
    pages = conn.execute("PRAGMA page_count").fetchone()[0]
    conn.execute(f"PRAGMA max_page_count={int(pages)}")


def _uncap(h):
    _conn(h).execute("PRAGMA max_page_count=1073741823")


def test_upsert_disk_full_is_typed_and_store_survives(tmp_path):
    h = _mem(tmp_path)
    seed = h.upsert_memory("alpha seed document about ravens")
    _cap_growth(h)
    with pytest.raises(HuginnStorageError) as caught:
        h.upsert_memory(BIG)
    assert "database or disk is full" in str(caught.value)
    assert "upsert" in str(caught.value)
    assert not isinstance(caught.value, sqlite3.Error)
    # Nothing was stored, and the store answers reads in-session.
    assert h.get(seed)["content"] == "alpha seed document about ravens"
    assert [r["id"] for r in h.search("ravens")] == [seed]
    _uncap(h)
    beta = h.upsert_memory("beta document after space returns")
    assert h.get(beta)["content"] == "beta document after space returns"
    h.close()
    # Reopen: consistent, prior data intact, failed write absent.
    h2 = _mem(tmp_path)
    try:
        assert h2.health()["integrity"] == "ok"
        assert h2.get(seed)["content"] == "alpha seed document about ravens"
        assert h2.get(beta) is not None
        assert len(h2.search("document")) == 2
    finally:
        h2.close()


def test_upsert_replace_disk_full_rolls_back_the_deindex(tmp_path):
    h = _mem(tmp_path)
    seed = h.upsert_memory("quixotic original about zebras")
    _cap_growth(h)
    # Replacing by explicit id de-indexes the old document's terms
    # before the new (huge) content row is written — the statement
    # that hits SQLITE_FULL. Without a rollback, the old document
    # would lose its index while keeping its old content.
    with pytest.raises(HuginnStorageError):
        h.upsert_memory(BIG, memory_id=seed)
    _uncap(h)
    h.upsert_memory("unrelated later write")
    doc = h.get(seed)
    assert doc["content"] == "quixotic original about zebras"
    assert [r["id"] for r in h.search("zebras")] == [seed]
    assert [r["id"] for r in h.search("quixotic")] == [seed]
    h.close()
