# Relio Studio — GUI Control Panel (Design)

Date: 2026-07-03

## Goal

After `pip install relio`, a user runs `relio gui` to open a **local web control
panel** ("Relio Studio") where they can **create** Relio projects and **control**
them (run/stop dev & serve, build/test/check, deploy/SDK/Dockerfile, browse the
running app's memory) — without touching the terminal.

## Delivery

New CLI command:

```
relio gui [--port 4000] [--no-open] [--host 127.0.0.1]
```

Starts a self-contained FastAPI app bundled in the package (`relio/studio/`),
serves a **no-build** HTML/CSS/JS frontend from `relio/studio/web/`, and opens the
browser. Requires the `server` extra (FastAPI + uvicorn), same as `relio serve`.

Frontend is intentionally build-free (vanilla JS): it ships as static files inside
the wheel, needs no Node to *use* Studio, and avoids the `relio check` gate (which
only scans `.py/.ts/.tsx`).

## Components (each isolated + unit-tested)

### `relio/studio/registry.py`
Pure filesystem logic, no FastAPI.
- `ProjectRecord(id, name, path, kind)` — `id` is a stable 12-char hash of the
  resolved path.
- `Registry(path=~/.relio/projects.json)`:
  - `list()` → records, each annotated `exists: bool` (folder still present).
  - `add(path, name=None, kind=None)` → dedupe by resolved path; infer `kind`.
  - `remove(id)` → drop from registry (does **not** delete files).
  - `detect(path)` → `kind|None`: a Relio project is a dir with `app.py` and a
    `requirements.txt`/`pyproject.toml` referencing `relio`.
  - `scan(folder)` → list of detected project paths under `folder` (one level).

### `relio/studio/process.py` — `ProcessManager`
Runs and tracks commands per project; streams output.
- Spawns via an **injectable** `spawner` (real one pipes stdout/stderr merged);
  tests inject a fake — no real processes in tests (mirrors the CLI's
  `runner`/`spawner` seam).
- Keyed by `(project_id, action)`. A reader thread appends lines to a bounded
  `deque` (buffer for late-joining log viewers).
- `start(project_id, action, cmd, cwd)` (no-op if already running),
  `stop(project_id, action)` (graceful terminate), `status(project_id)`
  (running actions + pid + returncode), `logs(project_id, action, since)`
  (buffered tail for SSE).

### `relio/studio/actions.py`
Maps a UI action to a command run in the project's directory, almost always
`[sys.executable, "-m", "relio", <sub>, ...]` — reusing all existing CLI logic
(npm resolution, uvicorn, docker, sdkgen). `check` is special-cased to call
`check_project()` directly for structured violations.

### `relio/studio/app.py` — FastAPI factory
Thin wiring; accepts injectable `registry` + `manager` for tests.
- `GET  /api/health`
- `GET  /api/projects` — list + running status + missing flag
- `POST /api/projects` — scaffold via `write_scaffold`/`write_ai_scaffold`
  (`{name, parent_dir, kind}`), auto-register
- `POST /api/projects/import` — `{path}` add existing
- `POST /api/projects/scan` — `{folder}` → detected; optional bulk add
- `DELETE /api/projects/{id}` — unregister
- `POST /api/projects/{id}/actions/{action}` — start (dev/serve/build/test/deploy/sdk/dockerfile)
- `POST /api/projects/{id}/stop/{action}` — stop
- `GET  /api/projects/{id}/check` — structured violations
- `GET  /api/projects/{id}/logs/{action}` — SSE stream (buffered tail + live)
- SPA/static fallback serves `relio/studio/web/`.

### `relio/studio/web/` (no build)
`index.html` + `styles.css` + `app.js`. Sidebar of projects + detail view with
tabs: **Overview**, **Run** (dev/serve start/stop + live logs + open-app link),
**Tasks** (build/test/check), **Deploy** (dockerfile/deploy/sdk), **Memory**
(iframe of the running app). Dialogs: "New Project", "Add existing", "Scan folder".

## Data flow

- **Create:** POST `/api/projects` → scaffold → auto-register → sidebar updates.
- **Run:** POST `.../actions/dev` → `ProcessManager.start` → status "running",
  "Open app" link (vite 5173 for dev, chosen `--port` for serve) → logs via SSE.
- **Task:** POST `.../actions/test` → streamed output + final return code.
- **Memory:** iframe the running project's own URL.

## Error handling

- Missing `npm`/`docker`, port in use, import errors → surfaced as a result card,
  not a stack trace (CLI already handles Windows `npm.cmd`; Studio reuses it via
  `python -m relio`).
- Stopping Studio terminates tracked child processes (graceful `terminate()`).
- Registry entries whose folder vanished are flagged `missing`, not dropped.

## Testing

- `registry.py`: temp-dir registry file; add/remove/detect/scan.
- `process.py`: fake spawner with canned output; start/stop/status/logs.
- `actions.py`: assert command construction per kind/action.
- `app.py`: FastAPI `TestClient` with injected fake registry + manager.
- Each module gets a `docs/*.md` entry so `relio check` stays green.

## Phasing (all phases in scope for this build)

1. Registry+scan, create, list, run/stop dev & serve, live logs, open-app link.
2. Build/test/check tasks with pass/fail.
3. Deploy/SDK/Dockerfile.
4. Embedded memory/data view (iframe of running app).

## Non-goals (YAGNI)

- Detached processes surviving Studio restart.
- Remote/multi-user hosting or auth (local-only, binds `127.0.0.1`).
- Editing project source in the GUI.
