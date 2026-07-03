# tests/test_memory_cache.py — the in-process recall cache must stay bounded.
from relio.memory import Memory
from relio.embedding.base import DeterministicEmbedder


def test_recall_cache_is_bounded(tmp_path):
    m = Memory(path=str(tmp_path / "m.db"), embedder=DeterministicEmbedder(dim=16))
    m.add("a fact")
    # Many distinct queries would otherwise grow the cache without limit.
    for i in range(Memory._RECALL_CACHE_MAX + 50):
        m.recall(f"query number {i}", limit=1)
    assert len(m._recall_cache) <= Memory._RECALL_CACHE_MAX
    m.close()


def test_recall_cache_still_hits_within_bound(tmp_path):
    m = Memory(path=str(tmp_path / "m.db"), embedder=DeterministicEmbedder(dim=16))
    m.add("a fact")
    first = m.recall("same query", limit=1)
    second = m.recall("same query", limit=1)
    assert first is second  # served from cache (identity), not recomputed
    m.close()
