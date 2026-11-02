"""RM-060 — Bulk remember pins.

``HebbianMemory.remember_many`` is the batch form of
``remember``: a list of item dicts (``remember``'s arguments
by name) stored under a stricter, faster contract than the
loop it replaces —

- every item is prepared (validated, serialized, hashed)
  exactly once, before the transaction opens, by the same
  preparation ``remember`` itself uses;
- all inserts land in ONE transaction: an invalid item or
  a hash collision (against the store, or within the batch)
  rolls the whole batch back — no stored prefix;
- the whole batch carries one timestamp;
- backpressure (the ``max_nodes`` check) is applied once,
  after the commit;
- per item, idempotency is exactly ``remember``'s: an
  existing content+category+path returns its id, first
  write wins, and a duplicate inside the batch returns the
  id its first occurrence created.

These tests pin the semantics against the loop road (same
items, logically identical stores), the transaction shape
(COMMIT and backpressure-count statements counted by trace
callback over the store's own connection), the atomic
refusals, the forced-collision road, the encrypted-store
composition, the log-redaction discipline, and the
committed BENCH gate record. No test depends on wall-clock
timings.
"""

import importlib.util
import json
import logging
from pathlib import Path

import pytest

import muninn.core
from muninn import HebbianMemory, Muninn
from muninn.config import MuninnConfig
from muninn.errors import MuninnValidationError

PKG = Path(__file__).parent.parent
SCRIPT = PKG / "scripts" / "bulk_remember.py"
COMMITTED = PKG / "scripts" / "bulk_remember.json"
ENV_KEYS = (
    "recorded_at",
    "machine",
    "system",
    "platform",
    "node",
    "cpu_count",
    "load_avg",
    "python_version",
    "sqlite_version",
)

SECRET = "bulk secret plum 7391"


