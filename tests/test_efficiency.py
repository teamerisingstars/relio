# tests/test_efficiency.py
from relio.memory import Memory
from relio.embedding.base import DeterministicEmbedder
from relio.record import MemoryRecord, MemoryType, Scope
from relio.render import render_lines


def _mem(tmp_path):
    return Memory(path=str(tmp_path / "e.db"), embedder=DeterministicEmbedder(dim=16))


def test_recall_is_cached_and_invalidated_on_write(tmp_path):
    m = _mem(tmp_path)
    m.add("Alice likes tea")
    r1 = m.recall("tea")
    r2 = m.recall("tea")
    assert r1 is r2  # served from cache (same object)

    m.add("Alice also likes coffee")  # write invalidates
    r3 = m.recall("tea")
    assert r3 is not r1  # recomputed
    m.close()


def test_forget_invalidates_recall_cache(tmp_path):
    m = _mem(tmp_path)
    rec = m.add("ephemeral note")
    assert m.recall("ephemeral note")
    m.forget(rec.id)
    assert all(r.id != rec.id for r in m.recall("ephemeral note"))
    m.close()


def test_render_lines_respects_char_budget():
    recs = [MemoryRecord(content="x" * 20) for _ in range(10)]
    out = render_lines(recs, max_chars=50)
    assert len(out) <= 50
    assert out.count("\n") < 9  # not all ten lines
    # always at least one line even if it exceeds budget
    assert render_lines(recs, max_chars=1).count("\n") == 0


def test_query_still_correct_with_indexes(tmp_path):
    m = _mem(tmp_path)
    m.add("a fact", type=MemoryType.FACT, scope=Scope(user="alice"))
    m.add("a note", type=MemoryType.SEMANTIC, scope=Scope(user="bob"))
    facts = m.query(type=MemoryType.FACT)
    assert [r.content for r in facts] == ["a fact"]
    alice = m.query(scope=Scope(user="alice"))
    assert [r.content for r in alice] == ["a fact"]
    m.close()
