# Relio DevOps / Packaging Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the layer that makes Relio one-port / one-container / one-command: FastAPI serves the built frontend alongside `/api`, a generated Dockerfile produces one host-agnostic image, and a `relio` CLI (incl. a `relio new` scaffold) ties it together.

**Architecture:** A `mount_frontend` helper turns `create_app` into a single-port server. A `relio` argparse CLI with an injectable subprocess `run` helper (so it's unit-testable). A Dockerfile generator and a zero-build `relio new` scaffold. All tests are offline — no real npm/docker/uvicorn spawned.

**Tech Stack:** Python (stdlib argparse/subprocess), FastAPI StaticFiles, pytest. Builds on the existing `relio` package (engine + server + frontend all done).

---

## File Structure

```
relio/src/relio/
  server/
    static.py        # mount_frontend(app, dist_dir)
    app.py           # create_app(..., frontend_dir=None)  [modified]
  cli/
    __init__.py
    main.py          # argparse CLI + run() + handlers
    dockerfile.py    # render_dockerfile()
    scaffold.py      # write_scaffold(target, name)
relio/tests/
  test_static.py
  test_dockerfile.py
  test_scaffold.py
  test_cli.py
```

All commands run from `relio`. Use `python -m pytest` (bare `pytest` is not on PATH).

---

### Task 0: CLI package + console script

**Files:**
- Create: `relio/src/relio/cli/__init__.py` (empty)
- Modify: `relio/pyproject.toml`

- [ ] **Step 1: Create the empty cli package**

Create `relio/src/relio/cli/__init__.py` (empty file).

- [ ] **Step 2: Add the console script to pyproject.toml**

In `relio/pyproject.toml`, add this section (after `[project.optional-dependencies]`):
```toml
[project.scripts]
relio = "relio.cli.main:main"
```

- [ ] **Step 3: Reinstall so the entry point + new package are picked up**

Run: `cd relio && pip install -e ".[dev]"`
Expected: reinstalls with no errors.

- [ ] **Step 4: Commit**

```bash
git add relio/pyproject.toml relio/src/relio/cli/__init__.py
git commit -m "chore: add relio CLI package + console script"
```

---

### Task 1: Single-port static serving

**Files:**
- Create: `relio/src/relio/server/static.py`
- Modify: `relio/src/relio/server/app.py`
- Test: `relio/tests/test_static.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_static.py
import pytest
from fastapi.testclient import TestClient

from relio.memory import Memory
from relio.embedding.base import DeterministicEmbedder
from relio.server.app import create_app
from relio.server.llm.fake import FakeProvider


def _client(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html>INDEX")
    (dist / "assets" / "app.js").write_text("APP")
    memory = Memory(path=str(tmp_path / "s.db"), embedder=DeterministicEmbedder(dim=16))
    app = create_app(memory, FakeProvider(), frontend_dir=str(dist))
    return TestClient(app), memory


def test_root_serves_index(tmp_path):
    client, memory = _client(tmp_path)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "INDEX" in resp.text
    memory.close()


def test_api_still_wins_over_spa(tmp_path):
    client, memory = _client(tmp_path)
    assert client.get("/api/health").json() == {"status": "ok"}
    memory.close()


def test_unknown_route_falls_back_to_index(tmp_path):
    client, memory = _client(tmp_path)
    assert "INDEX" in client.get("/dashboard/anything").text
    memory.close()


def test_asset_is_served(tmp_path):
    client, memory = _client(tmp_path)
    assert client.get("/assets/app.js").text == "APP"
    memory.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd relio && python -m pytest tests/test_static.py -v`
Expected: FAIL — `create_app()` has no `frontend_dir` parameter (TypeError) or `relio.server.static` missing.

- [ ] **Step 3: Write `static.py` and wire it into `app.py`**

```python
# src/relio/server/static.py
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def mount_frontend(app: FastAPI, dist_dir: str) -> None:
    """Serve a built SPA from `dist_dir`: assets + an index.html catch-all.

    Call AFTER including the API routers so `/api/*` always wins.
    """
    dist = Path(dist_dir)
    if not dist.is_dir():
        raise FileNotFoundError(f"frontend dist not found: {dist_dir}")
    index = dist / "index.html"
    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str) -> FileResponse:
        candidate = dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(index))
```

Then modify `src/relio/server/app.py`. Add the import and the `frontend_dir` parameter, and mount the frontend **last** (after both routers):

```python
# src/relio/server/app.py — add near the other imports
from .static import mount_frontend
```

```python
# src/relio/server/app.py — change the create_app signature + body
def create_app(
    memory: Memory,
    provider: LLMProvider,
    settings: Optional[Settings] = None,
    frontend_dir: Optional[str] = None,
) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="Relio")

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    app.include_router(build_memory_router(memory))
    app.include_router(build_chat_router(memory, provider, settings))
    app.state.relio_memory = memory
    app.state.relio_provider = provider
    app.state.relio_settings = settings
    if frontend_dir is not None:
        mount_frontend(app, frontend_dir)  # catch-all registered last
    return app
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd relio && python -m pytest tests/test_static.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Run the existing server tests to confirm no regression**

Run: `cd relio && python -m pytest tests/server -v`
Expected: PASS (existing server tests still green — `frontend_dir` defaults to None, so no catch-all is added for them).

- [ ] **Step 6: Commit**

```bash
git add relio/src/relio/server/static.py relio/src/relio/server/app.py relio/tests/test_static.py
git commit -m "feat: single-port static serving (mount_frontend)"
```

---

### Task 2: Dockerfile generator

**Files:**
- Create: `relio/src/relio/cli/dockerfile.py`
- Test: `relio/tests/test_dockerfile.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dockerfile.py
from relio.cli.dockerfile import render_dockerfile


def test_dockerfile_has_node_build_and_python_runtime():
    df = render_dockerfile()
    assert "FROM node" in df
    assert "npm run build" in df
    assert "FROM python" in df
    assert "uvicorn" in df
    assert "EXPOSE" in df
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd relio && python -m pytest tests/test_dockerfile.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'relio.cli.dockerfile'`

- [ ] **Step 3: Write the implementation**

```python
# src/relio/cli/dockerfile.py
from __future__ import annotations

_DOCKERFILE = """\
# syntax=docker/dockerfile:1

# --- stage 1: build the React frontend ---
FROM node:20-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- stage 2: python runtime serving API + built frontend on one port ---
FROM python:3.12-slim AS runtime
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . ./
COPY --from=frontend /frontend/dist ./frontend/dist
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
"""


def render_dockerfile() -> str:
    """The production Dockerfile for an app using the React frontend.

    The app's `app.py` must expose `app = create_app(..., frontend_dir="frontend/dist")`.
    """
    return _DOCKERFILE
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd relio && python -m pytest tests/test_dockerfile.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add relio/src/relio/cli/dockerfile.py relio/tests/test_dockerfile.py
git commit -m "feat: production Dockerfile generator"
```

---

### Task 3: `relio new` scaffold

**Files:**
- Create: `relio/src/relio/cli/scaffold.py`
- Test: `relio/tests/test_scaffold.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_scaffold.py
from relio.cli.scaffold import write_scaffold


def test_scaffold_creates_runnable_starter(tmp_path):
    root = write_scaffold(str(tmp_path / "myapp"), "myapp")
    assert (root / "app.py").is_file()
    assert (root / "web" / "index.html").is_file()
    assert (root / "Dockerfile").is_file()
    assert (root / "requirements.txt").is_file()
    assert (root / "README.md").is_file()

    assert "create_app" in (root / "app.py").read_text()
    index = (root / "web" / "index.html").read_text()
    assert "myapp" in index and "/api/chat" in index
    assert "relio[server]" in (root / "requirements.txt").read_text()
    assert "uvicorn" in (root / "Dockerfile").read_text()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd relio && python -m pytest tests/test_scaffold.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'relio.cli.scaffold'`

- [ ] **Step 3: Write the implementation**

```python
# src/relio/cli/scaffold.py
from __future__ import annotations

from pathlib import Path
from typing import Optional

_APP_PY = '''\
from relio import Memory
from relio.server import create_app
from relio.server.llm.claude import ClaudeProvider

# One SQLite file, one local memory store. The chat LLM uses ANTHROPIC_API_KEY.
memory = Memory(path="relio.db")
app = create_app(memory, ClaudeProvider(), frontend_dir="web")
'''

_INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{name}</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 640px; margin: 40px auto; padding: 0 16px; }}
  #log {{ white-space: pre-wrap; border: 1px solid #ddd; border-radius: 8px; padding: 12px; min-height: 220px; }}
  form {{ display: flex; gap: 8px; margin-top: 12px; }}
  input {{ flex: 1; padding: 8px; }}
</style>
</head>
<body>
<h1>{name}</h1>
<div id="log"></div>
<form id="f"><input id="m" placeholder="Ask..." autocomplete="off" /><button>Send</button></form>
<script>
const log = document.getElementById('log');
document.getElementById('f').onsubmit = async (e) => {{
  e.preventDefault();
  const m = document.getElementById('m');
  const text = m.value.trim();
  if (!text) return;
  m.value = '';
  log.textContent += '\\nyou: ' + text + '\\nrelio: ';
  const res = await fetch('/api/chat', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify({{ message: text, user: 'you' }}),
  }});
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = '';
  while (true) {{
    const {{ done, value }} = await reader.read();
    if (done) break;
    buf += dec.decode(value, {{ stream: true }});
    let i;
    while ((i = buf.indexOf('\\n\\n')) !== -1) {{
      const f = buf.slice(0, i).trim();
      buf = buf.slice(i + 2);
      if (!f.startsWith('data:')) continue;
      const p = JSON.parse(f.slice(f.indexOf(':') + 1).trim());
      if (p.delta) log.textContent += p.delta;
    }}
  }}
}};
</script>
</body>
</html>
"""

_DOCKERFILE = """\
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . ./
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
"""

_REQUIREMENTS = "relio[server]\n"

_GITIGNORE = "__pycache__/\n*.db\n*.db-wal\n*.db-shm\n"

_README = """\
# {name}

A memory-native AI app built with [Relio](https://github.com/relio-ai).

## Run locally
```
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-...        # the chat LLM
uvicorn app:app --reload
```
Open http://localhost:8000

## Deploy (one container, any host)
```
docker build -t {name} .
docker run -p 8000:8000 -e ANTHROPIC_API_KEY=sk-... {name}
```
"""


def write_scaffold(target: str, name: Optional[str] = None) -> Path:
    """Create a zero-build, runnable single-port starter app at `target`."""
    root = Path(target)
    name = name or root.name
    (root / "web").mkdir(parents=True, exist_ok=True)
    (root / "app.py").write_text(_APP_PY)
    (root / "web" / "index.html").write_text(_INDEX_HTML.format(name=name))
    (root / "Dockerfile").write_text(_DOCKERFILE)
    (root / "requirements.txt").write_text(_REQUIREMENTS)
    (root / ".gitignore").write_text(_GITIGNORE)
    (root / "README.md").write_text(_README.format(name=name))
    return root
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd relio && python -m pytest tests/test_scaffold.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add relio/src/relio/cli/scaffold.py relio/tests/test_scaffold.py
git commit -m "feat: relio new scaffold (zero-build single-port starter)"
```

---

### Task 4: The CLI

**Files:**
- Create: `relio/src/relio/cli/main.py`
- Test: `relio/tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli.py
import pytest

from relio.cli.main import build_parser, main


class FakeRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, cmd, cwd=None):
        self.calls.append(cmd)
        return 0


def test_parser_recognizes_subcommands():
    parser = build_parser()
    assert parser.parse_args(["new", "myapp"]).command == "new"
    assert parser.parse_args(["new", "myapp"]).name == "myapp"
    assert parser.parse_args(["serve", "--port", "9000"]).port == 9000
    for c in ("dev", "build", "dockerfile", "deploy"):
        assert parser.parse_args([c]).command == c


def test_build_runs_npm():
    runner = FakeRunner()
    assert main(["build"], runner=runner) == 0
    assert runner.calls == [["npm", "--prefix", "frontend", "run", "build"]]


def test_serve_runs_uvicorn_on_the_port():
    runner = FakeRunner()
    main(["serve", "--port", "9000"], runner=runner)
    assert runner.calls == [
        ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "9000"]
    ]


def test_deploy_builds_the_docker_image():
    runner = FakeRunner()
    main(["deploy"], runner=runner)
    assert runner.calls == [["docker", "build", "-t", "relio-app", "."]]


def test_dockerfile_writes_a_dockerfile(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main(["dockerfile"], runner=FakeRunner())
    assert (tmp_path / "Dockerfile").is_file()
    assert "uvicorn" in (tmp_path / "Dockerfile").read_text()


def test_new_scaffolds_an_app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main(["new", "myapp"], runner=FakeRunner())
    assert (tmp_path / "myapp" / "app.py").is_file()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd relio && python -m pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'relio.cli.main'`

- [ ] **Step 3: Write the implementation**

```python
# src/relio/cli/main.py
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import Callable, Optional

from .dockerfile import render_dockerfile
from .scaffold import write_scaffold

Runner = Callable[..., int]


def run(cmd: list[str], cwd: Optional[str] = None) -> int:
    return subprocess.call(cmd, cwd=cwd)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="relio", description="Relio framework CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    new = sub.add_parser("new", help="scaffold a new memory-native app")
    new.add_argument("name")

    sub.add_parser("dev", help="run backend + frontend dev servers")
    sub.add_parser("build", help="build the React frontend")

    serve = sub.add_parser("serve", help="serve API + built frontend on one port")
    serve.add_argument("--port", type=int, default=8000)

    sub.add_parser("dockerfile", help="write the production Dockerfile")
    sub.add_parser("deploy", help="build the Docker image")
    return parser


def cmd_new(args: argparse.Namespace, runner: Runner) -> int:
    write_scaffold(args.name, args.name)
    return 0


def cmd_dev(args: argparse.Namespace, runner: Runner) -> int:
    # Vite dev server proxies /api to the backend (started separately with --reload).
    return runner(["npm", "--prefix", "frontend", "run", "dev"])


def cmd_build(args: argparse.Namespace, runner: Runner) -> int:
    return runner(["npm", "--prefix", "frontend", "run", "build"])


def cmd_serve(args: argparse.Namespace, runner: Runner) -> int:
    return runner(["uvicorn", "app:app", "--host", "0.0.0.0", "--port", str(args.port)])


def cmd_dockerfile(args: argparse.Namespace, runner: Runner) -> int:
    Path("Dockerfile").write_text(render_dockerfile())
    return 0


def cmd_deploy(args: argparse.Namespace, runner: Runner) -> int:
    return runner(["docker", "build", "-t", "relio-app", "."])


_HANDLERS: dict[str, Callable[[argparse.Namespace, Runner], int]] = {
    "new": cmd_new,
    "dev": cmd_dev,
    "build": cmd_build,
    "serve": cmd_serve,
    "dockerfile": cmd_dockerfile,
    "deploy": cmd_deploy,
}


def main(argv: Optional[list[str]] = None, runner: Runner = run) -> int:
    args = build_parser().parse_args(argv)
    return _HANDLERS[args.command](args, runner)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd relio && python -m pytest tests/test_cli.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Verify the console script + full suite**

Run: `cd relio && relio --help`
Expected: prints usage listing the subcommands (confirms the entry point works). If `relio` is not on PATH, run `python -m relio.cli.main --help` instead and note it.

Run: `cd relio && python -m pytest -v -m "not integration"`
Expected: PASS — all engine, server, and devops tests green.

- [ ] **Step 6: Commit**

```bash
git add relio/src/relio/cli/main.py relio/tests/test_cli.py
git commit -m "feat: relio CLI (new/dev/build/serve/dockerfile/deploy)"
```

---

## Self-Review

**Spec coverage (DevOps design doc):**
- Single-port serving (`mount_frontend` + `create_app(frontend_dir=)`) → Task 1. ✅
- Dockerfile generator (multi-stage node→python) → Task 2. ✅
- `relio new` zero-build runnable scaffold → Task 3. ✅
- CLI: new/dev/build/serve/dockerfile/deploy + injectable runner + console script → Tasks 0, 4. ✅
- Offline tests (no real npm/docker/uvicorn) → all test tasks use temp dirs + FakeRunner. ✅

**Deferred (not in this plan, by design):** fly.toml/compose generators, registry push, auth, hosted control plane, RN/Tauri shells, OpenAPI→TS codegen.

**Type/name consistency:** `create_app(memory, provider, settings=None, frontend_dir=None)` (Task 1) — the added 4th param is keyword-default, so existing callers (server tests, conftest) are unaffected. `render_dockerfile()` (Task 2) and `write_scaffold(target, name=None)` (Task 3) are imported by `cli/main.py` (Task 4) with matching signatures. The CLI's `run(cmd, cwd=None)` matches the `FakeRunner.__call__(cmd, cwd=None)` test double. Command lists in the tests match the handler implementations exactly. The scaffold's `app.py` uses `create_app(..., frontend_dir="web")`, consistent with Task 1's new parameter.

**Placeholder scan:** No TBD/TODO; every code step contains complete, runnable code.