def _load_script():
    spec = importlib.util.spec_from_file_location("muninn_bulk_remember", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def mem(tmp_path):
    m = HebbianMemory(
        MuninnConfig(db_path=str(tmp_path / "m.db"), auto_backup=False)
    )
    yield m
    m.close()


def _traced(mem, fn):
    """Run ``fn`` traced; return (result, [statement texts])."""
    seen = []
    conn = mem._get_conn()
    conn.set_trace_callback(seen.append)
    try:
        result = fn()
    finally:
        conn.set_trace_callback(None)
    return result, [" ".join(sql.split()) for sql in seen]


def _count_starting(texts, prefix):
    return sum(1 for t in texts if t.upper().startswith(prefix))


# ─── the batch road stores, in order, with full fidelity ─────


def test_batch_stores_all_items_in_input_order(mem):
    items = [
        {"content": "first bulk memory", "category": "lore", "path": "a/b",
         "importance": 7, "tags": ["Raven", " Dawn "], "emotional_valence": 0.25,
         "metadata": {"source": "test"}},
        {"content": {"structured": [1, 2, 3]}, "category": "data"},
        {"content": "third bulk memory"},
    ]
    ids = mem.remember_many(items)
    assert len(ids) == 3 and len(set(ids)) == 3
    assert mem.stats()["total_nodes"] == 3
    first = mem.get_node(ids[0])
    assert first.content == "first bulk memory"
    assert first.memory_type == "lore" and first.path == "a/b"
    assert first.importance == 7 and first.tags == ["raven", "dawn"]
    assert first.emotional_valence == 0.25
    assert first.metadata == {"source": "test"}
    assert mem.get_node(ids[1]).content == {"structured": [1, 2, 3]}
    third = mem.get_node(ids[2])
    assert third.content == "third bulk memory"
    assert third.memory_type == "general" and third.importance == 5


def test_batch_matches_the_loop_it_replaces(tmp_path):
    items = [
        {"content": f"parity memory {i}", "category": f"cat{i % 3}",
         "path": f"p/{i % 2}", "importance": (i % 10) + 1,
         "tags": [f"t{i % 4}"], "emotional_valence": -0.5 + (i % 3) * 0.5,
         "metadata": {"i": i}}
        for i in range(40)
    ]
    loop = HebbianMemory(
        MuninnConfig(db_path=str(tmp_path / "loop.db"), auto_backup=False)
    )
    batch = HebbianMemory(
        MuninnConfig(db_path=str(tmp_path / "batch.db"), auto_backup=False)
    )
    try:
        loop_ids = [loop.remember(**item) for item in items]
        batch_ids = batch.remember_many(items)
        assert batch_ids == loop_ids
        assert batch.stats() | {"db_path": ""} == loop.stats() | {"db_path": ""}
        for node_id in batch_ids:
            a, b = loop.get_node(node_id), batch.get_node(node_id)
            assert (a.content, a.path, a.memory_type, a.importance,
                    a.emotional_valence, a.tags, a.metadata) == (
                        b.content, b.path, b.memory_type, b.importance,
                        b.emotional_valence, b.tags, b.metadata)
        # One timestamp for the whole batch (the activate_batch
        # discipline): every batch row shares created_at, while
        # the loop's rows were stamped per call.
        stamps = {
            r[0]
            for r in batch._get_conn().execute("SELECT created_at FROM nodes")
        }
        assert len(stamps) == 1
    finally:
        loop.close()
        batch.close()


def test_batch_empty_is_a_noop(mem):
    mem.remember("already here")
    before = mem.stats()
    assert mem.remember_many([]) == []
    assert mem.stats() == before


def test_batch_duplicate_inside_batch_returns_one_id(mem):
    ids = mem.remember_many([
        {"content": "twin memory", "category": "lore"},
        {"content": "other memory"},
        {"content": "twin memory", "category": "lore", "importance": 9},
    ])
    assert ids[0] == ids[2] != ids[1]
    assert mem.stats()["total_nodes"] == 2
    # First write wins, exactly as a remember retry behaves.
    assert mem.get_node(ids[0]).importance == 5


def test_batch_hit_against_existing_store_first_write_wins(mem):
    existing = mem.remember("kept memory", category="lore", importance=8)
    ids = mem.remember_many([
        {"content": "kept memory", "category": "lore", "importance": 2},
        {"content": "brand new memory"},
    ])
    assert ids[0] == existing
    assert mem.get_node(existing).importance == 8
    assert mem.stats()["total_nodes"] == 2


def test_batch_works_through_the_facade(tmp_path):
    facade = Muninn(data_path=str(tmp_path))
    try:
        ids = facade.remember_many([{"content": "facade one"},
                                    {"content": "facade two"}])
        assert len(ids) == 2
        assert facade.get_node(ids[0]).content == "facade one"
    finally:
        facade.close()


# ─── one transaction, one backpressure ───────────────────────


def test_batch_is_one_transaction_and_one_backpressure_check(mem):
    items = [{"content": f"counted {i}"} for i in range(50)]
    ids, texts = _traced(mem, lambda: mem.remember_many(items))
    assert len(ids) == 50
    # Exactly one COMMIT for the whole ingest (no backpressure
    # fires under the default ceiling, so nothing else commits),
    # and the backpressure head-count ran exactly once.
    assert _count_starting(texts, "COMMIT") == 1
    assert sum(1 for t in texts if t.startswith("SELECT COUNT(*) FROM nodes")) == 1
    # The loop road, for contrast, commits per node.
    other_items = [{"content": f"loop counted {i}"} for i in range(5)]
    _ids, loop_texts = _traced(
        mem, lambda: [mem.remember(**item) for item in other_items]
    )
    assert _count_starting(loop_texts, "COMMIT") == 5


def test_batch_backpressure_applied_once_at_the_end(tmp_path):
    m = HebbianMemory(
        MuninnConfig(
            db_path=str(tmp_path / "m.db"), auto_backup=False, max_nodes=10
        )
    )
    try:
        # Importance rises with creation order (1,1,1,2,2,2,…),
        # so the five lowest-value victims are the first five
        # created — the backpressure order (importance,
        # access_count, updated_at, id) is fully deterministic
        # here: one shared batch timestamp, zero access counts.
        items = [
            {"content": f"graded {i}", "importance": i // 3 + 1}
            for i in range(15)
        ]
        ids, texts = _traced(m, lambda: m.remember_many(items))
        assert len(ids) == 15
        # Two commits total: the batch's one, and the single
        # backpressure pass after it.
        assert _count_starting(texts, "COMMIT") == 2
        assert m.stats()["total_nodes"] == 10
        kept = {m.get_node(i).content for i in ids if m.get_node(i) is not None}
        assert kept == {f"graded {i}" for i in range(5, 15)}
        tombstoned = {
            r[0]
            for r in m._get_conn().execute("SELECT memory_id FROM deleted_nodes")
        }
        assert len(tombstoned) == 5
    finally:
        m.close()


# ─── atomic refusals: nothing of the batch survives ──────────


def test_batch_invalid_item_refuses_the_whole_batch(mem):
    mem.remember("standing memory")
    with pytest.raises(MuninnValidationError) as caught:
        mem.remember_many([
            {"content": "batch prefix that must not survive"},
            {"content": "bad item", "importance": 99},
        ])
    assert "importance must be in [1, 10], got 99" in str(caught.value)
    assert mem.stats()["total_nodes"] == 1
    assert mem.retrieve(query="batch prefix") == []


def test_batch_container_and_item_shapes_are_typed(mem):
    with pytest.raises(MuninnValidationError) as caught:
        mem.remember_many("not a list")
    assert str(caught.value) == "items must be a list of dicts"
    with pytest.raises(MuninnValidationError) as caught:
        mem.remember_many([{"content": "fine"}, "not a dict"])
    assert str(caught.value) == "each item must be a dict"
    with pytest.raises(MuninnValidationError) as caught:
        mem.remember_many([{"content": "fine", "bogus": 1}])
    assert str(caught.value) == "unknown item fields: ['bogus']"
    with pytest.raises(MuninnValidationError) as caught:
        mem.remember_many([{"path": "no content here"}])
    assert str(caught.value) == "each item must carry a 'content' key"
    with pytest.raises(MuninnValidationError) as caught:
        mem.remember_many([{"content": None}])
    assert str(caught.value) == "content must not be None"
    assert mem.stats()["total_nodes"] == 0


def test_batch_oversize_item_refuses_before_any_write(tmp_path):
    m = HebbianMemory(
        MuninnConfig(
            db_path=str(tmp_path / "m.db"),
            auto_backup=False,
            max_content_bytes=16,
        )
    )
    try:
        with pytest.raises(MuninnValidationError):
            m.remember_many([
                {"content": "small"},
                {"content": "this content is far over sixteen bytes"},
            ])
        assert m.stats()["total_nodes"] == 0
    finally:
        m.close()


def test_batch_forced_collision_rolls_back_everything(mem, monkeypatch):
    monkeypatch.setattr(
        muninn.core, "_content_hash", lambda text, is_json: "f" * 64
    )
    keeper = mem.remember("the one true memory")
    with pytest.raises(MuninnValidationError) as caught:
        mem.remember_many([
            {"content": "prefix of the doomed batch"},
            {"content": "a different memory under the same forced hash"},
        ])
    assert "content hash collision" in str(caught.value)
    assert f"(id {keeper})" in str(caught.value)
    # Neither batch item landed; the pre-existing node is alone
    # and untouched.
    assert mem.stats()["total_nodes"] == 1
    assert mem.get_node(keeper).content == "the one true memory"


def test_batch_disk_full_is_typed_and_atomic(mem):
    # The RM-029 fault road: cap the store at its current page
    # count so the batch's growth hits SQLITE_FULL mid-batch.
    mem.remember("seed")
    conn = mem._get_conn()
    pages = conn.execute("PRAGMA page_count").fetchone()[0]
    conn.execute(f"PRAGMA max_page_count={int(pages)}")
    big = "x" * 20000
    with pytest.raises(Exception) as caught:
        mem.remember_many([{"content": big}, {"content": big + "y"}])
    assert type(caught.value).__name__ == "MuninnStorageError"
    assert "remember_many" in str(caught.value)
    # The write guard rolled the batch back: only the seed.
    assert mem.stats()["total_nodes"] == 1


# ─── composition: encryption + log discipline ────────────────


def test_batch_on_an_encrypted_store(tmp_path):
    pytest.importorskip("cryptography")
    cfg = MuninnConfig(
        db_path=str(tmp_path / "enc.db"),
        auto_backup=False,
        store_encryption=True,
        encryption_passphrase="bulk remember passphrase",
    )
    m = HebbianMemory(cfg)
    try:
        ids = m.remember_many([
            {"content": "sealed one", "category": "vault"},
            {"content": "sealed two", "category": "vault"},
        ])
        assert m.get_node(ids[0]).content == "sealed one"
        # Idempotent hit through the keyed lookup tag.
        assert m.remember_many([{"content": "sealed one", "category": "vault"}]) == [
            ids[0]
        ]
        raw = m._get_conn().execute(
            "SELECT content FROM nodes WHERE id = ?", (ids[0],)
        ).fetchone()[0]
        assert "sealed one" not in raw
    finally:
        m.close()


def test_batch_log_redaction_discipline(tmp_path, caplog):
    off = HebbianMemory(
        MuninnConfig(db_path=str(tmp_path / "off.db"), auto_backup=False)
    )
    try:
        with caplog.at_level(logging.DEBUG, logger="muninn"):
            off.remember_many([{"content": SECRET}])
        assert all(SECRET not in r.getMessage() for r in caplog.records)
    finally:
        off.close()
    caplog.clear()
    on = HebbianMemory(
        MuninnConfig(
            db_path=str(tmp_path / "on.db"),
            auto_backup=False,
            debug_log_content=True,
        )
    )
    try:
        with caplog.at_level(logging.DEBUG, logger="muninn"):
            on.remember_many([{"content": SECRET}])
        carriers = [r for r in caplog.records if SECRET in r.getMessage()]
        assert carriers, "flag on: the batch path must log content at DEBUG"
        assert all(r.levelno == logging.DEBUG for r in carriers)
    finally:
        on.close()


# ─── the gate script + committed record ──────────────────────


def test_gate_script_small_run_shape():
    module = _load_script()
    record = module.run_bulk_remember(n_nodes=40, repeat=2)
    assert record["kind"] == "bulk_remember"
    assert set(record["results_ms"]) == set(module.OPS)
    assert record["details"]["nodes"] == 40
    assert record["details"]["stores_verified_identical"] is True
    assert record["details"]["corpus"]["count"] == 40
    for key in ENV_KEYS:
        assert key in record["environment"]


def test_committed_record_carries_the_gate():
    record = json.loads(COMMITTED.read_text())
    assert record["package"] == "muninn"
    assert record["kind"] == "bulk_remember"
    assert set(record["results_ms"]) == {"remember_loop", "remember_many"}
    # The roadmap's acceptance shape: a 10k-node ingest.
    assert record["details"]["nodes"] == 10000
    assert record["details"]["stores_verified_identical"] is True
    assert record["details"]["corpus"]["count"] == 10000
    assert record["results_ms"]["remember_many"] > 0
    assert record["results_ms"]["remember_loop"] > 0
    for key in ENV_KEYS:
        assert key in record["environment"]
