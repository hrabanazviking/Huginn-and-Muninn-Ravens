"""RM-041 — Path safety for huginn (local backend).

Threat TH-02 (docs/THREAT_MODEL.md): a symlinked store path or
parent, or a world-writable parent directory, can redirect a
store — or its restore — somewhere an attacker controls.
Before this slice the behaviour was only *recorded*: paths are
``~``-expanded and deliberately not symlink-resolved, and no
mode checked the parent. This slice adds the explicit opt-in
``HuginnConfig(strict_path_safety=True)`` for the local
backend (the Qdrant backend has no local file):

* strict ON refuses, on open, with a typed
  ``HuginnStorageError``: a store path that is a symlink or has
  any symlinked parent component, and a store whose parent
  directory is world-writable;
* strict OFF (the default) changes nothing — symlinked paths
  and world-writable parents open exactly as before, which
  these tests also pin, so the opt-in cannot silently become
  the default.

The refusal is a pre-flight at the head of ``open_store`` (the
RM-030/RM-033 pattern): a refused open creates nothing, not
even the RM-037 coordination lock file. Refusals are proven
against ``LocalBackend`` directly (the facade is lazy, so a
backend refusal surfaces on first use); success paths are
proven through the facade.
"""

import os

import pytest

from huginn import HuginnMemory, HuginnStorageError
from huginn.config import HuginnConfig
from huginn.local_backend import LocalBackend

SYMLINK_MSG = (
    "is a symlink or has a symlinked parent and strict path "
    "safety is enabled; refusing to open"
)
WORLD_WRITABLE_MSG = (
    "has a world-writable parent directory and strict path "
    "safety is enabled; refusing to open"
)


def _cfg(path, **overrides):
    return HuginnConfig(backend="local", local_db_path=str(path), **overrides)


def _strict(path):
    return _cfg(path, strict_path_safety=True)


def _real_store(tmp_path):
    real = tmp_path / "real.db"
    mem = HuginnMemory(_cfg(real))
    mem.upsert_memory("alpha memory")
    mem.close()
    return real


def test_default_mode_opens_symlinked_store_path(tmp_path):
    real = _real_store(tmp_path)
    link = tmp_path / "link.db"
    os.symlink(real, link)
    mem = HuginnMemory(_cfg(link))
    try:
        assert len(mem.search("alpha")) == 1
    finally:
        mem.close()


def test_default_mode_opens_store_under_symlinked_parent(tmp_path):
    real_dir = tmp_path / "realdir"
    real_dir.mkdir()
    link_dir = tmp_path / "linkdir"
    os.symlink(real_dir, link_dir, target_is_directory=True)
    mem = HuginnMemory(_cfg(link_dir / "h.db"))
    try:
        mem.upsert_memory("alpha memory")
        assert len(mem.search("alpha")) == 1
    finally:
        mem.close()


def test_default_mode_opens_store_in_world_writable_parent(tmp_path):
    parent = tmp_path / "shared"
    parent.mkdir()
    os.chmod(parent, 0o777)
    mem = HuginnMemory(_cfg(parent / "h.db"))
    try:
        mem.upsert_memory("alpha memory")
        assert len(mem.search("alpha")) == 1
    finally:
        mem.close()


def test_strict_mode_refuses_symlinked_store_path(tmp_path):
    real = _real_store(tmp_path)
    link = tmp_path / "link.db"
    os.symlink(real, link)
    with pytest.raises(HuginnStorageError) as excinfo:
        LocalBackend(_strict(link))
    assert str(excinfo.value) == f"huginn store {link} {SYMLINK_MSG}"
    # The refusal is a pre-flight: nothing was created beside
    # the target, not even the coordination lock file.
    assert not (tmp_path / "link.db.open-lock").exists()


def test_strict_mode_refuses_symlinked_parent(tmp_path):
    real_dir = tmp_path / "realdir"
    real_dir.mkdir()
    link_dir = tmp_path / "linkdir"
    os.symlink(real_dir, link_dir, target_is_directory=True)
    with pytest.raises(HuginnStorageError) as excinfo:
        LocalBackend(_strict(link_dir / "h.db"))
    assert str(excinfo.value) == f"huginn store {link_dir / 'h.db'} {SYMLINK_MSG}"
    assert not (real_dir / "h.db").exists()


def test_strict_mode_refuses_symlinked_ancestor(tmp_path):
    real_dir = tmp_path / "realdir"
    sub = real_dir / "sub"
    sub.mkdir(parents=True)
    link_dir = tmp_path / "linkdir"
    os.symlink(real_dir, link_dir, target_is_directory=True)
    with pytest.raises(HuginnStorageError) as excinfo:
        LocalBackend(_strict(link_dir / "sub" / "h.db"))
    assert SYMLINK_MSG in str(excinfo.value)
    assert not (sub / "h.db").exists()


def test_strict_mode_refuses_world_writable_parent(tmp_path):
    parent = tmp_path / "shared"
    parent.mkdir()
    os.chmod(parent, 0o777)
    with pytest.raises(HuginnStorageError) as excinfo:
        LocalBackend(_strict(parent / "h.db"))
    assert str(excinfo.value) == f"huginn store {parent / 'h.db'} {WORLD_WRITABLE_MSG}"
    assert not (parent / "h.db").exists()
    # The same parent with the world-writable bit removed
    # opens under strict mode and works.
    os.chmod(parent, 0o755)
    mem = HuginnMemory(_strict(parent / "h.db"))
    try:
        mem.upsert_memory("alpha memory")
        assert len(mem.search("alpha")) == 1
    finally:
        mem.close()


def test_strict_mode_opens_normal_store_and_reopens(tmp_path):
    path = tmp_path / "h.db"
    mem = HuginnMemory(_strict(path))
    mem.upsert_memory("alpha memory")
    mem.close()
    again = HuginnMemory(_strict(path))
    try:
        assert len(again.search("alpha")) == 1
        assert again.health()["recovered_from_backup"] is False
    finally:
        again.close()


def test_strict_mode_creates_missing_parent(tmp_path):
    path = tmp_path / "newdir" / "h.db"
    mem = HuginnMemory(_strict(path))
    try:
        mem.upsert_memory("alpha memory")
        assert len(mem.search("alpha")) == 1
    finally:
        mem.close()
