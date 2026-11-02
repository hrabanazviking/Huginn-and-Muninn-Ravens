"""RM-049 — Store encryption, build (huginn, local backend).

Implements the RM-048 decision (``docs/STORE_ENCRYPTION.md``):
application-level envelope encryption behind the ``encryption``
extra and the ``store_encryption`` config flag. Acceptance,
from the roadmap read through the decision record:

* an encrypted local store's content is unreadable by plain
  sqlite3 — ``documents.content`` / ``documents.tags`` /
  ``doc_vectors.vector`` are ``enc:v1:`` envelopes and the term
  index holds keyed HMAC tags, so no plaintext token of a
  stored memory appears in a raw dump;
* TF-IDF scoring over the transformed terms is the plaintext
  computation (terms are only ever compared for equality);
* a wrong-key open raises the typed storage error with the
  store untouched, and a plain (flag-off) open of a marked
  store refuses the same way;
* the recovery road works against encrypted stores: a corrupt
  main store is restored from its rolling backup and the
  content decrypts.
"""

import hashlib
import sqlite3

import pytest

from huginn import HuginnMemory
from huginn.config import HuginnConfig
from huginn.errors import HuginnConfigurationError, HuginnStorageError

PASSPHRASE = "correct horse battery staple"
SECRET = "zebra quill secret phrase about falcons"


def _enc_config(db, **kw):
    return HuginnConfig(
        backend="local",
        local_db_path=str(db),
        store_encryption=True,
        encryption_passphrase=PASSPHRASE,
        **kw,
    )


def _raw(db, sql):
    conn = sqlite3.connect(str(db))
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def test_encrypted_store_is_unreadable_by_plain_sqlite3(tmp_path):
    db = tmp_path / "h.db"
    mem = HuginnMemory(_enc_config(db))
    mem.upsert_memory(SECRET, category="fact", tags=["silverfalcon"])
    mem.upsert_memory("an ordinary note about harbours", category="fact")
    mem.close()

    docs = _raw(db, "SELECT content, content_hash, tags FROM documents")
    assert len(docs) == 2
    dump = "\n".join(str(value) for row in docs for value in row)
    for token in ("zebra", "quill", "falcons", "silverfalcon", "harbours"):
        assert token not in dump, f"plaintext token {token!r} leaked into the raw store"
    for content, content_hash, tags in docs:
        assert content.startswith("enc:v1:")
        assert tags.startswith("enc:v1:")
        plain = hashlib.sha256(f"fact\x00{SECRET}".encode()).hexdigest()
        assert content_hash != plain
        assert len(content_hash) == 64
    # The term index holds keyed tags, never plaintext tokens.
    terms = [r[0] for r in _raw(db, "SELECT term FROM doc_terms")]
    assert terms and all(len(t) == 64 for t in terms)
    stats_terms = [r[0] for r in _raw(db, "SELECT term FROM corpus_stats")]
    assert stats_terms and all(len(t) == 64 for t in stats_terms)
    assert "zebra" not in terms
    marker = _raw(db, "SELECT value FROM meta WHERE key = 'encryption_version'")
    assert marker and marker[0][0] == "1"


def test_tfidf_search_matches_plain_store_scores(tmp_path):
    corpus = [
        "the falcon hunts over the northern harbour at dawn",
        "zebra quill secret phrase about falcons and harbours",
        "a recipe for barley soup with leeks and thyme",
    ]
    plain = HuginnMemory(
        HuginnConfig(backend="local", local_db_path=str(tmp_path / "plain.db"))
    )
    enc = HuginnMemory(_enc_config(tmp_path / "enc.db"))
    for doc in corpus:
        plain.upsert_memory(doc, category="fact")
        enc.upsert_memory(doc, category="fact")
    plain_hits = plain.search("falcon harbour", limit=5)
    enc_hits = enc.search("falcon harbour", limit=5)
    assert [h["content"] for h in enc_hits] == [h["content"] for h in plain_hits]
    assert len(enc_hits) == len(plain_hits) >= 1
    for enc_hit, plain_hit in zip(enc_hits, plain_hits, strict=True):
        assert enc_hit["score"] == pytest.approx(plain_hit["score"])
    # A query only the second document answers, on both stores.
    plain_hits = plain.search("zebra quill", limit=5)
    enc_hits = enc.search("zebra quill", limit=5)
    assert [h["content"] for h in enc_hits] == [h["content"] for h in plain_hits]
    assert len(enc_hits) == 1 and "zebra" in enc_hits[0]["content"]
    # Idempotent re-upsert under the keyed tag returns the same id.
    first_id = enc_hits[0]["id"]
    assert enc.upsert_memory(enc_hits[0]["content"], category="fact") == first_id
    got = enc.get(first_id)
    assert got is not None and got["content"] == enc_hits[0]["content"]
    plain.close()
    enc.close()


