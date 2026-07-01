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


def test_run_stream_yields_tool_and_final_events(tmp_path):
    ai = _ai(tmp_path)

    @ai.tool
    def get_status() -> str:
        return "in_stock"

    agent = ai.agent("ops", tools=["get_status"])
    events = list(agent.run_stream("check status"))
    kinds = [e["type"] for e in events]
    assert "tool_call" in kinds and "tool_result" in kinds
    assert kinds[-1] == "final"                       # final is always last
    assert events[-1]["text"] == "done"
    # tool_call carries the name; tool_result carries the output
    tc = next(e for e in events if e["type"] == "tool_call")
    tr = next(e for e in events if e["type"] == "tool_result")
    assert tc["name"] == "get_status" and tr["output"] == "in_stock"
    ai.close()


def test_run_persist_records_turns_for_multi_turn(tmp_path):
    ai = _ai(tmp_path)
    agent = ai.agent("copilot")
    agent.run("first question", persist=True)
    # the task + final answer were written to the agent's own space
    turns = ai.memory.history(agent.space, limit=10)
    roles = [t.metadata.get("role") for t in turns]
    assert "user" in roles and "assistant" in roles
    assert any("first question" in t.content for t in turns)
    ai.close()


def test_agent_run_requires_provider(tmp_path):
    m = Memory(path=str(tmp_path / "np.db"), embedder=DeterministicEmbedder(dim=16))
    ai = RelioAI(memory=m)  # no provider
    import pytest

    with pytest.raises(RuntimeError):
        ai.agent("x").run("task")
    ai.close()
