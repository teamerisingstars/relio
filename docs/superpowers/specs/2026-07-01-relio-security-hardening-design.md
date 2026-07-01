# Security Hardening

**Date:** 2026-07-01
**Status:** Approved for implementation

Closes the framework gaps, contains the AI-specific threats, and adds the
recommended controls from the security review.

## Server (in `create_app`, new keyword args + `relio/server/security.py`)
- **Error sanitization** — chat / agent SSE no longer leak `str(exc)`; emit a
  generic `"internal error"` and log the real one.
- **Rate limiting** — `RateLimiter` (fixed window, in-process); `create_app(...,
  rate_limit=(count, seconds))` → 429 over the limit, keyed by client host.
- **Request-size limit** — `create_app(..., max_body_bytes=N)` → 413 over N.
- **CORS** — `create_app(..., cors_origins=[...])`.

## Auth (`ApiKeyAuth`)
- **Hashed keys** — `ApiKeyAuth(keys, hashed=True)` stores/looks up SHA-256
  digests (no plaintext at rest).
- **Expiry** — a principal may carry `expires_at`; expired → 401.

## Exposure map / tool safety
- **Destructive tools** — `@ai.tool(destructive=True)`; `call_tool` (and agents)
  refuse without `confirm=True`. Contains prompt-injection blast radius before an
  autonomous loop exists.

## Extraction
- **Schema validation** — `ai.extract(..., validate=True)` checks the model's
  output has the schema's `required` fields; missing → `ValueError`. Model output
  is untrusted.

## Docs & CI
- **`SECURITY.md`** — supported versions, private disclosure, the security model,
  a "deploy securely" checklist, and the AI-threat notes (prompt injection,
  memory poisoning) with mitigations.
- **`.github/dependabot.yml`** — pip + github-actions + npm(templates) updates.
- **`.github/workflows/security.yml`** — `pip-audit` on push/PR.

## AI-specific threats — how they're contained
- **Prompt injection** → least-privilege exposure map + bounded agent tool slices
  + destructive-tool confirmation; documented.
- **Memory poisoning** → scope isolation (cross-tenant blocked); documented.
- **Data exfiltration** → secure-by-default scoping; deploy guide warns against
  anonymous auth in production.

## Tests
- RateLimiter allows N then blocks; `max_body_bytes` → 413; CORS header present;
  chat error is sanitized (no secret leak).
- ApiKeyAuth hashed keys resolve; expired → 401; plaintext still works.
- Destructive tool without `confirm` raises; with `confirm` runs.
- `validate_extraction` raises on missing required field; `extract(validate=True)`
  enforces it.
