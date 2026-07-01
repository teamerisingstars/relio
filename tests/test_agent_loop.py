# tests/test_agent_loop.py
from relio import RelioAI
from relio.embedding.base import DeterministicEmbedder
from relio.memory import Memory
from relio.server.llm.fake import FakeProvider


def _ai(tmp_path):
    m = Memory(path=str(tmp_path / "loop.db"), embedder=DeterministicEmbedder(dim=16))
    return RelioAI(memory=m, provider=FakeProvider())


def test_agent_run_autonomously_calls_a_tool(tmp_path):
    ai = _ai(tmp_path)
    calls = []

    @ai.tool
    def get_status() -> str:
        calls.append(True)
        return "in_stock"

    agent = ai.agent("ops", tools=["get_status"])
    result = agent.run("check status")
    assert calls == [True]          # the model autonomously invoked the tool
    assert result == "done"
    ai.close()


def test_agent_run_blocks_destructive_tools(tmp_path):
    ai = _ai(tmp_path)
    ran = []

    @ai.tool(destructive=True)
    def wipe() -> str:
        ran.append(True)
        return "wiped"

    agent = ai.agent("ops", tools=["wipe"])
    agent.run("do it")
    assert ran == []                # destructive tool never auto-executed
    ai.close()


def test_agent_run_requires_provider(tmp_path):
    m = Memory(path=str(tmp_path / "np.db"), embedder=DeterministicEmbedder(dim=16))
    ai = RelioAI(memory=m)  # no provider
    import pytest

    with pytest.raises(RuntimeError):
        ai.agent("x").run("task")
    ai.close()
