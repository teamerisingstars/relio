# tests/test_static.py
import pytest
from fastapi.testclient import TestClient

from relio.memory import Memory
from relio.embedding.base import DeterministicEmbedder
from relio.server.app import create_app
from relio.server.llm.fake import FakeProvider


def _client(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html>INDEX")
    (dist / "assets" / "app.js").write_text("APP")
    memory = Memory(path=str(tmp_path / "s.db"), embedder=DeterministicEmbedder(dim=16))
    app = create_app(memory, FakeProvider(), frontend_dir=str(dist))
    return TestClient(app), memory


def test_root_serves_index(tmp_path):
    client, memory = _client(tmp_path)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "INDEX" in resp.text
    memory.close()


def test_api_still_wins_over_spa(tmp_path):
    client, memory = _client(tmp_path)
    assert client.get("/api/health").json() == {"status": "ok"}
    memory.close()


def test_unknown_route_falls_back_to_index(tmp_path):
    client, memory = _client(tmp_path)
    assert "INDEX" in client.get("/dashboard/anything").text
    memory.close()


def test_asset_is_served(tmp_path):
    client, memory = _client(tmp_path)
    assert client.get("/assets/app.js").text == "APP"
    memory.close()


def test_missing_frontend_dir_raises(tmp_path):
    memory = Memory(path=str(tmp_path / "s.db"), embedder=DeterministicEmbedder(dim=16))
    with pytest.raises(FileNotFoundError):
        create_app(memory, FakeProvider(), frontend_dir=str(tmp_path / "nope"))
    memory.close()
