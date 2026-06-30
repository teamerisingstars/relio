import pytest
from fastapi.testclient import TestClient

from relio.embedding.base import DeterministicEmbedder
from relio.memory import Memory
from relio.server.app import create_app


@pytest.fixture
def no_llm_client(tmp_path):
    m = Memory(path=str(tmp_path / "n.db"), embedder=DeterministicEmbedder(dim=16))
    app = create_app(m)  # no provider — a pure memory/data backend
    with TestClient(app) as c:
        yield c
    m.close()


def test_memory_crud_works_without_a_provider(no_llm_client):
    add = no_llm_client.post("/api/memory", json={"content": "Alice likes tea"})
    assert add.status_code == 201
    found = no_llm_client.get("/api/memory/search", params={"q": "Alice likes tea"})
    assert any("tea" in r["content"] for r in found.json()["results"])


def test_history_and_graph_work_without_a_provider(no_llm_client):
    assert no_llm_client.get("/api/history").status_code == 200
    nb = no_llm_client.get("/api/graph/neighbors", params={"id": "missing"})
    assert nb.status_code == 200 and nb.json()["neighbors"] == []


def test_chat_is_absent_without_a_provider(no_llm_client):
    assert no_llm_client.post("/api/chat", json={"message": "hi"}).status_code == 404


def test_health_ok_without_a_provider(no_llm_client):
    assert no_llm_client.get("/api/health").json() == {"status": "ok"}