def test_vector_search_over_encrypted_vectors(tmp_path):
    db = tmp_path / "v.db"
    mem = HuginnMemory(_enc_config(db, embedder="hashing"))
    mem.upsert_memory(SECRET, category="fact")
    mem.upsert_memory("an ordinary note about harbours", category="fact")
    hits = mem.search("zebra falcons", limit=5)
    assert hits and hits[0]["content"] == SECRET
    mem.close()
    vectors = _raw(db, "SELECT vector FROM doc_vectors")
    assert vectors and all(v[0].startswith("enc:v1:") for v in vectors)


def test_wrong_passphrase_refused_and_store_untouched(tmp_path):
    db = tmp_path / "h.db"
    mem = HuginnMemory(_enc_config(db))
    mem.upsert_memory(SECRET)
    mem.close()
    before = db.read_bytes()
    with pytest.raises(HuginnStorageError) as excinfo:
        HuginnMemory(
            HuginnConfig(
                backend="local",
                local_db_path=str(db),
                store_encryption=True,
                encryption_passphrase="not the passphrase",
            )
        ).get(1)
    assert "passphrase does not unlock it" in str(excinfo.value)
    assert "not the passphrase" not in str(excinfo.value)
    assert db.read_bytes() == before


def test_plain_open_of_encrypted_store_refused(tmp_path):
    db = tmp_path / "h.db"
    mem = HuginnMemory(_enc_config(db))
    mem.upsert_memory(SECRET)
    mem.close()
    plain = HuginnMemory(HuginnConfig(backend="local", local_db_path=str(db)))
    with pytest.raises(HuginnStorageError) as excinfo:
        plain.get(1)
    assert "is encrypted; refusing to open it without store_encryption" in str(excinfo.value)


def test_flag_on_existing_plain_store_with_documents_refused(tmp_path):
    db = tmp_path / "h.db"
    mem = HuginnMemory(HuginnConfig(backend="local", local_db_path=str(db)))
    mem.upsert_memory("a plain memory")
    mem.close()
    flagged = HuginnMemory(_enc_config(db))
    with pytest.raises(HuginnStorageError) as excinfo:
        flagged.get(1)
    assert "is not encrypted but already holds documents" in str(excinfo.value)


def test_passphrase_required_and_never_in_repr():
    with pytest.raises(HuginnConfigurationError) as excinfo:
        HuginnConfig(store_encryption=True)
    assert "encryption_passphrase is required" in str(excinfo.value)
    config = HuginnConfig(store_encryption=True, encryption_passphrase=PASSPHRASE)
    assert PASSPHRASE not in repr(config)


def test_encrypted_store_recovers_from_rolling_backup(tmp_path):
    db = tmp_path / "h.db"
    mem = HuginnMemory(_enc_config(db))
    keep_id = mem.upsert_memory("the encrypted memory that must survive", category="fact")
    mem.close()
    # The facade is lazy: the second open happens on first use,
    # and it refreshes the rolling backup with that state inside.
    mem = HuginnMemory(_enc_config(db))
    mem.health()
    mem.close()
    assert (tmp_path / "h.db.bak-1").exists()
    with open(db, "r+b") as fh:
        fh.write(b"GARBAGE-NOT-A-DATABASE" * 16)
    mem = HuginnMemory(_enc_config(db))
    health = mem.health()
    assert health["recovered_from_backup"] is True
    got = mem.get(keep_id)
    assert got is not None and "must survive" in got["content"]
    hits = mem.search("encrypted memory survive", limit=5)
    assert hits and hits[0]["id"] == keep_id
    mem.close()


def test_flag_off_store_stays_plaintext(tmp_path):
    db = tmp_path / "h.db"
    mem = HuginnMemory(HuginnConfig(backend="local", local_db_path=str(db)))
    mem.upsert_memory(SECRET, category="fact")
    mem.close()
    docs = _raw(db, "SELECT content, content_hash FROM documents")
    assert docs[0][0] == SECRET
    assert docs[0][1] == hashlib.sha256(f"fact\x00{SECRET}".encode()).hexdigest()
    terms = [r[0] for r in _raw(db, "SELECT term FROM doc_terms")]
    assert "zebra" in terms
