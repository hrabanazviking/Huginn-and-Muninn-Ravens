"""RM-026 — Input fuzzing, huginn.

Property-style fuzz over every Huginn validator (content,
category, importance, valence, tags, memory ids, and the
search / flight / module-function arguments around them),
stdlib-only: corpora are generated from recorded seeds with
:mod:`random`, so every run replays exactly. The twin of
RM-025's muninn suite, over the huginn surfaces the roadmap
names: upsert / search / get / delete arguments and query text
(empty, huge, unicode-edge, NUL-bearing).

The law under test, for every generated input, on every entry
point: the call either succeeds, or raises a typed Huginn
error (``HuginnError`` subclass) — never an untyped exception
— and a rejected write leaves NO partial write behind: the
store's document count is exactly what it was before the
call, and the store still works afterwards. ``fly`` keeps its
ancestor semantics within that law: it never raises at all —
a validation failure comes home as a flight with ``error``
set and no results.

Seeds (recorded per the roadmap's acceptance):
20261031, 20261101, 42. Corpus pools below are fixed; the
seeds drive which combinations each test exercises.

Out of scope by roadmap design: lone-surrogate strings —
RM-034 owns their typed rejection, so the string pool here
contains no lone surrogates.
"""

import random

import pytest

from huginn import HuginnConfig, HuginnMemory, analyze_query, semantic_search
from huginn.errors import HuginnConfigurationError, HuginnError

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


def _mem(tmp_path, name="h.db"):
    return HuginnMemory(
        HuginnConfig(backend="local", local_db_path=str(tmp_path / name))
    )


def _docs(h):
    return h.health()["documents"]


def _call_outcome(fn):
    """'ok' or the typed error's class name; untyped errors fail here."""
    try:
        fn()
    except HuginnError as exc:
        return type(exc).__name__
    return "ok"


def _assert_typed_or_ok(h, fn, *, write):
    before = _docs(h)
    outcome = _call_outcome(fn)
    if write and outcome != "ok":
        assert _docs(h) == before, "rejected write left a partial write behind"
    return outcome


def test_fuzz_memory_ids(tmp_path):
    h = _mem(tmp_path)
    h.upsert_memory("anchor memory about ravens")
    rng = random.Random(SEEDS[0])
    pool = NUMBERS + STRINGS + CONTAINERS
    for value in rng.choices(pool, k=40) + [2**63, 2**100, -1, "x", 1.5, True]:
        _assert_typed_or_ok(h, lambda v=value: h.get(v), write=False)
        _assert_typed_or_ok(h, lambda v=value: h.delete(v), write=True)
        # memory_id=None is the documented "auto id" shape, not fuzz
        if value is not None:
            _assert_typed_or_ok(
                h, lambda v=value: h.upsert_memory("id probe", memory_id=v),
                write=True,
            )
    # the store still works, exactly, after the barrage (the
    # anchor itself may legitimately have been deleted by a
    # generated id that named it — that is a valid call, not
    # damage — so prove the cycle on a fresh document)
    probe = h.upsert_memory("post barrage anchor")
    assert h.get(probe)["content"] == "post barrage anchor"
    assert h.delete(probe) is True
    assert h.get(probe) is None
    h.close()


def test_fuzz_content_and_category(tmp_path):
    h = _mem(tmp_path)
    contents = [
        "", "   ", "plain memory", "é漢字🎉" * 20, "a\x00b cde",
        "a" * 20000, "'; DROP TABLE documents; --",
        0, 1, True, 1.5, [1, "two"], {"nested": 1}, {1, 2},
        b"bytes", object(), None, float("nan"),
    ]
    for value in contents:
        _assert_typed_or_ok(h, lambda v=value: h.upsert_memory(v), write=True)
    rng = random.Random(SEEDS[1])
    for value in rng.choices(HOSTILE, k=30):
        _assert_typed_or_ok(
            h, lambda v=value: h.upsert_memory("category probe", category=v),
            write=True,
        )
        _assert_typed_or_ok(
            h, lambda v=value: h.search("category", category=v), write=False
        )
    h.close()


