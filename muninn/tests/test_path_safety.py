"""RM-041 — Path safety for muninn.

Threat TH-02 (docs/THREAT_MODEL.md): a symlinked store path or
parent, or a world-writable parent directory, can redirect a
store — or its restore — somewhere an attacker controls.
Before this slice the behaviour was only *recorded*: paths are
``~``-expanded and deliberately not symlink-resolved, and no
mode checked the parent. This slice adds the explicit opt-in
``MuninnConfig(strict_path_safety=True)``:

* strict ON refuses, on open, with a typed
  ``MuninnStorageError``: a store path that is a symlink or has
  any symlinked parent component, and a store whose parent
  directory is world-writable;
* strict OFF (the default) changes nothing — symlinked paths
  and world-writable parents open exactly as before, which
  these tests also pin, so the opt-in cannot silently become
  the default.

The refusal is a pre-flight at the head of ``open_store`` (the
RM-030/RM-033 pattern): a refused open creates nothing, not
even the RM-037 coordination lock file.
"""

import os

import pytest

from muninn import HebbianMemory, MuninnStorageError
from muninn.config import MuninnConfig

SYMLINK_MSG = (
    "is a symlink or has a symlinked parent and strict path "
    "safety is enabled; refusing to open"
)
WORLD_WRITABLE_MSG = (
    "has a world-writable parent directory and strict path "
    "safety is enabled; refusing to open"
)


def _strict(path):
    return MuninnConfig(db_path=str(path), strict_path_safety=True)


def _real_store(tmp_path):
    real = tmp_path / "real.db"
    mem = HebbianMemory(MuninnConfig(db_path=str(real)))
    mem.remember("alpha")
    mem.close()
    return real


def test_default_mode_opens_symlinked_store_path(tmp_path):
    real = _real_store(tmp_path)
    link = tmp_path / "link.db"
    os.symlink(real, link)
    mem = HebbianMemory(MuninnConfig(db_path=str(link)))
    try:
        assert mem.stats()["total_nodes"] == 1
    finally:
        mem.close()


def test_default_mode_opens_store_under_symlinked_parent(tmp_path):
    real_dir = tmp_path / "realdir"
    real_dir.mkdir()
    link_dir = tmp_path / "linkdir"
    os.symlink(real_dir, link_dir, target_is_directory=True)
    mem = HebbianMemory(MuninnConfig(db_path=str(link_dir / "m.db")))
    try:
        mem.remember("alpha")
        assert mem.stats()["total_nodes"] == 1
    finally:
        mem.close()


def test_default_mode_opens_store_in_world_writable_parent(tmp_path):
    parent = tmp_path / "shared"
    parent.mkdir()
    os.chmod(parent, 0o777)
    mem = HebbianMemory(MuninnConfig(db_path=str(parent / "m.db")))
    try:
        mem.remember("alpha")
        assert mem.stats()["total_nodes"] == 1
    finally:
        mem.close()


def test_strict_mode_refuses_symlinked_store_path(tmp_path):
    real = _real_store(tmp_path)
    link = tmp_path / "link.db"
    os.symlink(real, link)
    with pytest.raises(MuninnStorageError) as excinfo:
        HebbianMemory(_strict(link))
    assert str(excinfo.value) == f"muninn store {link} {SYMLINK_MSG}"
    # The refusal is a pre-flight: nothing was created beside
    # the target, not even the coordination lock file.
    assert not (tmp_path / "link.db.open-lock").exists()


def test_strict_mode_refuses_symlinked_parent(tmp_path):
    real_dir = tmp_path / "realdir"
    real_dir.mkdir()
    link_dir = tmp_path / "linkdir"
    os.symlink(real_dir, link_dir, target_is_directory=True)
    with pytest.raises(MuninnStorageError) as excinfo:
        HebbianMemory(_strict(link_dir / "m.db"))
    assert str(excinfo.value) == f"muninn store {link_dir / 'm.db'} {SYMLINK_MSG}"
    assert not (real_dir / "m.db").exists()


def test_strict_mode_refuses_symlinked_ancestor(tmp_path):
    real_dir = tmp_path / "realdir"
    sub = real_dir / "sub"
    sub.mkdir(parents=True)
    link_dir = tmp_path / "linkdir"
    os.symlink(real_dir, link_dir, target_is_directory=True)
    with pytest.raises(MuninnStorageError) as excinfo:
        HebbianMemory(_strict(link_dir / "sub" / "m.db"))
    assert SYMLINK_MSG in str(excinfo.value)
    assert not (sub / "m.db").exists()


def test_strict_mode_refuses_world_writable_parent(tmp_path):
    parent = tmp_path / "shared"
    parent.mkdir()
    os.chmod(parent, 0o777)
    with pytest.raises(MuninnStorageError) as excinfo:
        HebbianMemory(_strict(parent / "m.db"))
    assert str(excinfo.value) == f"muninn store {parent / 'm.db'} {WORLD_WRITABLE_MSG}"
    assert not (parent / "m.db").exists()
    # The same parent with the world-writable bit removed
    # opens under strict mode and works.
    os.chmod(parent, 0o755)
    mem = HebbianMemory(_strict(parent / "m.db"))
    try:
        mem.remember("alpha")
        assert mem.stats()["total_nodes"] == 1
    finally:
        mem.close()


def test_strict_mode_opens_normal_store_and_reopens(tmp_path):
    path = tmp_path / "m.db"
    mem = HebbianMemory(_strict(path))
    mem.remember("alpha")
    mem.close()
    again = HebbianMemory(_strict(path))
    try:
        assert again.stats()["total_nodes"] == 1
        assert again.recovered_from_backup is False
    finally:
        again.close()


def test_strict_mode_creates_missing_parent(tmp_path):
    path = tmp_path / "newdir" / "m.db"
    mem = HebbianMemory(_strict(path))
    try:
        mem.remember("alpha")
        assert mem.stats()["total_nodes"] == 1
    finally:
        mem.close()
