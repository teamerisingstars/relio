# relio/embedding/local.py
from __future__ import annotations

from .base import Embedder

_DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"
_MODEL_DIMS = {"BAAI/bge-small-en-v1.5": 384}


class LocalEmbedder(Embedder):
    """Local, zero-API-cost embedder using fastembed (ONNX)."""

    def __init__(self, model_name: str = _DEFAULT_MODEL) -> None:
        from fastembed import TextEmbedding

        self._model_name = model_name
        self._model = TextEmbedding(model_name=model_name)
        self._dim = _MODEL_DIMS.get(model_name, 384)

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, text: str) -> list[float]:
        # fastembed yields numpy arrays; take the first and convert to list.
        vec = next(iter(self._model.embed([text])))
        return [float(x) for x in vec]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        # fastembed embeds a whole list in one ONNX pass, in order.
        return [[float(x) for x in vec] for vec in self._model.embed(list(texts))]
