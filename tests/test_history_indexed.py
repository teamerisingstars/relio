# tests/test_history_indexed.py — history() must use the indexed newest_first
# query, not a full-table all() scan (perf on the per-chat-turn hot path).
from relio.embedding.base import DeterministicEmbedder
from relio.memory import Memory
from relio.record import MemoryType, Scope


def _mem(tmp_path):
    return Memory(path=str(tmp_path / "h.db"), embedder=DeterministicEmbedder(dim=16))


def test_history_returns_last_n_oldest_first(tmp_path):
    m = _mem(tmp_path)
    for i in range(5):
        m.add(f"turn {i}", type=MemoryType.SESSION, scope=Scope(user="a"))
    hist = m.history(scope=Scope(user="a"), limit=3)
    assert [r.content for r in hist] == ["turn 2", "turn 3", "turn 4"]
    m.close()


def test_history_does_not_full_scan(tmp_path, monkeypatch):
    m = _mem(tmp_path)
    for i in range(3):
        m.add(f"turn {i}", type=MemoryType.SESSION, scope=Scope(user="a"))
    calls = {"all": 0}
    real_all = m._backend.all
    monkeypatch.setattr(
        m._backend, "all",
        lambda: (calls.__setitem__("all", calls["all"] + 1), real_all())[1],
    )
    m.history(scope=Scope(user="a"), limit=2)
    assert calls["all"] == 0  # used the indexed query path, not all()
    m.close()


def test_history_scoped_and_excludes_other_users(tmp_path):
    m = _mem(tmp_path)
    m.add("alice turn", type=MemoryType.SESSION, scope=Scope(user="alice"))
    m.add("bob turn", type=MemoryType.SESSION, scope=Scope(user="bob"))
    hist = m.history(scope=Scope(user="alice"))
    assert [r.content for r in hist] == ["alice turn"]
    m.close()
