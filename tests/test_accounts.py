# tests/test_accounts.py
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from relio.accounts import (
    GoogleOAuth,
    InMemoryUserStore,
    SqliteUserStore,
    build_accounts_router,
    hash_password,
    issue_token,
    verify_password,
)
from relio.server.auth import JWTAuth

SECRET = "a-long-test-secret-at-least-32-bytes-long!!"


# --- passwords --------------------------------------------------------------

def test_password_hash_roundtrip():
    h = hash_password("hunter2")
    assert h != "hunter2"
    assert verify_password("hunter2", h) is True
    assert verify_password("wrong", h) is False


def test_verify_password_handles_malformed_hash():
    assert verify_password("x", "not-a-valid-hash") is False


# --- store ------------------------------------------------------------------

def test_inmemory_store_create_and_lookup():
    s = InMemoryUserStore()
    u = s.create("a@b.com", password_hash="h", tenant="acme")
    assert s.get_by_email("a@b.com").id == u.id
    assert s.get_by_id(u.id).email == "a@b.com"
    with pytest.raises(ValueError):
        s.create("a@b.com")


def test_sqlite_store_persists(tmp_path):
    s = SqliteUserStore(str(tmp_path / "users.db"))
    u = s.create("x@y.com", password_hash="h")
    assert s.get_by_email("x@y.com").id == u.id


def test_merge_profile_is_atomic_and_recursive(tmp_path):
    for s in (InMemoryUserStore(), SqliteUserStore(str(tmp_path / "u.db"))):
        u = s.create("a@b.com", profile={"intake": {"q1": "a"}, "keep": 1})
        # nested merge (q1 kept, q2 added), top-level add, and null-delete of "keep"
        out = s.merge_profile(u.id, {"intake": {"q2": "b"}, "focus": ["x"], "keep": None})
        assert out == {"intake": {"q1": "a", "q2": "b"}, "focus": ["x"]}
        assert s.get_by_id(u.id).profile == out


# --- token issued here is verified by JWTAuth -------------------------------

def test_issued_token_is_verified_by_jwtauth():
    class _Req:
        def __init__(self, headers):
            self.headers = headers

    s = InMemoryUserStore()
    user = s.create("a@b.com", password_hash="h", tenant="acme")
    token = issue_token(user, SECRET)
    scope = JWTAuth(SECRET)(_Req({"authorization": f"Bearer {token}"}))
    assert scope.user == user.id
    assert scope.tenant == "acme"


# --- routes end-to-end ------------------------------------------------------

def _app(store, google=None):
    app = FastAPI()
    app.include_router(build_accounts_router(store, SECRET, google=google))
    auth = JWTAuth(SECRET)

    @app.get("/me")
    def me(request: Request):
        scope = auth(request)
        return {"user": scope.user, "tenant": scope.tenant}

    return app


def test_register_login_and_authenticated_request():
    client = TestClient(_app(InMemoryUserStore()))
    reg = client.post("/auth/register", json={"email": "a@b.com", "password": "pw12345678"})
    assert reg.status_code == 200
    token = reg.json()["token"]

    assert client.post("/auth/register", json={"email": "a@b.com", "password": "x"}).status_code == 409
    assert client.post("/auth/login", json={"email": "a@b.com", "password": "nope"}).status_code == 401
    ok = client.post("/auth/login", json={"email": "a@b.com", "password": "pw12345678"})
    assert ok.status_code == 200

    me = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["user"].startswith("usr_")


# --- Google OAuth -----------------------------------------------------------

def test_google_authorize_url_has_params():
    g = GoogleOAuth("cid", "sec", "https://app/cb")
    url = g.authorize_url(state="xyz")
    assert "client_id=cid" in url
    assert "scope=" in url and "state=xyz" in url


def test_google_callback_creates_then_reuses_user():
    store = InMemoryUserStore()
    google = GoogleOAuth("cid", "sec", "https://app/cb", fetch=lambda code: {"email": "g@b.com", "name": "G"})
    client = TestClient(_app(store, google=google))

    from urllib.parse import parse_qs, urlparse

    redirect = client.get("/auth/google", follow_redirects=False)
    assert redirect.status_code in (302, 307)
    assert "accounts.google.com" in redirect.headers["location"]
    state = parse_qs(urlparse(redirect.headers["location"]).query)["state"][0]  # CSRF state

    cb = client.get("/auth/google/callback", params={"code": "abc", "state": state})
    assert cb.status_code == 200 and "token" in cb.json()
    assert store.get_by_email("g@b.com") is not None
    first_id = store.get_by_email("g@b.com").id

    r2 = client.get("/auth/google", follow_redirects=False)
    state2 = parse_qs(urlparse(r2.headers["location"]).query)["state"][0]
    cb2 = client.get("/auth/google/callback", params={"code": "def", "state": state2})
    assert cb2.json()["user_id"] == first_id
