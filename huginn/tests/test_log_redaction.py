"""RM-044 — Log redaction for huginn.

Threat TH-05 (docs/THREAT_MODEL.md): memory content reaching
package log output, where hosts ship logs onward. Before this
slice the behaviour rested on inspection alone (the TH-05
inventory found no content argument at any log site, but
nothing scanned for a regression). This slice pins it and
adds the one sanctioned road:

* ``HuginnConfig.debug_log_content`` defaults to False, and
  with it off NO log record at any level — DEBUG included —
  carries memory content, over the store, search and heal
  paths (proven on the local backend);
* with it on, content may appear ONLY at DEBUG level and
  ONLY from the facade's store/search paths — never at INFO
  or above, and the heal path carries no content at any
  level even with the flag on (its report is counts by
  design).
"""

import logging
import sqlite3

from huginn import HuginnMemory
from huginn.config import HuginnConfig

SECRET = "SECRET-RAVEN-CONTENT-044"


def _cfg(tmp_path, **overrides):
    return HuginnConfig(
        backend="local", local_db_path=str(tmp_path / "h.db"), **overrides
    )


def _messages(caplog):
    return [record.getMessage() for record in caplog.records]


def _assert_no_content(caplog):
    for record in caplog.records:
        assert SECRET not in record.getMessage(), (
            f"content leaked into a {record.levelname} log record: "
            f"{record.getMessage()!r}"
        )


def test_debug_log_content_defaults_off(tmp_path):
    assert _cfg(tmp_path).debug_log_content is False


def test_store_path_emits_no_content_with_flag_off(tmp_path, caplog):
    huginn = HuginnMemory(_cfg(tmp_path))
    try:
        with caplog.at_level(logging.DEBUG, logger="huginn"):
            huginn.upsert_memory(content=SECRET, category="fact")
    finally:
        huginn.close()
    _assert_no_content(caplog)


def test_search_path_emits_no_content_with_flag_off(tmp_path, caplog):
    huginn = HuginnMemory(_cfg(tmp_path))
    try:
        huginn.upsert_memory(content=f"prefix {SECRET} suffix", category="fact")
        with caplog.at_level(logging.DEBUG, logger="huginn"):
            found = huginn.search(SECRET)
        assert len(found) == 1
    finally:
        huginn.close()
    _assert_no_content(caplog)


def test_heal_path_emits_no_content_with_flag_off(tmp_path, caplog):
    huginn = HuginnMemory(_cfg(tmp_path))
    try:
        huginn.upsert_memory(content=f"drift {SECRET} memory", category="fact")
        conn = sqlite3.connect(str(tmp_path / "h.db"))
        conn.execute("UPDATE corpus_stats SET doc_freq = 999 WHERE term = 'drift'")
        conn.execute(
            "INSERT INTO doc_terms (doc_id, term, tf) VALUES (99999, 'ghost', 1)"
        )
        conn.commit()
        conn.close()
        with caplog.at_level(logging.DEBUG, logger="huginn"):
            report = huginn._backend.heal()
        assert report["doc_freq_fixed"] >= 1
        # The heal path really did log — a counts-only warning.
        assert any("heal repaired" in message for message in _messages(caplog))
    finally:
        huginn.close()
    _assert_no_content(caplog)


def test_flag_on_store_emits_content_at_debug_only(tmp_path, caplog):
    huginn = HuginnMemory(_cfg(tmp_path, debug_log_content=True))
    try:
        with caplog.at_level(logging.DEBUG, logger="huginn"):
            huginn.upsert_memory(content=SECRET, category="fact")
    finally:
        huginn.close()
    carriers = [r for r in caplog.records if SECRET in r.getMessage()]
    assert carriers, "flag on: the store path must log content at DEBUG"
    assert all(r.levelno == logging.DEBUG for r in carriers)


def test_flag_on_search_emits_content_at_debug_only(tmp_path, caplog):
    huginn = HuginnMemory(_cfg(tmp_path, debug_log_content=True))
    try:
        huginn.upsert_memory(content=f"prefix {SECRET} suffix", category="fact")
        caplog.clear()
        with caplog.at_level(logging.DEBUG, logger="huginn"):
            found = huginn.search(SECRET)
        assert len(found) == 1
    finally:
        huginn.close()
    carriers = [r for r in caplog.records if SECRET in r.getMessage()]
    assert carriers, "flag on: the search path must log content at DEBUG"
    assert all(r.levelno == logging.DEBUG for r in carriers)


def test_flag_on_heal_still_emits_no_content(tmp_path, caplog):
    huginn = HuginnMemory(_cfg(tmp_path, debug_log_content=True))
    try:
        huginn.upsert_memory(content=f"drift {SECRET} memory", category="fact")
        conn = sqlite3.connect(str(tmp_path / "h.db"))
        conn.execute("UPDATE corpus_stats SET doc_freq = 999 WHERE term = 'drift'")
        conn.commit()
        conn.close()
        caplog.clear()
        with caplog.at_level(logging.DEBUG, logger="huginn"):
            report = huginn._backend.heal()
        assert report["doc_freq_fixed"] >= 1
        assert any("heal repaired" in message for message in _messages(caplog))
    finally:
        huginn.close()
    _assert_no_content(caplog)
