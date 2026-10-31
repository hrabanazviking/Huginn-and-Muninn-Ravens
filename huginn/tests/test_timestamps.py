"""RM-012 — Timestamp discipline for huginn (local backend).

All stored timestamps are UTC ISO-8601 from the one helper
(``huginn.local_backend._now``), issued through the monotonic
guard (``LocalBackend._tick``): a backwards system clock can
never make a document's ``updated_at`` precede its
``created_at``, and a reopened store keeps issuing timestamps
after its own history. The Qdrant backend stores no timestamps.
"""

import itertools
import sqlite3
from datetime import UTC, datetime, timedelta

import huginn.local_backend
from huginn import HuginnMemory
from huginn.config import HuginnConfig


def _rows(db_path):
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT id, created_at, updated_at FROM documents ORDER BY id"
    ).fetchall()
    conn.close()
    return rows


def _local(db_path):
    return HuginnMemory(HuginnConfig(backend="local", local_db_path=db_path))


def test_all_stored_timestamps_are_utc_iso8601(tmp_path):
    db = str(tmp_path / "h.db")
    h = _local(db)
    h.upsert_memory("a document with timestamps in it")
    h.upsert_memory("a document with timestamps in it", importance=9)
    h.close()
    rows = _rows(db)
    assert rows
    for _id, created, updated in rows:
        for raw in (created, updated):
            parsed = datetime.fromisoformat(raw)
            assert parsed.tzinfo is not None
            assert parsed.utcoffset() == UTC.utcoffset(parsed)
            assert raw.endswith("+00:00"), raw
        assert updated >= created


def test_clock_skew_update_never_precedes_create(tmp_path, monkeypatch):
    db = str(tmp_path / "h.db")
    base = datetime.fromisoformat("2026-01-01T00:00:10+00:00")
    ticks = itertools.count()
    monkeypatch.setattr(
        huginn.local_backend,
        "_now",
        lambda: (base - timedelta(seconds=next(ticks))).isoformat(),
    )
    h = _local(db)
    h.upsert_memory("skew target document of some length")
    h.upsert_memory("skew target document of some length", importance=9)
    h.close()
    (_id, created, updated) = _rows(db)[0]
    # The second upsert's clock reading was EARLIER than the
    # first; the guard clamped it to last-issued + 1µs.
    assert datetime.fromisoformat(updated) > datetime.fromisoformat(created)


def test_guard_seeded_from_store_on_reopen(tmp_path, monkeypatch):
    db = str(tmp_path / "h.db")
    monkeypatch.setattr(
        huginn.local_backend, "_now", lambda: "2026-06-01T12:00:00+00:00"
    )
    h = _local(db)
    h.upsert_memory("written before the clock fell down")
    h.close()
    monkeypatch.setattr(
        huginn.local_backend, "_now", lambda: "2026-06-01T11:00:00+00:00"
    )
    h2 = _local(db)
    h2.upsert_memory("written after the clock fell down")
    h2.close()
    rows = _rows(db)
    assert len(rows) == 2
    assert rows[1][1] > rows[0][1]
