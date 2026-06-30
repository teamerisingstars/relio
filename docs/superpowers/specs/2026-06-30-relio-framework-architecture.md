# Relio Framework — Architecture

**Date:** 2026-06-30
**Status:** Draft for review
**Companion to:** `2026-06-30-relio-memory-design.md` (the memory engine / core spec)

This document describes the architecture of the **whole framework** — the
Python+React full-stack framework whose defining feature is that it builds and
deploys as a **single unit (one port, one command)**. The memory engine spec
covers the core; this covers everything around it and how it composes.

---

## 1. Two things to keep separate

- **The framework** = what the user is building and ships to other developers.
  It provides: the **memory engine** (Relio Memory core), a **CLI**, **project
  templates**, the **FastAPI⇄React integration glue**, and the **DevOps
  generators** (Dockerfile, reverse-proxy config, process orchestration).
- **An app** = what a developer creates with the framework (`relio new myapp`).
  It is a scaffolded project that depends on the framework and runs as one
  single-port deployable.

Most of this doc describes the **runtime architecture of an app** (because that
is where "one port, one deploy" lives) and the **framework components** that
produce it.

---

## 2. Layered architecture (an app at runtime)

```
                        ┌─────────────────────────────┐
   one public port ───► │   Reverse proxy / entrypoint │   (Caddy, or FastAPI as router)
                        │   /api/* → backend           │
                        │   /*     → frontend          │
                        └───────────┬─────────────────┘
                          ┌─────────┴──────────┐
                          ▼                    ▼
              ┌───────────────────┐   ┌──────────────────────┐
              │  React frontend   │   │   FastAPI backend     │
              │  (SPA default;    │   │   - REST + streaming  │
              │   SSR opt-in)     │   │   - agent loop (LLM)  │
              │  chat/agent UI    │   │   - auth (later)      │
              └───────────────────┘   └──────────┬───────────┘
                                                  │ in-process call (no network)
                                                  ▼
                                   ┌──────────────────────────────┐
                                   │   Relio Memory engine        │
                                   │   API → Recall → Embedding     │
                                   │        → Store core            │
                                   └──────────────┬────────────────┘
                                                  ▼
                                   ┌──────────────────────────────┐
                                   │  Single SQLite file            │
                                   │  vectors + structured + KV +   │
                                   │  graph (on local disk/volume)  │
                                   └──────────────────────────────┘

   (Also: an MCP server process exposes the same engine to external agents.)
```

**Key property:** the backend calls the memory engine **in-process** (a Python
function call, not a network hop) because both are Python. No sidecar, no second
database service. The only "service" boundary inside the container is the proxy
in front of frontend+backend, which is what unifies them onto one port.

---

## 3. Layers in detail

### 3.1 Reverse proxy / single entrypoint
- Exposes **one port** publicly; routes `/api/*` → FastAPI, everything else →
  the frontend (static files or the SSR renderer).
- Default implementation: **FastAPI mounts the built SPA as static files** (then
  there is literally one process). When SSR is enabled, a small **Caddy** (or
  similar) sits in front of a Node renderer + FastAPI — still one port, one
  container. The topology is **chosen per app at build time** (see §10.4).
- Framework-generated; the developer never writes proxy config.

### 3.2 Frontend layer (React)
- React app built with Vite. Ships a **chat/agent UI kit** (message stream,
  tool/Memory views, input box) so an app looks complete on day one.
- Talks to the backend only through `/api`. **Types are generated from the
  backend's OpenAPI schema**, so the memory record and API shapes are defined
  once (Python/Pydantic) and mirrored in TypeScript automatically.
- Default render mode: **static SPA**. SSR is an opt-in that the proxy already
  accommodates.

### 3.3 Backend layer (FastAPI)
- REST + streaming (SSE/websocket) endpoints, e.g. `POST /api/chat`.
- The **agent loop**: receives a user turn → `relio.recall()` for relevant
  memory → calls the LLM (via an AI SDK / Claude) → streams the reply → writes
  new facts with `relio.add()`.
- Auth / multi-tenant: deferred, but this is the layer that will own it.
- Imports the engine as a library; no network between backend and memory.

### 3.4 Memory engine (Relio Memory core)
- The embeddable Python library specified in the engine design doc: Public API →
  Recall engine → Embedding layer (+ cache/dedup, local default model) → Store
  core → single SQLite file (vectors via `sqlite-vec`, structured columns, KV
  with TTL, graph `nodes`/`edges`).
- Also runs as an **MCP server** so external agents (Claude, etc.) use the same
  memory without going through the app's HTTP API.

### 3.5 Storage
- **One SQLite file** on local disk or a mounted volume (default). Backups = copy
  a file. No external database service — this is what makes the app cheap and
  self-contained.
- Accessed through a **pluggable `StorageBackend` interface** so it can later
  swap to Postgres+pgvector without changing callers. See §10.1.

---

## 4. Framework components (what the user builds)

1. **`relio` engine package** — the memory core + MCP server (per engine spec).
2. **CLI** — `relio new` (scaffold), `relio dev` (run both with hot-reload on
   one URL), `relio build` (produce the one container/artifact), `relio
   deploy` (ship it).
