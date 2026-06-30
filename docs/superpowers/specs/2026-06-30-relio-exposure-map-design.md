# Step 2 — Exposure Map (governed DB↔AI bridge)

**Date:** 2026-06-30
**Status:** Approved for implementation
**Implements:** D3 of architecture v2.

## Goal

Let the AI use **only** a declared subset of the app's data: a registry of
callable operations ("what to call") + a field allowlist ("only these columns"),
publishable as MCP tools. Unmapped data is invisible to the AI.

## Design

`relio/exposure.py`:
- `ToolSpec(name, fn, description, parameters)` — a registered operation; the
  parameter schema is derived from the function signature.
- `ExposureMap`:
  - `tool(fn=None, *, name, description)` — decorator/registrar.
  - `list()` / `names()` / `get(name)` / `call(name, **kwargs)`.
  - `project(obj, fields)` — the field allowlist; returns a dict containing only
    the listed fields (works for dicts and objects).

`RelioAI` integration:
- `ai.tool(...)` registers; `ai.call_tool(name, **kw)` invokes.
- `ai.expose(obj, fields)` projects to allowed fields.
- `ai.list_tools()` returns the catalog (name/description/parameters) for the
  LLM/agent.
- `ai.mcp_server(include_tools=True)` registers every map tool onto the FastMCP
  server, so the same governed surface reaches external agents.

This registry is the substrate for per-agent tool slices (Step 3).

## Out of scope (YAGNI)

- Auto-deriving tools from ORM models — explicit registration only.
- Argument validation/coercion beyond what the callable does.

## Tests

- Register via `@ai.tool`; `list_tools` shows name/description/params.
- `call_tool` invokes the function; unknown name raises.
- `expose` filters fields for both a dict and an object (private fields dropped).
- `mcp_server(include_tools=True)` exposes the registered tool alongside
  add/recall.
