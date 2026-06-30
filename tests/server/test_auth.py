import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from relio.embedding.base import DeterministicEmbedder
from relio.memory import Memory
from relio.record import Scope
from relio.server.app import create_app
from relio.server.auth import ApiKeyAuth, anonymous_auth
from relio.server.llm.fake import FakeProvider

KEYS = {
    "sk-alice": {"tenant": "acme", "user": "alice"},
    "sk-bob": {"tenant": "globex", "user": "bob"},
}


class _Req:
    """Minimal stand-in for a Starlette Request (only .headers is used)."""

    def __init__(self, headers):
        self.headers = headers


# --- unit -------------------------------------------------------------------

def test_anonymous_auth_returns_empty_scope():
    assert anonymous_auth(_Req({})) == Scope()


def test_api_key_auth_resolves_principal_from_bearer():
    auth = ApiKeyAuth(KEYS)
    scope = auth(_Req({"authorization": "Bearer sk-alice"}))
    assert scope == Scope(tenant="acme", user="alice")


def test_api_key_auth_resolves_principal_from_x_api_key():
    auth = ApiKeyAuth(KEYS)
    scope = auth(_Req({"x-api-key": "sk-bob"}))
    assert scope == Scope(tenant="globex", user="bob")


def test_api_key_auth_rejects_missing_key():
    with pytest.raises(HTTPException) as exc:
        ApiKeyAuth(KEYS)(_Req({}))
    assert exc.value.status_code == 401


def test_api_key_auth_rejects_invalid_key():
    with pytest.raises(HTTPException) as exc:
        ApiKeyAuth(KEYS)(_Req({"x-api-key": "sk-nope"}))
    assert exc.value.status_code == 401


# --- integration ------------------------------------------------------------

@pytest.fixture
def auth_client(tmp_path):
    memory = Memory(path=str(tmp_path / "auth.db"), embedder=DeterministicEmbedder(dim=16))
    app = create_app(memory, FakeProvider(), auth=ApiKeyAuth(KEYS))
    with TestClient(app) as c:
        yield c
    memory.close()


def _h(key):
    return {"Authorization": f"Bearer {key}"}


def test_request_without_key_is_rejected(auth_client):
    assert auth_client.post("/api/memory", json={"content": "x"}).status_code == 401


def test_tenants_are_isolated(auth_client):
    auth_client.post("/api/memory", json={"content": "secret note"}, headers=_h("sk-alice"))
    # Bob cannot see Alice's memory...
    bob = auth_client.get("/api/memory/search", params={"q": "secret note"}, headers=_h("sk-bob"))
    assert bob.json()["results"] == []
    # ...but Alice can.
    alice = auth_client.get("/api/memory/search", params={"q": "secret note"}, headers=_h("sk-alice"))
    assert any("secret note" in r["content"] for r in alice.json()["results"])


def test_get_by_id_across_tenants_is_404(auth_client):
    created = auth_client.post(
        "/api/memory", json={"content": "alice private"}, headers=_h("sk-alice")
    ).json()
    rid = created["id"]
    assert auth_client.get(f"/api/memory/{rid}", headers=_h("sk-alice")).status_code == 200
    assert auth_client.get(f"/api/memory/{rid}", headers=_h("sk-bob")).status_code == 404
    assert auth_client.delete(f"/api/memory/{rid}", headers=_h("sk-bob")).status_code == 404
