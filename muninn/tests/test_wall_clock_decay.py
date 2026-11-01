"""RM-021 — Clock-free decay + optional wall-clock mode for muninn.

Plain ``decay(days)`` stays exactly as it was: computed from the
explicit ``days`` argument only, never reading the clock. The new
``decay_wall_clock()`` is the opt-in mode — off by default — that
derives ``days`` from the marker (``decay_last_run_at``) stored in
the store's meta table. These tests patch the one clock helper
(``muninn.core._now``, the RM-012 seam) with fixed readings and
prove the behaviour for clock jumps in both directions, the
first-run arming, a corrupt marker, marker persistence across a
reopen, and that plain ``decay()`` never touches the marker.
"""

import sqlite3
from datetime import timedelta

import pytest

import muninn.core
from muninn import HebbianMemory
from muninn.config import MuninnConfig

T0 = "2026-01-01T00:00:00+00:00"


def _mem(tmp_path, name="m.db"):
    return HebbianMemory(MuninnConfig(db_path=str(tmp_path / name)))


def _set_clock(monkeypatch, iso):
    monkeypatch.setattr(muninn.core, "_now", lambda: iso)


def _shift(iso, days):
    from datetime import datetime

    return (datetime.fromisoformat(iso) + timedelta(days=days)).isoformat()


def _marker(db_path):
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT value FROM meta WHERE key = 'decay_last_run_at'"
    ).fetchone()
    conn.close()
    return row[0] if row else None


def _pair_with_edge(m, strength=0.8):
    a = m.remember("alpha raven memory", importance=7)
    b = m.remember("beta raven memory", importance=6)
    m.associate(a, b, strength=strength)
    return a, b


def test_first_call_arms_marker_and_decays_nothing(tmp_path, monkeypatch):
    db = str(tmp_path / "m.db")
    m = _mem(tmp_path)
    a, _ = _pair_with_edge(m)
    _set_clock(monkeypatch, T0)
    try:
        report = m.decay_wall_clock()
        assert report["mode"] == "wall_clock"
        assert report["first_run"] is True
        assert report["marker_reset"] is False
        assert report["elapsed_days"] == 0.0
        assert report["days"] == 0.0
        assert report["edge_factor"] == 1.0
        assert report["last_run_at"] is None
        assert report["run_at"] == T0
        # Nothing faded: the edge keeps its exact strength.
        assert m.get_associations(a)[0]["strength"] == pytest.approx(0.8)
    finally:
        m.close()
    assert _marker(db) == T0


def test_forward_jump_decays_by_elapsed_days(tmp_path, monkeypatch):
    m = _mem(tmp_path)
    a, _ = _pair_with_edge(m)
    try:
        _set_clock(monkeypatch, T0)
        m.decay_wall_clock()  # arm
        _set_clock(monkeypatch, _shift(T0, 30))
        report = m.decay_wall_clock()
        assert report["first_run"] is False
        assert report["elapsed_days"] == pytest.approx(30.0)
        assert report["last_run_at"] == T0
        assert report["marker_advanced"] is True
        # Edge half-life is 30 days by default: 0.8 * 0.5 == 0.4.
        assert report["edge_factor"] == pytest.approx(0.5)
        assert m.get_associations(a)[0]["strength"] == pytest.approx(0.4)
    finally:
        m.close()


def test_backward_jump_decays_nothing_and_marker_holds(tmp_path, monkeypatch):
    db = str(tmp_path / "m.db")
    m = _mem(tmp_path)
    a, _ = _pair_with_edge(m)
    try:
        _set_clock(monkeypatch, _shift(T0, 30))
        m.decay_wall_clock()  # arm at T0+30
        strength_before = m.get_associations(a)[0]["strength"]
        _set_clock(monkeypatch, T0)  # clock jumps 30 days BACK
        report = m.decay_wall_clock()
        assert report["elapsed_days"] == 0.0
        assert report["edge_factor"] == 1.0
        assert report["marker_advanced"] is False
        assert report["last_run_at"] == _shift(T0, 30)
        assert m.get_associations(a)[0]["strength"] == strength_before
        # The next healthy reading measures from the held marker,
        # not from the regressed clock: T0+31 is exactly 1 day on.
        _set_clock(monkeypatch, _shift(T0, 31))
        follow = m.decay_wall_clock()
        assert follow["elapsed_days"] == pytest.approx(1.0)
    finally:
        m.close()
    assert _marker(db) == _shift(T0, 31)


def test_corrupt_marker_is_rearmed_and_reported(tmp_path, monkeypatch):
    db = str(tmp_path / "m.db")
    m = _mem(tmp_path)
    a, _ = _pair_with_edge(m)
    _set_clock(monkeypatch, T0)
    try:
        m.decay_wall_clock()  # arm properly first
        conn = sqlite3.connect(db)
        conn.execute(
            "UPDATE meta SET value = 'not-a-timestamp' "
            "WHERE key = 'decay_last_run_at'"
        )
        conn.commit()
        conn.close()
        # The live connection may have the old value cached in a
        # transaction snapshot; read through the store itself.
        report = m.decay_wall_clock()
        assert report["marker_reset"] is True
        assert report["first_run"] is False
        assert report["elapsed_days"] == 0.0
        assert m.get_associations(a)[0]["strength"] == pytest.approx(0.8)
    finally:
        m.close()
    assert _marker(db) == T0


def test_marker_survives_reopen(tmp_path, monkeypatch):
    db = str(tmp_path / "m.db")
    m = _mem(tmp_path)
    _pair_with_edge(m)
    _set_clock(monkeypatch, T0)
    m.decay_wall_clock()  # arm
    m.close()
    _set_clock(monkeypatch, _shift(T0, 10))
    reopened = HebbianMemory(MuninnConfig(db_path=db))
    try:
        report = reopened.decay_wall_clock()
        assert report["first_run"] is False
        assert report["last_run_at"] == T0
        assert report["elapsed_days"] == pytest.approx(10.0)
    finally:
        reopened.close()
    assert _marker(db) == _shift(T0, 10)


def test_plain_decay_never_touches_the_marker(tmp_path, monkeypatch):
    db = str(tmp_path / "m.db")
    m = _mem(tmp_path)
    _pair_with_edge(m)
    _set_clock(monkeypatch, T0)
    try:
        m.decay(days=5.0)
        m.decay(days=0.0)
    finally:
        m.close()
    assert _marker(db) is None
