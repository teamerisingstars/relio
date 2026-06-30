# tests/test_embedding.py
from relio.embedding.base import Embedder, DeterministicEmbedder


def test_deterministic_embedder_is_stable_and_right_dim():
    emb = DeterministicEmbedder(dim=8)
    a = emb.embed("hello")
    b = emb.embed("hello")
    c = emb.embed("world")
    assert emb.dim == 8
    assert len(a) == 8
    assert a == b           # same text -> same vector
    assert a != c           # different text -> different vector


def test_deterministic_embedder_is_an_embedder():
    assert isinstance(DeterministicEmbedder(dim=4), Embedder)


# tests/test_embedding.py  (append)
from relio.embedding.cache import CachingEmbedder


class CountingEmbedder(DeterministicEmbedder):
    def __init__(self, dim=4):
        super().__init__(dim)
        self.calls = 0

    def embed(self, text):
        self.calls += 1
        return super().embed(text)


def test_caching_embedder_only_embeds_unique_text_once():
    inner = CountingEmbedder(dim=4)
    cached = CachingEmbedder(inner)
    v1 = cached.embed("same")
    v2 = cached.embed("same")
    cached.embed("other")
    assert v1 == v2
    assert inner.calls == 2          # "same" embedded once, "other" once
    assert cached.dim == 4


# tests/test_embedding.py  (append)
import pytest


@pytest.mark.integration
def test_local_embedder_returns_expected_dim():
    pytest.importorskip("fastembed")
    from relio.embedding.local import LocalEmbedder

    emb = LocalEmbedder()           # default BAAI/bge-small-en-v1.5
    v = emb.embed("hello world")
    assert emb.dim == 384
    assert len(v) == 384
    assert all(isinstance(x, float) for x in v)
