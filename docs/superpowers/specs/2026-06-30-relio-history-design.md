# Feature A — Multi-turn Conversation History

**Date:** 2026-06-30
**Status:** Approved for implementation
**Part of:** Relio missing-features build-out (Feature A of A–G)

## Problem

`run_chat` (`relio/server/agent.py`) sends only the current user message to
the LLM: `[Message(role="user", content=message)]`. Prior turns are lost, so
every message starts cold. `Message` already supports an `assistant` role and
`MemoryType.SESSION` already exists but is unused.

## Goal

Persist each conversation turn (user + assistant) and replay the last N turns to
the LLM on the next request, so the agent has working short-term conversational
memory that survives a process restart. Keep conversation history **separate
from semantic memory** so chat turns never pollute vector recall.

## Design

### Representation
A turn is a `MemoryRecord` with:
- `type = MemoryType.SESSION`
- `content` = the message text
- `metadata = {"role": "user" | "assistant"}`
- `scope` = the request scope (tenant/user/session)
- **no embedding** (`embedding=None`)

Reuses the existing `records` table — no new schema, no `StorageBackend`
interface change. The future Postgres backend (Feature B) inherits history for
free.

### Separation from semantic recall
Turns are stored without embeddings. Vector `search()` only returns embedded
rows, so history can never surface in `recall()`. "What the user told us"
(semantic, embedded) and "what was said" (transcript, not embedded) stay
distinct.

### Retrieval
`Memory.history(scope, limit)` is chronological, not semantic: it filters
`backend.all()` by session scope + `SESSION` type, sorts by `created_at`
ascending, and returns the last `limit` turns. Over `all()` for now — acceptable
for single-node; optimizable later without an interface change.

Replay uses **whatever scope is given**. A missing `session` simply groups turns
at the user level.

## Changes by file

| File | Change |
|------|--------|
| `relio/record.py` | Extract `scope_matches(query, record)` as a shared module function; `RecallEngine` reuses it |
| `relio/memory.py` | Add `embed: bool = True` flag to `add()`; add `add_turn(role, content, scope)` and `history(scope, limit=20)` |
| `relio/server/agent.py` | `run_chat` loads history → builds `[*history, user]` → after streaming, persists user + assistant turns |
| `relio/server/routes/chat.py` | Add `GET /api/history` returning a session transcript; no change to `POST /api/chat` request shape |

## Out of scope (YAGNI)

- Token-budget summarization / truncation of long histories — simple last-N
  limit only.
- No separate messages table; no UI changes beyond the new endpoint existing.
- `default_capture` (storing user messages as semantic facts) is unchanged.

## Tests (written first)

1. `add(embed=False)` stores a record that does **not** appear in `recall()`.
2. `history()` returns turns in insertion order, respects `limit`, and is
   scope-isolated (session A never sees session B).
3. `run_chat` replays prior turns to the provider (fake provider asserts it
   received them) and persists both new turns.
4. Route: two `POST /api/chat` calls → `GET /api/history` returns 4 ordered
   turns.
