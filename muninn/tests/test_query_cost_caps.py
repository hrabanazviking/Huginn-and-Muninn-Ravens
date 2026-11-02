"""RM-053 — Query cost ceilings for muninn (threat TH-13).

``spread_activation`` examines candidate edges (neighbour
rows) as it walks. Before this slice the walk was bounded
only by the store itself: a hub node, or a dense graph,
made one call examine every edge it could reach, however
large that was. The slice adds the explicit ceiling
``MuninnConfig.max_spread_candidates``:

* one call examines at most that many candidate edges;
* when the ceiling bites, the expansion stops
  deterministically (frontier nodes and neighbours in id
  order) and the call returns what it has;
* the bite is visible: ``last_spread_activation_stats``
  records ``candidates_examined`` (== the ceiling when
  capped), ``cap``, ``capped`` and ``nodes_returned`` —
  a dedicated attribute, NOT a ``stats()`` / ``health()``
  field, because those snapshots are pinned pure (a read
  must not change them);
* below the ceiling the result is exactly the unbounded
  walk's result.

Record: ``docs/QUERY_COST_CAPS.md``.
"""

import pytest

from muninn import HebbianMemory
from muninn.config import MuninnConfig
from muninn.errors import MuninnConfigurationError


def _mem(tmp_path, **overrides):
    return HebbianMemory(
        MuninnConfig(db_path=str(tmp_path / "m.db"), **overrides)
    )


def _star(mem, hub=1, leaves=30):
    for leaf in range(hub + 1, hub + leaves + 1):
        mem.associate(hub, leaf, strength=0.9)


def test_default_ceiling_and_initial_stats(tmp_path):
    mem = _mem(tmp_path)
    try:
        assert mem.config.max_spread_candidates == 100000
        assert mem.last_spread_activation_stats == {
            "candidates_examined": 0,
            "cap": 100000,
            "capped": False,
            "nodes_returned": 0,
        }
    finally:
        mem.close()


def test_ceiling_is_validated_at_construction(tmp_path):
    with pytest.raises(MuninnConfigurationError):
        MuninnConfig(db_path=str(tmp_path / "x.db"), max_spread_candidates=0)
    with pytest.raises(MuninnConfigurationError):
        MuninnConfig(db_path=str(tmp_path / "x.db"), max_spread_candidates=-5)
    with pytest.raises(MuninnConfigurationError):
        MuninnConfig(db_path=str(tmp_path / "x.db"), max_spread_candidates="ten")


def test_below_the_ceiling_the_walk_is_unchanged(tmp_path):
    mem = _mem(tmp_path)
    try:
        mem.associate(1, 2, strength=1.0)
        mem.associate(2, 3, strength=1.0)
        mem.associate(1, 4, strength=0.1)
        spread = mem.spread_activation([1], depth=2, attenuation=0.5)
        assert spread[1] == 1.0
        assert spread[2] == pytest.approx(0.5)
        assert spread[3] == pytest.approx(0.25)
        assert spread[4] < spread[3]
        stats = mem.last_spread_activation_stats
        # Edges examined: from 1 → {2, 4}; from 2 → {1, 3};
        # from 4 → {1}. Five candidate edges, no bite.
        assert stats["candidates_examined"] == 5
        assert stats["capped"] is False
        assert stats["nodes_returned"] == 4
    finally:
        mem.close()


def test_cap_bites_deterministically_at_the_ceiling(tmp_path):
    mem = _mem(tmp_path, max_spread_candidates=10)
    try:
        _star(mem, leaves=30)
        first = mem.spread_activation([1], depth=1, attenuation=0.5)
        stats = mem.last_spread_activation_stats
        assert stats["candidates_examined"] == 10
        assert stats["cap"] == 10
        assert stats["capped"] is True
        # Neighbours are considered in id order: the seed
        # plus leaves 2..11, and nothing beyond the bite.
        assert set(first) == {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11}
        assert stats["nodes_returned"] == 11
        second = mem.spread_activation([1], depth=1, attenuation=0.5)
        assert list(second.items()) == list(first.items())
    finally:
        mem.close()


def test_cap_of_one_examines_exactly_one_candidate(tmp_path):
    mem = _mem(tmp_path, max_spread_candidates=1)
    try:
        _star(mem, leaves=5)
        spread = mem.spread_activation([1], depth=1)
        assert mem.last_spread_activation_stats["candidates_examined"] == 1
        assert mem.last_spread_activation_stats["capped"] is True
        assert set(spread) == {1, 2}
    finally:
        mem.close()


def test_worst_case_dense_graph_stays_within_the_bound(tmp_path):
    """BENCH acceptance: a fully connected synthetic corpus
    (the worst case for spreading — every node reaches every
    other in one hop) cannot make one call examine more
    candidate edges than the stated ceiling."""
    mem = _mem(tmp_path, max_spread_candidates=200)
    try:
        nodes = list(range(1, 26))
        for i, a in enumerate(nodes):
            for b in nodes[i + 1:]:
                mem.associate(a, b, strength=0.9)
        spread = mem.spread_activation([1], depth=3, attenuation=0.5)
        stats = mem.last_spread_activation_stats
        assert stats["candidates_examined"] == 200
        assert stats["capped"] is True
        assert set(spread) <= set(nodes)
    finally:
        mem.close()


def test_spread_stays_a_pure_read_for_stats_and_health(tmp_path):
    """The accounting lives on the dedicated attribute only:
    a capped spread must not change the stats()/health()
    snapshots (the RM-009 read-purity pin)."""
    mem = _mem(tmp_path, max_spread_candidates=3)
    try:
        _star(mem, leaves=10)
        stats_before = mem.stats()
        health_before = mem.health()
        mem.spread_activation([1], depth=1)
        assert mem.last_spread_activation_stats["capped"] is True
        assert mem.stats() == stats_before
        assert mem.health() == health_before
    finally:
        mem.close()
