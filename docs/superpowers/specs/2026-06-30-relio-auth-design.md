# Feature D — Auth / Multi-tenancy (secure by default)

**Date:** 2026-06-30
**Status:** Approved for implementation
**Part of:** Relio missing-features build-out (Feature D of A–G)

## Problem

`make_scope()` builds the engine scope from `tenant`/`user` in the **request
body** — any client can claim any tenant. The architecture (§10.2) requires
identity to come from an authenticated principal, with a pluggable auth hook and
a minimal built-in.

## Decision: secure by default

The principal (`tenant`/`user`/`agent`) is resolved **only** by an auth hook;
client-supplied identity is never trusted. `session` is not a security boundary
and still comes from the request. With no auth configured, requests resolve to
an **anonymous** scope (all-None) — so body-claimed identity is ignored even in
the default. This rewrites the existing client-asserted tests.

## Design

### `relio/server/auth.py`
- `AuthHook = Callable[[Request], Scope]` — returns the principal scope.
- `anonymous_auth(request) -> Scope()` — the default; no identity.
- `ApiKeyAuth(keys)` — `keys: {api_key: {"tenant", "user", "agent"}}`. Reads
  `Authorization: Bearer <key>` or `X-API-Key`; unknown/missing → `HTTP 401`.
  Builds the principal via `make_scope`.

### Wiring
- `create_app(..., auth: AuthHook = anonymous_auth)` passes the hook to the
  memory and chat routers.
- Each router defines a `principal` FastAPI dependency (`auth(request)`).
- **Memory:** `add` stores under `principal + session`; `search` filters by
  `principal`; `get`/`delete` enforce ownership (`scope_matches(principal,
  record.scope)`, else 404).
- **Chat / history:** scope = `principal + session` from the body/params.

### Schemas
`AddRequest` and `ChatRequest` drop `tenant`/`user`/`agent` (identity is not a
client field); they keep `session`, `content`/`message`, etc.

## Out of scope (YAGNI)

- Graph routes stay id-based (no per-node ownership check yet) — documented
  follow-up.
- Sessions/JWT/OAuth — those arrive as custom `AuthHook`s an app supplies; only
  the API-key built-in ships now.
- DB-per-tenant isolation (the other §10.2 model) — separate later feature.

## Tests

- `ApiKeyAuth`: valid key → principal scope; missing/invalid → 401.
- With `ApiKeyAuth`, tenant A cannot read tenant B's memory (write as A, search
  as B → empty); A reads its own.
- `get`/`delete` by id across principals → 404.
- Default (anonymous) app: existing behavior; no isolation by body identity.
- Rewritten: `test_search_is_scoped_by_user` (now via auth), the two schema
  default tests.
