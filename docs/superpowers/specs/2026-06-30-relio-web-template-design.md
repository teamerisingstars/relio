# Feature F — Rich `relio new` React Template

**Date:** 2026-06-30
**Status:** Implemented
**Part of:** Relio missing-features build-out (Feature F of A–G)

## Problem

`relio new` emitted a single `app.py` plus a plain-HTML chat page — not the
React UI kit the architecture (§3.2, §4.3) promises.

## Decision

Store templates as real files under `relio/templates/` and **copy** them, rather
than inlining React source as Python strings. `relio new <name> --web` copies
the web template and generates the typed SDK (Feature E) into it. The HTML
starter stays the default (`relio new <name>`), so existing scaffold behavior is
unchanged.

## Design

- `relio/templates/web/`: a real Vite + React + TypeScript app — `package.json`,
  `tsconfig.json`, `vite.config.ts` (dev proxy `/api` → `:8000`), `index.html`,
  and `src/` with `App.tsx`, `ChatView.tsx`, `MemoryBrowser.tsx`, `styles.css`.
  Components import `RelioClient` and types from `./sdk/*`.
- `write_scaffold(target, name, web=False)`:
  - `web=False` → existing HTML starter.
  - `web=True` → copy the template, run the SDK generator into
    `web/src/sdk/{types.ts,client.ts}`, write a `web/dist`-serving `app.py`, a
    multi-stage Dockerfile (node build → python runtime), requirements,
    gitignore, README.
- `relio new <name> --web` flag drives it.
- `pyproject` `force-include` ships `relio/templates/` in the wheel.

## Out of scope (YAGNI)

- Running `npm install` / building the app during scaffold (the user does that).
- Auth wiring in the template (uses anonymous default; API key is a follow-up).
- Mobile/desktop templates — Feature G.

## Tests

- `write_scaffold(web=True)` produces `app.py` (serving `web/dist`),
  `web/package.json`, `web/src/App.tsx`, generated `sdk/types.ts` +
  `sdk/client.ts`, and a node→python multi-stage Dockerfile.
- `relio new <name> --web` writes the React app + SDK.
- HTML default scaffold unchanged (existing tests still green).