def test_fuzz_importance_and_valence(tmp_path):
    h = _mem(tmp_path)
    rng = random.Random(SEEDS[1])
    for value in rng.choices(HOSTILE, k=40) + [float("nan"), "warm", None]:
        _assert_typed_or_ok(
            h, lambda v=value: h.upsert_memory("iprobe", importance=v), write=True
        )
        _assert_typed_or_ok(
            h, lambda v=value: h.upsert_memory("vprobe", emotional_valence=v),
            write=True,
        )
    h.close()


def test_fuzz_tags(tmp_path):
    h = _mem(tmp_path)
    keep = h.upsert_memory("tagged anchor", tags=["one"])
    circular = []
    circular.append(circular)
    rng = random.Random(SEEDS[2])
    pool = rng.choices(HOSTILE, k=30) + [circular, "solo-string", 42, b"bytes"]
    for value in pool:
        _assert_typed_or_ok(
            h, lambda v=value: h.upsert_memory("tprobe", tags=v), write=True
        )
    # element coercion kept: a list of mixed scalars lands as strings
    mixed = h.upsert_memory("mixed tags", tags=[1, None, True])
    assert h.get(mixed)["tags"] == ["1", "None", "True"]
    assert h.get(keep)["tags"] == ["one"]
    h.close()


def test_fuzz_search_arguments(tmp_path):
    h = _mem(tmp_path)
    h.upsert_memory("ravens fly over the fjord at dawn", importance=7)
    h.upsert_memory("odin traded an eye for wisdom", importance=3)
    rng = random.Random(SEEDS[0])
    pool = rng.choices(HOSTILE, k=36) + [float("nan"), float("inf"), "5", None]
    for value in pool:
        for fn in [
            lambda v=value: h.search(v),
            lambda v=value: h.search("ravens", limit=v),
            lambda v=value: h.search("ravens", min_importance=v),
            lambda v=value: h.search("ravens", category=v),
        ]:
            _assert_typed_or_ok(h, fn, write=False)
    # valid searches still answer exactly after the barrage
    hits = h.search("ravens fjord", limit=5)
    assert [r["content"] for r in hits] == ["ravens fly over the fjord at dawn"]
    h.close()


def test_fuzz_query_text_entry_points(tmp_path):
    h = _mem(tmp_path)
    h.upsert_memory("ravens fly over the fjord at dawn")
    rng = random.Random(SEEDS[1])
    pool = rng.choices(HOSTILE, k=24) + [123, None, ["x"], {"k": 1}]
    docs = ["ravens fly north", "odin seeks wisdom"]
    for value in pool:
        _assert_typed_or_ok(h, lambda v=value: analyze_query(v), write=False)
        _assert_typed_or_ok(h, lambda v=value: h.analyze_query(v), write=False)
        _assert_typed_or_ok(
            h, lambda v=value: semantic_search(v, docs), write=False
        )
        _assert_typed_or_ok(
            h, lambda v=value: semantic_search("ravens", docs, top_k=v),
            write=False,
        )
        _assert_typed_or_ok(
            h, lambda v=value: semantic_search("ravens", v), write=False
        )
        _assert_typed_or_ok(
            h, lambda v=value: h.multi_hop_retrieve(v), write=False
        )
        _assert_typed_or_ok(
            h, lambda v=value: h.multi_hop_retrieve("ravens", hop_count=v),
            write=False,
        )
        _assert_typed_or_ok(
            h,
            lambda v=value: h.multi_hop_retrieve(
                "ravens", max_results_per_hop=v
            ),
            write=False,
        )
    # fly never raises at all: a bad query or count comes home
    # as an error flight, and a good flight still flies
    for bad in [123, None, ["x"], {"k": 1}]:
        flight = h.fly(bad)
        assert flight.results == [] and flight.error
    flight = h.fly("ravens", max_results="x")
    assert flight.results == [] and flight.error
    good = h.fly("ravens fjord")
    assert good.error is None and len(good.results) == 1
    h.close()


