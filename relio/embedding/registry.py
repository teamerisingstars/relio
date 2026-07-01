# relio/embedding/registry.py
from __future__ import annotations

import os
from typing import Optional

from .base import DeterministicEmbedder, Embedder

# Offline, no-download embedders (deterministic hashing) vs. the real local model
# (fastembed, ~130MB on first use). Selectable so CI / air-gapped / test runs
# don't pay the download.
_OFFLINE = {"deterministic", "fake", "hash", "offline"}
_LOCAL = {"", "local", "fastembed", "default"}


def make_embedder(name: Optional[str] = None) -> Embedder:
    """Build an embedder by name, or from `RELIO_EMBEDDER` when `name` is None.

    - "local" / "fastembed" (default): the real local model (downloads ~130MB once).
    - "deterministic" / "fake" / "offline": zero-dependency hashing embedder — no
      download, reproducible; ideal for tests, CI, and air-gapped runs.
    """
    key = (name or os.environ.get("RELIO_EMBEDDER") or "local").strip().lower()
    if key in _OFFLINE:
        return DeterministicEmbedder()
    if key in _LOCAL:
        from .local import LocalEmbedder

        return LocalEmbedder()
    raise ValueError(
        f"unknown embedder: {name!r} (use 'local' or 'deterministic'; "
        f"or set RELIO_EMBEDDER)"
    )
