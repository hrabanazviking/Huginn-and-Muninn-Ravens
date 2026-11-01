"""RM-025 — Input fuzzing, muninn.

Property-style fuzz over every Muninn validator (ids, valence,
importance, paths, tags, metadata, and the numeric parameters
around them), stdlib-only: corpora are generated from recorded
seeds with :mod:`random`, so every run replays exactly.

The law under test, for every generated input, on every entry
point: the call either succeeds, or raises a typed Muninn error
(``MuninnError`` subclass) — never an untyped exception — and a
rejected write leaves NO partial write behind: the store's
stats (nodes / connections / activations) are exactly what they
were before the call, and the store still works afterwards.

Seeds (recorded per the roadmap's acceptance):
20261031, 20261101, 42. Corpus pools below are fixed; the seeds
drive which combinations each test exercises.

Out of scope by roadmap design: lone-surrogate content strings
— RM-034 owns their typed rejection, so the string pool here
contains no lone surrogates.
"""

import random

import pytest

from muninn import HebbianMemory
from muninn.config import MuninnConfig
from muninn.errors import MuninnConfigurationError, MuninnError

SEEDS = (20261031, 20261101, 42)

NUMBERS = [
    None, True, False, 0, 1, -1, 5, 10, 11, 2**63 - 1, 2**63, 2**64,
    2**100, -(2**100), 0.0, 0.5, 1.0, -0.5, 1.5, 5.0, 5.5,
    float("nan"), float("inf"), float("-inf"), 1e308, -1e308,
]
STRINGS = [
    "", "x", "0", "1", "-1", "0.5", "abc", "warm", "high", "1e3",
    "a" * 500, "\x00nul\x00", "é漢字🎉", "  padded  ", "'; DROP TABLE",
    "[]", "{}", "None", "nan", "inf",
]
CONTAINERS = [
    [], [1], [1, 2], {}, {"k": 1}, {"k": [1, {"deep": True}]},
    {1, 2}, (1, 2), b"bytes", object(), ["a", 1, None, True],
]
HOSTILE = NUMBERS + STRINGS + CONTAINERS


def _mem(tmp_path, name="m.db"):
    return HebbianMemory(MuninnConfig(db_path=str(tmp_path / name)))


def _stats(m):
    s = m.stats()
    return (s["total_nodes"], s["total_connections"], s["total_activations"])


def _call_outcome(fn):
    """'ok' or the typed error's class name; untyped errors fail here."""
    try:
        fn()
    except MuninnError as exc:
        return type(exc).__name__
    return "ok"


def _assert_typed_or_ok(m, fn, *, write):
    before = _stats(m)
    outcome = _call_outcome(fn)
    if write and outcome != "ok":
        assert _stats(m) == before, "rejected write left a partial write behind"
    return outcome


def test_fuzz_memory_ids(tmp_path):
    m = _mem(tmp_path)
    keep = m.remember("anchor")
    rng = random.Random(SEEDS[0])
    pool = NUMBERS + STRINGS + CONTAINERS
    for value in rng.choices(pool, k=40) + [2**63, 2**100, -1, "x", None, 1.5]:
        for fn, write in [
            (lambda v=value: m.activate(v), True),
            (lambda v=value: m.get_node(v), False),
            (lambda v=value: m.activation_count(v), False),
            (lambda v=value: m.get_associations(v), False),
            (lambda v=value: m.forget(v), True),
            (lambda v=value: m.update(v, importance=5), True),
            (lambda v=value: m.spread_activation(v), False),
            (lambda v=value: m.spread_activation([v]), False),
        ]:
            _assert_typed_or_ok(m, fn, write=write)
    # the store still works, exactly, after the barrage (some
    # generated ids were valid and legitimately activated keep)
    before = m.activation_count(keep)
    m.activate(keep)
    assert m.activation_count(keep) == before + 1
    m.close()


