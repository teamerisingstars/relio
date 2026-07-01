# tests/test_aiapp.py
import json

from fastapi.testclient import TestClient

from relio import AIApp, RelioAI
from relio.embedding.base import DeterministicEmbedder
from relio.memory import Memory
from relio.server.llm.fake import FakeProvider


def _aiapp(tmp_path):
    m = Memory(path=str(tmp_path / "aiapp.db"), embedder=DeterministicEmbedder(dim=16))
    return AIApp(ai=RelioAI(memory=m, provider=FakeProvider()))


def _deltas(sse_text: str) -> str:
    out = []
    for line in sse_text.splitlines():
        if line.startswith("data: "):
            payload = json.loads(line[len("data: "):])
            if "delta" in payload:
                out.append(payload["delta"])
    return "".join(out)


def test_aiapp_registers_agents(tmp_path):
    app = _aiapp(tmp_path)
    app.agent("billing", system="You handle billing.")
    assert "billing" in app.agents
    app.ai.close()


def test_build_serves_base_routes_and_agents(tmp_path):
    app = _aiapp(tmp_path)
    app.agent("assistant", system="You are helpful.")
    client = TestClient(app.build())

    assert client.get("/api/health").json() == {"status": "ok"}          # base route
    assert client.post("/api/memory", json={"content": "hi"}).status_code == 201

    listing = client.get("/api/agents").json()["agents"]
    assert any(a["name"] == "assistant" for a in listing)

    resp = client.post("/api/agents/assistant/chat", json={"message": "hi there"})
    assert resp.status_code == 200
    assert "hi there" in _deltas(resp.text)
    app.ai.close()


def test_unknown_agent_returns_404(tmp_path):
    app = _aiapp(tmp_path)
    client = TestClient(app.build())
    assert client.post("/api/agents/nope/chat", json={"message": "x"}).status_code == 404
    app.ai.close()


def test_agents_are_isolated_through_the_app(tmp_path):
    app = _aiapp(tmp_path)
    billing = app.agent("billing")
    support = app.agent("support")
    billing.remember("invoice 42 overdue")
    assert any("invoice 42" in r.content for r in billing.recall("overdue"))
    assert support.recall("overdue") == []
    app.ai.close()