def test_fuzz_huge_unicode_and_nul_text(tmp_path):
    h = _mem(tmp_path)
    texts = [
        "ravens " * 20000,  # huge content
        "raven \U0001f600\U0001f525 fly",  # astral-plane emoji
        "familj 👨‍👩‍👧‍👦 zwj sequence",  # ZWJ sequence (fuzz pool text)
        "cafe\u0301 combining marks",
        "نسر عربي rtl script raven",
        "nul\x00bearing content tokens",
    ]
    ids = {}
    for text in texts:
        doc_id = h.upsert_memory(text)
        ids[text] = doc_id
        # stored content round-trips byte-exact, NUL included
        assert h.get(doc_id)["content"] == text
    queries = [
        "ravens " * 20000,  # huge query
        "raven", "zwj", "combining", "rtl", "nul\x00bearing",
        "\x00", "é" * 5000,
    ]
    for query in queries:
        outcome = _call_outcome(lambda q=query: h.search(q))
        assert outcome == "ok"
    assert h.search("nul\x00bearing")[0]["id"] == ids["nul\x00bearing content tokens"]
    h.close()


def test_fuzz_config_values(tmp_path):
    fields = [
        "backend", "embedder", "qdrant_url", "local_db_path",
        "collection_name", "vector_dim", "qdrant_timeout",
        "busy_timeout_ms", "backup_keep", "st_model", "qdrant_api_key",
    ]
    rng = random.Random(SEEDS[1])
    for field in fields:
        for value in rng.choices(HOSTILE, k=20) + [float("nan"), "abc", None, []]:
            params = {
                "backend": "local",
                "local_db_path": str(tmp_path / "c.db"),
                field: value,
            }
            try:
                HuginnConfig(**params)
            except HuginnConfigurationError:
                pass
            except HuginnError:
                raise AssertionError(
                    f"{field}={value!r} raised a non-config typed error"
                ) from None
            # any other exception type escapes and fails the test: untyped


def test_fuzz_rejected_writes_leave_store_functional(tmp_path):
    h = _mem(tmp_path)
    keep = h.upsert_memory("alpha ravens", importance=5)
    before = _docs(h)
    failures = [
        lambda: h.upsert_memory("x", memory_id=2**100),
        lambda: h.upsert_memory("x", tags=42),
        lambda: h.upsert_memory("x", tags="abc"),
        lambda: h.upsert_memory("x", category=123),
        lambda: h.upsert_memory("x", importance="high"),
        lambda: h.upsert_memory("x", emotional_valence=float("nan")),
        lambda: h.delete(2**63),
    ]
    for fn in failures:
        with pytest.raises(HuginnError):
            fn()
        assert _docs(h) == before
    # the next good writes land exactly, and reads stay pure
    new_id = h.upsert_memory("beta wisdom", tags=["two"])
    assert h.get(new_id)["tags"] == ["two"]
    assert h.get(keep)["content"] == "alpha ravens"
    assert h.health()["integrity"] == "ok"
    h.close()


def test_fuzz_outcomes_are_deterministic_per_seed(tmp_path):
    def run(name):
        h = _mem(tmp_path, name)
        keep = h.upsert_memory("anchor ravens")
        rng = random.Random(SEEDS[2])
        outcomes = []
        for value in rng.choices(HOSTILE, k=30):
            outcomes.append(_call_outcome(lambda v=value: h.get(v)))
            outcomes.append(
                _call_outcome(lambda v=value: h.upsert_memory("p", importance=v))
            )
            outcomes.append(
                _call_outcome(lambda v=value: h.search("ravens", limit=v))
            )
            outcomes.append(_call_outcome(lambda v=value: analyze_query(v)))
        outcomes.append(_call_outcome(lambda: h.get(keep)))
        h.close()
        return outcomes

    first = run("d1.db")
    second = run("d2.db")
    assert first == second
    assert "ok" in first and len(set(first)) > 1
