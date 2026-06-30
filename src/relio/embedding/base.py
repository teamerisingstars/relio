# src/relio/embedding/base.py
from __future__ import annotations

import hashlib
import math
from abc import ABC, abstractmethod


class Embedder(ABC):
    @property
    @abstractmethod
    def dim(self) -> int:
        ...

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        ...


class DeterministicEmbedder(Embedder):
    """Hash-based embedder for fast, offline, reproducible tests."""

    def __init__(self, dim: int = 384) -> None:
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, text: str) -> list[float]:
        vec: list[float] = []
        counter = 0
        while len(vec) < self._dim:
            h = hashlib.sha256(f"{counter}:{text}".encode()).digest()
            for i in range(0, len(h), 4):
                if len(vec) >= self._dim:
                    break
                n = int.from_bytes(h[i : i + 4], "big")
                vec.append((n / 2**32) * 2 - 1)  # in [-1, 1)
            counter += 1
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]
