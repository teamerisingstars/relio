# tests/test_query.py
import pytest

from relio.memory import Memory
from relio.embedding.base import DeterministicEmbedder
from relio.record import MemoryType, Scope


def _mem(tmp_path):
    return Memory(path=str(tmp_path / "q.db"), embedder=DeterministicEmbedder(dim=16))


def test_query_filters_by_type(tmp_path):
    m = _mem(tmp_path)
    m.add("a fact", type=MemoryType.FACT)
    m.add("a note", type=MemoryType.SEMANTIC)
    assert [r.content for r in m.query(type=MemoryType.FACT)] == ["a fact"]
    m.close()


def test_query_filters_by_scope(tmp_path):
    m = _mem(tmp_path)
    m.add("alice note", scope=Scope(user="alice"))
    m.add("bob note", scope=Scope(user="bob"))
    assert [r.content for r in m.query(scope=Scope(user="alice"))] == ["alice note"]
    m.close()


def test_query_filters_by_metadata(tmp_path):
    m = _mem(tmp_path)
    m.add("x", metadata={"category": "task"})
    m.add("y", metadata={"category": "idea"})
    assert [r.content for r in m.query(where={"category": "idea"})] == ["y"]
    m.close()


def test_query_returns_non_embedded_records(tmp_path):
    m = _mem(tmp_path)
    m.add_turn("user", "hello", Scope(session="s1"))  # stored with embed=False
    assert m.recall("hello") == []  # invisible to semantic recall...
    assert [r.content for r in m.query(type=MemoryType.SESSION)] == ["hello"]  # ...visible here
    m.close()


def test_query_respects_insertion_order_and_limit(tmp_path):
    m = _mem(tmp_path)
    for i in range(4):
        m.add(f"n{i}", type=MemoryType.FACT)
    assert [r.content for r in m.query(type=MemoryType.FACT, limit=2)] == ["n0", "n1"]
    m.close()


def test_invalid_metadata_key_is_rejected(tmp_path):
    m = _mem(tmp_path)
    with pytest.raises(ValueError):
        m.query(where={"bad key!": "x"})
    m.close()


def test_transaction_commits_all_on_success(tmp_path):
    m = _mem(tmp_path)
    with m.transaction():
        m.add("one", type=MemoryType.FACT)
        m.add("two", type=MemoryType.FACT)
    assert len(m.query(type=MemoryType.FACT)) == 2
    m.close()


def test_transaction_rolls_back_on_exception(tmp_path):
    m = _mem(tmp_path)
    m.add("pre", type=MemoryType.FACT)
    with pytest.raises(RuntimeError):
        with m.transaction():
            m.add("mid", type=MemoryType.FACT)
            raise RuntimeError("boom")
    assert [r.content for r in m.query(type=MemoryType.FACT)] == ["pre"]
    m.close()


def test_add_many_embeds_in_one_batch_and_is_recallable(tmp_path):
    from tests.test_embedding import CountingEmbedder

    m = Memory(path=str(tmp_path / "b.db"), embedder=CountingEmbedder(dim=16))
    records = m.add_many(["alpha fact", "beta fact"])
    assert len(records) == 2
    assert m._embedder._inner.calls == 2  # exactly two embeds, via one batch
    found = m.recall("alpha fact", limit=5)
    assert any("alpha" in r.content for r in found)
    m.close()


def test_add_many_without_embedding_is_query_only(tmp_path):
    m = _mem(tmp_path)
    m.add_many(["x", "y"], type=MemoryType.SESSION, embed=False)
    assert m.recall("x") == []  # not embedded
    assert len(m.query(type=MemoryType.SESSION)) == 2
    m.close()


def test_add_many_accepts_rows_with_metadata(tmp_path):
    from relio.record import Scope

    m = _mem(tmp_path)
    records = m.add_many(
        [
            "a plain string still works",
            {"content": "ROAS row", "metadata": {"roas": 3.2, "campaign": "c1"}},
            {"content": "other tenant row", "scope": Scope(tenant="t2"), "data": {"raw": 1}},
        ],
        embed=False,
    )
    assert len(records) == 3
    # metadata is queryable (range filter + ordering — the reporting use case)
    hot = m.query(where={"roas__gt": 3.0})
    assert [r.metadata["campaign"] for r in hot] == ["c1"]
    # per-row scope + data are honored
    assert records[2].scope.tenant == "t2"
    assert records[2].data == {"raw": 1}
    m.close()


def test_add_many_rejects_bad_item_types(tmp_path):
    m = _mem(tmp_path)
    with pytest.raises(TypeError):
        m.add_many([123])  # not str or mapping
    m.close()


def test_sql_analytics_is_postgres_only(tmp_path):
    m = _mem(tmp_path)  # SQLite
    with pytest.raises(NotImplementedError):
        m.sql("SELECT 1")
    m.close()
