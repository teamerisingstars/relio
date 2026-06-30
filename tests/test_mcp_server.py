# tests/test_mcp_server.py
import pytest

from relio.memory import Memory
from relio.embedding.base import DeterministicEmbedder


def test_build_mcp_server_exposes_add_and_recall(tmp_path):
    pytest.importorskip("mcp")
    from relio.mcp_server import build_mcp_server

    m = Memory(path=str(tmp_path / "m.db"), embedder=DeterministicEmbedder(dim=16))
    server, tools = build_mcp_server(m)
    assert set(tools) == {"add", "recall"}

    tools["add"]("Alice likes hiking")
    text = tools["recall"]("hiking")
    assert "hiking" in text
    m.close()
