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


def test_embed_batch_matches_individual_embeds():
    emb = DeterministicEmbedder(dim=8)
    texts = ["a", "b", "c"]
    assert emb.embed_batch(texts) == [emb.embed(t) for t in texts]


def test_caching_embed_batch_dedups_and_caches():
    inner = CountingEmbedder(dim=4)
    cached = CachingEmbedder(inner)
    out = cached.embed_batch(["x", "x", "y"])
    assert out[0] == out[1]          # duplicate resolves to same vector
    assert inner.calls == 2          # only unique x, y embedded
    cached.embed_batch(["x", "y"])   # fully cached now
    assert inner.calls == 2          # no new inner work


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
