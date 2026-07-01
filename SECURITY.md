# Security Policy

## Supported versions

Relio is pre-1.0; security fixes land on the latest `0.1.x` release. Please stay
current.

## Reporting a vulnerability

**Do not open a public issue for security problems.** Report privately via
GitHub's **[Security Advisories](https://github.com/teamerisingstars/relio/security/advisories/new)**
(Security → Report a vulnerability), or email the maintainers. We aim to
acknowledge within a few days and coordinate a fix and disclosure.

## The security model

Relio is designed to keep the AI boundary tight:

- **Secure-by-default auth** — identity comes from an auth hook, never the
  request body; tenants are isolated by scope; `get`/`delete` enforce ownership.
- **Exposure map** — the AI reaches your data only through declared, field-limited
  operations (`ai.tool` / `ai.expose`). Everything else is invisible to the model.
- **Bounded agents** — each agent is limited to its own memory namespace and tool
  slice.
- **Destructive-tool confirmation** — tools marked `destructive=True` require an
  explicit `confirm=True` to run.
- **Parameterised SQL** and guarded JSON-path interpolation (`^\w+$`).

## Built-in hardening (opt-in)

```python
create_app(
    memory, provider,
    auth=ApiKeyAuth(keys, hashed=True),   # SHA-256 keys, optional per-key expiry
    rate_limit=(60, 60),                  # 60 requests / 60s per client
    max_body_bytes=1_000_000,             # reject oversized bodies (413)
    cors_origins=["https://yourapp.com"], # lock down browsers
)
```

Errors are never leaked to clients (SSE emits `"internal error"`; the real cause
is logged). Validate model output with `ai.extract(..., validate=True)`.

**JWT / OAuth** (bring your own IdP — Auth0, Cognito, Clerk, …) via `pip install
"relio[jwt]"`:

```python
from relio.server.auth import JWTAuth

auth = JWTAuth(secret, audience="my-api", tenant_claim="org")  # verifies sig + exp
app = create_app(memory, provider, auth=auth)
```

Auth is fully pluggable: any `Callable[[Request], Scope]` works as an `AuthHook`.

## AI-specific threats (inherent to LLM apps)

- **Prompt injection** — recalled memory, tool output, and document content flow
  into the prompt and can try to steer an agent. Relio *contains the blast
  radius* via the exposure map (least data) + bounded tool slices (least tools) +
  destructive-tool confirmation. Keep exposure maps minimal; don't grant agents
  destructive tools without confirmation.
- **Memory poisoning** — users can plant manipulative memories. Scope isolation
  blocks cross-tenant poisoning; treat recalled memory as untrusted context.
- **Untrusted model output** — extraction results are model-controlled; validate
  before feeding them to business logic.

## Deploying securely — checklist

- [ ] **Configure real auth** — do **not** ship anonymous auth to production.
- [ ] Store API keys **hashed** (`ApiKeyAuth(..., hashed=True)`); set `expires_at`.
- [ ] Enable `rate_limit`, `max_body_bytes`, and `cors_origins`.
- [ ] Serve over **HTTPS/TLS** (at your proxy/host).
- [ ] Keep secrets in env (`ANTHROPIC_API_KEY`), never in code.
- [ ] Keep **exposure maps minimal**; mark mutating tools `destructive=True`.
- [ ] Don't expose the **MCP server** publicly without authentication.
- [ ] Keep dependencies patched (Dependabot + `pip-audit` are wired in CI).
