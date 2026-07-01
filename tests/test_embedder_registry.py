# tests/test_embedder_registry.py
import pytest

from relio.embedding.base import DeterministicEmbedder
from relio.embedding.registry import make_embedder


def test_make_embedder_deterministic_is_offline_no_download():
    for name in ("deterministic", "fake", "offline", "DETERMINISTIC"):
        assert isinstance(make_embedder(name), DeterministicEmbedder)


def test_make_embedder_reads_env(monkeypatch):
    monkeypatch.setenv("RELIO_EMBEDDER", "deterministic")
    assert isinstance(make_embedder(), DeterministicEmbedder)


def test_make_embedder_unknown_raises():
    with pytest.raises(ValueError):
        make_embedder("nope")


def test_memory_honors_env_embedder_without_downloading(tmp_path, monkeypatch):
    # A bare Memory() must NOT trigger the ~130MB local-model download when the
    # offline embedder is selected via env.
    monkeypatch.setenv("RELIO_EMBEDDER", "deterministic")
    from relio.memory import Memory

    m = Memory(path=str(tmp_path / "m.db"))
    assert isinstance(m.embedder._inner, DeterministicEmbedder)
    m.add("hello world")
    assert any("hello" in r.content for r in m.recall("hello"))
    m.close()
