# Changelog

All notable changes to Relio are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [0.1.5] - 2026-07-01

### Added
- **Autonomous agent tool-calling** — `agent.run(task)` lets the LLM pick tools
  from the agent's slice, execute them, feed results back, and loop to a final
  answer. **Destructive tools are never auto-run** (blocked pending confirmation).
  New provider capability `complete_with_tools` (Claude + OpenAI + **Gemini**;
  `FakeProvider` for offline tests).
- **Query operators + pagination** — `query(where=...)` supports
  `field__gt/gte/lt/lte/ne/contains/startswith/in` (default exact), plus
  `order_by` (`-field` = desc), `limit`, and `offset`. Exposed on
  `POST /api/memory/query`.
- **Scoped graph** — `neighbors` / `in_neighbors` / `traverse` accept a `scope`
  and filter by it; `GET /api/graph/neighbors` now enforces the principal.
- **Accounts polish** — refresh tokens (`/auth/refresh`), password reset
  (`/auth/reset-request` + `/auth/reset`), **Google / GitHub / Microsoft OAuth**,
  and optional **login rate-limiting**.
- **OAuth CSRF protection** — the OAuth login step now sets a signed, HttpOnly
  `state` cookie and the callback rejects any request whose `state` doesn't match
  (`hmac.compare_digest`), closing the login-CSRF gap.
- **`GET /auth/me`** — returns the authenticated user (id, email, name, tenant,
  provider, profile); `401` when unauthenticated.
- **Extensible user profiles** — `User.profile` (arbitrary JSON) plus `name`;
  `register` accepts `name` + `profile`, and `store.set_profile(...)` persists
  updates (SQLite column added with an automatic migration for older DBs).
- **SPA-friendly OAuth** — pass `frontend_url` and OAuth callbacks redirect to
  it with `#token=…&refresh=…` instead of returning JSON.
- **Configurable token lifetimes** — `token_ttl` / `refresh_ttl` on
  `build_accounts_router(...)`.
- **Voice / speech-to-text** — new provider capability `transcribe(audio)` and
  `RelioAI.transcribe(...)` (OpenAI Whisper; `FakeProvider` for offline tests),
  the server-side fallback for the browser Web Speech API.
- **Provider capability negotiation** (ADR-003) — `provider.capabilities()` /
  `.supports("transcribe")` (auto-derived from overridden methods) and
  `RelioAI.supports(...)` let apps pre-flight before calling. Unsupported
  capabilities now raise a clear `CapabilityError` at the seam instead of a deep
  `NotImplementedError`. `make_provider(name, requires=[...])` fails fast at
  construction if the chosen provider can't meet the required capabilities.

- **`relio migrate --from <src> --to <dst>`** — copy a memory store between
  backends (e.g. SQLite → Postgres), preserving ids/scope/metadata/timestamps and
  re-embedding content (`--no-embed` for a structured-only copy). See ADR-002.
- **Per-request scope injection for exposed tools** — a tool that declares a
  `scope` parameter gets the caller's `Scope` injected per-call (hidden from the
  LLM-facing schema), so one registered tool serves every tenant instead of being
  closure-bound to one principal. Agents inject their own space automatically.
- **`add_many` / `RelioAI.remember_many` accept rows with metadata** — each item
  may be a string *or* `{"content", "type"?, "scope"?, "data"?, "metadata"?}`, so
  you can bulk-ingest structured rows (then range-filter/order on the metadata).
- **`RELIO_EMBEDDER` selects the embedder** — `deterministic` (offline, no
  download) vs `local` (fastembed, ~130MB). A bare `Memory()` honors it, so CI /
  air-gapped / test runs skip the model download. New `make_embedder(name)`.
- **`python -m relio`** now works (added `relio/__main__.py`) — same entry point
  as the `relio` console script.
- **`MemoryType.EPISODIC`** — a time-anchored event type alongside
  SEMANTIC/FACT/SESSION/NODE/EDGE.
- **`ClaudeProvider(api_key=...)`** — parity with `OpenAIProvider`; `make_provider`
  forwards it. (`None` still falls back to `ANTHROPIC_API_KEY`.)
- **Docs:** structured-query operator/key rules ([docs/querying.md](docs/querying.md))
  and the provider capability matrix ([docs/providers.md](docs/providers.md)).

