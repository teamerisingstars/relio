# Accounts (auth batteries)

The optional `relio[accounts]` extra adds a ready account system layered on the
server's auth seam. Modules under `relio/accounts/`:

- **store** — the `User` model and `UserStore` protocol (bring your own backing
  store; an in-memory one ships for dev/tests).
- **passwords** — PBKDF2-HMAC-SHA256 hashing/verification (constant-time compare).
- **tokens** — issue and read JWTs: short-lived access tokens, longer refresh
  tokens (each with a unique `jti` for rotation), and password-reset tokens. These
  verify against `relio.server.auth.JWTAuth(secret)`.
- **revocation** — a `RevocationStore` (with an in-memory implementation) that
  tracks revoked refresh-token `jti`s, so logout and refresh-rotation can
  invalidate a token before it expires.
- **routes** — the FastAPI router (register / login / refresh / logout /
  reset-request / reset / OAuth callbacks).
- **google / github / microsoft** — OAuth provider adapters (authorization-code
  exchange against fixed provider endpoints).

## Token lifecycle

`issue_tokens()` returns an access + refresh pair. On refresh, the old refresh
token's `jti` is added to the **revocation** store and a new pair is issued
(rotation); logout revokes the current `jti`. Reset tokens are type-tagged so a
reset token can't be used as a refresh token.

See also [multi-tenancy](multi-tenancy.md) for how account `tenant` maps to the
memory scope, and [open-core-seams](open-core-seams.md) for the auth seam.
