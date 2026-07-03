# Relio Studio (the `gui` command)

Relio Studio is a local, browser-based control panel for creating and controlling
Relio projects — so you don't have to remember the CLI. Launch it with:

```bash
relio gui                 # opens http://127.0.0.1:4000 in your browser
relio gui --port 4100     # choose a port
relio gui --no-open       # don't auto-open the browser
relio gui --host 0.0.0.0  # bind more widely (local-only by default)
```

Studio requires the `server` extra (`pip install "relio[server]"`), the same as
`relio serve`. It binds to `127.0.0.1` by default — it's a local dev tool, not a
hosted service.

## What you can do

- **Create a project** — the *New project* dialog scaffolds `app`, `web`,
  `mobile`, `desktop`, or `ai` starters (the same code paths as `relio new`).
- **Add / scan existing projects** — register a folder, or scan a workspace for
  any folder that looks like a Relio project (`app.py` + a `relio` dependency).
- **Run / stop** the dev server and one-port `serve`, with live streaming logs and
  an *Open app* link.
- **Build / test / check** — trigger `relio build`, `relio test`, and the
  governance gate, seeing output and violations inline.
- **Deploy / SDK / Dockerfile** — write the Dockerfile, build the image, or
  generate client SDKs.
- **Browse memory** — embed the running app to inspect its chat & memory.

## How it's built

Studio is a small, isolated subsystem under `relio/studio/`:

- **`registry`** (`registry.py`) — tracks known projects in
  `~/.relio/projects.json`; also handles `detect` and `scan`.
- **`process`** (`process.py`) — the `ProcessManager` spawns, tracks, and streams
  the output of commands per project.
- **`actions`** (`actions.py`) — maps each UI action to a
  `python -m relio <sub>` command, reusing all of the installed CLI's logic.
- **`app`** (`app.py`) — the FastAPI factory (`create_studio_app`) wiring routes
  onto the registry, the manager, and the scaffold/check helpers.
- **`launch`** (`launch.py`) — the `uvicorn` entrypoint used by `relio gui`.
- **`web/`** — a no-build HTML/CSS/JS frontend served straight from the package.

The registry and process manager are injectable, so the whole thing is unit-tested
without touching your home directory or spawning real processes.
