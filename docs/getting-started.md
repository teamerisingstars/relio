# Getting started

## Install

Requires **Python 3.11+** (and Node 18+ only if you scaffold a web/mobile/desktop
client).

```bash
pip install "relio[server]"     # engine + FastAPI server + Claude provider
```

Optional extras (combine, e.g. `.[server,postgres]`):

| Extra | Adds |
|-------|------|
| `local` | local ONNX embeddings (`fastembed`) — zero-API-cost vectors |
| `mcp` | the MCP server |
| `postgres` | Postgres + pgvector backend (connection-pooled) |
| `server` | FastAPI, uvicorn, Anthropic SDK |
| `openai` / `gemini` | those providers |
| `jwt` / `accounts` | JWT auth hook / full user accounts |
| `ai` | the full AI-app stack for `AIApp` (server + local + mcp) |
| `dev` | everything + pytest/coverage |

> Use a virtual environment so the `relio` command lands on your PATH.

## Quickstart — use the AI component

```python
from relio import RelioAI

ai = RelioAI(path="relio.db")     # local SQLite + local embeddings, no LLM needed
ai.remember("Alice manages the Acme account")
print(ai.recall("who manages Acme?")[0].content)
```

Offline / CI: set `RELIO_EMBEDDER=deterministic` to skip the ~130MB local-model
download and use a reproducible hashing embedder.

Add an LLM for chat / extraction (set `ANTHROPIC_API_KEY`, or pass `api_key=`):

```python
from relio import RelioAI
from relio.server.llm.claude import ClaudeProvider

ai = RelioAI(path="relio.db", provider=ClaudeProvider())
for chunk in ai.chat("what do you know about Acme?"):
    print(chunk, end="")
```

Any provider by name (`"none"` disables the LLM):

```python
from relio.server.llm import make_provider
provider = make_provider("openai", model="gpt-4o")   # claude / openai / gemini / fake / none
```

## The `RelioAI` seam

```python
ai.remember(text, scope=...)     ai.recall(query)              # store / semantic retrieval
ai.remember_many([...])          ai.query(type=, where=, order_by=)  # bulk / structured filter
ai.embed(["a", "b"])             ai.add_node / add_edge / neighbors / traverse
ai.chat(message)                 ai.extract / ai.extract_file  # needs a provider
ai.transcribe(audio)             ai.mcp_server(include_tools=True)
```

## Bulk-ingest rows with metadata

```python
from relio.record import MemoryType

ai.remember_many([
    {"content": "Campaign c1 report", "type": MemoryType.FACT,
     "metadata": {"campaign": "c1", "roas": 3.2, "status": "active"}},
    {"content": "Campaign c2 report", "type": MemoryType.FACT,
     "metadata": {"campaign": "c2", "roas": 1.1, "status": "paused"}},
])
winners = ai.query(type=MemoryType.FACT, where={"roas__gte": 2.0}, order_by="-roas")
```

See **[Structured query](querying.md)** for the full operator set.

## Scaffold a full app

```bash
relio new myapp --web     # FastAPI backend + React (Vite) frontend + generated SDK
cd myapp
relio dev                 # backend + Vite dev server on one URL
relio sdk --app app:app   # regenerate the client SDK from YOUR endpoints
```

`relio new` also supports `--mobile` (Expo) and `--desktop` (Tauri), all on the
same generated TypeScript SDK. `python -m relio` works anywhere the console
script does.

## Governance gate

```bash
relio check     # fails if any module lacks a test or a doc
```

Keeps generated + hand-written code honest without a heavy CI story.
