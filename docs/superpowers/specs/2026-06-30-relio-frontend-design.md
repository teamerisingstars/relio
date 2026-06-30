# Relio Frontend Layer — Design

**Date:** 2026-06-30
**Status:** Draft for review
**Builds on:** the backend (`/api/*`) and `2026-06-30-relio-framework-architecture.md` §3.2 / §11.

## Goal

A Vite + React + TypeScript single-page app — the reference client of the Relio
framework. It talks to the backend over `/api`, streams the chat agent loop, and
includes a memory browser so the unified memory store is visible, not just chat.
Later, the DevOps layer has FastAPI serve this app's built `dist/` on one port.

## Scope (this plan)

In: Vite/React/TS scaffold; a typed API client (add / search / delete memory +
SSE chat stream); a two-pane UI (streaming **ChatView** + **MemoryBrowser**);
Vitest + React Testing Library component tests with the API client mocked.
**Out:** OpenAPI→TS codegen (hand-written client for now), auth UI, settings
panel, mobile/desktop shells, the reverse-proxy/Docker layer.

## Where it lives

A new `relio/frontend/` folder (sibling to `src/` and `tests/` in the package) —
the React app of the single package. Dev uses Vite's proxy to forward `/api` to
the FastAPI backend; prod (later) builds to `frontend/dist/` served by FastAPI.

```
relio/frontend/
  package.json
  tsconfig.json
  vite.config.ts        # Vite + Vitest config + dev proxy /api -> :8000
  index.html            # loads fonts; mounts #root
  src/
    main.tsx            # React entry
    App.tsx             # two-pane layout
    api/
      types.ts          # MemoryRecord, Scope, SearchResult (mirror backend)
      client.ts         # addMemory / searchMemory / deleteMemory / chatStream
    components/
      ChatView.tsx      # streaming chat
      MemoryBrowser.tsx # search + list + add + delete
    styles.css          # design tokens + layout
  tests/
    client.test.ts
    ChatView.test.tsx
    MemoryBrowser.test.tsx
```

## Components

### Typed API client (`api/client.ts` + `api/types.ts`)
Hand-written, mirrors the backend contract:
- `addMemory(content, {user?}) -> MemoryRecord` — `POST /api/memory`
- `searchMemory(q, {user?, limit?}) -> {results, text}` — `GET /api/memory/search`
- `deleteMemory(id) -> {deleted}` — `DELETE /api/memory/{id}`
- `chatStream(message, {user?}) -> AsyncGenerator<string>` — `POST /api/chat`,
  reads the response body stream, parses `data: {...}\n\n` SSE frames, yields each
  `delta`, stops on `{"done": true}`, throws on `{"error"}`.

### ChatView
Message list + input. On send: append the user message, open `chatStream`, and
append assistant tokens as they arrive (live streaming). Disables input while
streaming; shows an error line if the stream errors.

### MemoryBrowser
A search box (calls `searchMemory`), a results list (each row: content +
type/scope chips + a delete button calling `deleteMemory`), and a small "add
memory" form (calls `addMemory`, then refreshes the list).

### App
Two-pane layout: ChatView (primary) + MemoryBrowser (side panel). A single
`user` value (default `"you"`) is threaded into both so memories are scoped
consistently.

## Design direction (distinctive, not generic)

Theme: an **"archive / memory"** aesthetic — calm, warm, characterful. Built via
the **frontend-design skill** at implementation time; avoid generic AI styling
(no Inter/Roboto/system-default body font, no purple-on-white gradients).

Design tokens (in `styles.css` as CSS custom properties):
- Canvas `#FAF7F2` (warm paper), surface `#FFFFFF`, ink `#1B1A17`, muted `#6B655C`
- Accent `#2F6F62` (muted teal — ties to "rely/recall"), accent-soft `#E7EFEC`
- Display font **Fraunces** (serif, headings/brand), body **IBM Plex Sans**
  (loaded via `<link>` in `index.html`)
- Rounded surfaces (12–16px), hairline borders `#E9E3DA`, generous spacing,
  user/assistant message bubbles with distinct alignment + tint.

## Error handling
- Network/API errors surface inline (a message row in chat; an error line in the
  browser) — never a blank screen.
- `chatStream` throws on an `{"error"}` SSE frame; ChatView catches and renders it.

## Testing (the gate)
Vitest + React Testing Library + jsdom, API client mocked (`vi.mock`) or `fetch`
stubbed:
- `client.test.ts` — `addMemory`/`searchMemory` request shape + JSON parsing
  (stub `fetch`); `chatStream` parses multi-frame SSE and yields deltas, stops at
  `done`, throws on `error` (stub `fetch` with a `ReadableStream`).
- `ChatView.test.tsx` — mock the client's `chatStream` to yield a couple of
  deltas; type a message, click send, assert the streamed assistant text renders
  and the user message appears.
- `MemoryBrowser.test.tsx` — mock `searchMemory`/`addMemory`; search renders
  result rows; submitting the add form calls `addMemory` and refreshes.

No live backend or browser needed — mirrors the backend's offline-test approach.

## Out of scope (later plans)
OpenAPI→TS codegen, auth/login UI, settings/model switcher, React Native + Tauri
shells, and the single-port DevOps layer (Caddy/Vite-proxy prod + Dockerfile +
`relio` CLI).

## Environment note
Requires Node.js + npm (the frontend toolchain). `npm install` pulls Vite, React,
TypeScript, Vitest, and Testing Library. Independent of the Python toolchain.
