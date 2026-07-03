# tests/test_graph.py
from relio.memory import Memory
from relio.embedding.base import DeterministicEmbedder
from relio.record import MemoryType


def _mem(tmp_path):
    return Memory(path=str(tmp_path / "g.db"), embedder=DeterministicEmbedder(dim=16))


def test_add_node_creates_a_node_record(tmp_path):
    m = _mem(tmp_path)
    n = m.add_node("Alice")
    assert n.type is MemoryType.NODE
    assert m.get(n.id).content == "Alice"
    m.close()


def test_neighbors_returns_linked_targets(tmp_path):
    m = _mem(tmp_path)
    alice = m.add_node("Alice")
    acme = m.add_node("Acme")
    m.add_edge(alice.id, "works_at", acme.id)
    assert [n.content for n in m.neighbors(alice.id)] == ["Acme"]
    m.close()


def test_neighbors_predicate_filter(tmp_path):
    m = _mem(tmp_path)
    alice = m.add_node("Alice")
    acme = m.add_node("Acme")
    bob = m.add_node("Bob")
    m.add_edge(alice.id, "works_at", acme.id)
    m.add_edge(alice.id, "knows", bob.id)
    assert [n.content for n in m.neighbors(alice.id, predicate="knows")] == ["Bob"]
    m.close()


def test_in_neighbors_finds_edge_source(tmp_path):
    m = _mem(tmp_path)
    alice = m.add_node("Alice")
    acme = m.add_node("Acme")
    m.add_edge(alice.id, "works_at", acme.id)
    assert [n.content for n in m.in_neighbors(acme.id)] == ["Alice"]
    m.close()


def test_traverse_reaches_grandchild(tmp_path):
    m = _mem(tmp_path)
    a = m.add_node("A")
    b = m.add_node("B")
    c = m.add_node("C")
    m.add_edge(a.id, "to", b.id)
    m.add_edge(b.id, "to", c.id)
    reached = m.traverse(a.id, depth=2)
    assert {n.content for n in reached} == {"B", "C"}
    # depth 1 stops at B
    assert {n.content for n in m.traverse(a.id, depth=1)} == {"B"}
    m.close()


def test_traverse_batches_lookups_no_per_edge_get(tmp_path, monkeypatch):
    # Regression (N+1): traverse must batch via get_many, not call get() per
    # node/edge. A depth-2 chain of 3 nodes should issue very few single get()s.
    m = _mem(tmp_path)
    a = m.add_node("A")
    b = m.add_node("B")
    c = m.add_node("C")
    m.add_edge(a.id, "to", b.id)
    m.add_edge(b.id, "to", c.id)
    calls = {"get": 0}
    real_get = m._backend.get
    monkeypatch.setattr(
        m._backend, "get",
        lambda rid: (calls.__setitem__("get", calls["get"] + 1), real_get(rid))[1],
    )
    reached = m.traverse(a.id, depth=2)
    assert {n.content for n in reached} == {"B", "C"}
    # Batched: get_many does the work, so single-get() calls stay ~0.
    assert calls["get"] <= 1
    m.close()


def test_traverse_is_cycle_safe(tmp_path):
    m = _mem(tmp_path)
    a = m.add_node("A")
    b = m.add_node("B")
    m.add_edge(a.id, "to", b.id)
    m.add_edge(b.id, "to", a.id)  # cycle
    reached = m.traverse(a.id, depth=5)
    assert {n.content for n in reached} == {"B"}  # A excluded (start), no infinite loop
    m.close()
