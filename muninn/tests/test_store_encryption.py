"""RM-049 — Store encryption, build (muninn).

Implements the RM-048 decision (``docs/STORE_ENCRYPTION.md``):
application-level envelope encryption behind the ``encryption``
extra and the ``store_encryption`` config flag. Acceptance,
from the roadmap read through the decision record:

* an encrypted store's memory content is unreadable by plain
  sqlite3 — the file opens, but every content-bearing value is
  an ``enc:v1:`` envelope and no plaintext token of a stored
  memory appears in a raw dump; the contracted tables
  (``activation_log`` / ``hebbian_connections``) stay directly
  readable with the stdlib;
* a wrong-key open raises the typed storage error with the
  store untouched, and a plain (flag-off) open of a marked
  store refuses the same way;
* the recovery road works against encrypted stores: a corrupt
  main store is restored from its rolling backup and the
  content decrypts — the same durability machinery, not a
  parallel weakened set.
"""

import hashlib
import sqlite3

import pytest

from muninn import HebbianMemory
from muninn.config import MuninnConfig
from muninn.errors import MuninnConfigurationError, MuninnStorageError

PASSPHRASE = "correct horse battery staple"
SECRET = "zebra quill secret phrase"


def _enc_config(db, **kw):
    return MuninnConfig(
        db_path=str(db), store_encryption=True, encryption_passphrase=PASSPHRASE, **kw
    )


def _raw_rows(db):
    conn = sqlite3.connect(str(db))
    try:
        return conn.execute(
            "SELECT content, content_hash, tags, metadata FROM nodes"
        ).fetchall()
    finally:
        conn.close()


def test_encrypted_store_is_unreadable_by_plain_sqlite3(tmp_path):
    db = tmp_path / "m.db"
    mem = HebbianMemory(_enc_config(db))
    node_id = mem.remember(
        SECRET,
        category="fact",
        tags=["silverfalcon"],
        metadata={"hiding": "amber vault note"},
    )
    mem.remember({"spell": "rune of hidden embers"}, category="fact")
    mem.activate(node_id)
    mem.close()

    rows = _raw_rows(db)
    assert len(rows) == 2
    dump = "\n".join(str(value) for row in rows for value in row)
    for token in ("zebra", "quill", "silverfalcon", "amber", "vault", "rune", "embers"):
        assert token not in dump, f"plaintext token {token!r} leaked into the raw store"
    for content, content_hash, tags, metadata in rows:
        assert content.startswith("enc:v1:")
        assert tags.startswith("enc:v1:")
        assert metadata.startswith("enc:v1:")
        # The stored hash is a keyed tag, not the plaintext SHA-256.
        plain = hashlib.sha256(f"s:{SECRET}".encode()).hexdigest()
        assert content_hash != plain
        assert len(content_hash) == 64
    # The contracted tables carry no content and stay readable
    # by plain sqlite3 exactly as before (shared-schema law).
    conn = sqlite3.connect(str(db))
    try:
        acts = conn.execute("SELECT COUNT(*) FROM activation_log").fetchone()[0]
        assert acts == 1
        conn.execute("SELECT * FROM hebbian_connections").fetchall()
        marker = conn.execute(
            "SELECT value FROM meta WHERE key = 'encryption_version'"
        ).fetchone()
        assert marker is not None and marker[0] == "1"
    finally:
        conn.close()


def test_roundtrip_idempotency_and_update(tmp_path):
    db = tmp_path / "m.db"
    mem = HebbianMemory(_enc_config(db))
    node_id = mem.remember(SECRET, tags=["one"], metadata={"k": "v"})
    assert mem.remember(SECRET) == node_id  # idempotent under the keyed tag
    mem.close()

    mem = HebbianMemory(_enc_config(db))
    node = mem.get_node(node_id)
    assert node is not None
    assert node.content == SECRET
    assert node.tags == ["one"]
    assert node.metadata == {"k": "v"}
    found = mem.retrieve(query="zebra quill")
    assert [n.id for n in found] == [node_id]
    assert mem.update(node_id, "a replaced secret", tags=["two"], metadata={"k": "w"})
    node = mem.get_node(node_id)
    assert node is not None
    assert node.content == "a replaced secret"
    assert node.tags == ["two"]
    assert node.metadata == {"k": "w"}
    mem.close()
    rows = _raw_rows(db)
    assert "replaced" not in "\n".join(str(v) for row in rows for v in row)


