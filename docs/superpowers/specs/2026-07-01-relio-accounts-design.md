# `relio.accounts` — User store, password login, Google OAuth

**Date:** 2026-07-01
**Status:** Approved for implementation

## Problem

Relio's `AuthHook` only *verifies* identity (request → scope). It ships no user
store, password login, or OAuth. The auth design doc says these "arrive as custom
`AuthHook`s an app supplies." This adds that layer as an optional module.

## Design

The login flow **issues a JWT**, which the existing `JWTAuth` hook verifies →
principal scope. So `accounts` produces tokens; `JWTAuth` consumes them. No new
verification path.

`relio/accounts/`:
- **`passwords.py`** — `hash_password` / `verify_password` using stdlib
  `pbkdf2_hmac` (no new crypto dep); constant-time compare.
- **`store.py`** — `User` + `UserStore` protocol; `InMemoryUserStore` and
  `SqliteUserStore` (own `users` table); `create` (unique email), `get_by_email`,
  `get_by_id`.
- **`tokens.py`** — `issue_token(user, secret, ttl)` → a JWT (`sub`=user id,
  `email`, `tenant`, `exp`), verifiable by `JWTAuth(secret)`.
- **`google.py`** — `GoogleOAuth(client_id, secret, redirect_uri)`:
  `authorize_url(state)` and `exchange_code(code) -> userinfo`. The HTTP exchange
  is injectable (`fetch=`) so it's testable without hitting Google.
- **`routes.py`** — `build_accounts_router(store, secret, google=None)`:
  `POST /auth/register`, `POST /auth/login` (→ `{token, user_id}`), and — when
  `google` is set — `GET /auth/google` (redirect) + `GET /auth/google/callback`
  (find-or-create user → token).

### Packaging
`accounts = ["relio[server,jwt]", "httpx>=0.27"]` — fastapi + pyjwt + httpx.
Not imported by top-level `relio` (opt-in: `from relio.accounts import ...`).

## Out of scope (YAGNI)

- Email verification, password reset, refresh tokens, rate-limited login (use the
  server's `rate_limit`).
- Other OAuth providers (Google only; the pattern generalizes).

## Tests

- `hash`/`verify` round-trip; wrong password / malformed hash → False.
- store: create + get; duplicate email → `ValueError`; SQLite persists.
- `issue_token` → `JWTAuth` verifies → scope has the user id (+ tenant).
- routes: register → token; login (right → token, wrong → 401); the token
  authenticates a `JWTAuth`-protected endpoint.
- Google: `authorize_url` has the params; callback (injected exchange) creates a
  user + token, and reuses an existing user.
