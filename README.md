# Relio

**An app-first AI framework.** Build a normal FastAPI + React app with your own
data, and *call AI in* where you need it — memory, retrieval, agents, document
extraction, and MCP — as one in-process component, not a pile of services.

> Relio is **memory-native**: vectors + graph + structured query live in one
> SQLite file (or Postgres), and the AI reaches your app's data only through a
> governed, field-limited **exposure map**.

- **One seamless system** — backend calls the AI in-process (no network hop), one
  port, one deploy.
- **AI is a component, not the product** — the `RelioAI` seam is LLM-optional;
  use just `recall`, or the whole stack (chat, agents, extraction, MCP).
- **Governed by default** — the AI sees only what you declare; agents are bounded
  contexts with their own memory + tools.
- **Batteries for building** — scaffolds (web/mobile/desktop), generated SDKs, and
  a dev harness that won't let code land without a test and a doc.

> Status: early / pre-release (`0.1.0`). The engine, server, SDKs, agents,
> extraction, and CLI are tested. Postgres paths and the vision/extraction model
> call are integration-gated (need a live DB / API). See [Status](#status).

---

## Install

Requires **Python 3.11+** (and Node 18+ only if you scaffold a web/mobile/desktop
client).

```bash
pip install "relio[server]"     # engine + FastAPI server + Claude provider
```

Optional extras:

| Extra | Adds |
|-------|------|
| `relio[local]` | local ONNX embeddings (`fastembed`) — zero-API-cost vectors |
| `relio[mcp]` | the MCP server |
| `relio[postgres]` | Postgres + pgvector backend (with connection pooling) |
| `relio[server]` | FastAPI, uvicorn, Anthropic SDK |
| `relio[dev]` | everything + pytest/coverage |

From source:

```bash
git clone <repo> relio && cd relio
pip install -e ".[dev]"
pytest            # 150+ tests
```

---

## Quickstart (use the AI component)

```python
from relio import RelioAI

ai = RelioAI(path="relio.db")          # local SQLite + local embeddings, no LLM needed
ai.remember("Alice manages the Acme account")
print(ai.recall("who manages Acme?")[0].content)   # -> "Alice manages the Acme account"
```

Add an LLM when you want chat/extraction (set `ANTHROPIC_API_KEY`):

```python
from relio import RelioAI
from relio.server.llm.claude import ClaudeProvider

ai = RelioAI(path="relio.db", provider=ClaudeProvider())
for chunk in ai.chat("what do you know about Acme?"):
    print(chunk, end="")
```

## Scaffold a full app

```bash
relio new myapp --web      # FastAPI backend + React (Vite) frontend + generated SDK
cd myapp
relio dev                  # backend + Vite dev server on one URL
```

`relio new` also supports `--mobile` (Expo) and `--desktop` (Tauri), all on the
same generated TypeScript SDK.

---

## Core concepts

### The `RelioAI` seam — the called-in component
One object composing the AI-system components. The LLM is optional.

```python
ai.remember(text, scope=...)        # store          ai.recall(query)        # semantic retrieval
ai.embed(["a", "b"])                # batch embeddings ai.query(type=..., where=...)  # structured filter
ai.add_node / add_edge / neighbors / traverse          # knowledge graph
ai.chat(message)                    # agent loop (needs a provider)
ai.extract / ai.extract_file        # structured / multimodal extraction
ai.mcp_server()                     # expose to external agents over MCP
```

### Exposure map — governed access to *your* data
Your app DB is private. The AI can call only what you declare, and see only the
fields you allow.

```python
@ai.tool
def lookup_account(name: str) -> dict:
    row = db.get_account(name)
    return ai.expose(row, fields=["name", "owner", "status"])   # cost/PII stay invisible

ai.call_tool("lookup_account", name="Acme")
# the same map auto-publishes as MCP tools: ai.mcp_server(include_tools=True)
```

### Agents — bounded contexts
Each agent gets its own memory namespace, tool slice, config, and session.
Private by default.

```python
billing = ai.agent("billing", tools=["lookup_account"], system="You handle billing.")
billing.remember("invoice 42 overdue")     # not visible to other agents
billing.call_tool("refund", ...)           # PermissionError — not in its slice
```

### Document extraction (AI beyond chat)
```python
bom = ai.extract_file("drawing.pdf", schema={"properties": {"part_no": {}, "qty": {}}})
```

### Run it as a server
```python
from relio import Memory
from relio.server import create_app
from relio.server.llm.claude import ClaudeProvider

app = create_app(Memory(path="relio.db"), ClaudeProvider())   # uvicorn app:app
# memory-only backend (no LLM):  create_app(Memory())
```

Endpoints: `POST /api/chat` (SSE), `/api/memory` CRUD + `/search` + `/query`,
`/api/history`, `/api/graph/neighbors`, `/api/health`. Identity comes from an
**auth hook** (`anonymous_auth` default, or `ApiKeyAuth`), never from the request
body — so tenants are isolated by construction.

---

## CLI

| Command | Does |
|---------|------|
| `relio new <name> [--web/--mobile/--desktop]` | scaffold an app (+ generated SDK + dev harness) |
| `relio dev` | run backend + frontend dev servers on one URL |
| `relio build` | build the React frontend |
| `relio serve [--port]` | serve API + built frontend on one port |
| `relio sdk [--out]` | generate the TS + Python SDKs from the API |
| `relio develop ["<task>"]` | drive the Claude Code CLI to build a feature (feeds gate gaps to it) |
| `relio test [--coverage --min N]` | run the test suites (optionally enforce coverage) |
| `relio check` | **governance gate** — fail if any module lacks a test and a doc |
| `relio dockerfile` / `relio deploy` | production Dockerfile / build image |

### The governance gate
A scaffolded app ships a `CLAUDE.md` (conventions), `docs/`, `tests/`, and a
`.claude/` Stop hook that runs `relio check`. The gate requires **every module
(Python and TypeScript) to have a test and a doc** — and a fresh scaffold passes
it out of the box. So agentic development with `relio develop` can't end with
undocumented or untested code.

---

## Backends & config

- **Default:** one SQLite file (vectors via `sqlite-vec`, WAL, indexed structured
  query). Backups = copy the file.
- **Scale:** `Memory(database_url="postgresql://…")` swaps to **Postgres +
  pgvector** (JSONB + GIN, connection pooling) — no caller changes.
- **Server config** via `RELIO_*` env (`RELIO_DATABASE_URL`, `RELIO_MODEL`, …).

---

## Project layout

```
relio/            # the framework package
  ai.py           # RelioAI seam            exposure.py  # exposure map
  agents.py       # bounded agents          memory.py    # the engine
  backends/       # sqlite, postgres        embedding/   # local + cache + batch
  server/         # FastAPI app, routes, auth, llm providers, agent loop
  cli/            # new/dev/serve/sdk/develop/test/check
  templates/      # web (React), mobile (Expo), desktop (Tauri)
docs/superpowers/specs/   # design specs (architecture v2 + every feature)
tests/            # 150+ tests
```

Start with [`docs/superpowers/specs/2026-06-30-relio-architecture-v2-app-first.md`](docs/superpowers/specs/2026-06-30-relio-architecture-v2-app-first.md)
for the full architecture.

---

## Status

| Area | State |
|------|-------|
| Engine, server, auth, graph, query, agents, SDK gen, scaffolds, CLI, dev harness | ✅ tested |
| Postgres + pgvector (backend, pooling, JSONB) | ⚙️ implemented; integration-gated (`RELIO_TEST_DATABASE_URL`, `pytest -m integration`) |
| Claude vision/extraction call | ⚙️ implemented; untested without an API key (the offline fake path is tested) |
| Generated TS SDK / mobile / desktop apps | ⚙️ scaffolded + structurally tested; not compiled in CI |

---

## License

Intended **open-core**: the framework is MIT (see [LICENSE](LICENSE)); a future
managed cloud + enterprise components are separately licensed. See the project's
licensing notes.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). In short: tests-first, every change keeps
the suite green, and design specs live under `docs/superpowers/specs/`.
