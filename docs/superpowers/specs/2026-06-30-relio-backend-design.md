# Relio Backend Layer — Design

**Date:** 2026-06-30
**Status:** Draft for review
**Builds on:** the engine (`relio.Memory`) and `2026-06-30-relio-framework-architecture.md` §3.3.

## Goal

A thin FastAPI app that exposes the Relio Memory engine over HTTP and runs the
lean AI agent loop — embedding the engine **in-process** (no second service).
This is the backend layer of the single-deploy Relio framework; the React
frontend and DevOps/single-port layers come in later plans.

## Scope (this plan)

In: memory HTTP endpoints, a streaming chat agent loop with automatic memory
capture, a pluggable LLM provider (Claude real + a fake for tests), scope
resolution, config. **Out:** frontend, auth backends beyond a permissive default,
the reverse-proxy/Docker DevOps layer, Postgres.

## Where it lives

Same installable package, new subpackage `relio.server` (keeps the single-package
model; imports the engine directly). New optional extra in `pyproject.toml`:
`server = ["fastapi", "uvicorn", "anthropic", "sse-starlette", "pydantic-settings"]`;
add `fastapi`, `httpx`, `pydantic-settings`, `anthropic` to the `dev` extra so
tests run.

```
relio/src/relio/server/
  __init__.py        # create_app re-export
  config.py          # Settings (pydantic-settings): db_path, model, anthropic_api_key
  schemas.py         # request/response Pydantic models
  scope.py           # scope_from_request dependency -> relio.Scope
  llm/
    __init__.py
    base.py          # Message, LLMProvider ABC (stream())
    fake.py          # FakeProvider (deterministic, offline) — default in tests
    claude.py        # ClaudeProvider (anthropic SDK) — real default
  agent.py           # run_chat(): recall -> prompt -> stream -> capture
  app.py             # create_app(memory, provider, settings) -> FastAPI
  routes/
    __init__.py
    memory.py        # /api/memory endpoints
    chat.py          # /api/chat (SSE)
```

## Components

### LLM provider (the seam that makes the backend testable)
`Message` = `{role: "user"|"assistant"|"system", content: str}`.
`LLMProvider.stream(messages: list[Message], system: str) -> Iterator[str]` yields
text chunks. Two implementations:
- **`FakeProvider`** — deterministic, offline; e.g. echoes a fixed reply derived
  from the last user message and the injected memory count. Default in tests.
- **`ClaudeProvider`** — wraps the Anthropic SDK streaming API; model from config
  (default a current Claude model id), API key from env. Used in production.

### Agent loop (`agent.py`)
`run_chat(memory, provider, message, scope) -> Iterator[str]`:
1. `recalled = memory.recall(message, scope=scope, limit=k)`.
2. Build `system` text that embeds `render_lines(recalled)` (token-light) under a
   "What you remember:" header.
3. `for chunk in provider.stream([{user: message}], system): accumulate; yield chunk`.
4. **Auto-capture (heuristic):** after streaming completes, store the user message
   as a memory: `memory.add(message, scope=scope)`. (Extraction is a single
   pluggable function `capture_turn(memory, message, reply, scope)`; the default
   stores the user message. LLM-based extraction is a later enhancement.)

### Endpoints
- `GET /api/health` → `{status: "ok"}`.
- `POST /api/memory` — body `{content, type?, user?, tenant?, agent?, session?, data?, ttl?, metadata?}` → 201 with the record JSON.
- `GET /api/memory/search?q=&user=&tenant=&type=&limit=` → `{results: [record...], text: "<rendered lines>"}`.
- `GET /api/memory/{id}` → record JSON or 404.
- `DELETE /api/memory/{id}` → `{deleted: bool}`.
- `POST /api/chat` — body `{message, user?, session?, tenant?}` → `text/event-stream` (SSE) of `{"delta": "..."}` events, terminated by a `{"done": true}` event. Auto-captures the turn after the stream ends.

### Scope resolution (`scope.py`)
`scope_from_request(...)` builds a `relio.Scope` from request fields (query params
for GET, body for POST). Default is permissive (whatever the client supplies, or
empty = global). This is the seam the architecture's auth hook later replaces;
for now no auth is enforced.

### Config (`config.py`)
`Settings` (pydantic-settings): `db_path="relio.db"`, `model="<claude-default>"`,
`anthropic_api_key` (from `ANTHROPIC_API_KEY` env), `recall_limit=5`. `create_app`
takes an optional `Settings`, `Memory`, and `LLMProvider` so tests inject a temp
DB + `DeterministicEmbedder` + `FakeProvider`.

## Error handling
- `GET/DELETE /api/memory/{id}` → 404 when the id is unknown.
- Invalid request bodies → FastAPI 422 (Pydantic).
- LLM provider errors during `/api/chat` → emit an SSE `{"error": "..."}` event and
  end the stream; the turn is not captured on error.

## Testing
- `FakeProvider` + `TestClient` (httpx) → no network, no API key.
- Memory endpoints: add → search → get → delete round-trip; 404 paths.
- Chat: SSE stream yields deltas then done; **the turn is captured** (a follow-up
  search finds the user message); injected-memory path (seed a memory, confirm the
  fake reply reflects the recalled count / the system prompt contained it).
- Scope: a memory added under user A is not returned when searching as user B.
- `ClaudeProvider` is covered by a thin unit test that mocks the Anthropic client
  (no real calls), marked `integration` if it needs the SDK.

## Out of scope (later plans)
React frontend; real auth/multi-tenant DB-per-tenant; reverse-proxy + Dockerfile
(single-port DevOps); LLM-based memory extraction; rate limiting.
