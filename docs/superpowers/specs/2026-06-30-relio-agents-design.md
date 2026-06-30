# Step 3 — Agents as Bounded Contexts

**Date:** 2026-06-30
**Status:** Approved for implementation
**Implements:** D4 of architecture v2. Builds on Step 2 (exposure map).

## Goal

An agent built into the app gets its **own space**, not a tap into a global AI:
its own memory namespace, its own tool slice, its own config, its own session.
Private by default; shared access is granted, never automatic.

## Design

`relio/agents.py` → `Agent`, constructed via `ai.agent(name, …)`:
- **Memory namespace** — `space = Scope(agent=name)` by default; `remember` /
  `recall` / `history` are scoped to it, so agents can't read each other's
  memory.
- **Tool slice** — `tools=[…]` names a subset of the exposure map; `call_tool`
  outside the slice raises `PermissionError`; `tools=None` grants all.
- **Config** — `system` (identity/instructions, prepended to the prompt via the
  new `run_chat(system_prefix=…)`), `model`, `recall_limit`.
- **Session** — `history` scoped to the agent's space.

`run_chat` gains `system_prefix` so an agent's instructions lead the system
prompt.

## Out of scope (YAGNI)

- Autonomous LLM tool-calling loop (model decides which tool) — the bounded
  surface + manual `call_tool` ship now; the auto-loop is a later step.
- Per-agent model routing wired into the provider (stored as config now).

## Tests

- `ai.agent("billing")` has `space.agent == "billing"`.
- Isolation: billing.remember → support.recall can't see it; billing.recall can.
- Tool slice: agent with `tools=["a"]` lists only `a`; `call_tool("b")` raises;
  `call_tool("a")` works; `tools=None` can call any.
- `chat` (with a provider) streams and persists into the agent's namespace; the
  `system` instruction reaches the provider's system prompt.
