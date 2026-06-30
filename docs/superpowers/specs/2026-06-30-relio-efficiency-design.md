# Step 5 — Efficiency Pass

**Date:** 2026-06-30
**Status:** Implemented (Postgres JSONB path integration-gated)
**Implements:** D7, D8 of architecture v2.

## Goal

Make the real cost centers cheaper without changing the single-seamless-system
design — no microservices.

## Changes

1. **Indexed structured query (D7)**
   - SQLite: expression indexes on `json_extract(doc,'$.type')` and each
     `$.scope.*` field — Feature J `query()` is now indexed, not a scan.
   - Postgres: `doc` column moved from `TEXT` → **`JSONB`** with a **GIN** index;
     reads parse the dict directly, query uses native `->>` / `#>>` (no per-query
     cast). Integration-gated.

2. **Recall result cache (D8)**
   - `Memory.recall` caches results keyed by (query, scope, type, limit). Any
     write (`add` / `add_many` / `add_turn` / `link` / `forget`) invalidates the
     cache, so results never go stale.

3. **Token-budget rendering (D8)**
   - `render_lines(records, max_chars=…)` stops adding lines once the budget is
     hit — caps how much recalled memory is injected into the prompt (LLM
     cost/latency lever).

## Out of scope (YAGNI)

- ANN vector index tuning (HNSW/IVFFlat config) — separate perf pass.
- Prompt/embedding cache beyond the existing embedding dedup.

## Tests

- Repeated identical `recall` returns the cached object; a write invalidates it
  and the new record appears.
- `render_lines(max_chars=…)` truncates to within budget (always ≥1 line).
- `query` still returns correct results with the new indexes (existing J tests).
- Postgres JSONB query + roundtrip (integration-gated).
