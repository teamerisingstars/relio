# Feature E — Generated SDKs (OpenAPI → TS + Python)

**Date:** 2026-06-30
**Status:** Implemented
**Part of:** Relio missing-features build-out (Feature E of A–G)

## Problem

The frontend's types are hand-written, duplicating the Pydantic record shape.
The architecture (§9, §11.1) wants the format defined once and flowed to every
client via generated SDKs.

## Decision

A **dependency-light, offline generator** that walks the FastAPI OpenAPI schema
and emits **types + a typed client** for both TypeScript and Python — no
external codegen toolchain (consistent with the repo's no-heavy-deps stance).
Routes carry explicit `operation_id`s so generated method names are clean.

## Design (`relio/sdkgen.py`)

- `generate_ts_types` / `generate_py_types`: enums → TS union / Python `Literal`;
  objects → `interface` / `TypedDict(total=False)`. A schema resolver handles
  `$ref`, `anyOf[..,null]` → optional, `allOf`, arrays, `additionalProperties`
  objects, and primitives.
- `generate_ts_client` / `generate_py_client`: one method per operation
  (path params → args, body → typed `body`, query → typed params), plus a
  hand-templated streaming `chat` method (SSE). TS uses `fetch`; Python uses
  stdlib `urllib` (zero runtime deps). Bearer API-key header supported.
- `generate_all(openapi)` → `{types.ts, client.ts, types.py, client.py}`.
- CLI: `relio sdk [--out sdk]` builds a throwaway app to read the schema and
  writes the four files.

## Out of scope (YAGNI)

- Runtime validation in clients (types are compile-time only).
- Pagination/retry/auth-refresh helpers.
- Executing/building the TS output here (no Node in CI) — structurally tested.

## Tests

- TS types contain `MemoryType` union + `MemoryRecord` interface with optional
  fields; TS client has typed `addMemory`/`getMemory`/`searchMemory` + streaming
  `chat`.
- Python types and client **compile** (`compile()`), with `add_memory` /
  `get_memory` / `chat` present.
- `generate_all` yields four non-empty files; `relio sdk` writes them.
