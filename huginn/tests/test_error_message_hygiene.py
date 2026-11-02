"""RM-054 — Error-message hygiene for huginn (threat TH-14).

Roadmap rule: typed errors never carry file contents, keys or
full paths beyond the store path the caller itself supplied.

Two uncontrolled-text roads existed. Locally, the generic
storage branches interpolated the underlying SQLite
exception's text verbatim — and SQLite can generate that text
from the store file itself: a trigger's ``RAISE(ABORT, '…')``
message *is* file content. Over the network, wrapped Qdrant
client errors carried the client's text with only the API key
masked (RM-045's ``***`` scrub): a server or proxy error can
quote a payload, a credential, or a path, and masking one
known secret cannot bound text the ravens do not control.

The rule now, both roads: a typed message is built only from
fixed text, package-computed values (counts, sizes, ids, type
names), the caller's own store path / Qdrant URL / collection
name, and the underlying exception's *class name* — never its
text. The full text remains available through the exception
chain (``__cause__``). The facade's non-raising error strings
(``health()``'s error, the ``auto`` fallback reason, a
flight's ``error``) are formatted from typed messages, and
the facade still key-scrubs them as defence in depth — this
suite scans all of them.

Scoping, stated plainly (the TH-14 boundary): validation
messages that echo a caller's own argument value back to that
same caller (``importance … got 'high'``) are deliberate,
RM-018-pinned API, not uncontrolled text, and are out of this
slice's scope. Live Qdrant stays NOT PROVEN — every network
proof below is against fake clients whose error text is the
combined planted leak.
"""

import ast
import sys
import types
from pathlib import Path

import pytest

from huginn import HuginnMemory
from huginn.config import HuginnConfig
from huginn.errors import HuginnBackendError, HuginnStorageError
from huginn.local_backend import LocalBackend
from huginn.qdrant_backend import QdrantBackend
from huginn.text import HashingEmbedder

CONTENT = "PLANTED-CONTENT-rm054"
FOREIGN_PATH = "/foreign/secret/place/other.db"
KEY = "PLANTED-QDRANT-KEY-rm054"
ENC_PASS = "PLANTED-ENC-PASSPHRASE-rm054"
LEAK = f"{CONTENT} at {FOREIGN_PATH} via {KEY} / {ENC_PASS}"
TOKENS = (CONTENT, FOREIGN_PATH, KEY, ENC_PASS)


def _scan_clean(message: str) -> None:
    for token in TOKENS:
        assert token not in message, f"{token!r} leaked into: {message}"


# ─── local road: SQLite text generated from the store file ───


def _trigger_store(tmp_path, name, table):
    mem = HuginnMemory(
        HuginnConfig(backend="local", local_db_path=str(tmp_path / name))
    )
    mem.upsert_memory(CONTENT)
    conn = mem._ensure_backend()._conn
    conn.execute(
        f"CREATE TRIGGER rm054_leak BEFORE INSERT ON {table}"
        f" BEGIN SELECT RAISE(ABORT, '{LEAK}'); END"
    )
    conn.commit()
    return mem


def test_local_write_guard_message_scans_clean(tmp_path):
    mem = _trigger_store(tmp_path, "w.db", "documents")
    with pytest.raises(HuginnStorageError) as caught:
        mem.upsert_memory("second memory")
    message = str(caught.value)
    _scan_clean(message)
    assert message == "huginn write failed during upsert: IntegrityError"
    assert CONTENT in str(caught.value.__cause__)
    mem.close()


def test_local_prepare_message_scans_clean(tmp_path):
    mem = _trigger_store(tmp_path, "p.db", "meta")
    path = tmp_path / "p.db"
    mem.close()
    with pytest.raises(HuginnStorageError) as caught:
        LocalBackend(HuginnConfig(backend="local", local_db_path=str(path)))
    message = str(caught.value)
    _scan_clean(message)
    assert str(path) in message  # the caller's own path: allowed
    assert message.endswith("could not be prepared: IntegrityError")


def test_local_disk_full_message_is_the_packages_own_text(tmp_path):
    mem = HuginnMemory(
        HuginnConfig(backend="local", local_db_path=str(tmp_path / "full.db"))
    )
    mem.upsert_memory("seed")
    conn = mem._ensure_backend()._conn
    pages = conn.execute("PRAGMA page_count").fetchone()[0]
    conn.execute(f"PRAGMA max_page_count={int(pages)}")
    with pytest.raises(HuginnStorageError) as caught:
        mem.upsert_memory("z" * 200_000)
    assert str(caught.value) == (
        "huginn write failed during upsert: database or disk is full"
    )
    mem.close()


def test_local_wrong_passphrase_message_scans_clean(tmp_path):
    pytest.importorskip("cryptography")
    backend = LocalBackend(
        HuginnConfig(
            backend="local",
            local_db_path=str(tmp_path / "enc.db"),
            store_encryption=True,
            encryption_passphrase=ENC_PASS,
        )
    )
    backend.upsert(
        "sealed", category="general", importance=5, tags=[],
        emotional_valence=0.0,
    )
    backend.close()
    wrong = "WRONG-PLANTED-PASSPHRASE-rm054"
    with pytest.raises(HuginnStorageError) as caught:
        LocalBackend(
            HuginnConfig(
                backend="local",
                local_db_path=str(tmp_path / "enc.db"),
                store_encryption=True,
                encryption_passphrase=wrong,
            )
        )
    message = str(caught.value)
    _scan_clean(message)
    assert wrong not in message


