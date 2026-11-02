"""RM-018 — Stable error messages for huginn.

Error strings are API: a caller matching on a message must not
be broken by a casual rewording. Two pins enforce that:

1. Behavioural — every deterministically triggerable typed
   error is raised through the public API, the backends, or
   config construction with fixed inputs, and its exact message
   must equal the CASE lines of ``golden_error_messages.txt``.
   Qdrant failures are produced against a fake client whose
   methods raise ``RuntimeError("boom")`` — the translation
   into ``HuginnBackendError`` is what is pinned; a live
   Qdrant round-trip stays NOT PROVEN.
2. Template — every ``raise Huginn*Error(...)`` site in
   ``src/huginn`` is re-extracted by AST (f-string values
   normalised to ``{}``) and the multiset must equal the
   golden's TEMPLATE lines. This is the pin that also covers
   the two sites no deterministic trigger can reach (the two
   RM-008 no-row-id guards): any new or reworded raise site
   fails here until the golden is updated deliberately in
   the same commit.
"""

import ast
import contextlib
import os
import sqlite3
import sys
import types
from collections import Counter
from pathlib import Path

import pytest

from huginn import HuginnMemory, semantic_search
from huginn.config import HuginnConfig
from huginn.local_backend import LocalBackend
from huginn.qdrant_backend import QdrantBackend, _content_hash, _derived_id
from huginn.text import HashingEmbedder, SentenceTransformerEmbedder

GOLDEN = Path(__file__).parent / "golden_error_messages.txt"
ERROR_NAMES = {
    "HuginnValidationError",
    "HuginnConfigurationError",
    "HuginnStorageError",
    "HuginnBackendError",
}


def _golden():
    cases = {}
    templates = Counter()
    for line in GOLDEN.read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        if line.startswith("CASE "):
            case_id, exc_name, message = line[5:].split(" | ", 2)
            cases[case_id] = (exc_name, message)
        elif line.startswith("TEMPLATE | "):
            _, exc_name, template = line.split(" | ", 2)
            templates[(exc_name, template)] += 1
    return cases, templates


def _capture(fn, tmp_path):
    try:
        fn()
    except Exception as exc:
        return type(exc).__name__, str(exc).replace(str(tmp_path), "<tmp_path>")
    raise AssertionError("trigger did not raise")


@contextlib.contextmanager
def _hidden_module(name):
    """Make ``import name`` raise ImportError, whatever is installed.

    The missing-extra errors must be triggerable even on a
    machine where the extra happens to be present: a ``None``
    in ``sys.modules`` is CPython's documented import blocker.
    """
    missing = object()
    saved = sys.modules.get(name, missing)
    sys.modules[name] = None
    try:
        yield
    finally:
        if saved is missing:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = saved


class _FakeModels:
    Distance = types.SimpleNamespace(COSINE="cosine")

    @staticmethod
    def VectorParams(size, distance):
        return types.SimpleNamespace(size=size, distance=distance)

    @staticmethod
    def PointStruct(id, vector, payload):
        return types.SimpleNamespace(id=id, vector=vector, payload=payload)

    @staticmethod
    def PointIdsList(points):
        return types.SimpleNamespace(points=points)


class _BoomClient:
    """Answers ping/collection checks; every operation fails."""

    def get_collections(self):
        return types.SimpleNamespace(collections=[])

    def get_collection(self, name):
        return types.SimpleNamespace(name=name)

    def upsert(self, **kwargs):
        raise RuntimeError("boom")

    def delete(self, **kwargs):
        raise RuntimeError("boom")

    def retrieve(self, **kwargs):
        raise RuntimeError("boom")

    def query_points(self, **kwargs):
        raise RuntimeError("boom")

    def count(self, **kwargs):
        raise RuntimeError("boom")


class _DownClient:
    def get_collections(self):
        raise RuntimeError("down")


class _MalformedClient:
    """RM-046: answers ping/collection; retrieve hands back
    points whose payload (id 41) or id itself (id 42's point)
    fails the payload hygiene check."""

    def get_collections(self):
        return types.SimpleNamespace(collections=[])

    def get_collection(self, name):
        return types.SimpleNamespace(name=name)

    def retrieve(self, collection_name, ids, with_payload=False):
        if ids == [41]:
            return [types.SimpleNamespace(id=41, payload={"content": "x"})]
        return [types.SimpleNamespace(id="bogus", payload={})]


