# Multi-tenancy & the exposure map

Relio is multi-tenant by design: every record carries a `Scope`
(`tenant`/`user`/`agent`/`session`), and access flows through two layers you
control — the **auth hook** (who is calling) and the **exposure map** (what the
AI may do on their behalf).

## 1. Identify the caller — the auth hook

`create_app(auth=...)` installs an `AuthHook: Callable[[Request], Scope]` that
turns each request into a `Scope`. Built-ins: `anonymous_auth`, `ApiKeyAuth`,
`JWTAuth`, and the full `relio.accounts` router.

```python
from relio.server.app import create_app
from relio.server.auth import ApiKeyAuth

app = create_app(memory, provider, auth=ApiKeyAuth({
    "sk-alice": {"tenant": "acme",   "user": "alice"},
    "sk-bob":   {"tenant": "globex", "user": "bob"},
}))
```

The hook's `Scope` is threaded through memory/query/graph, so tenants are
isolated automatically — Bob's search never returns Acme's records.

!!! warning "extra_routers are protected too"
    Your own routers passed via `extra_routers=[...]` get the **same** `auth`
    dependency by default — an unauthenticated request to a custom endpoint is
    `401`, not wide open. For a **public** router (e.g. login/register), mark it
    with a tuple so the rest stay protected:

    ```python
    create_app(..., auth=JWTAuth(secret), extra_routers=[
        (accounts_router, False),   # public: register/login must work with no token
        my_app_router,              # protected by the default
    ])
    ```

    `protect_extra_routers=False` opts the whole set out.

## 2. Govern what the AI can do — the exposure map

Your app DB is private. The AI can call only what you register (`@ai.tool`) and
see only the fields you allow (`ai.expose`). Destructive tools require an
explicit `confirm=True`.

```python
@ai.tool
def lookup_account(name: str) -> dict:
    row = db.get_account(name)
    return ai.expose(row, fields=["name", "owner", "status"])   # cost/PII stay invisible

@ai.tool(destructive=True)
def pause_campaign(campaign_id: str) -> dict:
    return db.pause(campaign_id)     # never auto-run by an agent; needs confirm=True
```

## 3. Per-request scope injection — one tool, every tenant

A tool that declares a **`scope` parameter** gets the caller's `Scope` injected
per-call. It is **hidden from the LLM-facing schema** — the model never sees or
controls it — so a single registered tool serves every tenant instead of being
closure-bound to one principal.

```python
from relio.record import Scope

@ai.tool
def list_campaigns(status: str, scope: Scope = None) -> list:
    """List campaigns for the current tenant."""
    return db.campaigns(tenant=scope.tenant, status=status)

# The LLM sees only `status`; you inject the principal at call time:
ai.call_tool("list_campaigns", scope=request_scope, status="active")
```

Wire it to the request: resolve the `Scope` from the auth hook, then pass it into
`call_tool` (or let an **agent** do it — an agent injects its own `space`
automatically):

```python
reporter = ai.agent("reporter", tools=["list_campaigns"])
reporter.call_tool("list_campaigns", status="active")   # scope == reporter's space
reporter.run("Which active campaigns underperformed?")  # autonomous, still scoped
```

## Recommended pattern (today)

1. `create_app(auth=ApiKeyAuth(...) | JWTAuth(...) | relio.accounts)` — identity → `Scope`.
2. Register scope-aware tools (`def tool(..., scope: Scope = None)`) — no per-tenant closures.
3. In each request handler, resolve the `Scope` from the hook and pass it to
   `ai.call_tool(name, scope=..., ...)`; for autonomous flows, use a per-request
   `ai.agent(...)` whose space is the tenant.
4. Keep `protect_extra_routers=True` (the default) so custom endpoints inherit auth.
