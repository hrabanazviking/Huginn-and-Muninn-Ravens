"""RM-029 — Disk-full behaviour for muninn.

The fault is injected with the real engine, not a mock:
``PRAGMA max_page_count`` is clamped to the store's current page
count, so the next write that needs a new page gets SQLite's own
SQLITE_FULL — the same ``database or disk is full`` error a full
filesystem produces. This suite pins the RM-029 contract:

* a write against a full store surfaces as a typed
  ``MuninnStorageError`` naming the operation — never a raw
  ``sqlite3.Error``;
* the failed call is rolled back: no partial write survives, and
  nothing from it leaks into a later commit;
* the store stays open and consistent in the same session, and
  after close/reopen: prior data intact, integrity ok, and
  writes succeed again once space returns (the cap is lifted).
"""

import sqlite3

import pytest

from muninn import HebbianMemory, MuninnStorageError
from muninn.config import MuninnConfig

BIG = "x" * 200_000  # under the 1 MiB content ceiling, far over one page


def _mem(tmp_path, name="m.db"):
    return HebbianMemory(MuninnConfig(db_path=str(tmp_path / name)))


def _cap_growth(m):
    conn = m._get_conn()
    pages = conn.execute("PRAGMA page_count").fetchone()[0]
    conn.execute(f"PRAGMA max_page_count={int(pages)}")


def _uncap(m):
    m._get_conn().execute("PRAGMA max_page_count=1073741823")


def test_remember_disk_full_is_typed_and_store_survives(tmp_path):
    m = _mem(tmp_path)
    seed = m.remember("alpha seed")
    _cap_growth(m)
    with pytest.raises(MuninnStorageError) as caught:
        m.remember(BIG)
    assert "database or disk is full" in str(caught.value)
    assert "remember" in str(caught.value)
    assert not isinstance(caught.value, sqlite3.Error)
    # Nothing was stored, and the store answers reads in-session.
    assert m.stats()["total_nodes"] == 1
    assert [n.id for n in m.retrieve("alpha")] == [seed]
    _uncap(m)
    beta = m.remember("beta after space returns")
    assert m.stats()["total_nodes"] == 2
    m.close()
    # Reopen: consistent, prior data intact, failed write absent.
    m2 = _mem(tmp_path)
    try:
        assert m2.health()["integrity"] == "ok"
        assert m2.get_node(seed).content == "alpha seed"
        assert m2.get_node(beta).content == "beta after space returns"
        assert m2.stats()["total_nodes"] == 2
    finally:
        m2.close()


def test_update_disk_full_keeps_the_original_node(tmp_path):
    m = _mem(tmp_path)
    seed = m.remember("original wording")
    _cap_growth(m)
    with pytest.raises(MuninnStorageError):
        m.update(seed, content=BIG)
    assert m.get_node(seed).content == "original wording"
    _uncap(m)
    assert m.update(seed, content="revised wording") is True
    assert m.get_node(seed).content == "revised wording"
    m.close()


def test_activate_batch_disk_full_rolls_back_every_activation(tmp_path):
    m = _mem(tmp_path)
    ids = [m.remember(f"batch target {i}") for i in range(300)]
    _cap_growth(m)
    # The batch logs 300 activations and wires ~45k pairs: far more
    # than the capped store can hold, so it fails part-way through
    # its one transaction, by design of the fault.
    with pytest.raises(MuninnStorageError):
        m.activate_batch(ids)
    assert m.activation_count(ids[0]) == 0
    assert m.get_associations(ids[0]) == []
    _uncap(m)
    # A later successful commit must not resurrect the failed batch.
    m.remember("unrelated later write")
    assert m.activation_count(ids[0]) == 0
    assert m.get_associations(ids[0]) == []
    m.close()
