from relio.server.schemas import AddRequest, ChatRequest
from relio.record import MemoryType


def test_add_request_defaults():
    req = AddRequest(content="hello")
    assert req.content == "hello"
    assert req.type is MemoryType.SEMANTIC
    assert req.session is None
    assert req.data == {}
    # Identity is not a client field — resolved from the authenticated principal.
    assert not hasattr(req, "user")


def test_chat_request_carries_message_and_session():
    req = ChatRequest(message="hi", session="s1")
    assert req.message == "hi"
    assert req.session == "s1"
    assert not hasattr(req, "user")


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


# NOTE: tenant/user isolation is now enforced via the auth principal, not via
# client-supplied fields. See tests/server/test_auth.py.
