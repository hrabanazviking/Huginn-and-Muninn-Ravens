"""RM-050 — Integrity attestation (muninn).

Optional HMAC/checksum chain over ``activation_log`` so
tampering with the log file outside the API is detectable on
open (threat TH-10; record ``docs/INTEGRITY_ATTESTATION.md``).
Acceptance, from the roadmap: *tamper test — modify one row
by raw SQL, open, detection reported.*

The chain is stdlib-only (PBKDF2-HMAC-SHA256 key derivation,
HMAC-SHA256 links), keyed by a caller passphrase that is never
stored; the store carries the salt, head and chained count as
``meta`` rows, so the schema — contracted ``activation_log``
included — is unmoved. Muninn-only slice: ``activation_log``
exists only in Muninn (Huginn keeps only the slice-log pin).
"""

import sqlite3

import pytest

from muninn import HebbianMemory
from muninn.config import MuninnConfig
from muninn.errors import MuninnConfigurationError, MuninnStorageError

PASSPHRASE = "chain passphrase one"


def _att_config(db, **kw):
    return MuninnConfig(
        db_path=str(db),
        integrity_attestation=True,
        integrity_passphrase=PASSPHRASE,
        **kw,
    )


def _raw(db, sql, params=()):
    conn = sqlite3.connect(str(db))
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def _meta(db):
    conn = sqlite3.connect(str(db))
    try:
        return dict(
            conn.execute(
                "SELECT key, value FROM meta WHERE key LIKE 'attestation_%'"
            ).fetchall()
        )
    finally:
        conn.close()


def _seed(db, activations=3):
    mem = HebbianMemory(_att_config(db))
    node = mem.remember("a memory worth auditing")
    for _ in range(activations):
        mem.activate(node)
    mem.close()
    return node


def test_flag_off_is_todays_behaviour(tmp_path):
    db = tmp_path / "m.db"
    mem = HebbianMemory(MuninnConfig(db_path=str(db)))
    node = mem.remember("plain")
    mem.activate(node)
    assert mem.integrity_attestation_status == "not_enabled"
    assert mem.health()["integrity_attestation"] == "not_enabled"
    mem.close()
    assert _meta(db) == {}


def test_chain_is_written_and_verifies_ok(tmp_path):
    db = tmp_path / "m.db"
    node = _seed(db)
    meta = _meta(db)
    assert meta["attestation_version"] == "1"
    assert int(meta["attestation_count"]) == 3
    assert len(meta["attestation_head"]) == 64
    # The passphrase and the derived key are nowhere in the store.
    conn = sqlite3.connect(str(db))
    try:
        dump = "\n".join(
            str(row) for row in conn.execute("SELECT key, value FROM meta").fetchall()
        )
    finally:
        conn.close()
    assert PASSPHRASE not in dump

    mem = HebbianMemory(_att_config(db))
    assert mem.integrity_attestation_status == "ok"
    assert mem.health()["integrity_attestation"] == "ok"
    assert mem.activation_count(node) == 3
    mem.activate(node)
    mem.close()
    assert int(_meta(db)["attestation_count"]) == 4


def test_tamper_with_one_row_by_raw_sql_is_detected_on_open(tmp_path):
    db = tmp_path / "m.db"
    _seed(db)
    _raw(db, "UPDATE activation_log SET source = 'forged' WHERE id = 1")

    mem = HebbianMemory(_att_config(db))
    assert mem.integrity_attestation_status == "tamper_detected"
    assert mem.health()["integrity_attestation"] == "tamper_detected"
    # Detection is reported, not a refusal and not a repair:
    # the store still opens and serves, and the tampered row
    # is still there for the caller to judge.
    assert mem.stats()["total_activations"] == 3
    mem.close()


def test_inserted_and_deleted_rows_are_detected(tmp_path):
    db = tmp_path / "m.db"
    _seed(db)
    _raw(
        db,
        "INSERT INTO activation_log (memory_id, activated_at,"
        " emotional_valence, source) VALUES (1,"
        " '2026-01-01T00:00:00+00:00', 0.0, 'planted')",
    )
    mem = HebbianMemory(_att_config(db))
    assert mem.integrity_attestation_status == "tamper_detected"
    mem.close()

    db2 = tmp_path / "m2.db"
    _seed(db2)
    _raw(db2, "DELETE FROM activation_log WHERE id = 2")
    mem = HebbianMemory(_att_config(db2))
    assert mem.integrity_attestation_status == "tamper_detected"
    mem.close()


def test_rewritten_head_is_detected(tmp_path):
    db = tmp_path / "m.db"
    _seed(db)
    _raw(db, "UPDATE meta SET value = ? WHERE key = 'attestation_head'", ("0" * 64,))
    mem = HebbianMemory(_att_config(db))
    assert mem.integrity_attestation_status == "tamper_detected"
    mem.close()


