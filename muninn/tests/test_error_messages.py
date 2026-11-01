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
   the two sites no deterministic trigger can reach (the
   schema-preparation failure and the RM-008 no-row-id guard):
   any new or reworded raise site fails here until the golden
   is updated deliberately in the same commit.
"""

import ast
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
    }
    return cases, m


def test_error_messages_match_golden(tmp_path):
    golden_cases, _ = _golden()
    cases, m = _cases(tmp_path)
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