class _CollidingClient:
    """RM-047: retrieve always hands back a well-formed point
    (correct hash for its own content) holding different
    content at the victim's derived id."""

    def __init__(self, point):
        self._point = point

    def get_collections(self):
        return types.SimpleNamespace(collections=[])

    def get_collection(self, name):
        return types.SimpleNamespace(name=name)

    def retrieve(self, collection_name, ids, with_payload=False):
        return [self._point]


class _NoCollectionClient:
    def get_collections(self):
        return types.SimpleNamespace(collections=[])

    def get_collection(self, name):
        raise RuntimeError("missing")

    def create_collection(self, **kwargs):
        raise RuntimeError("nope")


def _qdrant_backend(client):
    backend = QdrantBackend(
        HuginnConfig(backend="qdrant"), HashingEmbedder(dim=384)
    )
    backend._client = client
    backend._models = _FakeModels
    return backend


def _deep_list(depth):
    root = cur = []
    for _ in range(depth):
        nxt = []
        cur.append(nxt)
        cur = nxt
    return root


def _cases(tmp_path):
    local_cfg = HuginnConfig(backend="local", local_db_path=str(tmp_path / "h.db"))
    h = HuginnMemory(local_cfg)
    tight = HuginnMemory(
        HuginnConfig(
            backend="local",
            local_db_path=str(tmp_path / "tight.db"),
            max_content_bytes=8,
        )
    )
    first_id = h.upsert_memory("shared content")
    assert first_id == 1
    # RM-047: a planted local row (id 2) carrying the victim
    # content's real hash but different content — the
    # idempotent upsert must refuse the hash hit.
    _local_conn = h._ensure_backend()._conn
    _local_conn.execute(
        "INSERT INTO documents (content, content_hash, category,"
        " importance, tags, emotional_valence, created_at, updated_at)"
        " VALUES (?, ?, 'general', 5, '[]', 0.0,"
        " '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')",
        ("planted different content", _content_hash("collision victim", "general")),
    )
    _local_conn.commit()
    # RM-047: a Qdrant point at the victim's derived id holding
    # different content under its own correct hash.
    _q_point = types.SimpleNamespace(
        id=_derived_id(_content_hash("qdrant collision victim", "general")),
        payload={
            "content": "planted different content",
            "category": "general",
            "importance": 5,
            "tags": [],
            "emotional_valence": 0.0,
            "content_hash": _content_hash("planted different content", "general"),
        },
    )
    colliding = _qdrant_backend(_CollidingClient(_q_point))
    closed_local = LocalBackend(
        HuginnConfig(backend="local", local_db_path=str(tmp_path / "l.db"))
    )
    closed_local.close()
    bad_path = tmp_path / "bad.db"
    bad_path.write_bytes(b"this is not a sqlite database at all........")
    # RM-029: a store whose growth is capped at its current page
    # count — the next large write gets SQLite's own SQLITE_FULL.
    full = HuginnMemory(
        HuginnConfig(backend="local", local_db_path=str(tmp_path / "full.db"))
    )
    full.upsert_memory("seed")
    _full_conn = full._ensure_backend()._conn
    _pages = _full_conn.execute("PRAGMA page_count").fetchone()[0]
    _full_conn.execute(f"PRAGMA max_page_count={int(_pages)}")
    # RM-030: a store file marked read-only (no write bit at all)
    # is refused on open with the read-only message.
    ro_path = tmp_path / "ro.db"
    ro_backend = LocalBackend(
        HuginnConfig(backend="local", local_db_path=str(ro_path))
    )
    ro_backend.close()
    os.chmod(ro_path, 0o444)
    # RM-031: a store whose write lock is held by a second
    # connection — opens and writes past a short busy timeout
    # raise the contention messages. The holder stays open for
    # the whole capture pass; it locks only this one file.
    locked_path = tmp_path / "locked.db"
    locked = HuginnMemory(
        HuginnConfig(
            backend="local", local_db_path=str(locked_path), busy_timeout_ms=300
        )
    )
    locked.upsert_memory("seed")
    # RM-033 fix: the holder must stay referenced for the whole
    # capture pass — it is returned to the caller below. Before
    # this, only an incidental reference cycle kept it alive;
    # when the cyclic GC collected it before the locked cases
    # ran, its connection closed, the lock rolled back, and
    # locked_open/locked_upsert intermittently did not raise
    # (diagnosed by per-case capture, RM-033 slice record).
    _holder = sqlite3.connect(str(locked_path))
    _holder.execute("BEGIN EXCLUSIVE")
    _holder.execute("CREATE TABLE IF NOT EXISTS rm031_hold (x INTEGER)")
    _holder.execute("INSERT INTO rm031_hold VALUES (1)")
    # RM-032: a store whose main file is gone but whose WAL
    # remains — the partial-state refusal names the lost main
    # file. The WAL is crafted through a raw connection and
    # restored to disk after its close checkpoints it away.
    walonly_path = tmp_path / "walonly.db"
    walonly = LocalBackend(
        HuginnConfig(backend="local", local_db_path=str(walonly_path))
    )
    walonly.close()
    _wal_conn = sqlite3.connect(str(walonly_path))
    _wal_conn.execute("PRAGMA journal_mode=WAL")
    _wal_conn.execute("INSERT INTO meta(key, value) VALUES ('rm032', 'x')")
    _wal_conn.commit()
    _wal_bytes = Path(f"{walonly_path}-wal").read_bytes()
    _wal_conn.close()
    Path(f"{walonly_path}-wal").write_bytes(_wal_bytes)
    walonly_path.unlink()
    # RM-033: a directory at the store path and a FIFO are
    # refused by the shape pre-flight with their own messages.
    dir_path = tmp_path / "dir.db"
    dir_path.mkdir()
    fifo_path = tmp_path / "fifo.db"
    os.mkfifo(fifo_path)
    # RM-041: a symlinked store path and a world-writable
    # parent directory, both opened with strict path safety on.
    link_path = tmp_path / "link.db"
    os.symlink(tmp_path / "h.db", link_path)
    # RM-049: an encrypted local store for the wrong-passphrase
    # and plain-open refusal cases. Built only when the
    # encryption extra is installed (the campaign's suite env
    # carries it); without it those cases are absent and the
    # golden diff names them plainly.
    enc_path = tmp_path / "enc.db"
    enc_built = False
    try:
        _enc_backend = LocalBackend(
            HuginnConfig(
                backend="local",
                local_db_path=str(enc_path),
                store_encryption=True,
                encryption_passphrase="case passphrase",
            )
        )
        _enc_backend.upsert(
            "sealed",
            category="general",
            importance=5,
            tags=[],
            emotional_valence=0.0,
        )
        _enc_backend.close()
        enc_built = True
    except Exception:
        enc_built = False
    shared_dir = tmp_path / "shared"
    shared_dir.mkdir()
    os.chmod(shared_dir, 0o777)
    # RM-054: stores whose own triggers make SQLite generate
    # its error text from file content — the generic write-guard
    # and prepare branches must name only the exception class.
    trigwrite = HuginnMemory(
        HuginnConfig(backend="local", local_db_path=str(tmp_path / "trigwrite.db"))
    )
    _tw_conn = trigwrite._ensure_backend()._conn
    _tw_conn.execute(
        "CREATE TRIGGER rm054_leak BEFORE INSERT ON documents"
        " BEGIN SELECT RAISE(ABORT, 'planted trigger text'); END"
    )
    _tw_conn.commit()
    trigprep_path = tmp_path / "trigprep.db"
    _trigprep = LocalBackend(
        HuginnConfig(backend="local", local_db_path=str(trigprep_path))
    )
    _tp_conn = _trigprep._conn
    _tp_conn.execute(
        "CREATE TRIGGER rm054_leak BEFORE INSERT ON meta"
        " BEGIN SELECT RAISE(ABORT, 'planted trigger text'); END"
    )
    _tp_conn.commit()
    _trigprep.close()
    embedder = HashingEmbedder(dim=384)
    qdrant_cfg = HuginnConfig(backend="qdrant")
    closed_qdrant = QdrantBackend(qdrant_cfg, embedder)
    closed_qdrant.close()
    boom = _qdrant_backend(_BoomClient())
    down = _qdrant_backend(_DownClient())
    no_collection = _qdrant_backend(_NoCollectionClient())
    malformed = _qdrant_backend(_MalformedClient())

    def cfg(**overrides):
        return lambda: HuginnConfig(**overrides)

    def missing_qdrant_extra():
        with _hidden_module("qdrant_client"):
            QdrantBackend(qdrant_cfg, embedder)._ensure_client()

    def missing_st_extra():
        with _hidden_module("sentence_transformers"):
            SentenceTransformerEmbedder()

    def close_facade():
        h.close()
        h.search("hello")

    cases = {
        "config_backend": cfg(backend="bogus"),
        "config_embedder": cfg(embedder="bogus"),
        "config_qdrant_url": cfg(qdrant_url=""),
        "config_qdrant_url_scheme": cfg(qdrant_url="ftp://localhost:6333"),
        "config_qdrant_url_host": cfg(qdrant_url="https://"),
        "config_qdrant_url_insecure": cfg(
            qdrant_url="http://qdrant.example:6333"
        ),
        "config_local_db_path": cfg(local_db_path=""),
        "config_collection_name": cfg(collection_name=""),
        "config_vector_dim": cfg(vector_dim=7),
        "config_qdrant_timeout": cfg(qdrant_timeout=0),
        "config_busy_timeout": cfg(busy_timeout_ms=-1),
        "config_backup_keep": cfg(backup_keep=-1),
        "config_max_content_bytes": cfg(max_content_bytes=0),
        "config_max_search_candidates": cfg(max_search_candidates=0),
        "content_oversize": lambda: tight.upsert_memory("123456789"),
        "config_st_model": cfg(st_model=""),
        "config_api_key_type": cfg(qdrant_api_key=123),
        "content_empty": lambda: h.upsert_memory(""),
        "importance_type": lambda: h.upsert_memory("a", importance="high"),
        "importance_range": lambda: h.upsert_memory("a", importance=11),
        "valence_type": lambda: h.upsert_memory("a", emotional_valence="warm"),
        "valence_range": lambda: h.upsert_memory("a", emotional_valence=1.5),
        "memory_id_type": lambda: h.get("x"),
        "memory_id_negative": lambda: h.get(-1),
        "memory_id_ceiling": lambda: h.get(2**63),
        "query_text_type": lambda: h.search(123),
        "min_importance_type": lambda: h.search("hello", min_importance=1.5),
        "min_importance_ceiling": lambda: h.search("hello", min_importance=2**63),
        "limit_type": lambda: h.search("hello", limit="x"),
        "category_type": lambda: h.search("hello", category=123),
        "tags_type": lambda: h.upsert_memory("a", tags=42),
        "documents_type": lambda: semantic_search("ravens", 123),
        "embedder_unknown": lambda: h._make_embedder("bogus"),
        "local_id_clash": lambda: h.upsert_memory("shared content", memory_id=99),
        "local_hash_collision": lambda: h.upsert_memory("collision victim"),
        "qdrant_hash_collision": lambda: colliding.upsert(
            "qdrant collision victim", category="general", importance=5,
            tags=[], emotional_valence=0.0,
        ),
        "write_guard_generic": lambda: trigwrite.upsert_memory("anything"),
        "prepare_generic": lambda: LocalBackend(
            HuginnConfig(backend="local", local_db_path=str(trigprep_path))
        ),
        "facade_closed": close_facade,
        "local_closed": lambda: closed_local.upsert(
            "x", category="general", importance=5, tags=[], emotional_valence=0.0
        ),
        "corrupt_store": lambda: LocalBackend(
            HuginnConfig(
                backend="local", local_db_path=str(bad_path), backup_keep=0
            )
        ),
        "qdrant_closed": lambda: closed_qdrant._ensure_client(),
        "qdrant_missing_extra": missing_qdrant_extra,
        "st_missing_extra": missing_st_extra,
        "qdrant_unreachable": lambda: down.ping(),
        "qdrant_collection_create": lambda: no_collection.upsert(
            "text", category="general", importance=5, tags=[], emotional_valence=0.0
        ),
        "qdrant_upsert_failed": lambda: boom.upsert(
            "text", category="general", importance=5, tags=[], emotional_valence=0.0
        ),
        "qdrant_delete_failed": lambda: boom.delete(1),
        "qdrant_retrieve_failed": lambda: boom.get(1),
        "qdrant_search_failed": lambda: boom.search(
            "text", limit=5, category=None, min_importance=1
        ),
        "qdrant_count_failed": lambda: boom.count(),
        "qdrant_malformed_payload": lambda: malformed.get(41),
        "qdrant_malformed_point_id": lambda: malformed.get(42),
        "disk_full_upsert": lambda: full.upsert_memory("z" * 200_000),
        "readonly_open": lambda: LocalBackend(
            HuginnConfig(backend="local", local_db_path=str(ro_path))
        ),
        "locked_open": lambda: LocalBackend(
            HuginnConfig(
                backend="local",
                local_db_path=str(locked_path),
                busy_timeout_ms=300,
            )
        ),
        "locked_upsert": lambda: locked.upsert_memory("blocked"),
        "missing_main_wal": lambda: LocalBackend(
            HuginnConfig(
                backend="local", local_db_path=str(walonly_path), backup_keep=0
            )
        ),
        "directory_store": lambda: LocalBackend(
            HuginnConfig(backend="local", local_db_path=str(dir_path))
        ),
        "nonfile_store": lambda: LocalBackend(
            HuginnConfig(backend="local", local_db_path=str(fifo_path))
        ),
        "strict_symlink_open": lambda: LocalBackend(
            HuginnConfig(
                backend="local",
                local_db_path=str(link_path),
                strict_path_safety=True,
            )
        ),
        "strict_world_writable_open": lambda: LocalBackend(
            HuginnConfig(
                backend="local",
                local_db_path=str(shared_dir / "h.db"),
                strict_path_safety=True,
            )
        ),
        "content_surrogate": lambda: h.upsert_memory("bad \ud800 end"),
        "query_surrogate": lambda: h.search("bad \ud800"),
        "tags_too_deep": lambda: h.upsert_memory("ok", tags=[_deep_list(101)]),
        "tags_oversize": lambda: tight.upsert_memory("ok", tags=["abcdefghij"]),
        **(
            {
                "encryption_passphrase_required": lambda: HuginnConfig(
                    store_encryption=True
                ),
                "encryption_wrong_passphrase": lambda: LocalBackend(
                    HuginnConfig(
                        backend="local",
                        local_db_path=str(enc_path),
                        store_encryption=True,
                        encryption_passphrase="wrong passphrase",
                    )
                ),
                "encryption_plain_open": lambda: LocalBackend(
                    HuginnConfig(backend="local", local_db_path=str(enc_path))
                ),
            }
            if enc_built
            else {}
        ),
    }
    return cases, _holder


