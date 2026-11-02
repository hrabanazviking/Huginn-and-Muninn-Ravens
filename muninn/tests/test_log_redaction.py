"""RM-044 — Log redaction for muninn.

Threat TH-05 (docs/THREAT_MODEL.md): memory content reaching
package log output, where hosts ship logs onward. Before this
slice the behaviour rested on inspection alone (the TH-05
inventory found no content argument at any log site, but
nothing scanned for a regression). This slice pins it and
adds the one sanctioned road:

* ``MuninnConfig.debug_log_content`` defaults to False, and
  with it off NO log record at any level — DEBUG included —
  carries memory content, over the store, retrieve and heal
  paths;
* with it on, content may appear ONLY at DEBUG level and
  ONLY from the store/retrieve paths — never at INFO or
  above, and the heal path carries no content at any level
  even with the flag on (its report is counts by design).
"""

import logging
import sqlite3

from muninn import HebbianMemory
from muninn.config import MuninnConfig

SECRET = "SECRET-RAVEN-CONTENT-044"


def _cfg(tmp_path, **overrides):
    return MuninnConfig(db_path=str(tmp_path / "m.db"), **overrides)


def _messages(caplog):
    return [record.getMessage() for record in caplog.records]


def _assert_no_content(caplog):
    for record in caplog.records:
        assert SECRET not in record.getMessage(), (
            f"content leaked into a {record.levelname} log record: "
            f"{record.getMessage()!r}"
        )


def test_debug_log_content_defaults_off(tmp_path):
    assert MuninnConfig(db_path=str(tmp_path / "m.db")).debug_log_content is False
    assert _cfg(tmp_path).debug_log_content is False


def test_store_path_emits_no_content_with_flag_off(tmp_path, caplog):
    mem = HebbianMemory(_cfg(tmp_path))
    try:
        with caplog.at_level(logging.DEBUG, logger="muninn"):
            mem.remember(SECRET)
    finally:
        mem.close()
    _assert_no_content(caplog)


def test_retrieve_path_emits_no_content_with_flag_off(tmp_path, caplog):
    mem = HebbianMemory(_cfg(tmp_path))
    try:
        mem.remember(f"prefix {SECRET} suffix")
        with caplog.at_level(logging.DEBUG, logger="muninn"):
            found = mem.retrieve(query=SECRET)
        assert len(found) == 1
    finally:
        mem.close()
    _assert_no_content(caplog)


def test_heal_path_emits_no_content_with_flag_off(tmp_path, caplog):
    mem = HebbianMemory(_cfg(tmp_path))
    try:
        mem.remember(SECRET)
        mem.activate_batch([1, 2])
        conn = sqlite3.connect(str(tmp_path / "m.db"))
        conn.execute(
            "INSERT INTO hebbian_connections VALUES (5, 5, 0.5, 1, 0, 't', 't')"
        )
        conn.commit()
        conn.close()
        with caplog.at_level(logging.DEBUG, logger="muninn"):
            report = mem.heal_structure()
        assert report["self_edges_pruned"] == 1
        # The heal path really did log — a counts-only warning.
        assert any("heal repaired" in message for message in _messages(caplog))
    finally:
        mem.close()
    _assert_no_content(caplog)


def test_flag_on_store_emits_content_at_debug_only(tmp_path, caplog):
    mem = HebbianMemory(_cfg(tmp_path, debug_log_content=True))
    try:
        with caplog.at_level(logging.DEBUG, logger="muninn"):
            mem.remember(SECRET)
    finally:
        mem.close()
    carriers = [r for r in caplog.records if SECRET in r.getMessage()]
    assert carriers, "flag on: the store path must log content at DEBUG"
    assert all(r.levelno == logging.DEBUG for r in carriers)


def test_flag_on_retrieve_emits_content_at_debug_only(tmp_path, caplog):
    mem = HebbianMemory(_cfg(tmp_path, debug_log_content=True))
    try:
        mem.remember(f"prefix {SECRET} suffix")
        caplog.clear()
        with caplog.at_level(logging.DEBUG, logger="muninn"):
            found = mem.retrieve(query=SECRET)
        assert len(found) == 1
    finally:
        mem.close()
    carriers = [r for r in caplog.records if SECRET in r.getMessage()]
    assert carriers, "flag on: the retrieve path must log content at DEBUG"
    assert all(r.levelno == logging.DEBUG for r in carriers)


def test_flag_on_heal_still_emits_no_content(tmp_path, caplog):
    mem = HebbianMemory(_cfg(tmp_path, debug_log_content=True))
    try:
        mem.remember(SECRET)
        conn = sqlite3.connect(str(tmp_path / "m.db"))
        conn.execute(
            "INSERT INTO hebbian_connections VALUES (5, 5, 0.5, 1, 0, 't', 't')"
        )
        conn.commit()
        conn.close()
        caplog.clear()
        with caplog.at_level(logging.DEBUG, logger="muninn"):
            report = mem.heal_structure()
        assert report["self_edges_pruned"] == 1
        assert any("heal repaired" in message for message in _messages(caplog))
    finally:
        mem.close()
    _assert_no_content(caplog)
