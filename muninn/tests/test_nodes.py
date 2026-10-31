"""Ancestor node semantics: store / retrieve / tree / update / move."""

import pytest

from muninn import HebbianMemory, MemoryNode, Muninn
from muninn.config import MuninnConfig
from muninn.errors import MuninnValidationError


@pytest.fixture
def mem(tmp_path):
    m = HebbianMemory(MuninnConfig(db_path=str(tmp_path / "m.db")))
    yield m
    m.close()


def test_remember_and_get_node(mem):
    nid = mem.remember(
        "Freyja is the Vanir goddess of love and seiðr",
        category="spiritual",
        path="pantheon/vanir",
        importance=9,
        tags=["Freyja", " seiðr "],
        emotional_valence=0.8,
        metadata={"source": "test"},
    )
    assert isinstance(nid, int)
    node = mem.get_node(nid)
    assert isinstance(node, MemoryNode)
    assert node.content.startswith("Freyja")
    assert node.memory_type == "spiritual"
    assert node.category == "spiritual"  # alias
    assert node.tags == ["freyja", "seiðr"]  # normalized
    assert node.metadata == {"source": "test"}
    assert mem.get_node(999999) is None


def test_remember_idempotent(mem):
    a = mem.remember("same content", category="fact", path="p")
    b = mem.remember("same content", category="fact", path="p")
    assert a == b
    assert mem.stats()["total_nodes"] == 1
    c = mem.remember("same content", category="other", path="p")
    assert c != a  # different category = different node


def test_structured_content_round_trip(mem):
    payload = {"character": "Volmarr", "conditions": ["prone"], "turn": 3}
    nid = mem.remember(payload, category="condition_event")
    node = mem.get_node(nid)
    assert node.content == payload
    assert node.to_dict()["content"] == payload
    clone = MemoryNode.from_dict(node.to_dict())
    assert clone.content == payload


def test_ancestor_store_retrieve(mem):
    mem.store(
        "Odin hung on the tree nine nights", path="myth/odin", memory_type="myth", importance=8
    )
    mem.store(
        "Thor fishes for the World Serpent", path="myth/thor", memory_type="myth", importance=7
    )
    mem.store("Python async patterns", path="skill/python", memory_type="skill", importance=6)
    hits = mem.retrieve("tree", memory_type="myth")
    assert len(hits) == 1 and "Odin" in hits[0].content
    assert len(mem.retrieve(memory_type="myth")) == 2
    assert len(mem.retrieve(tags=["nope"])) == 0
    assert len(mem.get_by_path("myth/odin")) == 1
    children = mem.get_children("myth")
    assert set(children) == {"myth/odin", "myth/thor"}
    tree = mem.get_tree_structure()
    assert tree["myth"]["odin"]["_nodes"] == 1


def test_update_and_move(mem):
    nid = mem.store("draft note", path="a/b", memory_type="note", importance=3)
    assert mem.update(nid, importance=9, tags=["kept"]) is True
    assert mem.get_node(nid).importance == 9
    assert mem.move(nid, "c/d") is True
    assert mem.get_node(nid).path == "c/d"
    assert mem.get_by_path("a/b") == []
    assert mem.update(424242, importance=5) is False
    with pytest.raises(MuninnValidationError):
        mem.update(nid, nonsense_field=1)


def test_forget_removes_node_and_wiring(mem):
    a = mem.remember("alpha", category="fact")
    b = mem.remember("beta", category="fact")
    mem.associate(a, b, strength=0.7)
    assert mem.forget(a) is True
    assert mem.get_node(a) is None
    assert mem.get_associations(b) == []
    assert mem.forget(a) is False  # second forget: nothing left to remove


def test_access_count_via_activate(mem):
    nid = mem.remember("counted", category="fact")
    mem.activate(nid)
    mem.activate(nid)
    assert mem.get_node(nid).access_count == 2


def test_backpressure_prunes_lowest_value(tmp_path):
    m = HebbianMemory(
        MuninnConfig(db_path=str(tmp_path / "m.db"), max_nodes=5)
    )
    ids = {}
    for i in range(5):
        ids[i] = m.remember(f"memory {i}", category="fact", importance=i + 1)
    m.remember("important newcomer", category="fact", importance=10)
    assert m.stats()["total_nodes"] == 5
    assert m.get_node(ids[0]) is None  # lowest importance pruned
    m.close()


def test_muninn_facade_directory_shape(tmp_path):
    m = Muninn(data_path=str(tmp_path / "store-dir"))
    nid = m.store("facade memory", path="x/y")
    assert m.get_node(nid).content == "facade memory"
    assert (tmp_path / "store-dir" / "muninn_hebbian.db").exists()
    m.close()
