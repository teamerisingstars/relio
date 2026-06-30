# tests/test_ai_seam.py
import pytest

import relio
from relio import RelioAI
from relio.embedding.base import DeterministicEmbedder
from relio.memory import Memory
from relio.record import MemoryType, Scope
from relio.server.llm.fake import FakeProvider


def _ai(tmp_path, provider=None):
    memory = Memory(path=str(tmp_path / "ai.db"), embedder=DeterministicEmbedder(dim=16))
    return RelioAI(memory=memory, provider=provider)


def test_exported_from_package():
    assert hasattr(relio, "RelioAI")


def test_remember_and_recall_roundtrip(tmp_path):
    ai = _ai(tmp_path)
    ai.remember("Alice works at Acme")
    assert any("Acme" in r.content for r in ai.recall("where does Alice work?"))
    ai.close()


def test_embed_single_and_batch(tmp_path):
    ai = _ai(tmp_path)
    single = ai.embed("hello")
    assert len(single) == 16
    batch = ai.embed(["a", "b"])
    assert len(batch) == 2 and len(batch[0]) == 16
    ai.close()


def test_graph_through_the_seam(tmp_path):
    ai = _ai(tmp_path)
    alice = ai.add_node("Alice")
    acme = ai.add_node("Acme")
    ai.add_edge(alice.id, "works_at", acme.id)
    assert [n.content for n in ai.neighbors(alice.id)] == ["Acme"]
    ai.close()


def test_structured_query_through_the_seam(tmp_path):
    ai = _ai(tmp_path)
    ai.remember("a fact", type=MemoryType.FACT)
    ai.remember("a note", type=MemoryType.SEMANTIC)
    assert [r.content for r in ai.query(type=MemoryType.FACT)] == ["a fact"]
    ai.close()


def test_chat_requires_a_provider(tmp_path):
    ai = _ai(tmp_path)  # no provider
    assert ai.has_llm is False
    with pytest.raises(RuntimeError):
        list(ai.chat("hi"))
    ai.close()


def test_chat_streams_with_a_provider(tmp_path):
    ai = _ai(tmp_path, provider=FakeProvider())
    assert ai.has_llm is True
    reply = "".join(ai.chat("I like hiking", scope=Scope(user="alice")))
    assert "I like hiking" in reply
    ai.close()


def test_mcp_server_tools_operate_on_this_memory(tmp_path):
    pytest.importorskip("mcp")
    ai = _ai(tmp_path)
    _server, tools = ai.mcp_server()
    rid = tools["add"]("Bob likes chess")
    assert rid.startswith("mem_")
    assert "chess" in tools["recall"]("chess")
    ai.close()