### Fixed
- **`relio sdk` now introspects *your* app** (`--app module:attr`, default
  `app:app`) instead of a throwaway base app — so custom endpoints are included
  in the generated client. If the app can't be imported it errors clearly rather
  than silently shipping a partial SDK.
- **`relio test` / `dev` / `build` work on Windows.** pytest now runs via
  `sys.executable -m pytest` and npm is resolved to `npm.cmd` (bare `pytest`/`npm`
  raised `WinError 2`). `serve`/`dev` launch uvicorn via `sys.executable -m
  uvicorn` too.
- **Fresh `--web` scaffold builds out of the box.** Added `src/vite-env.d.ts`
  (`vite/client` types) so `npm run build`'s `tsc` step no longer fails on the
  `./styles.css` side-effect import.
- **`create_app(auth=...)` now protects `extra_routers`.** They previously ran
  with no auth even when a hook was configured — a security footgun. They now get
  the same `Depends(auth)` as built-in routers (opt out with
  `protect_extra_routers=False` for genuinely public routes).
- `relio deploy --name <image>` — the image name is configurable (was hardcoded
  to `relio-app`).
- Scaffolded component presence tests now `import { test, expect } from "vitest"`
  explicitly (no reliance on Vitest globals).

## [0.1.4] - 2026-07-01

### Added
- **User accounts** — `relio.accounts` (`pip install "relio[accounts]"`): a user
  store (in-memory + SQLite), password login (stdlib PBKDF2), and **Google
  OAuth**. Login issues a JWT that the existing `JWTAuth` hook verifies —
  `build_accounts_router(store, secret, google=...)` adds
  `/auth/register|login|google`.
- **Multiple LLM providers, not just Claude** — `OpenAIProvider` (and any
  OpenAI-compatible endpoint via `base_url`: Groq / Together / Ollama / local)
  and `GeminiProvider`, alongside `ClaudeProvider`. New extras: `openai`,
  `gemini`.
- **`make_provider(name)` registry** — choose the AI by name
  (`claude`/`openai`/`gemini`/`fake`) via `RELIO_PROVIDER` / `Settings.provider`,
  and **disable the LLM explicitly with `"none"`** — the intentional way to run
  without a provider (rather than omitting the argument).

### Fixed
- `relio dev` / `relio build` now target the scaffolded app's `web/` directory
  (they previously ran `npm --prefix frontend`, which doesn't exist in a
  scaffolded app).
- `create_app(..., frontend_dir=…)` serves the API only (with a warning) when the
  frontend hasn't been built yet, instead of raising `FileNotFoundError` — so
  `uvicorn app:app` works before `relio build`.
- The SPA catch-all now returns a real **404** for unknown `/api/*` paths instead
  of serving `index.html`, so missing/typo'd API routes fail loudly.
- **Providers construct lazily** — `ClaudeProvider()` / `OpenAIProvider()` /
  `GeminiProvider()` no longer create their SDK client (or require an API key) at
  construction; the client is built on first use. The app boots without a key.
- `relio check` now matches module names as **whole words** (case-insensitive)
  instead of any substring, so a module isn't counted as tested/documented just
  because its stem appears inside another word.
- **`Depends(JWTAuth(...))` / `Depends(ApiKeyAuth(...))` now enforce auth.**
  `auth.py` no longer uses stringized annotations, which had made an AuthHook
  *instance* unusable as a FastAPI dependency (`request` was treated as a query
  param → 422, auth silently skipped).
- **`create_app(..., extra_routers=[...])`** — app routers are registered before
  the SPA catch-all, so a mounted frontend no longer shadows your routes.
- **Scaffold files are written UTF-8.** Generated `tests/test_app.py` (which
  contains an em-dash) previously wrote as cp1252 on Windows, producing a
  `SyntaxError: Non-UTF-8 code` that broke the app's pytest + `relio check`.
- **Fresh `--web` scaffold now `npm run build`s.** The web `tsconfig` relaxes
  `noUnusedLocals` (the generated SDK has unused type imports) and excludes
  `*.test.tsx`/`*.spec.tsx` from the `tsc` build (they're type-checked/run by
  vitest), so `tsc && vite build` no longer fails on generated code.

## [0.1.3] - 2026-07-01