# ─── network road: Qdrant client text ────────────────────────


class _FakeModels:
    class Distance:
        COSINE = "cosine"

    @staticmethod
    def VectorParams(size, distance):
        return types.SimpleNamespace(size=size, distance=distance)

    @staticmethod
    def PointStruct(id, vector, payload):
        return types.SimpleNamespace(id=id, vector=vector, payload=payload)

    @staticmethod
    def PointIdsList(points):
        return types.SimpleNamespace(points=points)


class _LeakyClient:
    """Every operation fails with the combined planted leak."""

    def get_collections(self):
        return types.SimpleNamespace(collections=[])

    def get_collection(self, name):
        return types.SimpleNamespace(name=name)

    def _boom(self):
        raise RuntimeError(LEAK)

    def upsert(self, **kwargs):
        self._boom()

    def delete(self, **kwargs):
        self._boom()

    def retrieve(self, **kwargs):
        self._boom()

    def query_points(self, **kwargs):
        self._boom()

    def count(self, **kwargs):
        self._boom()


class _LeakyDownClient:
    def get_collections(self):
        raise RuntimeError(LEAK)


class _LeakyCreateClient:
    def get_collections(self):
        return types.SimpleNamespace(collections=[])

    def get_collection(self, name):
        raise RuntimeError("missing")

    def create_collection(self, **kwargs):
        raise RuntimeError(LEAK)


def _backend(client):
    backend = QdrantBackend(
        HuginnConfig(
            backend="qdrant",
            qdrant_url="https://qdrant.example:6334",
            qdrant_api_key=KEY,
        ),
        HashingEmbedder(dim=64),
    )
    backend._client = client
    backend._models = _FakeModels
    return backend


def test_qdrant_operation_messages_scan_clean():
    backend = _backend(_LeakyClient())
    operations = [
        lambda: backend.upsert(
            "text", category="general", importance=5, tags=[],
            emotional_valence=0.0,
        ),
        lambda: backend.delete(1),
        lambda: backend.get(1),
        lambda: backend.search("text", limit=5, category=None, min_importance=1),
        lambda: backend.count(),
    ]
    for operation in operations:
        with pytest.raises(HuginnBackendError) as caught:
            operation()
        message = str(caught.value)
        _scan_clean(message)
        assert "RuntimeError" in message
        assert CONTENT in str(caught.value.__cause__)
    backend.close()


def test_qdrant_ping_and_create_messages_scan_clean(monkeypatch):
    down = _backend(_LeakyDownClient())
    with pytest.raises(HuginnBackendError) as caught:
        down.ping()
    _scan_clean(str(caught.value))
    assert "RuntimeError" in str(caught.value)
    down.close()

    create = _backend(_LeakyCreateClient())
    with pytest.raises(HuginnBackendError) as caught:
        create.upsert(
            "text", category="general", importance=5, tags=[],
            emotional_valence=0.0,
        )
    _scan_clean(str(caught.value))
    assert "RuntimeError" in str(caught.value)
    create.close()


def _fake_module(monkeypatch, client_cls):
    module = types.ModuleType("qdrant_client")
    module.QdrantClient = client_cls
    module.models = _FakeModels
    monkeypatch.setitem(sys.modules, "qdrant_client", module)
    return module


def test_facade_error_surfaces_scan_clean(monkeypatch, tmp_path):
    _fake_module(monkeypatch, _LeakyDownClient)
    # auto mode: the fallback reason is recorded in health().
    auto = HuginnMemory(
        config=HuginnConfig(
            backend="auto",
            qdrant_url="https://qdrant.example:6334",
            qdrant_api_key=KEY,
            local_db_path=str(tmp_path / "auto.db"),
        )
    )
    try:
        auto.upsert_memory(content="fallback still lands", category="fact")
        health = auto.health()
    finally:
        auto.close()
    assert health["status"] == "degraded"
    _scan_clean(health["fallback_reason"])

    # explicit mode: health()'s error and a flight's error.
    explicit = HuginnMemory(
        config=HuginnConfig(
            backend="qdrant",
            qdrant_url="https://qdrant.example:6334",
            qdrant_api_key=KEY,
            embedder="hashing",
            vector_dim=64,
        )
    )
    try:
        health = explicit.health()
        flight = explicit.fly("anything")
    finally:
        explicit.close()
    assert health["status"] == "unhealthy"
    _scan_clean(health["error"])
    assert flight.error is not None
    _scan_clean(flight.error)


def test_no_raise_site_interpolates_exception_text():
    """AST pin: in every ``raise Huginn*Error(...)`` message
    expression, an exception variable may appear only as the
    argument of ``_error_kind(...)`` (SQLite sites) or of the
    Qdrant backend's ``_scrub(...)`` (class-name helper)."""
    here = Path(__file__).resolve()
    src = None
    for parent in here.parents:
        candidate = parent / "huginn" / "src" / "huginn"
        if candidate.is_dir() and (parent / "RAVENS_ROADMAP_2026-10-31.md").is_file():
            src = candidate
            break
    if src is None:
        pytest.skip("not running inside a repo checkout (no src/huginn)")
    error_names = {
        "HuginnValidationError",
        "HuginnConfigurationError",
        "HuginnStorageError",
        "HuginnBackendError",
    }

    def _helper_name(func):
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            return func.attr
        return None

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
                if isinstance(sub, ast.Call) and _helper_name(sub.func) in {
                    "_error_kind",
                    "_scrub",
                }:
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
