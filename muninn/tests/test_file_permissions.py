"""RM-042 — File permissions for muninn.

Threat TH-03 (docs/THREAT_MODEL.md): before this slice a new
store file was created by SQLite under the process umask —
``0o644`` on a typical ``022`` umask — so every local account
could read the memories. This slice (docs/FILE_PERMISSIONS.md):

* a store file created by an open (fresh store, or one
  restored onto a path that did not exist) is set owner-only
  ``0o600`` where the OS allows, with its WAL/SHM sidecars;
* an existing store's permissions are never changed by
  opening it — a looser existing file is reported in
  ``health()`` as the ``file_permissions_warning`` field
  (None when the file grants nothing to group/other).

Linux/POSIX permission tests, per the roadmap's acceptance.
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


def test_new_store_file_is_owner_only(tmp_path):
    path = tmp_path / "m.db"
    mem = _open(path)
    try:
        mem.remember("alpha")
        assert _mode(path) == 0o600
    finally:
        mem.close()
    assert _mode(path) == 0o600


def test_new_store_file_is_owner_only_even_under_permissive_umask(tmp_path):
    path = tmp_path / "m.db"
    old_umask = os.umask(0)
    try:
        mem = _open(path)
        try:
            mem.remember("alpha")
        finally:
            mem.close()
    finally:
        os.umask(old_umask)
    # Without the slice this file would be 0o666 under umask 0.
    assert _mode(path) == 0o600


def test_new_store_sidecars_are_owner_only_while_open(tmp_path):
    path = tmp_path / "m.db"
    mem = _open(path)
    try:
        mem.remember("alpha")
        for suffix in ("-wal", "-shm"):
            sidecar = tmp_path / f"m.db{suffix}"
            if sidecar.exists():
                assert _mode(sidecar) == 0o600, suffix
    finally:
        mem.close()


def test_new_store_health_has_no_permissions_warning(tmp_path):
    mem = _open(tmp_path / "m.db")
    try:
        mem.remember("alpha")
        assert mem.health()["file_permissions_warning"] is None
    finally:
        mem.close()


def test_existing_looser_file_is_not_repermissioned_but_warns(tmp_path):
    path = tmp_path / "m.db"
    mem = _open(path)
    mem.remember("alpha")
    mem.close()
    os.chmod(path, 0o644)
    again = _open(path)
    try:
        assert again.stats()["total_nodes"] == 1
        # Opening never silently rewrites an existing file's mode.
        assert _mode(path) == 0o644
        warning = again.health()["file_permissions_warning"]
        assert warning is not None
        assert "0644" in warning
        assert "0600" in warning
    finally:
        again.close()
    assert _mode(path) == 0o644


def test_existing_group_readable_file_warns_with_its_mode(tmp_path):
    path = tmp_path / "m.db"
    mem = _open(path)
    mem.remember("alpha")
    mem.close()
    os.chmod(path, 0o640)
    again = _open(path)
    try:
        warning = again.health()["file_permissions_warning"]
        assert warning is not None
        assert "0640" in warning
    finally:
        again.close()


def test_existing_owner_only_file_reopens_without_warning(tmp_path):
    path = tmp_path / "m.db"
    mem = _open(path)
    mem.remember("alpha")
    mem.close()
    assert _mode(path) == 0o600
    again = _open(path)
    try:
        assert again.health()["file_permissions_warning"] is None
        assert _mode(path) == 0o600
    finally:
        again.close()
