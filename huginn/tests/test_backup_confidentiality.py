"""RM-043 — Backup confidentiality for huginn (local backend).

Threat TH-04 (docs/THREAT_MODEL.md): the rolling ``.bak-N``
generations are full copies of memory. RM-042 made new
local store files owner-only, but a backup snapshot was
still created by SQLite under the process umask — an
owner-only store's backup could land at ``0o644``, readable
by every local account, for as long as the generation is
kept. This slice (docs/BACKUP_CONFIDENTIALITY.md): the
snapshot inherits the store file's own permissions at the
moment it is taken — owner-only in, owner-only out; a
deliberately loosened store's backups inherit exactly that
looseness (inheritance, not a forced mode), and rotated
generations keep the mode they were taken with.

Backups are exercised through the roads callers actually
hit: the auto-backup on open, and ``huginn._db.take_backup``
(the machinery every Huginn backup goes through).

POSIX permission tests.
"""

import os
import stat

import pytest

from huginn import HuginnMemory
from huginn._db import take_backup
from huginn.config import HuginnConfig

pytestmark = pytest.mark.skipif(
    os.name != "posix", reason="POSIX permission bits required"
)


def _mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


def _open(path):
    return HuginnMemory(
        HuginnConfig(backend="local", local_db_path=str(path))
    )


def test_backup_on_open_of_owner_only_store_is_owner_only(tmp_path):
    path = tmp_path / "h.db"
    mem = _open(path)
    mem.upsert_memory("alpha memory")
    mem.close()
    assert _mode(path) == 0o600
    again = _open(path)  # auto-backup on open: no .bak-1 yet
    try:
        again.health()  # Huginn is lazy: first use opens the store
        bak = tmp_path / "h.db.bak-1"
        assert bak.exists()
        assert _mode(bak) == 0o600
    finally:
        again.close()


def test_backup_inherits_even_under_permissive_umask(tmp_path):
    path = tmp_path / "h.db"
    mem = _open(path)
    mem.upsert_memory("alpha memory")
    mem.close()
    old_umask = os.umask(0)
    try:
        taken = take_backup(path, 3)
    finally:
        os.umask(old_umask)
    assert taken is not None
    # Without the slice the snapshot would be 0o666 here.
    assert _mode(taken) == 0o600


def test_backup_inherits_a_loosened_store_mode(tmp_path):
    path = tmp_path / "h.db"
    mem = _open(path)
    mem.upsert_memory("alpha memory")
    mem.close()
    os.chmod(path, 0o644)
    taken = take_backup(path, 3)
    assert taken is not None
    # Inheritance, not a forced 0600.
    assert _mode(taken) == 0o644


def test_rotated_generations_keep_the_mode_they_were_taken_with(tmp_path):
    path = tmp_path / "h.db"
    mem = _open(path)
    mem.upsert_memory("alpha memory")
    mem.close()
    first = take_backup(path, 3)
    assert first is not None and _mode(first) == 0o600
    os.chmod(path, 0o640)
    second = take_backup(path, 3)
    assert second is not None
    assert _mode(tmp_path / "h.db.bak-1") == 0o640  # newest: inherited now
    assert _mode(tmp_path / "h.db.bak-2") == 0o600  # rotated: kept its own
