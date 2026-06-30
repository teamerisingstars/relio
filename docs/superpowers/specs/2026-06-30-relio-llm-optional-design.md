# Feature H — LLM-optional Core

**Date:** 2026-06-30
**Status:** Approved for implementation
**Part of:** Relio "widen the fit" subset (Feature H of H–K)

## Problem

The write-up claimed "an LLM is assumed to be in the loop." The memory
primitives already work without an LLM, but the server forces one:
`create_app` requires a `provider`, and `/api/history` (pure memory) is bundled
in the LLM chat router. So a memory-only / non-AI data backend isn't cleanly
expressible.

## Goal

Make the LLM genuinely optional: a Relio backend can run with **no provider**,
exposing memory + graph + history, with chat simply absent.

## Design

- **Move `/api/history`** from the chat router to the memory router — it reads
  `memory.history`, no LLM involved. Path and behavior unchanged.
- **`create_app(memory, provider=None, ...)`**: register the chat router only
  when a provider is supplied. Health, memory, graph (and history) always
  register. With no provider, `POST /api/chat` is simply not mounted (404).
- `ClaudeProvider` already imports `anthropic` lazily, so importing the server
  never requires the LLM dependency — no change needed there.

## Out of scope (YAGNI)

- A 501 stub for `/api/chat` when disabled (absent route → 404 is fine).
- Removing the provider from the scaffold's default app (chat stays the default
  experience; this is about *enabling* the memory-only mode).

## Tests

- `create_app(memory)` with no provider: `/api/memory` add/search, `/api/graph`,
  and `/api/history` all work; `POST /api/chat` returns 404.
- Existing app (with provider): chat + history still work (history path
  unchanged).
