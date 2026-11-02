"""RM-051 — Secure forget for muninn (TH-11).

Threat TH-11 (docs/THREAT_MODEL.md): plain ``forget`` /
``delete`` remove the live rows, but the forgotten content
can still sit in the store's other copies — WAL frames not
yet checkpointed, freed pages in the main file, and every
rolling ``.bak-N`` generation until rotation. This suite is
the roadmap's forensic acceptance test: it searches the
actual files on disk for a forgotten string before and
after, in both directions:

* after plain ``forget``, the string is **still findable**
  (the audit's truth, pinned so it cannot be forgotten);
* after ``secure_forget``, **no file** in the store's
  family — main file, ``-wal``, ``-shm``, every backup
  generation and the backup temp file — holds the string,
  while every other memory survives intact, live and in
  the one fresh backup generation the purge leaves behind.

``secure_forget`` is ``forget`` plus the purge: the delete
runs under ``PRAGMA secure_delete=ON`` (restored
afterwards), the WAL is checkpoint-truncated, the store
file is rewritten with ``VACUUM``, the WAL is truncated
again, and every pre-existing backup generation is
discarded and replaced by a single fresh snapshot of the
purged store (when ``backup_keep`` allows one). Its cost —
a full store rewrite and the loss of all older backup
generations — is stated in docs/SECURE_FORGET.md.
"""

from pathlib import Path

import pytest

from muninn import HebbianMemory
from muninn.config import MuninnConfig
from muninn.errors import MuninnValidationError

SECRET = "rm051-secret-zqxw-forget-me-987654321"
KEEPER = "rm051-keeper-ordinary-memory-123456789"


def _files_holding(base: Path, needle: str) -> list[str]:
    """Every file under ``base`` whose bytes contain ``needle``."""
    hits = []
    for path in sorted(base.iterdir()):
        if path.is_file() and needle.encode() in path.read_bytes():
            hits.append(path.name)
    return hits


def _open(tmp_path: Path, **overrides) -> HebbianMemory:
    config = MuninnConfig(db_path=str(tmp_path / "m.db"), **overrides)
    return HebbianMemory(config)


def test_plain_forget_leaves_the_content_in_the_backups(tmp_path):
    mem = _open(tmp_path)
    secret_id = mem.remember(SECRET, category="secretcat")
    mem.remember(KEEPER, category="general")
    mem.backup()
    assert _files_holding(tmp_path, SECRET)  # the copies exist
    assert mem.forget(secret_id) is True
    assert mem.get_node(secret_id) is None
    # The audit's truth: the live rows are gone, the copies are not.
    holding = _files_holding(tmp_path, SECRET)
    assert any(name.endswith(".bak-1") for name in holding), holding
    mem.close()


def test_secure_forget_purges_every_file_while_open(tmp_path):
    mem = _open(tmp_path)
    secret_id = mem.remember(SECRET, category="secretcat")
    keeper_id = mem.remember(KEEPER, category="general")
    mem.backup()
    assert _files_holding(tmp_path, SECRET)
    assert mem.secure_forget(secret_id) is True
    assert mem.get_node(secret_id) is None
    assert mem.get_node(keeper_id).content == KEEPER
    assert _files_holding(tmp_path, SECRET) == []
    # The one fresh backup generation is a real, purged snapshot:
    # it holds the keeper and not the secret.
    assert _files_holding(tmp_path, KEEPER) != []
    assert (tmp_path / "m.db.bak-1").is_file()
    mem.close()
    assert _files_holding(tmp_path, SECRET) == []


def test_secure_forget_purges_a_checkpointed_store(tmp_path):
    mem = _open(tmp_path)
    secret_id = mem.remember(SECRET, category="secretcat")
    keeper_id = mem.remember(KEEPER, category="general")
    mem.close()  # close checkpoints: the secret now lives in the main file
    assert SECRET.encode() in (tmp_path / "m.db").read_bytes()
    mem = _open(tmp_path)  # auto-backup on open copies it again
    assert _files_holding(tmp_path, SECRET)
    assert mem.secure_forget(secret_id) is True
    assert _files_holding(tmp_path, SECRET) == []
    assert mem.get_node(keeper_id).content == KEEPER
    mem.close()
    assert _files_holding(tmp_path, SECRET) == []
    mem = _open(tmp_path)
    assert mem.get_node(secret_id) is None
    assert mem.get_node(keeper_id).content == KEEPER
    mem.close()


