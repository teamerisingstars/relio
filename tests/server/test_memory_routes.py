from relio.server.schemas import AddRequest, ChatRequest
from relio.record import MemoryType


def test_add_request_defaults():
    req = AddRequest(content="hello")
    assert req.content == "hello"
    assert req.type is MemoryType.SEMANTIC
    assert req.user is None
    assert req.data == {}


def test_chat_request_requires_message():
    req = ChatRequest(message="hi", user="alice")
    assert req.message == "hi"
    assert req.user == "alice"


from relio.server.scope import make_scope
from relio.record import Scope


def test_make_scope_sets_only_provided_fields():
    s = make_scope(user="alice", tenant="acme")
    assert s == Scope(user="alice", tenant="acme")
    assert s.agent is None


def test_add_get_delete_roundtrip(client):
    add = client.post("/api/memory", json={"content": "Alice likes tea", "user": "alice"})
    assert add.status_code == 201
    rec = add.json()
    assert rec["content"] == "Alice likes tea"
    rid = rec["id"]

    got = client.get(f"/api/memory/{rid}")
    assert got.status_code == 200
    assert got.json()["content"] == "Alice likes tea"

    deleted = client.delete(f"/api/memory/{rid}")
    assert deleted.json() == {"deleted": True}
    assert client.get(f"/api/memory/{rid}").status_code == 404


def test_search_returns_results_and_text(client):
    client.post("/api/memory", json={"content": "apple pie recipe", "user": "alice"})
    resp = client.get("/api/memory/search", params={"q": "apple pie recipe", "user": "alice"})
    assert resp.status_code == 200
    body = resp.json()
    assert any("apple pie" in r["content"] for r in body["results"])
    assert body["text"].startswith("- ")


def test_search_is_scoped_by_user(client):
    client.post("/api/memory", json={"content": "secret note", "user": "alice"})
    resp = client.get("/api/memory/search", params={"q": "secret note", "user": "bob"})
    assert resp.json()["results"] == []
