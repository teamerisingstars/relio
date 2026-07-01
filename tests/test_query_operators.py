# tests/test_query_operators.py
import pytest

from relio.memory import Memory
from relio.embedding.base import DeterministicEmbedder
from relio.record import MemoryType, Scope


def _mem(tmp_path):
    return Memory(path=str(tmp_path / "q.db"), embedder=DeterministicEmbedder(dim=16))


def _seed(m):
    m.add("a", type=MemoryType.FACT, metadata={"amount": 100, "name": "alpha"})
    m.add("b", type=MemoryType.FACT, metadata={"amount": 500, "name": "beta"})
    m.add("c", type=MemoryType.FACT, metadata={"amount": 900, "name": "gamma"})


def test_range_operators(tmp_path):
    m = _mem(tmp_path)
    _seed(m)
    assert {r.content for r in m.query(where={"amount__gt": 400})} == {"b", "c"}
    assert {r.content for r in m.query(where={"amount__lte": 500})} == {"a", "b"}
    m.close()


def test_contains_operator(tmp_path):
    m = _mem(tmp_path)
    _seed(m)
    assert [r.content for r in m.query(where={"name__contains": "amm"})] == ["c"]  # gamma
    m.close()


def test_order_by_and_pagination(tmp_path):
    m = _mem(tmp_path)
    _seed(m)
    desc = [r.metadata["amount"] for r in m.query(order_by="-amount")]
    assert desc == [900, 500, 100]
    page = m.query(order_by="amount", limit=1, offset=1)
    assert page[0].metadata["amount"] == 500
    m.close()


def test_ne_in_startswith_operators(tmp_path):
    m = _mem(tmp_path)
    _seed(m)
    assert {r.content for r in m.query(where={"amount__ne": 500})} == {"a", "c"}
    assert {r.content for r in m.query(where={"amount__in": [100, 900]})} == {"a", "c"}
    assert {r.content for r in m.query(where={"name__startswith": "al"})} == {"a"}  # alpha
    m.close()


def test_invalid_where_field_rejected(tmp_path):
    m = _mem(tmp_path)
    with pytest.raises(ValueError):
        m.query(where={"bad field__gt": 1})
    m.close()


def test_graph_neighbors_are_scope_filtered(tmp_path):
    m = _mem(tmp_path)
    hub = m.add_node("hub")
    a = m.add_node("acme-node", scope=Scope(tenant="acme"))
    g = m.add_node("globex-node", scope=Scope(tenant="globex"))
    m.add_edge(hub.id, "to", a.id)
    m.add_edge(hub.id, "to", g.id)
    both = {n.content for n in m.neighbors(hub.id)}
    assert both == {"acme-node", "globex-node"}
    acme_only = {n.content for n in m.neighbors(hub.id, scope=Scope(tenant="acme"))}
    assert acme_only == {"acme-node"}   # globex node filtered out by scope
    m.close()
