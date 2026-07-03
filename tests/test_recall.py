# tests/test_recall.py
import time

from relio.backends.sqlite import SQLiteBackend
from relio.embedding.base import DeterministicEmbedder
from relio.recall import RecallEngine
from relio.record import MemoryRecord, MemoryType, Scope


def _engine(tmp_path):
    emb = DeterministicEmbedder(dim=16)
    be = SQLiteBackend(str(tmp_path / "m.db"), dim=16)
    return RecallEngine(be, emb), be, emb


def test_recall_filters_by_scope(tmp_path):
    engine, be, emb = _engine(tmp_path)
    a = MemoryRecord(content="apple pie recipe", scope=Scope(user="alice"))
    b = MemoryRecord(content="apple pie recipe", scope=Scope(user="bob"))
    be.add(a, emb.embed(a.content))
    be.add(b, emb.embed(b.content))
    results = engine.recall("apple pie recipe", scope=Scope(user="alice"), limit=5)
    assert [r.scope.user for r in results] == ["alice"]
    be.close()


def test_recall_not_starved_by_another_tenants_closer_vectors(tmp_path):
    # Regression (multi-tenant): with a fixed over-fetch, tenant bob's matches
    # could be crowded out of the top-k by many closer alice vectors, so bob got
    # too few. Adaptive over-fetch must still return bob's `limit` results.
    engine, be, emb = _engine(tmp_path)
    for i in range(60):  # lots of near-identical alice vectors
        a = MemoryRecord(content="apple pie recipe", scope=Scope(user="alice"))
        be.add(a, emb.embed(a.content))
    for i in range(3):
        b = MemoryRecord(content="apple pie recipe", scope=Scope(user="bob"))
        be.add(b, emb.embed(b.content))
    results = engine.recall("apple pie recipe", scope=Scope(user="bob"), limit=3)
    assert len(results) == 3
    assert all(r.scope.user == "bob" for r in results)
    be.close()


def test_recall_filters_by_type(tmp_path):
    engine, be, emb = _engine(tmp_path)
    f = MemoryRecord(type=MemoryType.FACT, content="lives in Kerala")
    s = MemoryRecord(type=MemoryType.SEMANTIC, content="lives in Kerala")
    be.add(f, emb.embed(f.content))
    be.add(s, emb.embed(s.content))
    results = engine.recall("lives in Kerala", type=MemoryType.FACT, limit=5)
    assert all(r.type is MemoryType.FACT for r in results)
    be.close()


def test_recall_excludes_expired_session_memories(tmp_path):
    engine, be, emb = _engine(tmp_path)
    rec = MemoryRecord(type=MemoryType.SESSION, content="temporary note", ttl=-1)
    be.add(rec, emb.embed(rec.content))
    results = engine.recall("temporary note", limit=5, now=time.time())
    assert results == []
    be.close()