def test_secure_forget_replaces_all_backup_generations(tmp_path):
    mem = _open(tmp_path)
    secret_id = mem.remember(SECRET, category="secretcat")
    mem.remember(KEEPER, category="general")
    mem.backup()
    mem.backup()
    mem.backup()
    generations = [p.name for p in tmp_path.iterdir() if ".bak-" in p.name]
    assert len(generations) == 3
    assert mem.secure_forget(secret_id) is True
    generations = [p.name for p in tmp_path.iterdir() if ".bak-" in p.name]
    assert generations == ["m.db.bak-1"]  # history replaced, not rotated
    assert _files_holding(tmp_path, SECRET) == []
    mem.close()


def test_secure_forget_of_a_missing_id_still_purges(tmp_path):
    mem = _open(tmp_path)
    secret_id = mem.remember(SECRET, category="secretcat")
    mem.backup()
    assert mem.forget(secret_id) is True  # live rows gone, copies remain
    assert _files_holding(tmp_path, SECRET)
    # Nothing live to remove — but the purge still runs, so a
    # caller remediating an earlier plain forget is covered.
    assert mem.secure_forget(999999) is False
    assert _files_holding(tmp_path, SECRET) == []
    mem.close()


def test_secure_forget_with_no_backups_kept(tmp_path):
    mem = _open(tmp_path, backup_keep=0, auto_backup=False)
    secret_id = mem.remember(SECRET, category="secretcat")
    keeper_id = mem.remember(KEEPER, category="general")
    assert mem.secure_forget(secret_id) is True
    assert _files_holding(tmp_path, SECRET) == []
    assert [p.name for p in tmp_path.iterdir() if ".bak-" in p.name] == []
    assert mem.get_node(keeper_id).content == KEEPER
    mem.close()


def test_secure_forget_tombstones_like_forget(tmp_path):
    mem = _open(tmp_path)
    secret_id = mem.remember(SECRET, category="secretcat")
    other_id = mem.remember(KEEPER, category="general")
    mem.associate(secret_id, other_id)
    assert mem.secure_forget(secret_id) is True
    # Wiring is gone with the node, exactly as forget leaves it.
    assert mem.get_associations(other_id) == []
    # The id can live again: re-remembering the same content is
    # a fresh node, not a resurrection of purged bytes.
    new_id = mem.remember(SECRET, category="secretcat")
    assert mem.get_node(new_id).content == SECRET
    mem.close()


def test_secure_forget_validates_the_id(tmp_path):
    mem = _open(tmp_path)
    for bad in (-1, True, "1", 1.5, None):
        with pytest.raises(MuninnValidationError):
            mem.secure_forget(bad)
    mem.close()


def test_secure_forget_on_an_encrypted_store(tmp_path):
    pytest.importorskip("cryptography")
    mem = _open(
        tmp_path, store_encryption=True, encryption_passphrase="rm051-passphrase"
    )
    secret_id = mem.remember(SECRET, category="secretcat")
    keeper_id = mem.remember(KEEPER, category="general")
    # The plaintext never reaches disk at all under RM-049.
    assert _files_holding(tmp_path, SECRET) == []
    assert mem.secure_forget(secret_id) is True
    assert mem.get_node(secret_id) is None
    assert mem.get_node(keeper_id).content == KEEPER
    mem.close()


def test_secure_forget_is_documented(tmp_path):
    here = Path(__file__).resolve()
    record = None
    for parent in here.parents:
        candidate = parent / "docs" / "SECURE_FORGET.md"
        if candidate.is_file() and (parent / "RAVENS_ROADMAP_2026-10-31.md").is_file():
            record = candidate.read_text()
            break
    if record is None:
        pytest.skip("not running inside a repo checkout (no docs/SECURE_FORGET.md)")
    assert "TH-11" in record
    assert "secure_forget" in record
    assert "VACUUM" in record
