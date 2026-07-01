# tests/test_accounts_polish.py
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from relio.accounts import (
    GitHubOAuth,
    InMemoryUserStore,
    build_accounts_router,
)
from relio.record import Scope
from relio.server.auth import JWTAuth

SECRET = "a-long-test-secret-at-least-32-bytes-long!!"


def _client(store, **kwargs):
    app = FastAPI()
    app.include_router(build_accounts_router(store, SECRET, **kwargs))
    auth = JWTAuth(SECRET)

    @app.get("/whoami")
    def whoami(request: Request):
        return {"user": auth(request).user}

    return TestClient(app)


def _oauth_start(client, name):
    from urllib.parse import parse_qs, urlparse

    r = client.get(f"/auth/{name}", follow_redirects=False)
    loc = r.headers["location"]
    state = parse_qs(urlparse(loc).query)["state"][0]
    return loc, state


def test_auth_me_returns_the_current_user_with_profile():
    store = InMemoryUserStore()
    client = _client(store)
    reg = client.post(
        "/auth/register",
        json={"email": "a@b.com", "password": "pw12345678", "name": "Al", "profile": {"role": "buyer"}},
    ).json()
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {reg['token']}"})
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "a@b.com" and body["name"] == "Al"
    assert body["profile"] == {"role": "buyer"}
    # no token -> 401
    assert client.get("/auth/me").status_code == 401


def test_register_stores_name_and_profile():
    store = InMemoryUserStore()
    client = _client(store)
    client.post(
        "/auth/register",
        json={"email": "x@y.com", "password": "pw12345678", "name": "Ex", "profile": {"intake": {"q1": "yes"}}},
    )
    user = store.get_by_email("x@y.com")
    assert user.name == "Ex"
    assert user.profile == {"intake": {"q1": "yes"}}


def test_oauth_frontend_redirect_carries_token():
    store = InMemoryUserStore()
    github = GitHubOAuth("cid", "sec", "https://app/cb", fetch=lambda c: {"email": "g@h.com"})
    client = _client(store, github=github, frontend_url="https://app.example.com/auth")
    _, state = _oauth_start(client, "github")
    cb = client.get("/auth/github/callback", params={"code": "abc", "state": state}, follow_redirects=False)
    assert cb.status_code in (302, 307)
    assert cb.headers["location"].startswith("https://app.example.com/auth#token=")


def test_refresh_issues_a_new_access_token():
    store = InMemoryUserStore()
    client = _client(store)
    reg = client.post("/auth/register", json={"email": "a@b.com", "password": "pw12345678"}).json()
    assert "refresh" in reg

    refreshed = client.post("/auth/refresh", json={"refresh": reg["refresh"]})
    assert refreshed.status_code == 200
    token = refreshed.json()["token"]
    assert client.get("/whoami", headers={"Authorization": f"Bearer {token}"}).json()["user"].startswith("usr_")
    # an access token is not a valid refresh token
    assert client.post("/auth/refresh", json={"refresh": reg["token"]}).status_code == 401


def test_password_reset_flow():
    store = InMemoryUserStore()
    client = _client(store)
    client.post("/auth/register", json={"email": "a@b.com", "password": "oldpw12345"})

    req = client.post("/auth/reset-request", json={"email": "a@b.com"}).json()
    reset_token = req["reset_token"]
    ok = client.post("/auth/reset", json={"token": reset_token, "password": "newpw67890"})
    assert ok.status_code == 200

    assert client.post("/auth/login", json={"email": "a@b.com", "password": "oldpw12345"}).status_code == 401
    assert client.post("/auth/login", json={"email": "a@b.com", "password": "newpw67890"}).status_code == 200


def test_reset_request_hides_unknown_email():
    client = _client(InMemoryUserStore())
    r = client.post("/auth/reset-request", json={"email": "nobody@x.com"})
    assert r.status_code == 200 and "reset_token" not in r.json()


def test_login_rate_limit():
    client = _client(InMemoryUserStore(), login_rate_limit=(1, 60))
    client.post("/auth/login", json={"email": "a@b.com", "password": "x"})   # 401 (counts)
    assert client.post("/auth/login", json={"email": "a@b.com", "password": "x"}).status_code == 429


def test_microsoft_oauth_normalizes_userprincipalname():
    from relio.accounts import MicrosoftOAuth

    store = InMemoryUserStore()
    ms = MicrosoftOAuth(
        "cid", "sec", "https://app/cb",
        fetch=lambda c: {"userPrincipalName": "m@x.com", "displayName": "M"},
    )
    client = _client(store, microsoft=ms)
    loc, state = _oauth_start(client, "microsoft")
    assert "login.microsoftonline.com" in loc
    cb = client.get("/auth/microsoft/callback", params={"code": "abc", "state": state})
    assert cb.status_code == 200
    assert store.get_by_email("m@x.com") is not None   # normalized from userPrincipalName


def test_github_oauth_creates_user():
    store = InMemoryUserStore()
    github = GitHubOAuth("cid", "sec", "https://app/cb", fetch=lambda c: {"email": "g@h.com", "name": "G"})
    client = _client(store, github=github)
    loc, state = _oauth_start(client, "github")
    assert "github.com" in loc
    cb = client.get("/auth/github/callback", params={"code": "abc", "state": state})
    assert cb.status_code == 200 and "token" in cb.json()
    assert store.get_by_email("g@h.com") is not None


def test_oauth_callback_rejects_missing_state():
    store = InMemoryUserStore()
    github = GitHubOAuth("cid", "sec", "https://app/cb", fetch=lambda c: {"email": "g@h.com"})
    client = _client(store, github=github)
    client.get("/auth/github", follow_redirects=False)  # sets the state cookie
    # callback with no state param -> CSRF check fails
    assert client.get("/auth/github/callback", params={"code": "abc"}).status_code == 400
