# Feature G — Mobile (Expo) + Desktop (Tauri) Scaffolds

**Date:** 2026-06-30
**Status:** Implemented (templates; not built in this environment)
**Part of:** Relio missing-features build-out (Feature G of A–G)

## Problem

The architecture (§11) promises web, mobile, and desktop clients on a shared
SDK, but only web existed. No `templates/mobile/` or `templates/desktop/`.

## Decision

Reuse Feature F's `templates/` + SDK-generation pattern. `relio new <name>
--mobile` and `--desktop` copy a template tree and generate the TypeScript SDK
into it. Honest scope: these are **structurally complete scaffolds**, not
compiled apps — Expo (simulator/toolchain) and Tauri (Rust toolchain) cannot be
built in this environment.

## Design

- `relio/templates/mobile/` — Expo / React Native thin client: `package.json`,
  `app.json`, `tsconfig.json`, `babel.config.js`, `App.tsx` (memory add/search
  over the SDK), README. Talks to a backend over the API.
- `relio/templates/desktop/` — Tauri overlay: `package.json` (adds
  `@tauri-apps/cli`), `src-tauri/` (`tauri.conf.json`, `Cargo.toml`, `build.rs`,
  `src/main.rs`), README. The desktop scaffold copies the **web** template first
  (reusing the React UI), then overlays this shell.
- `write_scaffold(..., mobile=False, desktop=False)` dispatches; a shared
  `_write_ts_sdk(dir)` generates `types.ts` + `client.ts` for every client.
- `relio new` gains `--mobile` / `--desktop` flags.
- `pyproject` `force-include` already ships `relio/templates/` (all clients).

## Known limitations (documented in templates)

- **Mobile chat streaming:** React Native's `fetch` has no streaming body, so
  `client.chat` (SSE via `getReader`) doesn't work there; the mobile starter
  uses the memory endpoints. Desktop (webview) streams fine.
- **On-device engine:** bundling the Python engine + SQLite as a Tauri sidecar
  (fully offline) is noted as roadmap, not implemented.

## Out of scope (YAGNI)

- `relio build mobile|desktop` platform-artifact commands.
- Native distribution (App Store / signing) — inherent per-platform steps.

## Tests

- `write_scaffold(mobile=True)` emits `App.tsx`, an Expo `package.json`, and the
  generated SDK at `src/sdk/`.
- `write_scaffold(desktop=True)` emits the reused web `src/App.tsx`, the
  `src-tauri/` shell, a tauri `package.json`, and the SDK.
- `relio new --mobile` / `--desktop` produce the same.
