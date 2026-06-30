# Step 1 — `RelioAI` Seam (the called-in AI component)

**Date:** 2026-06-30
**Status:** Approved for implementation
**Implements:** D1 (app-first), D2 (RelioAI seam) of architecture v2.

## Goal

One injectable object the developer's backend reaches for where AI is needed —
composing the AI-system components into a single seam, LLM-optional. This is the
"called-in component," not a set of pre-wired routes.

## Design

`relio/ai.py` → `RelioAI`, composing `Memory` (+ graph + structured query),
an optional `LLMProvider`, the embedder, and the MCP server.

### Components available in this step
- **Memory / RAG:** `remember`, `recall`, `recall_text`.
- **Embeddings:** `embed(text | list[str])` — single or batch.
- **Graph:** `add_node`, `add_edge`, `neighbors`, `in_neighbors`, `traverse`.
- **Structured query:** `query(type, scope, where, limit)`.
- **Reasoning:** `chat(message, scope, …)` — streams via the agent loop; raises a
  clear error if no provider (`has_llm` reports availability).
- **Interop:** `mcp_server()` → the existing FastMCP server bound to *this*
  memory.
- **Transactions:** `transaction()` passthrough.

`Memory` gains a public `embedder` property so the seam can embed without
reaching into internals.

### Components deferred to their own steps (named here, not built)
- `tools` / exposure map → Step 2 (D3).
- `agent(...)` bounded contexts → Step 3 (D4).
- `extract(...)` multimodal/structured → Step 4 (D6).
- MCP **client** + publishing the exposure map → Steps 2–3.

These are intentionally absent rather than stubbed, so the seam only exposes what
actually works today.

## Out of scope (YAGNI)

- Re-posturing the scaffold/`create_app` around `RelioAI` (follow-up in this
  step's PR once the seam is proven) — kept separate to keep the change testable.
- Caching / guardrails / observability wrappers (cross-cutting, later).

## Tests

- `RelioAI()` builds a working memory; `remember`/`recall` round-trip.
- `embed("x")` returns a vector; `embed(["a","b"])` returns two.
- Graph: `add_node`/`add_edge`/`neighbors` work through the seam.
- `query` filters by type/metadata through the seam.
- No provider: `has_llm` is False and `chat` raises; with `FakeProvider`, `chat`
  streams the reply.
- `mcp_server()` returns a server whose `add`/`recall` tools operate on this
  memory.
