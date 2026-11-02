"""RM-051 — Secure forget for huginn (TH-11).

Threat TH-11 (docs/THREAT_MODEL.md): plain ``delete``
removes the live document, its term-index rows and its
vector, but the forgotten content can still sit in the
local store's other copies — WAL frames not yet
checkpointed, freed pages in the main file, and every
rolling ``.bak-N`` generation until rotation. This suite
is the roadmap's forensic acceptance test for the local
backend: it searches the actual files on disk for a
forgotten string before and after, in both directions:

* after plain ``delete``, the string is **still
  findable** in the backup generations (the audit's
  truth, pinned so it cannot be forgotten);
* after ``secure_forget``, **no file** in the store's
  family — main file, ``-wal``, ``-shm``, every backup
  generation and the backup temp file — holds the
  string, while every other document survives intact,
  live and in the one fresh backup generation the purge
  leaves behind.

``secure_forget`` is ``delete`` plus the purge: the
delete runs under ``PRAGMA secure_delete=ON`` (restored
afterwards), the WAL is checkpoint-truncated, the store
file is rewritten with ``VACUUM``, the WAL is truncated
again, and every pre-existing backup generation is
discarded and replaced by a single fresh snapshot of
the purged store (when ``backup_keep`` allows one). Its
cost — a full store rewrite and the loss of all older
backup generations — is stated in docs/SECURE_FORGET.md.

The Qdrant backend has no local files to purge: its
``secure_forget`` is its ``delete`` (the point is
removed server-side; what the server's own snapshots
retain is the operator's domain, stated in the record
doc). That delegation is pinned here against a stub
client; a live Qdrant round-trip stays NOT PROVEN.
"""

import types
from pathlib import Path

import pytest

from huginn import HuginnConfig, HuginnMemory
from huginn.errors import HuginnValidationError
from huginn.qdrant_backend import QdrantBackend
from huginn.text import HashingEmbedder

SECRET = "rm051-secret-zqxw-forget-me-987654321"
KEEPER = "rm051-keeper-ordinary-memory-123456789"


def _files_holding(base: Path, needle: str) -> list[str]:
    """Every file under ``base`` whose bytes contain ``needle``."""
    hits = []
    for path in sorted(base.iterdir()):
        if path.is_file() and needle.encode() in path.read_bytes():
            hits.append(path.name)
    return hits


def _open(tmp_path: Path, **overrides) -> HuginnMemory:
    base = {"backend": "local", "local_db_path": str(tmp_path / "h.db")}
    base.update(overrides)
    return HuginnMemory(HuginnConfig(**base))


def test_plain_delete_leaves_the_content_in_the_backups(tmp_path):
    h = _open(tmp_path)
    secret_id = h.upsert_memory(SECRET, category="secretcat")
    h.upsert_memory(KEEPER, category="general")
    h.close()
    h = _open(tmp_path)  # auto-backup on open copies the store
    assert _files_holding(tmp_path, SECRET)
    assert h.delete(secret_id) is True
    assert h.get(secret_id) is None
    # The audit's truth: the live rows are gone, the copies are not.
    holding = _files_holding(tmp_path, SECRET)
    assert any(name.endswith(".bak-1") for name in holding), holding
    h.close()


def test_secure_forget_purges_every_file(tmp_path):
    h = _open(tmp_path)
    secret_id = h.upsert_memory(SECRET, category="secretcat")
    keeper_id = h.upsert_memory(KEEPER, category="general")
    h.close()
    h = _open(tmp_path)  # a backup generation now holds the secret
    assert _files_holding(tmp_path, SECRET)
    assert h.secure_forget(secret_id) is True
    assert h.get(secret_id) is None
    assert h.get(keeper_id)["content"] == KEEPER
    assert h.search("zqxw") == []  # the secret's distinctive token is gone
    assert _files_holding(tmp_path, SECRET) == []
    # The one fresh backup generation is a real, purged snapshot:
    # it holds the keeper and not the secret.
    assert _files_holding(tmp_path, KEEPER) != []
    assert (tmp_path / "h.db.bak-1").is_file()
    h.close()
    assert _files_holding(tmp_path, SECRET) == []
    h = _open(tmp_path)
    assert h.get(secret_id) is None
    assert h.get(keeper_id)["content"] == KEEPER
    h.close()


def test_secure_forget_of_a_missing_id_still_purges(tmp_path):
    h = _open(tmp_path)
    secret_id = h.upsert_memory(SECRET, category="secretcat")
    h.close()
    h = _open(tmp_path)
    assert h.delete(secret_id) is True  # live rows gone, copies remain
    assert _files_holding(tmp_path, SECRET)
    # Nothing live to remove — but the purge still runs, so a
    # caller remediating an earlier plain delete is covered.
    assert h.secure_forget(999999) is False
    assert _files_holding(tmp_path, SECRET) == []
    h.close()


def test_secure_forget_with_no_backups_kept(tmp_path):
    h = _open(tmp_path, backup_keep=0, auto_backup=False)
    secret_id = h.upsert_memory(SECRET, category="secretcat")
    keeper_id = h.upsert_memory(KEEPER, category="general")
    assert h.secure_forget(secret_id) is True
    assert _files_holding(tmp_path, SECRET) == []
    assert [p.name for p in tmp_path.iterdir() if ".bak-" in p.name] == []
    assert h.get(keeper_id)["content"] == KEEPER
    h.close()


def test_secure_forget_validates_the_id(tmp_path):
    h = _open(tmp_path)
    h.upsert_memory(KEEPER, category="general")  # force the backend open
    for bad in (-1, True, "1", 1.5, None):
        with pytest.raises(HuginnValidationError):
            h.secure_forget(bad)
    h.close()


def test_secure_forget_on_an_encrypted_store(tmp_path):
    pytest.importorskip("cryptography")
    h = _open(
        tmp_path, store_encryption=True, encryption_passphrase="rm051-passphrase"
    )
    secret_id = h.upsert_memory(SECRET, category="secretcat")
    keeper_id = h.upsert_memory(KEEPER, category="general")
    # The plaintext never reaches disk at all under RM-049.
    assert _files_holding(tmp_path, SECRET) == []
    assert h.secure_forget(secret_id) is True
    assert h.get(secret_id) is None
    assert h.get(keeper_id)["content"] == KEEPER
    h.close()


class _StubClient:
    """The slice of the Qdrant client ``delete`` uses."""

    def __init__(self, points):
        self.points = points  # id -> payload dict
        self.deleted = []

    def retrieve(self, collection_name, ids):
        return [object() for i in ids if i in self.points]

    def delete(self, collection_name, points_selector):
        for point_id in points_selector.points:
            self.deleted.append(point_id)
            self.points.pop(point_id, None)


def test_qdrant_secure_forget_is_the_server_side_delete(tmp_path):
    backend = QdrantBackend(
        HuginnConfig(
            backend="qdrant",
            qdrant_url="http://fake:6333",
            allow_insecure_http=True,
            local_db_path=str(tmp_path / "h.db"),
        ),
        embedder=HashingEmbedder(dim=64),
    )
    stub = _StubClient({7: {"content": SECRET}})
    backend._models = types.SimpleNamespace(
        PointIdsList=lambda points: types.SimpleNamespace(points=points)
    )
    backend.ping = lambda: None  # type: ignore[method-assign]
    backend._ensure_collection = lambda: None  # type: ignore[method-assign]
    backend._ensure_client = lambda: stub  # type: ignore[method-assign]
    assert backend.secure_forget(7) is True
    assert stub.deleted == [7]
    assert backend.secure_forget(7) is False  # already gone
    backend.close()


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
