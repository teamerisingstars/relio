# Changelog

All notable changes to Relio are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

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

[0.1.4]: https://github.com/teamerisingstars/relio/releases/tag/v0.1.4
[0.1.3]: https://github.com/teamerisingstars/relio/releases/tag/v0.1.3
[0.1.2]: https://github.com/teamerisingstars/relio/releases/tag/v0.1.2
[0.1.1]: https://github.com/teamerisingstars/relio/releases/tag/v0.1.1
[0.1.0]: https://github.com/teamerisingstars/relio/releases/tag/v0.1.0