3. **Project templates** — scaffolded apps: pre-wired FastAPI backend, and
   **web (React), mobile (React Native/Expo), and desktop (Tauri)** clients, each
   with the UI kit and a working chat-with-memory example. `relio new` picks any
   subset (see §11).
4. **Integration glue** — FastAPI⇄engine wiring, OpenAPI→**SDK generation**
   (TypeScript SDK for web/RN, Python SDK for CLI/desktop/server), the agent-loop
   helpers.
5. **DevOps generators** — produce the Dockerfile, proxy/router config, and
   process orchestration so build/deploy is single-command.
6. **Config** (`relio.config.py`) — embedder choice, model/API keys, DB path,
   port. One file controls the app.

---

## 5. Request flows

**In-app chat (the common path):**
1. UI sends a turn to `POST /api/chat` (through the proxy on the one port).
2. FastAPI agent loop calls `relio.recall(query, scope)` in-process.
3. Engine returns token-light memory lines; backend builds the prompt and calls
   the LLM, streaming tokens back to the UI.
4. New facts from the turn are written via `relio.add(...)`.

**External agent (compatibility path):**
1. An MCP-capable agent connects to the **MCP server**.
2. It calls `add` / `recall` tools directly against the same SQLite file.

---

## 6. Build & deploy pipeline (single command)

```
relio build:
  1. Build React  ──►  static assets (or SSR bundle)
  2. Collect assets into the FastAPI app (or behind the proxy)
  3. Assemble Dockerfile + proxy config + processes
  4. Output: ONE container image

relio deploy:
  - Run/push that one image  ──►  one port, any host
```

The two toolchains (Python, JS) exist under the hood; the CLI orchestrates them
behind one command. The deployer sees one artifact and one port.

---

## 7. Repo / package layout

**An app created with the framework** (clients are opt-in via `relio new`):
```
myapp/
  relio.config.py        # single config file
  backend/                # FastAPI app: routes, agent loop
  web/                    # React app (Vite) + UI kit            [--web]
  mobile/                 # React Native / Expo app              [--mobile]
  desktop/                # Tauri app (can bundle backend)       [--desktop]
  sdk/                    # generated TS + Python clients
  data/relio.db          # the single SQLite memory file (gitignored)
  Dockerfile              # generated by `relio build` (backend/web)
  proxy/                  # generated proxy config (if SSR)
```
The memory engine is a **dependency** (`pip install relio`), not vendored.

**The framework repo itself (what the user develops):**
```
relio/
  engine/                 # the memory core + MCP server  ← built FIRST
  cli/                    # relio new|dev|build|deploy
  templates/              # scaffolds: backend, web, mobile (RN), desktop (Tauri)
  integration/            # FastAPI glue, OpenAPI→SDK gen (TS+Py), agent helpers
  devops/                 # Dockerfile + proxy generators
```

---

## 8. Build order (within the one framework)

1. **Engine** (this is the moat; everything depends on it) — per engine spec.
2. **Backend integration** — FastAPI wiring + agent loop around the engine.
3. **SDK generation** — OpenAPI→TypeScript + Python clients (the substrate every
   non-web device uses).
4. **Web frontend** — React UI kit on the TS SDK.
5. **DevOps layer + CLI** — single-port proxy, Dockerfile generator, `dev/build/
   deploy`.
6. **Mobile + desktop clients** — React Native/Expo and Tauri scaffolds on the
   same SDK (Tauri optionally bundles the backend for offline). Built after web,
   since they reuse its UI kit and the SDK.
7. **Templates** — tie it together into `relio new --web/--mobile/--desktop`.

Each layer is usable on its own and only depends on the layers beneath it.

---

## 9. Cross-cutting concerns

- **One source of truth for the format:** the memory record is defined in the
  engine (Pydantic); the API exposes it; the frontend gets generated TS types.
- **Config in one place:** `relio.config.py`.
- **Licensing:** all layers MIT/permissive; SQLite public domain; framework
  intended MIT.
- **Out of scope (for now):** hosted control plane / managed SaaS, horizontal
  scaling beyond what a single Postgres node gives, billing. (Auth and
  multi-tenancy are now partially in scope — see §10.2.)

---

## 10. Architecture refinements (decided)

These four refinements were decided after the first draft and supersede the
"deferred" notes above where they overlap.

### 10.1 Storage — pluggable backend, SQLite default
- The engine talks to a **`StorageBackend` interface**, never to SQLite directly.
  Callers (recall, store core) depend only on this interface.
- **Default backend: SQLite in WAL mode** — many concurrent readers + one
  serialized writer, which suits a single-node AI backend. Vectors via
  `sqlite-vec`, structured columns, KV, and graph tables all in the one file.
- **Documented scale path: a `Postgres + pgvector` backend** implementing the
  same interface — swap via config, **no caller changes**. Built when single-node
  limits are hit (roughly: very high write concurrency or many millions of
  vectors), not in the first build.
- **Durability:** SQLite backups = copy the file; optional **Litestream** for
  continuous backup to object storage. Postgres = standard backups.
