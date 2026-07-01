# tests/test_security.py
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from relio import RelioAI
from relio.embedding.base import DeterministicEmbedder
from relio.memory import Memory
from relio.record import Scope
from relio.server.app import create_app
from relio.server.auth import ApiKeyAuth, hash_key
from relio.server.llm.base import LLMProvider, Message
from relio.server.security import RateLimiter


class _Req:
    def __init__(self, headers):
        self.headers = headers


def _mem(tmp_path):
    return Memory(path=str(tmp_path / "s.db"), embedder=DeterministicEmbedder(dim=16))


# --- rate limiting ----------------------------------------------------------

def test_rate_limiter_allows_then_blocks_then_resets():
    rl = RateLimiter(2, 60)
    assert rl.allow("k", 0.0) is True
    assert rl.allow("k", 0.0) is True
    assert rl.allow("k", 0.0) is False   # 3rd in the window
    assert rl.allow("k", 61.0) is True   # new window


def test_rate_limit_middleware_returns_429(tmp_path):
    m = _mem(tmp_path)
    client = TestClient(create_app(m, rate_limit=(1, 60)))
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/health").status_code == 429
    m.close()


def test_request_size_limit_returns_413(tmp_path):
    m = _mem(tmp_path)
    client = TestClient(create_app(m, max_body_bytes=10))
    assert client.post("/api/memory", json={"content": "x" * 100}).status_code == 413
    m.close()


def test_cors_header_present(tmp_path):
    m = _mem(tmp_path)
    client = TestClient(create_app(m, cors_origins=["https://example.com"]))
    r = client.get("/api/health", headers={"Origin": "https://example.com"})
    assert r.headers.get("access-control-allow-origin") == "https://example.com"
    m.close()


# --- error sanitization -----------------------------------------------------

class RaisingProvider(LLMProvider):
    def stream(self, messages: list[Message], system: str):
        raise RuntimeError("SENSITIVE_DB_PASSWORD")
        yield ""  # unreachable; makes this a generator


def test_chat_errors_are_sanitized(tmp_path):
    m = _mem(tmp_path)
    client = TestClient(create_app(m, RaisingProvider()))
    r = client.post("/api/chat", json={"message": "hi"})
    assert "SENSITIVE_DB_PASSWORD" not in r.text     # no internal leak
    assert '"error": "internal error"' in r.text
    m.close()


# --- auth hardening ---------------------------------------------------------

def test_hashed_api_keys_resolve():
    auth = ApiKeyAuth({hash_key("sk-alice"): {"tenant": "acme", "user": "alice"}}, hashed=True)
    assert auth(_Req({"authorization": "Bearer sk-alice"})) == Scope(tenant="acme", user="alice")


def test_expired_api_key_is_rejected():
    auth = ApiKeyAuth({"sk-x": {"user": "x", "expires_at": 100}}, now=lambda: 200)
    with pytest.raises(HTTPException) as exc:
        auth(_Req({"x-api-key": "sk-x"}))
    assert exc.value.status_code == 401


def test_unexpired_api_key_ok():
    auth = ApiKeyAuth({"sk-x": {"user": "x", "expires_at": 300}}, now=lambda: 200)
    assert auth(_Req({"x-api-key": "sk-x"})).user == "x"


# --- destructive tool guard -------------------------------------------------

def test_destructive_tool_requires_confirmation(tmp_path):
    ai = RelioAI(memory=_mem(tmp_path))

    @ai.tool(destructive=True)
    def delete_account(id: str) -> bool:
        return True

    with pytest.raises(PermissionError):
        ai.call_tool("delete_account", id="a1")           # blocked
    assert ai.call_tool("delete_account", id="a1", confirm=True) is True
    assert ai.list_tools()[0]["destructive"] is True
    ai.close()


# --- JWT auth hook ----------------------------------------------------------

def test_jwt_missing_token_is_401():
    from relio.server.auth import JWTAuth

    with pytest.raises(HTTPException) as exc:
        JWTAuth("secret")(_Req({}))
    assert exc.value.status_code == 401


def test_jwt_valid_token_maps_claims_to_scope():
    jwt = pytest.importorskip("jwt")
    from relio.server.auth import JWTAuth

    token = jwt.encode({"sub": "alice", "tenant": "acme"}, "secret", algorithm="HS256")
    scope = JWTAuth("secret")(_Req({"authorization": f"Bearer {token}"}))
    assert scope == Scope(tenant="acme", user="alice")


def test_jwt_bad_signature_is_401():
    jwt = pytest.importorskip("jwt")
    from relio.server.auth import JWTAuth

    token = jwt.encode({"sub": "x"}, "secret", algorithm="HS256")
    with pytest.raises(HTTPException) as exc:
        JWTAuth("WRONG-secret")(_Req({"authorization": f"Bearer {token}"}))
    assert exc.value.status_code == 401


def test_jwt_expired_token_is_401():
    jwt = pytest.importorskip("jwt")
    from relio.server.auth import JWTAuth

    token = jwt.encode({"sub": "x", "exp": 100}, "secret", algorithm="HS256")  # 1970
    with pytest.raises(HTTPException) as exc:
        JWTAuth("secret")(_Req({"authorization": f"Bearer {token}"}))
    assert exc.value.status_code == 401