def test_fuzz_valence_and_importance(tmp_path):
    m = _mem(tmp_path)
    keep = m.remember("anchor")
    rng = random.Random(SEEDS[1])
    for value in rng.choices(HOSTILE, k=40) + [float("nan"), "warm", None]:
        _assert_typed_or_ok(
            m, lambda v=value: m.activate(keep, emotional_valence=v), write=True
        )
        _assert_typed_or_ok(
            m, lambda v=value: m.remember("vprobe", emotional_valence=v), write=True
        )
        _assert_typed_or_ok(
            m, lambda v=value: m.remember("iprobe", importance=v), write=True
        )
        _assert_typed_or_ok(
            m, lambda v=value: m.update(keep, emotional_valence=v), write=True
        )
        _assert_typed_or_ok(
            m, lambda v=value: m.update(keep, importance=v), write=True
        )
    m.close()


def test_fuzz_associate_strength_and_delta(tmp_path):
    m = _mem(tmp_path)
    a = m.remember("alpha")
    b = m.remember("beta")
    m.associate(a, b, strength=0.5)
    baseline = m.get_associations(a)
    rng = random.Random(SEEDS[2])
    for value in rng.choices(HOSTILE, k=40) + [float("nan"), "0.5", None.__class__]:
        outcome = _assert_typed_or_ok(
            m, lambda v=value: m.associate(a, b, strength=v), write=True
        )
        if outcome != "ok":
            assert m.get_associations(a) == baseline
        else:
            baseline = m.get_associations(a)  # a valid call legitimately moved it
        outcome = _assert_typed_or_ok(
            m, lambda v=value: m.associate(a, b, delta=v), write=True
        )
        if outcome != "ok":
            # an invalid delta must not even clear the tombstones:
            # the wiring visible afterwards is byte-identical
            after = m.get_associations(a)
            assert [x["memory_id"] for x in after] == [x["memory_id"] for x in baseline]
        else:
            baseline = m.get_associations(a)
    m.close()


def test_fuzz_activate_batch_is_atomic(tmp_path):
    m = _mem(tmp_path)
    keep = m.remember("anchor")
    rng = random.Random(SEEDS[0])
    batches = [
        "nope", 123, None, {"a": 1}, [keep, "x"], [keep, None],
        [keep, 2**100], [keep, float("nan")], [keep, -1], [keep, 1.5],
        [keep, [1]], [keep, {"k": 1}],
    ]
    batches += [rng.choices(HOSTILE, k=3) for _ in range(12)]
    for batch in batches:
        _assert_typed_or_ok(m, lambda bt=batch: m.activate_batch(bt), write=True)
    assert m.activation_count(keep) == 0
    m.close()


def test_fuzz_numeric_parameters(tmp_path):
    m = _mem(tmp_path)
    a = m.remember("alpha")
    b = m.remember("beta")
    m.associate(a, b, strength=0.5)
    rng = random.Random(SEEDS[1])
    pool = rng.choices(HOSTILE, k=36) + [float("nan"), float("inf"), "5", None]
    for value in pool:
        for fn, write in [
            (lambda v=value: m.get_associations(a, min_strength=v), False),
            (lambda v=value: m.get_associations(a, limit=v), False),
            (lambda v=value: m.spread_activation([a], attenuation=v), False),
            (lambda v=value: m.spread_activation([a], depth=v), False),
            (lambda v=value: m.spread_activation([a], min_strength=v), False),
            (lambda v=value: m.spread_activation([a], limit=v), False),
            (lambda v=value: m.retrieve(top_k=v), False),
            (lambda v=value: m.consolidate(threshold=v), True),
            (lambda v=value: m.decay(days=v), True),
        ]:
            _assert_typed_or_ok(m, fn, write=write)
    m.close()


def test_fuzz_tags_and_metadata(tmp_path):
    m = _mem(tmp_path)
    keep = m.remember("anchor", tags=["one"], metadata={"k": 1})
    circular = {}
    circular["loop"] = circular
    rng = random.Random(SEEDS[2])
    pool = rng.choices(HOSTILE, k=30) + [circular, "solo-string", 42, b"bytes"]
    for value in pool:
        _assert_typed_or_ok(m, lambda v=value: m.remember("tprobe", tags=v), write=True)
        _assert_typed_or_ok(m, lambda v=value: m.update(keep, tags=v), write=True)
        _assert_typed_or_ok(m, lambda v=value: m.retrieve(tags=v), write=False)
        _assert_typed_or_ok(
            m, lambda v=value: m.remember("mprobe", metadata=v), write=True
        )
        _assert_typed_or_ok(m, lambda v=value: m.update(keep, metadata=v), write=True)
    # valid generated tag/metadata values legitimately landed on
    # keep during the barrage; reset explicitly, then prove the
    # store holds exactly what the last good writes said
    m.update(keep, tags=["one"], metadata={"k": 1})
    node = m.get_node(keep)
    assert node is not None and node.tags == ["one"] and node.metadata == {"k": 1}
    m.close()