- This keeps the cheap/self-contained default while removing the "rewrite to
  scale" risk.

### 10.2 Multi-tenancy & auth — support both isolation models
- **Scope** gains a `tenant` dimension (alongside user/agent/session). Every
  engine query is **filtered by scope**, derived from the authenticated
  principal — an app cannot accidentally read across tenants.
- **Two isolation models, both shipped (configurable per app):**
  - **Shared DB + enforced scoping** (default) — one database, row-level tenant
    filtering. Cheapest, simplest.
  - **DB-per-tenant** — one SQLite file (or Postgres schema) per tenant. Strong
    isolation, trivial per-tenant backup/export/delete. Opt-in for strict B2B.
- **Auth is pluggable:** the framework ships a minimal built-in (API key /
  session) to start, plus an **auth hook** so an app brings its own (JWT/OAuth).
  The hook's job is to resolve the request to a `tenant`/`user` scope, which the
  backend then passes to the engine. The backend layer owns auth; the engine only
  ever sees a scope.

### 10.3 Agent / LLM layer — lean loop *and* raw primitives
- **Primitives are first-class:** `relio.recall()` / `relio.add()` and a basic
  chat endpoint are always available, so a developer can write their own agent
  loop and ignore ours. The memory layer never *requires* our loop.
- **Batteries-included lean loop (optional):** a thin, typed `recall → LLM → add`
  loop with:
  - a **pluggable LLM-provider interface**, **Claude (Anthropic) as default**,
    streaming via SSE;
  - a configurable **memory token budget** controlling how many token-light
    recall lines get injected into the prompt;
  - **pluggable memory extraction** deciding what a turn is worth storing —
    heuristic default (store user-stated facts/preferences), optional LLM-based
    extraction.
- **No heavy agent framework** (no LangChain/LlamaIndex dependency) — keeps the
  layer small and avoids a second opinionated memory system fighting ours.

### 10.4 Deploy topology — chosen per app at build time
- Each app selects its topology in `relio.config.py`; `relio build` generates
  the matching container:
  - **SPA single-process** (default) — React built to static, served by FastAPI
    on one port. One process, no extra proxy. Simplest, cheapest.
  - **Proxied SSR** — Caddy (or similar) in front of a Node SSR renderer +
    FastAPI, managed by a small process supervisor. Still one container, one port,
    one deploy.
- **Dev** (`relio dev`) always runs the Vite dev server (HMR) + uvicorn
  (reload) with the frontend proxying `/api` to the backend, presented at a
  single URL — regardless of the prod topology chosen.
- **Deploy targets:** one Docker image → any Docker host; first-class docs for
  Fly / Render / Railway / a plain VPS. (Vercel is JS-only and does not fit the
  Python backend — noted explicitly.)

---

## 11. Multi-device / client tier

The backend is **API-first** (HTTP `/api` + MCP) and **headless** — the web app
is just the reference client. The framework ships **web, mobile, and desktop**
clients, all talking to the same backend, plus generated SDKs to keep them in
sync with the format.

### 11.1 The substrate (required, effectively already true)
- The backend works with **no frontend at all**; any device that speaks HTTP (or
  MCP) is a valid client.
- **Generated client SDKs** keep clients aligned with the one source of truth:
  a **TypeScript SDK** (web / React Native) and a **Python SDK** (CLI / desktop /
  server), both generated from the backend's OpenAPI schema. The memory record
  shape is defined once (Pydantic) and flows out to every client.

### 11.2 Clients the framework scaffolds

| Client | Tech | Notes |
|--------|------|-------|
| **Web** | React (Vite) | Reference client; the single-port deploy in §1–§6 |
| **Mobile** | **React Native / Expo** | Reuses the UI-kit logic and the TS SDK; a thin client talking to the backend |
| **Desktop** | **Tauri** | Wraps the web UI; can **bundle the backend (engine + SQLite) as a sidecar** for a fully offline, on-device app |

- `relio new` can scaffold any subset (`--web`, `--mobile`, `--desktop`).
- `relio build mobile` / `relio build desktop` produce the platform artifacts.

### 11.3 Offline / on-device

- **Desktop offline is strong now:** because the engine is an embeddable Python
  library backed by one SQLite file, a **Tauri app bundles the whole backend
  locally** (engine + DB as a sidecar process) — no server, fully offline,
  single-device AI memory.
- **Mobile is a thin client by default:** iOS/Android do not run Python natively,
  so phones **talk to a backend over the API**. True **on-device memory on a
  phone** would require a **native port of the engine** — feasible *because the
  format is open and SQLite-based* (a Swift/Kotlin reader of the same
  `sqlite-vec` file), but it is a large, separate future effort, not in the first
  builds.

### 11.4 Honest distribution caveat
The "one port, one command, one deploy" property is about the **server/web**
backend. **Native mobile and desktop apps are distributed through their own
channels** (App Store / TestFlight / Play Store; signed installers / auto-update)
— that is inherent to those platforms and cannot be folded into a single server
deploy. The framework still gives a **single build command per platform**
(`relio build mobile|desktop`), but shipping a native app is a separate
distribution step from deploying the backend.
