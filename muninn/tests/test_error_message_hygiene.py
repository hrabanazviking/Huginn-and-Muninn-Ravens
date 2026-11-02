"""RM-054 — Error-message hygiene for muninn (threat TH-14).

Roadmap rule: typed errors never carry file contents, keys or
full paths beyond the store path the caller itself supplied.

Before this slice, the generic storage branches interpolated
the underlying SQLite exception's text verbatim — and SQLite
can generate that text from the store file itself: a trigger's
``RAISE(ABORT, '…')`` message *is* file content, and it rode
straight into ``MuninnStorageError`` (proven by the probe that
motivated this slice; the same planted text is the fixture
below). The rule now: a typed message is built only from fixed
text, package-computed values (counts, sizes, ids, type names),
the caller's own store path, and the underlying exception's
*class name* — never its text. The full text remains available
through the exception chain (``__cause__``), which this suite
also pins, so no diagnostic is destroyed; it just never
becomes a string this package formats.

Scoping, stated plainly (the TH-14 boundary): validation
messages that echo a caller's own argument value back to that
same caller (``importance … got 'high'``) are deliberate,
RM-018-pinned API, not uncontrolled text, and are out of this
slice's scope. What is scanned here is every surface where
*uncontrolled* text — from the store file, from SQLite, from
a configured secret's neighbourhood — could enter a message.
"""

import ast
from pathlib import Path

import pytest

from muninn import HebbianMemory
from muninn.config import MuninnConfig
from muninn.errors import MuninnStorageError

CONTENT = "PLANTED-CONTENT-rm054"
FOREIGN_PATH = "/foreign/secret/place/other.db"
ENC_PASS = "PLANTED-ENC-PASSPHRASE-rm054"
INT_PASS = "PLANTED-INT-PASSPHRASE-rm054"
LEAK = f"{CONTENT} at {FOREIGN_PATH} via {ENC_PASS} / {INT_PASS}"
TOKENS = (CONTENT, FOREIGN_PATH, ENC_PASS, INT_PASS)


def _scan_clean(message: str) -> None:
    for token in TOKENS:
        assert token not in message, f"{token!r} leaked into: {message}"


def _trigger_store(tmp_path, name, table, passphrase_kwargs=None):
    """A store holding CONTENT as a real memory, plus a trigger
    whose RAISE text is the combined leak (file content, a
    foreign path, and both configured passphrases)."""
    kwargs = dict(passphrase_kwargs or {})
    mem = HebbianMemory(
        MuninnConfig(db_path=str(tmp_path / name), **kwargs)
    )
    mem.remember(CONTENT)
    conn = mem._get_conn()
    conn.execute(
        f"CREATE TRIGGER rm054_leak BEFORE INSERT ON {table}"
        f" BEGIN SELECT RAISE(ABORT, '{LEAK}'); END"
    )
    conn.commit()
    return mem


def test_write_guard_message_scans_clean(tmp_path):
    mem = _trigger_store(tmp_path, "w.db", "nodes")
    with pytest.raises(MuninnStorageError) as caught:
        mem.remember("second memory")
    message = str(caught.value)
    _scan_clean(message)
    assert message == "muninn write failed during remember: IntegrityError"
    # The diagnostic is not destroyed — it lives only in the
    # exception chain, never in the formatted message.
    assert CONTENT in str(caught.value.__cause__)
    mem.close()


def test_prepare_message_scans_clean(tmp_path):
    mem = _trigger_store(tmp_path, "p.db", "meta")
    path = tmp_path / "p.db"
    mem.close()
    with pytest.raises(MuninnStorageError) as caught:
        HebbianMemory(MuninnConfig(db_path=str(path)))
    message = str(caught.value)
    _scan_clean(message)
    # The one allowed path: the store path the caller supplied.
    assert str(path) in message
    assert message.endswith("could not be prepared: IntegrityError")


def test_encrypted_store_write_error_hides_passphrase(tmp_path):
    pytest.importorskip("cryptography")
    mem = _trigger_store(
        tmp_path,
        "enc.db",
        "nodes",
        {"store_encryption": True, "encryption_passphrase": ENC_PASS},
    )
    with pytest.raises(MuninnStorageError) as caught:
        mem.remember("second memory")
    _scan_clean(str(caught.value))
    mem.close()


def test_attested_store_write_error_hides_passphrase(tmp_path):
    mem = _trigger_store(
        tmp_path,
        "att.db",
        "nodes",
        {"integrity_attestation": True, "integrity_passphrase": INT_PASS},
    )
    with pytest.raises(MuninnStorageError) as caught:
        mem.remember("second memory")
    _scan_clean(str(caught.value))
    mem.close()


def test_wrong_passphrase_message_scans_clean(tmp_path):
    pytest.importorskip("cryptography")
    mem = HebbianMemory(
        MuninnConfig(
            db_path=str(tmp_path / "enc.db"),
            store_encryption=True,
            encryption_passphrase=ENC_PASS,
        )
    )
    mem.remember("sealed")
    mem.close()
    wrong = "WRONG-PLANTED-PASSPHRASE-rm054"
    with pytest.raises(MuninnStorageError) as caught:
        HebbianMemory(
            MuninnConfig(
                db_path=str(tmp_path / "enc.db"),
                store_encryption=True,
                encryption_passphrase=wrong,
            )
        )
    message = str(caught.value)
    _scan_clean(message)
    assert wrong not in message


def test_disk_full_message_is_the_packages_own_text(tmp_path):
    mem = HebbianMemory(MuninnConfig(db_path=str(tmp_path / "full.db")))
    mem.remember("seed")
    conn = mem._get_conn()
    pages = conn.execute("PRAGMA page_count").fetchone()[0]
    conn.execute(f"PRAGMA max_page_count={int(pages)}")
    with pytest.raises(MuninnStorageError) as caught:
        mem.remember("z" * 200_000)
    # RM-029's shape, kept — but the wording is now classified
    # and emitted by the package (RM-054), not echoed.
    assert str(caught.value) == (
        "muninn write failed during remember: database or disk is full"
    )
    mem.close()


def test_no_raise_site_interpolates_exception_text():
    """AST pin: in every ``raise Muninn*Error(...)`` message
    expression, an exception variable may appear only as the
    argument of ``_error_kind(...)`` — the class-name helper."""
    here = Path(__file__).resolve()
    src = None
    for parent in here.parents:
        candidate = parent / "muninn" / "src" / "muninn"
        if candidate.is_dir() and (parent / "RAVENS_ROADMAP_2026-10-31.md").is_file():
            src = candidate
            break
    if src is None:
        pytest.skip("not running inside a repo checkout (no src/muninn)")
    error_names = {
        "MuninnValidationError",
        "MuninnConfigurationError",
        "MuninnStorageError",
    }
    violations = []
    for path in sorted(src.glob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call)):
                continue
            func = node.exc.func
            name = func.id if isinstance(func, ast.Name) else None
            if name not in error_names or not node.exc.args:
                continue
            message_expr = node.exc.args[0]
            excused = set()
            for sub in ast.walk(message_expr):
                if (
                    isinstance(sub, ast.Call)
                    and isinstance(sub.func, ast.Name)
                    and sub.func.id == "_error_kind"
                ):
                    for arg in sub.args:
                        excused.add(id(arg))
            for sub in ast.walk(message_expr):
                if (
                    isinstance(sub, ast.Name)
                    and sub.id in {"exc", "e"}
                    and id(sub) not in excused
                ):
                    violations.append(f"{path.name}:{node.lineno}")
    assert violations == []
