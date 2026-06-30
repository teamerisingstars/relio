# tests/test_memory.py
from relio.memory import Memory
from relio.embedding.base import DeterministicEmbedder
from relio.record import MemoryType, Scope


def _mem(tmp_path):
    return Memory(
        path=str(tmp_path / "m.db"),
        embedder=DeterministicEmbedder(dim=16),
    )


def test_add_then_recall_returns_the_memory(tmp_path):
    m = _mem(tmp_path)
    m.add("Alice works at Acme")
    results = m.recall("where does Alice work?", limit=3)
    assert any("Acme" in r.content for r in results)
    m.close()


def test_get_and_forget(tmp_path):
    m = _mem(tmp_path)
    rec = m.add("ephemeral", type=MemoryType.SESSION, ttl=3600)
    assert m.get(rec.id).content == "ephemeral"
    assert m.forget(rec.id) is True
    assert m.get(rec.id) is None
    m.close()


def test_link_adds_a_relation(tmp_path):
    m = _mem(tmp_path)
    person = m.add("Alice", type=MemoryType.NODE)
    org = m.add("Acme", type=MemoryType.NODE)
    m.link(person.id, "works_at", org.id)
    again = m.get(person.id)
    assert again.relations[0].predicate == "works_at"
    assert again.relations[0].target_id == org.id
    m.close()


def test_recall_text_renders_lines(tmp_path):
    m = _mem(tmp_path)
    m.add("prefers Python")
    text = m.recall_text("python", limit=3)
    assert text.startswith("- ")
    m.close()


def test_duplicate_content_is_embedded_once(tmp_path):
    from tests.test_embedding import CountingEmbedder

    m = Memory(path=str(tmp_path / "m.db"), embedder=CountingEmbedder(dim=16))
    m.add("same text")
    m.recall("same text")          # embeds the query once...
    before = m._embedder._inner.calls     # CachingEmbedder wraps CountingEmbedder
    m.recall("same text")          # ...cached on the second identical query
    assert m._embedder._inner.calls == before
    m.close()


def test_link_bumps_updated_at(tmp_path):
    m = _mem(tmp_path)
    a = m.add("Alice")
    b = m.add("Acme")
    before = m.get(a.id).updated_at
    m.link(a.id, "works_at", b.id)
    assert m.get(a.id).updated_at > before
    m.close()


def test_recall_omits_expired_session_memory_via_facade(tmp_path):
    m = _mem(tmp_path)
    m.add("temporary scratch", type=MemoryType.SESSION, ttl=-1)
    assert m.recall("temporary scratch", limit=5) == []
    m.close()


# tests/test_memory.py  (append)
def test_top_level_imports_are_exported():
    import relio

    assert hasattr(relio, "Memory")
    assert hasattr(relio, "MemoryRecord")
    assert hasattr(relio, "MemoryType")
    assert hasattr(relio, "Scope")