def test_fuzz_content_paths_and_categories(tmp_path):
    m = _mem(tmp_path)
    rng = random.Random(SEEDS[0])
    contents = [
        "", "plain", "é漢字🎉" * 20, "\x00embedded", "a" * 5000,
        0, 1, True, 1.5, [1, "two", {"three": 3}], {"nested": {"deep": [1, 2]}},
        {1, 2}, b"bytes", object(), None, float("nan"),
    ]
    for value in contents:
        _assert_typed_or_ok(m, lambda v=value: m.remember(v), write=True)
    for value in rng.choices(STRINGS + NUMBERS, k=20):
        _assert_typed_or_ok(
            m, lambda v=value: m.remember("pprobe", path=v), write=True
        )
        _assert_typed_or_ok(
            m, lambda v=value: m.remember("cprobe", category=v), write=True
        )
        _assert_typed_or_ok(m, lambda v=value: m.get_by_path(v), write=False)
        _assert_typed_or_ok(m, lambda v=value: m.get_children(v), write=False)
        _assert_typed_or_ok(m, lambda v=value: m.retrieve(query=v), write=False)
    m.close()


def test_fuzz_config_values(tmp_path):
    fields = [
        "learning_rate", "decay_half_life_days", "confidence_half_life_days",
        "prune_threshold", "consolidation_threshold", "busy_timeout_ms",
        "backup_keep", "max_nodes",
    ]
    rng = random.Random(SEEDS[1])
    for field in fields:
        for value in rng.choices(HOSTILE, k=20) + [float("nan"), "abc", None, []]:
            try:
                MuninnConfig(db_path=str(tmp_path / "c.db"), **{field: value})
            except MuninnConfigurationError:
                pass
            except MuninnError:
                raise AssertionError(
                    f"{field}={value!r} raised a non-config typed error"
                ) from None
            # any other exception type escapes and fails the test: untyped


def test_fuzz_rejected_writes_leave_store_functional(tmp_path):
    m = _mem(tmp_path)
    a = m.remember("alpha")
    b = m.remember("beta")
    before = _stats(m)
    failures = [
        lambda: m.activate(2**100),
        lambda: m.activate_batch([a, 2**100]),
        lambda: m.associate(a, b, delta="fast"),
        lambda: m.associate(a, b, strength=object()),
        lambda: m.decay(days=float("nan")),
        lambda: m.consolidate(threshold="high"),
        lambda: m.remember("x", tags=42),
        lambda: m.update(a, metadata=_circular()),
    ]
    for fn in failures:
        with pytest.raises(MuninnError):
            fn()
        assert _stats(m) == before
    # no pending transaction leaked: the next good writes land exactly
    m.activate(a)
    assert m.activation_count(a) == 1
    assert m.get_associations(a) == []
    m.associate(a, b, strength=0.25)
    assert m.get_associations(a)[0]["strength"] == 0.25
    assert m.health()["integrity"] == "ok"
    m.close()


def _circular():
    d = {}
    d["loop"] = d
    return d


def test_fuzz_outcomes_are_deterministic_per_seed(tmp_path):
    def run(name):
        m = _mem(tmp_path, name)
        keep = m.remember("anchor")
        rng = random.Random(SEEDS[2])
        outcomes = []
        for value in rng.choices(HOSTILE, k=30):
            outcomes.append(_call_outcome(lambda v=value: m.activate(keep, emotional_valence=v)))
            outcomes.append(_call_outcome(lambda v=value: m.associate(keep, keep + 1, delta=v)))
            outcomes.append(_call_outcome(lambda v=value: m.decay(days=v)))
        m.close()
        return outcomes

    first = run("d1.db")
    second = run("d2.db")
    assert first == second
    assert "ok" in first and len(set(first)) > 1