def test_wrong_passphrase_refused_and_store_untouched(tmp_path):
    db = tmp_path / "m.db"
    mem = HebbianMemory(_enc_config(db))
    mem.remember(SECRET)
    mem.close()
    before = db.read_bytes()
    with pytest.raises(MuninnStorageError) as excinfo:
        HebbianMemory(
            MuninnConfig(
                db_path=str(db),
                store_encryption=True,
                encryption_passphrase="not the passphrase",
            )
        )
    assert "passphrase does not unlock it" in str(excinfo.value)
    assert "not the passphrase" not in str(excinfo.value)
    assert db.read_bytes() == before


def test_plain_open_of_encrypted_store_refused(tmp_path):
    db = tmp_path / "m.db"
    mem = HebbianMemory(_enc_config(db))
    mem.remember(SECRET)
    mem.close()
    with pytest.raises(MuninnStorageError) as excinfo:
        HebbianMemory(MuninnConfig(db_path=str(db)))
    assert "is encrypted; refusing to open it without store_encryption" in str(excinfo.value)


def test_flag_on_existing_plain_store_with_memories_refused(tmp_path):
    db = tmp_path / "m.db"
    mem = HebbianMemory(MuninnConfig(db_path=str(db)))
    mem.remember("a plain memory")
    mem.close()
    with pytest.raises(MuninnStorageError) as excinfo:
        HebbianMemory(_enc_config(db))
    assert "is not encrypted but already holds memories" in str(excinfo.value)
    # The plain store still opens plainly afterwards.
    mem = HebbianMemory(MuninnConfig(db_path=str(db)))
    assert mem.stats()["total_nodes"] == 1
    mem.close()


def test_flag_on_empty_plain_store_initializes_encryption(tmp_path):
    db = tmp_path / "m.db"
    mem = HebbianMemory(MuninnConfig(db_path=str(db)))
    mem.close()
    mem = HebbianMemory(_enc_config(db))
    node_id = mem.remember(SECRET)
    mem.close()
    rows = _raw_rows(db)
    assert rows[0][0].startswith("enc:v1:")
    mem = HebbianMemory(_enc_config(db))
    node = mem.get_node(node_id)
    assert node is not None and node.content == SECRET
    mem.close()


def test_passphrase_required_and_never_in_repr():
    with pytest.raises(MuninnConfigurationError) as excinfo:
        MuninnConfig(store_encryption=True)
    assert "encryption_passphrase is required" in str(excinfo.value)
    config = MuninnConfig(store_encryption=True, encryption_passphrase=PASSPHRASE)
    assert PASSPHRASE not in repr(config)


def test_encrypted_store_recovers_from_rolling_backup(tmp_path):
    db = tmp_path / "m.db"
    mem = HebbianMemory(_enc_config(db))
    keep_id = mem.remember("the encrypted memory that must survive", category="fact")
    mem.close()
    # Second open refreshes the rolling backup with that state inside.
    mem = HebbianMemory(_enc_config(db))
    mem.close()
    assert (tmp_path / "m.db.bak-1").exists()
    with open(db, "r+b") as fh:
        fh.write(b"GARBAGE-NOT-A-DATABASE" * 16)
    mem = HebbianMemory(_enc_config(db))
    assert mem.recovered_from_backup is True
    assert mem.health()["status"] == "healthy"
    node = mem.get_node(keep_id)
    assert node is not None and "must survive" in node.content
    mem.close()


def test_flag_off_store_stays_plaintext(tmp_path):
    db = tmp_path / "m.db"
    mem = HebbianMemory(MuninnConfig(db_path=str(db)))
    mem.remember(SECRET)
    mem.close()
    rows = _raw_rows(db)
    assert rows[0][0] == SECRET
    assert rows[0][1] == hashlib.sha256(f"s:{SECRET}".encode()).hexdigest()
