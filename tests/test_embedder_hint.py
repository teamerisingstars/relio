# tests/test_embedder_hint.py — a missing fastembed gives an actionable message.
import sys

import pytest

from relio.embedding.local import LocalEmbedder


def test_local_embedder_without_fastembed_hints_the_fix(monkeypatch):
    # Simulate fastembed not installed (the default `relio[server]` install).
    monkeypatch.setitem(sys.modules, "fastembed", None)
    with pytest.raises(ImportError) as exc:
        LocalEmbedder()
    msg = str(exc.value)
    assert "relio[local]" in msg
    assert "RELIO_EMBEDDER=deterministic" in msg
