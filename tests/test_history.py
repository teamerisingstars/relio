# tests/test_history.py
from relio.memory import Memory
from relio.embedding.base import DeterministicEmbedder
from relio.record import MemoryType, Scope


def _mem(tmp_path):
    return Memory(path=str(tmp_path / "h.db"), embedder=DeterministicEmbedder(dim=16))


def test_add_with_embed_false_is_not_recallable(tmp_path):
    m = _mem(tmp_path)
    m.add("you said hello", type=MemoryType.SESSION, embed=False)
    assert m.recall("hello", limit=5) == []
    m.close()


def test_add_turn_records_role_and_is_not_recallable(tmp_path):
    m = _mem(tmp_path)
    scope = Scope(user="alice", session="s1")
    rec = m.add_turn("user", "I like hiking", scope)
    assert rec.type is MemoryType.SESSION
    assert rec.metadata["role"] == "user"
    assert m.recall("hiking", scope=scope, limit=5) == []  # not embedded
    m.close()


def test_history_returns_turns_in_order(tmp_path):
    m = _mem(tmp_path)
    scope = Scope(user="alice", session="s1")
    m.add_turn("user", "first", scope)
    m.add_turn("assistant", "second", scope)
    m.add_turn("user", "third", scope)
    hist = m.history(scope)
    assert [h.content for h in hist] == ["first", "second", "third"]
    assert [h.metadata["role"] for h in hist] == ["user", "assistant", "user"]
    m.close()


def test_history_respects_limit_keeping_most_recent(tmp_path):
    m = _mem(tmp_path)
    scope = Scope(user="alice", session="s1")
    for i in range(5):
        m.add_turn("user", f"msg{i}", scope)
    hist = m.history(scope, limit=2)
    assert [h.content for h in hist] == ["msg3", "msg4"]
    m.close()


def test_history_is_scope_isolated(tmp_path):
    m = _mem(tmp_path)
    a = Scope(user="alice", session="s1")
    b = Scope(user="bob", session="s2")
    m.add_turn("user", "alice secret", a)
    m.add_turn("user", "bob secret", b)
    assert [h.content for h in m.history(a)] == ["alice secret"]
    assert [h.content for h in m.history(b)] == ["bob secret"]
    m.close()


def test_history_excludes_non_session_records(tmp_path):
    m = _mem(tmp_path)
    scope = Scope(user="alice", session="s1")
    m.add("a semantic fact", scope=scope)  # SEMANTIC, embedded
    m.add_turn("user", "a turn", scope)
    hist = m.history(scope)
    assert [h.content for h in hist] == ["a turn"]
    m.close()
