"""RM-012 — Timestamp discipline for muninn.

All stored timestamps are UTC ISO-8601 from the one helper
(``muninn.core._now``), issued through the monotonic guard
(``HebbianMemory._tick``): a backwards system clock can never
produce an out-of-order activation log. The clock-skew tests
patch the helper with a clock that runs backwards and prove
the stored order survives.
"""

import itertools
import sqlite3
from datetime import UTC, datetime

import muninn.core
from muninn import HebbianMemory
from muninn.config import MuninnConfig

TIMESTAMP_COLUMNS = {
    "nodes": ["created_at", "updated_at"],
    "activation_log": ["activated_at"],
    "hebbian_connections": ["created_at", "last_coactivated_at"],
    "node_activation": ["last_activated_at"],
    "deleted_nodes": ["deleted_at"],
}


def _backwards_clock(monkeypatch, start="2026-01-01T00:00:10+00:00"):
    """Patch _now to a clock that steps BACK one second per call."""
    base = datetime.fromisoformat(start)
    ticks = itertools.count()

    def fake_now():
        from datetime import timedelta

        return (base - timedelta(seconds=next(ticks))).isoformat()

    monkeypatch.setattr(muninn.core, "_now", fake_now)
    return base


def _log_times(db_path):
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT activated_at FROM activation_log ORDER BY id"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def test_all_stored_timestamps_are_utc_iso8601(tmp_path):
    db = str(tmp_path / "m.db")
    m = HebbianMemory(MuninnConfig(db_path=db))
    a = m.remember("a memory with a timestamp", importance=5)
    b = m.remember("a second memory with a timestamp", importance=5)
    m.activate_batch([a, b])
    m.associate(a, b, strength=0.5)
    m.forget(b)
    m.close()
    conn = sqlite3.connect(db)
    seen = 0
    for table, cols in TIMESTAMP_COLUMNS.items():
        for col in cols:
            for (raw,) in conn.execute(
                f"SELECT {col} FROM {table} WHERE {col} IS NOT NULL"
            ).fetchall():
                parsed = datetime.fromisoformat(raw)
                assert parsed.tzinfo is not None
                assert parsed.utcoffset() == UTC.utcoffset(parsed)
                assert raw.endswith("+00:00"), raw
                seen += 1
    conn.close()
    assert seen > 0


def test_clock_skew_activation_log_stays_strictly_increasing(tmp_path, monkeypatch):
    db = str(tmp_path / "m.db")
    base = _backwards_clock(monkeypatch)
    m = HebbianMemory(MuninnConfig(db_path=db))
    nid = m.remember("skew target memory")
    for _ in range(5):
        m.activate(nid)
    m.close()
    times = [datetime.fromisoformat(t) for t in _log_times(db)]
    assert len(times) == 5
    assert all(
        later > earlier
        for earlier, later in zip(times, times[1:], strict=False)
    )
    # The guard clamps to last-issued + 1µs: remember() took the
    # first (highest) reading for the node row, so the log starts
    # just past it and never goes back despite the falling clock.
    assert times[0] > base


def test_guard_seeded_from_store_on_reopen(tmp_path, monkeypatch):
    db = str(tmp_path / "m.db")
    late = "2026-06-01T12:00:00+00:00"
    monkeypatch.setattr(muninn.core, "_now", lambda: late)
    m = HebbianMemory(MuninnConfig(db_path=db))
    nid = m.remember("written before the clock fell")
    m.activate(nid)
    m.close()
    # The clock falls back an hour; a fresh object on the same
    # store must still log strictly after the stored history.
    monkeypatch.setattr(muninn.core, "_now", lambda: "2026-06-01T11:00:00+00:00")
    m2 = HebbianMemory(MuninnConfig(db_path=db))
    m2.activate(nid)
    m2.close()
    times = [datetime.fromisoformat(t) for t in _log_times(db)]
    assert len(times) == 2
    # remember() took the frozen reading itself; the activation
    # clamped one microsecond past it, and the reopened store's
    # activation clamped past that — strictly increasing throughout.
    assert times[1] > times[0] > datetime.fromisoformat(late)


def test_normal_clock_is_untouched_by_the_guard(tmp_path, monkeypatch):
    db = str(tmp_path / "m.db")
    readings = iter(
        ["2026-01-01T00:00:01+00:00", "2026-01-01T00:00:02+00:00"]
    )
    monkeypatch.setattr(muninn.core, "_now", lambda: next(readings))
    m = HebbianMemory(MuninnConfig(db_path=db))
    nid = m.remember("plain clock memory")
    m.activate(nid)
    m.close()
    # remember() consumed the first reading for the node row; the
    # activation carries the second, exactly as the clock said.
    assert _log_times(db) == ["2026-01-01T00:00:02+00:00"]
