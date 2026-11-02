"""RM-018 — Stable error messages for muninn.

Error strings are API: a caller matching on a message must not
be broken by a casual rewording. Two pins enforce that:

1. Behavioural — every deterministically triggerable typed
   error is raised through the public API (or config
   construction) with fixed inputs, and its exact message must
   equal the CASE lines of ``golden_error_messages.txt``.
2. Template — every ``raise Muninn*Error(...)`` site in
   ``src/muninn`` is re-extracted by AST (f-string values
   normalised to ``{}``) and the multiset must equal the
   golden's TEMPLATE lines. This is the pin that also covers
   the one site no deterministic trigger can reach (the
   RM-008 no-row-id guard; RM-054 gave the schema-preparation
   failure a deterministic trigger — a store trigger aborting
   the prepare-time meta insert):
   any new or reworded raise site fails here until the golden
   is updated deliberately in the same commit.
"""

import ast
import hashlib
import os
import sqlite3
from collections import Counter
from pathlib import Path

import pytest

from muninn import HebbianMemory
from muninn.config import MuninnConfig

GOLDEN = Path(__file__).parent / "golden_error_messages.txt"
ERROR_NAMES = {
    "MuninnValidationError",
    "MuninnConfigurationError",
    "MuninnStorageError",
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


def _deep_dict(depth):
    root = cur = {}
    for _ in range(depth):
        cur["a"] = {}
        cur = cur["a"]
    return root


def _deep_list(depth):
    root = cur = []
    for _ in range(depth):
        nxt = []
        cur.append(nxt)
        cur = nxt
    return root


def _cases(tmp_path):
    m = HebbianMemory(MuninnConfig(db_path=str(tmp_path / "m.db")))
    alpha = m.remember("alpha")
    beta = m.remember("beta")
    assert alpha != beta
    circular = {}
    circular["loop"] = circular
    closed = HebbianMemory(MuninnConfig(db_path=str(tmp_path / "closed.db")))
    closed.close()
    tight = HebbianMemory(
        MuninnConfig(
            db_path=str(tmp_path / "tight.db"),
            max_content_bytes=8,
            max_metadata_bytes=8,
        )
    )
    bad_path = tmp_path / "bad.db"
    bad_path.write_bytes(b"this is not a sqlite database at all........")
    # RM-029: a store whose growth is capped at its current page
    # count — the next large write gets SQLite's own SQLITE_FULL.
    full = HebbianMemory(MuninnConfig(db_path=str(tmp_path / "full.db")))
    full.remember("seed")
    _full_conn = full._get_conn()
    _pages = _full_conn.execute("PRAGMA page_count").fetchone()[0]
    _full_conn.execute(f"PRAGMA max_page_count={int(_pages)}")
    # RM-030: a store file marked read-only (no write bit at all)
    # is refused on open with the read-only message.
    ro_path = tmp_path / "ro.db"
    ro_mem = HebbianMemory(MuninnConfig(db_path=str(ro_path)))
    ro_mem.close()
    os.chmod(ro_path, 0o444)
    # RM-031: a store whose write lock is held by a second
    # connection — opens and writes past a short busy timeout
    # raise the contention messages. The holder stays open for
    # the whole capture pass; it locks only this one file.
    locked_path = tmp_path / "locked.db"
    locked = HebbianMemory(
        MuninnConfig(db_path=str(locked_path), busy_timeout_ms=300)
    )
    locked.remember("seed")
    # RM-033 fix: the holder must stay referenced for the whole
    # capture pass — it is returned to the caller below. Before
    # this, only an incidental reference cycle kept it alive;
    # when the cyclic GC collected it before the locked cases
    # ran, its connection closed, the lock rolled back, and
    # locked_open/locked_remember intermittently did not raise
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
    walonly = HebbianMemory(MuninnConfig(db_path=str(walonly_path)))
    walonly.remember("stranded")
    walonly.close()
    _wal_conn = sqlite3.connect(str(walonly_path))
    _wal_conn.execute("PRAGMA journal_mode=WAL")
    _wal_conn.execute("INSERT INTO meta(key, value) VALUES ('rm032', 'x')")
    _wal_conn.commit()
    _wal_bytes = Path(f"{walonly_path}-wal").read_bytes()
    _wal_conn.close()
    Path(f"{walonly_path}-wal").write_bytes(_wal_bytes)
    # RM-033: a directory at the store path and a FIFO are
    # refused by the shape pre-flight with their own messages.
    dir_path = tmp_path / "dir.db"
    dir_path.mkdir()
    fifo_path = tmp_path / "fifo.db"
    os.mkfifo(fifo_path)
    walonly_path.unlink()
    # RM-047: a planted row carrying the victim content's real
    # SHA-256 but different content — the idempotent-store
    # fallback must refuse the hash hit instead of merging.
    collide = HebbianMemory(MuninnConfig(db_path=str(tmp_path / "collide.db")))
    _victim_hash = hashlib.sha256(("s:" + "gamma incoming").encode()).hexdigest()
    _cconn = collide._get_conn()
    _cconn.execute(
        "INSERT INTO nodes (content, content_is_json, content_hash,"
        " path, category, importance, emotional_valence, tags,"
        " metadata, created_at, updated_at)"
        " VALUES (?, 0, ?, '', 'general', 5, 0.0, '[]', '{}',"
        " '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')",
        ("planted different content", _victim_hash),
    )
    _cconn.commit()
    # RM-041: a symlinked store path and a world-writable
    # parent directory, both opened with strict path safety on.
    link_path = tmp_path / "link.db"
    os.symlink(tmp_path / "m.db", link_path)
    # RM-049: an encrypted store for the wrong-passphrase and
    # plain-open refusal cases. Built only when the encryption
    # extra is installed (the campaign's suite env carries it);
    # without it those cases are absent and the golden diff
    # names them plainly.
    enc_path = tmp_path / "enc.db"
    enc_built = False
    try:
        _enc_mem = HebbianMemory(
            MuninnConfig(
                db_path=str(enc_path),
                store_encryption=True,
                encryption_passphrase="case passphrase",
            )
        )
        _enc_mem.remember("sealed")
        _enc_mem.close()
        enc_built = True
    except Exception:
        enc_built = False
    # RM-050: an attested store for the plain-open refusal
    # case (stdlib-only — always built).
    att_path = tmp_path / "att.db"
    _att_mem = HebbianMemory(
        MuninnConfig(
            db_path=str(att_path),
            integrity_attestation=True,
            integrity_passphrase="case passphrase",
        )
    )
    _att_mem.remember("chained")
    _att_mem.close()
    shared_dir = tmp_path / "shared"
    shared_dir.mkdir()
    os.chmod(shared_dir, 0o777)
    # RM-054: stores whose own triggers make SQLite generate
    # its error text from file content — the generic write-guard
    # and prepare branches must name only the exception class.
    trigwrite = HebbianMemory(MuninnConfig(db_path=str(tmp_path / "trigwrite.db")))
    _tw_conn = trigwrite._get_conn()
    _tw_conn.execute(
        "CREATE TRIGGER rm054_leak BEFORE INSERT ON nodes"
        " BEGIN SELECT RAISE(ABORT, 'planted trigger text'); END"
    )
    _tw_conn.commit()
    trigprep_path = tmp_path / "trigprep.db"
    _trigprep = HebbianMemory(MuninnConfig(db_path=str(trigprep_path)))
    _tp_conn = _trigprep._get_conn()
    _tp_conn.execute(
        "CREATE TRIGGER rm054_leak BEFORE INSERT ON meta"
        " BEGIN SELECT RAISE(ABORT, 'planted trigger text'); END"
    )
    _tp_conn.commit()
    _trigprep.close()

    def cfg(**overrides):
        return lambda: MuninnConfig(db_path=str(tmp_path / "m.db"), **overrides)

    cases = {
        "config_db_path": lambda: MuninnConfig(db_path=""),
        "config_learning_rate": cfg(learning_rate=0),
        "config_decay_half_life": cfg(decay_half_life_days=0),
        "config_confidence_half_life": cfg(confidence_half_life_days=-1),
        "config_prune_threshold": cfg(prune_threshold=1),
        "config_consolidation_threshold": cfg(consolidation_threshold=0),
        "config_busy_timeout": cfg(busy_timeout_ms=-1),
        "config_backup_keep": cfg(backup_keep=-1),
        "config_max_nodes": cfg(max_nodes=0),
        "config_max_content_bytes": cfg(max_content_bytes=0),
        "config_max_metadata_bytes": cfg(max_metadata_bytes=0),
        "config_max_spread_candidates": cfg(max_spread_candidates=0),
        "config_cache_size": cfg(cache_size=-1),
        "path_type": lambda: m.remember("x", path=123),
        "path_depth": lambda: m.remember("x", path="/".join(["a"] * 65)),
        "path_size": lambda: m.remember("x", path="x" * 2049),
        "content_oversize": lambda: tight.remember("123456789"),
        "metadata_oversize": lambda: tight.remember(
            "ok", metadata={"k": "12345678"}
        ),
        "memory_id_type": lambda: m.activate("x"),
        "memory_id_negative": lambda: m.activate(-1),
        "importance_type": lambda: m.remember("a", importance="high"),
        "importance_range": lambda: m.remember("a", importance=11),
        "valence_type": lambda: m.activate(1, emotional_valence="warm"),
        "valence_range": lambda: m.activate(1, emotional_valence=1.5),
        "content_not_serializable": lambda: m.remember({1, 2}),
        "batch_not_a_list": lambda: m.activate_batch("nope"),
        "bulk_not_a_list": lambda: m.remember_many("nope"),
        "bulk_item_not_a_dict": lambda: m.remember_many(["nope"]),
        "bulk_unknown_fields": lambda: m.remember_many(
            [{"content": "x", "bogus": 1}]
        ),
        "bulk_missing_content": lambda: m.remember_many([{"path": "p"}]),
        "associate_self": lambda: m.associate(1, 1),
        "associate_both": lambda: m.associate(1, 2, strength=0.5, delta=0.5),
        "associate_strength_range": lambda: m.associate(1, 2, strength=1.5),
        "associate_delta_range": lambda: m.associate(1, 2, delta=0),
        "min_strength_range": lambda: m.get_associations(1, min_strength=2),
        "attenuation_range": lambda: m.spread_activation([1], attenuation=0),
        "content_none": lambda: m.remember(None),
        "metadata_not_serializable": lambda: m.remember("ok", metadata=circular),
        "unknown_node_fields": lambda: m.update(1, bogus=1),
        "update_duplicate": lambda: m.update(beta, content="alpha"),
        "decay_days": lambda: m.decay(days=-1),
        "consolidate_threshold": lambda: m.consolidate(threshold=0),
        "closed": lambda: closed.activate(1),
        "corrupt_store": lambda: HebbianMemory(
            MuninnConfig(db_path=str(bad_path), backup_keep=0)
        ),
        "disk_full_remember": lambda: full.remember("z" * 200_000),
        "readonly_open": lambda: HebbianMemory(
            MuninnConfig(db_path=str(ro_path))
        ),
        "locked_open": lambda: HebbianMemory(
            MuninnConfig(db_path=str(locked_path), busy_timeout_ms=300)
        ),
        "locked_remember": lambda: locked.remember("blocked"),
        "missing_main_wal": lambda: HebbianMemory(
            MuninnConfig(db_path=str(walonly_path), backup_keep=0)
        ),
        "directory_store": lambda: HebbianMemory(
            MuninnConfig(db_path=str(dir_path))
        ),
        "nonfile_store": lambda: HebbianMemory(
            MuninnConfig(db_path=str(fifo_path))
        ),
        "strict_symlink_open": lambda: HebbianMemory(
            MuninnConfig(db_path=str(link_path), strict_path_safety=True)
        ),
        "strict_world_writable_open": lambda: HebbianMemory(
            MuninnConfig(
                db_path=str(shared_dir / "m.db"), strict_path_safety=True
            )
        ),
        "write_guard_generic": lambda: trigwrite.remember("anything"),
        "prepare_generic": lambda: HebbianMemory(
            MuninnConfig(db_path=str(trigprep_path))
        ),
        "attestation_passphrase_required": lambda: MuninnConfig(
            integrity_attestation=True
        ),
        "attestation_plain_open": lambda: HebbianMemory(
            MuninnConfig(db_path=str(att_path))
        ),
        "hash_collision": lambda: collide.remember("gamma incoming"),
        "content_surrogate": lambda: m.remember("bad \ud800 end"),
        "path_surrogate": lambda: m.remember("clean", path="a/\ud800"),
        "metadata_too_deep": lambda: m.remember("ok", metadata=_deep_dict(101)),
        "content_too_deep": lambda: m.remember(_deep_list(101)),
        "tags_oversize": lambda: tight.remember("ok", tags=["abcdefghij"]),
        **(
            {
                "encryption_passphrase_required": lambda: MuninnConfig(
                    store_encryption=True
                ),
                "encryption_wrong_passphrase": lambda: HebbianMemory(
                    MuninnConfig(
                        db_path=str(enc_path),
                        store_encryption=True,
                        encryption_passphrase="wrong passphrase",
                    )
                ),
                "encryption_plain_open": lambda: HebbianMemory(
                    MuninnConfig(db_path=str(enc_path))
                ),
            }
            if enc_built
            else {}
        ),
    }
    return cases, m, _holder


def test_error_messages_match_golden(tmp_path):
    golden_cases, _ = _golden()
    cases, m, _holder = _cases(tmp_path)
    try:
        actual = {case_id: _capture(fn, tmp_path) for case_id, fn in cases.items()}
    finally:
        m.close()
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
        candidate = parent / "muninn" / "src" / "muninn"
        if candidate.is_dir() and (parent / "RAVENS_ROADMAP_2026-10-31.md").is_file():
            src = candidate
            break
    if src is None:
        pytest.skip("not running inside a repo checkout (no src/muninn)")
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
            "muninn raise sites drifted from the RM-018 golden templates. "
            "If a message change is deliberate, update "
            "golden_error_messages.txt in the same commit.\n" + "\n".join(lines)
        )


def test_golden_cases_cover_every_typed_error_class():
    golden_cases, _ = _golden()
    covered = {exc_name for exc_name, _ in golden_cases.values()}
    assert covered == ERROR_NAMES