def test_error_messages_match_golden(tmp_path):
    golden_cases, _ = _golden()
    cases, _holder = _cases(tmp_path)
    actual = {case_id: _capture(fn, tmp_path) for case_id, fn in cases.items()}
    assert actual == golden_cases


def _template_of(expr):
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return expr.value
    if isinstance(expr, ast.JoinedStr):
        parts = []
        for value in expr.values:
            if isinstance(value, ast.Constant):
                parts.append(str(value.value))
            else:
                parts.append("{}")
        return "".join(parts)
    raise AssertionError(f"unsupported raise-message expression: {ast.dump(expr)[:80]}")


def _source_templates():
    here = Path(__file__).resolve()
    src = None
    for parent in here.parents:
        candidate = parent / "huginn" / "src" / "huginn"
        if candidate.is_dir() and (parent / "RAVENS_ROADMAP_2026-10-31.md").is_file():
            src = candidate
            break
    if src is None:
        pytest.skip("not running inside a repo checkout (no src/huginn)")
    found = Counter()
    for path in sorted(src.glob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call)):
                continue
            func = node.exc.func
            name = func.id if isinstance(func, ast.Name) else None
            if name in ERROR_NAMES:
                assert node.exc.args, f"raise without a message at {path}:{node.lineno}"
                found[(name, _template_of(node.exc.args[0]))] += 1
    return found


def test_every_raise_site_template_is_pinned():
    _, golden_templates = _golden()
    actual = _source_templates()
    if actual != golden_templates:
        lines = []
        for key in sorted((actual - golden_templates) + (golden_templates - actual)):
            lines.append(
                f"{key[0]} | {key[1]} "
                f"(source x{actual[key]}, golden x{golden_templates[key]})"
            )
        raise AssertionError(
            "huginn raise sites drifted from the RM-018 golden templates. "
            "If a message change is deliberate, update "
            "golden_error_messages.txt in the same commit.\n" + "\n".join(lines)
        )


def test_golden_cases_cover_every_typed_error_class():
    golden_cases, _ = _golden()
    covered = {exc_name for exc_name, _ in golden_cases.values()}
    assert covered == ERROR_NAMES
