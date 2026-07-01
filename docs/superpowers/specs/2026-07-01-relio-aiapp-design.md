# AIApp — Opinionated AI-application framework (same package, `ai` extra)

**Date:** 2026-07-01
**Status:** Approved for implementation

## Goal

A batteries-included layer for building **AI-first applications**, shipped inside
the `relio` package and installed via a new `ai` extra — not a separate repo.
It composes what Relio already has (`RelioAI` + bounded agents + the server) into
a high-level `AIApp` and a `relio ai new` scaffold.

## Design

### `relio/aiapp/` subpackage
- **`AIApp`** — wires a `RelioAI`, a set of **bounded agents**, and a ready HTTP
  server:
  - `AIApp(ai=None, *, provider=None, path=..., embedder=..., database_url=..., settings=..., auth=...)`
  - `.agent(name, **kw)` — register a bounded agent (delegates to `RelioAI.agent`).
  - `.tool(...)` — register an exposure-map tool.
  - `.agents` — the registered agents.
  - `.build()` — returns a FastAPI app = the base Relio routes **plus** an agents
    router. Lazy-imports FastAPI, so importing `AIApp` never requires the server
    extra until you build.
- **agents router** — `GET /api/agents` (list names + tool slices) and
  `POST /api/agents/{name}/chat` (SSE stream from that bounded agent; 404 for
  unknown).

### Packaging
- New extra: `ai = ["relio[server,local,mcp]"]` — one install for the full AI-app
  stack. The `aiapp` code lives in core `relio` (import works without the extra;
  `.build()` needs the server extra).
- `AIApp` exported from `relio` top-level.

### CLI
- `relio ai new <name>` — scaffolds an AI-first app: `app.py` using `AIApp` + a
  starter `assistant` agent, `requirements.txt` (`relio[ai]`), Dockerfile, and the
  dev harness (so it passes `relio check`).

## Out of scope (YAGNI)

- Per-request tenant scoping of agent chat (agents use their fixed space for now).
- Multi-agent orchestration / hand-off (agents are independent bounded contexts).
- A dedicated agent UI template.

## Tests

- `AIApp.agent` registers; `.agents` reflects it.
- `.build()` serves base routes (`/api/health`, `/api/memory`) **and** the agents
  router; `GET /api/agents` lists the agent; `POST /api/agents/{name}/chat`
  streams a reply; unknown agent → 404.
- `relio ai new <name>` scaffolds an `AIApp`-based app that passes `relio check`.