def test_wrong_passphrase_reports_tamper_detected(tmp_path):
    db = tmp_path / "m.db"
    _seed(db)
    mem = HebbianMemory(
        MuninnConfig(
            db_path=str(db),
            integrity_attestation=True,
            integrity_passphrase="not the passphrase",
        )
    )
    # By design the chain cannot tell a wrong key from a
    # tampered log — both recompute to a different head.
    assert mem.integrity_attestation_status == "tamper_detected"
    mem.close()


def test_marked_store_refuses_a_plain_open(tmp_path):
    db = tmp_path / "m.db"
    _seed(db)
    before = db.read_bytes()
    with pytest.raises(MuninnStorageError) as excinfo:
        HebbianMemory(MuninnConfig(db_path=str(db)))
    assert "carries integrity attestation" in str(excinfo.value)
    assert db.read_bytes() == before


def test_passphrase_is_required_and_typed(tmp_path):
    with pytest.raises(MuninnConfigurationError) as excinfo:
        MuninnConfig(db_path=str(tmp_path / "m.db"), integrity_attestation=True)
    assert "integrity_passphrase is required" in str(excinfo.value)
    with pytest.raises(MuninnConfigurationError):
        MuninnConfig(
            db_path=str(tmp_path / "m.db"),
            integrity_attestation=True,
            integrity_passphrase=42,
        )


def test_enabling_on_an_existing_store_bootstraps_as_found(tmp_path):
    db = tmp_path / "m.db"
    mem = HebbianMemory(MuninnConfig(db_path=str(db)))
    node = mem.remember("pre-attestation memory")
    mem.activate(node)
    mem.activate(node)
    mem.close()
    assert _meta(db) == {}

    mem = HebbianMemory(_att_config(db))
    assert mem.integrity_attestation_status == "ok"
    mem.close()
    assert int(_meta(db)["attestation_count"]) == 2

    _raw(db, "UPDATE activation_log SET emotional_valence = 0.9 WHERE id = 1")
    mem = HebbianMemory(_att_config(db))
    assert mem.integrity_attestation_status == "tamper_detected"
    mem.close()


def test_activate_batch_and_bulk_road_are_chained(tmp_path):
    db = tmp_path / "m.db"
    mem = HebbianMemory(_att_config(db))
    ids = [mem.remember(f"memory {i}") for i in range(5)]
    mem.activate_batch(ids)  # the per-pair loop road
    # 70 unique ids take the RM-035 bulk road (>= 64).
    bulk_ids = [mem.remember(f"bulk {i}") for i in range(70)]
    mem.activate_batch(bulk_ids)
    mem.close()
    assert int(_meta(db)["attestation_count"]) == 75

    mem = HebbianMemory(_att_config(db))
    assert mem.integrity_attestation_status == "ok"
    mem.close()


def test_retrieve_touch_is_chained(tmp_path):
    db = tmp_path / "m.db"
    mem = HebbianMemory(_att_config(db))
    mem.remember("touchable thought")
    found = mem.retrieve(query="touchable", touch=True)
    assert found
    mem.close()
    assert int(_meta(db)["attestation_count"]) == 1
    mem = HebbianMemory(_att_config(db))
    assert mem.integrity_attestation_status == "ok"
    mem.close()


def test_attestation_and_encryption_compose(tmp_path):
    pytest.importorskip("cryptography")
    db = tmp_path / "m.db"
    cfg = MuninnConfig(
        db_path=str(db),
        store_encryption=True,
        encryption_passphrase="encryption passphrase",
        integrity_attestation=True,
        integrity_passphrase=PASSPHRASE,
    )
    mem = HebbianMemory(cfg)
    node = mem.remember("sealed and chained")
    mem.activate(node)
    mem.close()

    mem = HebbianMemory(cfg)
    assert mem.integrity_attestation_status == "ok"
    assert mem.get_node(node).content == "sealed and chained"
    mem.close()

    _raw(db, "UPDATE activation_log SET source = 'forged' WHERE id = 1")
    mem = HebbianMemory(cfg)
    assert mem.integrity_attestation_status == "tamper_detected"
    mem.close()


def test_backup_restore_keeps_the_chain(tmp_path):
    db = tmp_path / "m.db"
    mem = HebbianMemory(_att_config(db, backup_keep=2))
    node = mem.remember("backed up and chained")
    mem.activate(node)
    mem.backup()
    mem.close()

    # Corrupt the main store outside the API; the open must
    # restore the attested backup, whose header is the one
    # that counts, and verify ok against it.
    db.write_bytes(b"this is not a sqlite database at all........")
    mem = HebbianMemory(_att_config(db))
    assert mem.recovered_from_backup
    assert mem.integrity_attestation_status == "ok"
    assert mem.get_node(node).content == "backed up and chained"
    mem.close()
