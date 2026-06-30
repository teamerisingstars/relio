# tests/test_agents.py
from typing import Iterator

import pytest

from relio import RelioAI
from relio.embedding.base import DeterministicEmbedder
from relio.memory import Memory
from relio.server.llm.base import LLMProvider, Message
from relio.server.llm.fake import FakeProvider


def _ai(tmp_path, provider=None):
    m = Memory(path=str(tmp_path / "ag.db"), embedder=DeterministicEmbedder(dim=16))
    return RelioAI(memory=m, provider=provider)


def test_agent_has_its_own_namespace(tmp_path):
    ai = _ai(tmp_path)
    billing = ai.agent("billing")
    assert billing.space.agent == "billing"
    ai.close()


def test_agents_memory_is_isolated(tmp_path):
    ai = _ai(tmp_path)
    billing = ai.agent("billing")
    support = ai.agent("support")
    billing.remember("invoice 42 is overdue")
    assert any("invoice 42" in r.content for r in billing.recall("overdue invoice"))
    assert support.recall("overdue invoice") == []  # cannot see billing's memory
    ai.close()


def test_tool_slice_is_enforced(tmp_path):
    ai = _ai(tmp_path)

    @ai.tool
    def price(part: str) -> float:
        return 1.0

    @ai.tool
    def refund(order: str) -> bool:
        return True

    billing = ai.agent("billing", tools=["price"])
    assert billing.tools() == ["price"]
    assert billing.call_tool("price", part="x") == 1.0
    with pytest.raises(PermissionError):
        billing.call_tool("refund", order="o1")

    unrestricted = ai.agent("admin")  # tools=None -> all
    assert set(unrestricted.tools()) == {"price", "refund"}
    ai.close()


class RecordingProvider(LLMProvider):
    def __init__(self) -> None:
        self.system = None

    def stream(self, messages: list[Message], system: str) -> Iterator[str]:
        self.system = system
        yield "ok"


def test_agent_chat_uses_its_system_prompt_and_namespace(tmp_path):
    rec = RecordingProvider()
    ai = _ai(tmp_path, provider=rec)
    billing = ai.agent("billing", system="You are the billing agent.")
    list(billing.chat("hello"))
    assert rec.system.startswith("You are the billing agent.")
    # turn persisted in billing's namespace
    assert [t.content for t in billing.history()][:1] == ["hello"]
    ai.close()


def test_agent_chat_streams_with_fake_provider(tmp_path):
    ai = _ai(tmp_path, provider=FakeProvider())
    billing = ai.agent("billing")
    assert "hi there" in "".join(billing.chat("hi there"))
    ai.close()
