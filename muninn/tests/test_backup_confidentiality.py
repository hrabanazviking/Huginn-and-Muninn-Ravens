"""RM-043 — Backup confidentiality for muninn.

Threat TH-04 (docs/THREAT_MODEL.md): the rolling ``.bak-N``
generations are full copies of memory. RM-042 made new
store files owner-only, but a backup snapshot was still
created by SQLite under the process umask — an owner-only
store's backup could land at ``0o644``, readable by every
local account, for as long as the generation is kept. This
slice (docs/BACKUP_CONFIDENTIALITY.md): the snapshot
inherits the store file's own permissions at the moment it
is taken — owner-only in, owner-only out; a deliberately
loosened store's backups inherit exactly that looseness
(inheritance, not a forced mode), and rotated generations
keep the mode they were taken with.

POSIX permission tests.
"""

import os
import stat

import pytest

from muninn import HebbianMemory
from muninn.config import MuninnConfig

pytestmark = pytest.mark.skipif(
    os.name != "posix", reason="POSIX permission bits required"
)


def _mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


def _open(path):
    return HebbianMemory(MuninnConfig(db_path=str(path)))


def test_backup_of_owner_only_store_is_owner_only(tmp_path):
    path = tmp_path / "m.db"
    mem = _open(path)
    try:
        mem.remember("alpha")
        taken = mem.backup()
        assert taken is not None
        assert _mode(path) == 0o600
        assert _mode(taken) == 0o600
        assert _mode(tmp_path / "m.db.bak-1") == 0o600
    finally:
        mem.close()


def test_backup_inherits_even_under_permissive_umask(tmp_path):
    path = tmp_path / "m.db"
    mem = _open(path)
    try:
        mem.remember("alpha")
        old_umask = os.umask(0)
        try:
            taken = mem.backup()
        finally:
            os.umask(old_umask)
        assert taken is not None
        # Without the slice the snapshot would be 0o666 here.
        assert _mode(taken) == 0o600
    finally:
        mem.close()


def test_backup_inherits_a_loosened_store_mode(tmp_path):
    path = tmp_path / "m.db"
    mem = _open(path)
    mem.remember("alpha")
    mem.close()
    os.chmod(path, 0o644)
    again = _open(path)
    try:
        taken = again.backup()
        assert taken is not None
        # Inheritance, not a forced 0600: the owner's stated
        # looseness is the backup's mode too.
        assert _mode(taken) == 0o644
    finally:
        again.close()


def test_backup_on_open_inherits_store_mode(tmp_path):
    path = tmp_path / "m.db"
    mem = _open(path)
    mem.remember("alpha")
    mem.close()
    os.chmod(path, 0o640)
    again = _open(path)  # auto-backup on open: no .bak-1 yet
    try:
        bak = tmp_path / "m.db.bak-1"
        assert bak.exists()
        assert _mode(bak) == 0o640
    finally:
        again.close()


def test_rotated_generations_keep_the_mode_they_were_taken_with(tmp_path):
    path = tmp_path / "m.db"
    mem = _open(path)
    try:
        mem.remember("alpha")
        first = mem.backup()
        assert first is not None and _mode(first) == 0o600
    finally:
        mem.close()
    os.chmod(path, 0o644)
    # auto_backup off: this test isolates explicit backup()
    # rotation (an auto-backup on the reopen would rotate too).
    again = HebbianMemory(
        MuninnConfig(db_path=str(path), auto_backup=False)
    )
    try:
        again.remember("beta")
        second = again.backup()
        assert second is not None
        assert _mode(tmp_path / "m.db.bak-1") == 0o644  # newest: inherited now
        assert _mode(tmp_path / "m.db.bak-2") == 0o600  # rotated: kept its own
    finally:
        again.close()
