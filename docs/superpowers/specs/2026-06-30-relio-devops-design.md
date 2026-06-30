# Relio DevOps / Packaging Layer — Design

**Date:** 2026-06-30
**Status:** Draft for review
**Builds on:** the backend (`relio.server`), the frontend (`relio/frontend`), and
`2026-06-30-relio-framework-architecture.md` §1, §6, §10.4.

## Goal

The layer that fuses engine + backend + frontend into **one port, one container,
one command** — the defining promise of the framework. FastAPI serves the built
frontend alongside `/api` on a single port; a generated Dockerfile produces one
host-agnostic image; and a `relio` CLI ties it together, including a `relio new`
scaffold that gives an indie dev a running memory-native AI app in one command.

## Target user (informs every choice)

Solo devs, indie hackers, self-hosters. So: **dead-simple, cheap, portable** —
a single container that runs anywhere (VPS, Fly, Render, Railway), local-first by
default, no Kubernetes, no managed services required.

## Scope (this plan)

In: single-port static serving from FastAPI; the `relio` CLI (`new` / `dev` /
`build` / `serve` / `dockerfile` / `deploy`); a Dockerfile generator; and a
`relio new` scaffold producing a runnable single-port starter. **Out:** push to a
specific registry/host config (fly.toml/compose), auth, multi-tenant hosting,
CI templates.

## Where it lives

```
relio/src/relio/
  server/
    static.py        # mount_frontend(app, dist_dir): serve SPA + /api on one port
    app.py           # create_app(..., frontend_dir=None) — mounts frontend if given
  cli/
    __init__.py
    main.py          # argparse CLI: new/dev/build/serve/dockerfile/deploy
    dockerfile.py    # render_dockerfile() -> multi-stage Dockerfile string
    scaffold.py      # write_scaffold(target): the `relio new` starter files
relio/tests/
  test_static.py
  test_cli.py
  test_dockerfile.py
  test_scaffold.py
```

`pyproject.toml` gains `[project.scripts] relio = "relio.cli.main:main"`.

## Components

### Single-port serving (`server/static.py`)
`mount_frontend(app, dist_dir)`: mounts `dist/assets` as static and registers a
**catch-all `GET /{full_path:path}`** that returns a real file when one exists,
else `index.html` (SPA fallback). `create_app` gains `frontend_dir: str | None`;
when set, it includes the API routers **first**, then mounts the frontend last —
so `/api/*` always wins and everything else serves the SPA. Result: API + UI on
one port, no proxy, no second process.

### The `relio` CLI (`cli/main.py`, argparse — zero new deps)
- `relio new <name>` — scaffold a runnable starter (see below).
- `relio dev` — run the FastAPI backend (uvicorn --reload) and the Vite dev
  server together for hot-reload development.
- `relio build` — `npm --prefix frontend run build` (produces `frontend/dist`).
- `relio serve [--port] [--frontend DIR]` — run uvicorn serving `create_app` with
  the built frontend on one port (the production run).
- `relio dockerfile` — write the generated Dockerfile to the project.
- `relio deploy` — build the Docker image (`docker build`) and print run
  instructions (host-agnostic; the user runs it anywhere).

Subprocess-invoking commands call a single injectable `run(cmd, cwd)` helper so
they're unit-testable by asserting the constructed command (no real npm/docker in
tests). `new`, `dockerfile`, and arg-parsing are tested directly.

### Dockerfile generator (`cli/dockerfile.py`)
`render_dockerfile()` returns a **multi-stage** Dockerfile string: stage 1 (Node)
runs `npm ci && npm run build` on `frontend/`; stage 2 (Python slim) installs
`relio[server]`, copies the app + built `dist`, exposes one port, and runs
`uvicorn` serving `create_app(..., frontend_dir="frontend/dist")`. One image,
any host.

### `relio new` scaffold (`cli/scaffold.py`)
`write_scaffold(target)` creates a **zero-build, instantly runnable** starter so a
dev sees a working memory-native chat app immediately:
- `app.py` — wires `Memory` + `ClaudeProvider` into `create_app`, serving a
  bundled static `web/` dir on one port.
- `web/index.html` — a tiny dependency-free chat page (vanilla JS: `fetch` +
  SSE against `/api/chat`) — works with **no Node/build step**.
- `Dockerfile` — Python-slim, `pip install relio[server]`, copy, run uvicorn.
- `requirements.txt` (`relio[server]`), `.gitignore`, `README.md` (run/deploy).

The full React app (`relio/frontend`) remains the richer reference UI the dev
graduates to via `relio dev` / `relio build`; the scaffold's vanilla page is the
zero-config on-ramp. This keeps `relio new` self-contained and testable.

## Error handling
- `serve`/`mount_frontend` with a missing `dist_dir` → clear error, not a crash.
- CLI: unknown subcommand → argparse usage/exit; missing `docker`/`npm` on
  `deploy`/`build` → the `run` helper surfaces the subprocess error.

## Testing (the gate)
- `test_static.py` — TestClient over a temp `dist/` (index.html + assets): `GET /`
  → index; `GET /api/health` → still the API; `GET /some/spa/route` → index
  (fallback); `GET /assets/app.js` → the asset.
- `test_dockerfile.py` — `render_dockerfile()` contains the Node build stage, the
  Python runtime stage, `uvicorn`, and `EXPOSE`.
- `test_scaffold.py` — `write_scaffold(tmp)` creates `app.py`, `web/index.html`,
  `Dockerfile`, `requirements.txt`, `README.md`; spot-check key contents.
- `test_cli.py` — the argparse parser recognizes each subcommand; `build`/`serve`/
  `deploy` construct the expected command list via an injected fake `run`; `new`
  delegates to `write_scaffold`.

All offline — no real npm/docker/uvicorn spawned in tests.

## Out of scope (later)
fly.toml / docker-compose generators, registry push, auth, hosted control plane,
the React Native + Tauri shells, OpenAPI→TS codegen.

## Environment note
`relio serve`/`deploy` need `uvicorn`/`docker` at runtime, and `relio build`/`dev`
need Node — but the **test suite mocks all subprocesses**, so it runs with neither.