### Fixed
- Web scaffold: align `react-dom` and `@types/react` / `@types/react-dom` to
  React 19. A Dependabot bump had upgraded `react` to 19 while leaving these on
  18, which broke `npm install` in scaffolded web apps. Added a regression test
  that fails on a react/react-dom major mismatch. ([#10](https://github.com/teamerisingstars/relio/issues/10))

## [0.1.2] - 2026-07-01

### Added
- **`AIApp`** — an opinionated, batteries-included framework for AI-first
  applications (in `relio.aiapp`): composes `RelioAI` + bounded agents + a ready
  HTTP server, including a per-agent router (`GET /api/agents`,
  `POST /api/agents/{name}/chat` with SSE).
- **`ai` extra** — `pip install "relio[ai]"` installs the full AI-app stack
  (server + local embeddings + MCP).
- **`relio ai new <name>`** — scaffolds an AI-first app (an `AIApp` with a
  starter agent) that passes the `relio check` governance gate out of the box.

### Security
- Rate limiting, request-size limits, and CORS via `create_app(rate_limit=…,
  max_body_bytes=…, cors_origins=…)`.
- SSE errors are sanitized (no internal details leaked to clients).
- `ApiKeyAuth` supports **hashed keys** (`hashed=True`) and per-key `expires_at`;
  new **`JWTAuth`** hook (`relio[jwt]`) verifies JWT bearer tokens.
- Destructive tools (`@ai.tool(destructive=True)`) require `confirm=True`.
- `ai.extract(..., validate=True)` validates model output against the schema.
- `SECURITY.md`, Dependabot, and a `pip-audit` CI workflow.

## [0.1.1] - 2026-07-01

### Added
- Automated PyPI publishing via GitHub Actions using **Trusted Publishing**
  (OIDC — no stored token).
- Package metadata: project URLs (Homepage/Repository/Issues), license, authors,
  keywords, and classifiers.
- `README.md`, `CONTRIBUTING.md`, and `LICENSE` (MIT).

### Fixed
- Removed a redundant wheel `force-include` that broke the build; the scaffold
  templates now ship correctly inside the wheel.

## [0.1.0] - 2026-06-30

Initial release — an app-first AI framework with a built-in, governed memory
engine.

### Added
- **Memory engine** — `add` / `recall` / `history` / structured `query` /
  multi-record transactions, with scope (tenant/user/agent/session), TTL, and
  relations.
- **Storage backends** — SQLite + `sqlite-vec` (default; WAL, indexed query) and
  Postgres + pgvector (JSONB + GIN, connection pooling); swap via `database_url`.
- **Embeddings** — local ONNX (`fastembed`) with a dedup cache and batch support.
- **Knowledge graph** — nodes, edges, neighbours, and cycle-safe traversal.
- **`RelioAI` seam** — one called-in AI component (LLM-optional): memory/RAG,
  embeddings, graph, chat, extraction, tools, and MCP.
- **Exposure map** — governed, field-limited access to app data (`ai.tool` /
  `ai.expose`), published as MCP tools.
- **Bounded agents** — each with its own memory namespace, tool slice, config,
  and session.
- **Multimodal / structured extraction** — `extract` / `extract_file`
  (document → structured data).
- **FastAPI server** — REST + SSE chat, secure-by-default auth (anonymous or API
  key), memory/graph/history/query routes; LLM-optional.
- **MCP server** — exposes memory (and the exposure map) to external agents.
- **Generated SDKs** — TypeScript + Python clients from the OpenAPI schema
  (`relio sdk`).
- **Scaffolds** — web (React/Vite), mobile (Expo), desktop (Tauri), each on the
  generated SDK.
- **Dev harness** — `relio develop` (drives Claude Code), `relio test`
  (+ coverage), and `relio check` (a governance gate requiring a test and a doc
  for every module, Python and TypeScript).

[0.1.5]: https://github.com/teamerisingstars/relio/releases/tag/v0.1.5
[0.1.4]: https://github.com/teamerisingstars/relio/releases/tag/v0.1.4
[0.1.3]: https://github.com/teamerisingstars/relio/releases/tag/v0.1.3
[0.1.2]: https://github.com/teamerisingstars/relio/releases/tag/v0.1.2
[0.1.1]: https://github.com/teamerisingstars/relio/releases/tag/v0.1.1
[0.1.0]: https://github.com/teamerisingstars/relio/releases/tag/v0.1.0
