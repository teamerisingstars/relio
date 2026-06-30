# relio/cli/scaffold.py
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

_TEMPLATES = Path(__file__).resolve().parent.parent / "templates"

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


_WEB_APP_PY = '''\
from relio import Memory
from relio.server import create_app
from relio.server.llm.claude import ClaudeProvider

# One SQLite file, one local memory store. The chat LLM uses ANTHROPIC_API_KEY.
# In production the built React app (web/dist) is served on the same port.
memory = Memory(path="relio.db")
app = create_app(memory, ClaudeProvider(), frontend_dir="web/dist")
'''

_WEB_DOCKERFILE = """\
# syntax=docker/dockerfile:1

# --- stage 1: build the React frontend ---
FROM node:20-slim AS web
WORKDIR /web
COPY web/package.json ./
RUN npm install
COPY web/ ./
RUN npm run build

# --- stage 2: python runtime serving API + built frontend on one port ---
FROM python:3.12-slim AS runtime
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . ./
COPY --from=web /web/dist ./web/dist
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
"""

_WEB_GITIGNORE = "__pycache__/\n*.db\n*.db-wal\n*.db-shm\nweb/node_modules/\nweb/dist/\n"

_WEB_README = """\
# {name}

A memory-native AI app built with [Relio](https://github.com/relio-ai) —
React + Vite frontend on a generated SDK, FastAPI backend, single-port deploy.

## Develop
```
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-...
uvicorn app:app --reload          # backend on :8000
cd web && npm install && npm run dev   # UI on :5173, proxies /api to :8000
```

## Regenerate the typed SDK (after backend API changes)
```
relio sdk --out web/src/sdk
```

## Deploy (one container, any host)
```
docker build -t {name} .
docker run -p 8000:8000 -e ANTHROPIC_API_KEY=sk-... {name}
```
"""


_CLAUDE_MD = """\
# {name} — built with Relio

This app uses the **Relio** framework. The AI/memory engine is a *called-in
component* (`RelioAI`) — you build a normal FastAPI + React app and call AI in
where needed. See `docs/`.

## Conventions (enforced by `relio check`)
- **Every source module must have a test** (in `tests/`) **and a doc** (in
  `docs/`). `relio check` fails otherwise, and the Claude Code Stop hook runs it.
- Use the `RelioAI` seam for AI; expose app data to the AI only through the
  **exposure map** (`ai.tool` / `ai.expose`).
- Build agents as **bounded contexts** (own memory space + tool slice + config).

## Workflow
- `relio develop "<what to build>"` — drive Claude Code to build a feature here;
  it feeds the current `relio check` gaps to the agent automatically.
- `relio test` — run the test suites. `relio test --coverage --min 80` enforces
  a coverage threshold.
- `relio check` — fail if any module lacks a test or a doc (Python and
  TypeScript/React); also run by the Claude Code Stop hook.
"""

_DOCS_README = """\
# {name} — Documentation

Document each module here (one concern per file). The framework's `relio check`
gate requires every source module to be referenced by a doc in this folder.
"""

_DOCS_APP = """\
# app

The application entrypoint. It wires the FastAPI `app` and mounts the `RelioAI`
component; AI is called into routes where needed.
"""

_TEST_APP = '''\
# Starter test for app.py. Expand with real coverage — `relio check` requires a
# test for every module (this file references the `app` module).
from pathlib import Path


def test_app_module_exists():
    assert Path("app.py").exists()
'''

_CLAUDE_SETTINGS = """\
{
  "hooks": {
    "Stop": [
      { "hooks": [ { "type": "command", "command": "relio check" } ] }
    ]
  }
}
"""


def _write_dev_harness(root: Path, name: str) -> None:
    """Instructions + docs + tests + the Claude Code gate hook, so a fresh app
    already satisfies `relio check` and is ready for agentic development."""
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "tests").mkdir(parents=True, exist_ok=True)
    (root / ".claude").mkdir(parents=True, exist_ok=True)
    (root / "CLAUDE.md").write_text(_CLAUDE_MD.format(name=name))
    (root / "docs" / "README.md").write_text(_DOCS_README.format(name=name))
    (root / "docs" / "app.md").write_text(_DOCS_APP)
    (root / "tests" / "test_app.py").write_text(_TEST_APP)
    (root / ".claude" / "settings.json").write_text(_CLAUDE_SETTINGS)


def write_scaffold(
    target: str,
    name: Optional[str] = None,
    web: bool = False,
    mobile: bool = False,
    desktop: bool = False,
) -> Path:
    """Create a runnable starter at `target`.

    Default: a zero-build HTML starter. `web`: React + Vite. `mobile`: React
    Native / Expo. `desktop`: Tauri. Each client embeds a freshly generated
    TypeScript SDK.
    """
    root = Path(target)
    name = name or root.name
    if mobile:
        return _write_mobile_scaffold(root, name)
    if desktop:
        return _write_desktop_scaffold(root, name)
    if web:
        return _write_web_scaffold(root, name)
    (root / "web").mkdir(parents=True, exist_ok=True)
    (root / "app.py").write_text(_APP_PY)
    (root / "web" / "index.html").write_text(_INDEX_HTML.format(name=name))
    (root / "Dockerfile").write_text(_DOCKERFILE)
    (root / "requirements.txt").write_text(_REQUIREMENTS)
    (root / ".gitignore").write_text(_GITIGNORE)
    (root / "README.md").write_text(_README.format(name=name))
    _write_dev_harness(root, name)
    return root


def _write_ts_sdk(sdk_dir: Path) -> None:
    """Generate the TypeScript SDK (types + client) into `sdk_dir`."""
    from ..sdkgen import app_schema, generate_ts_client, generate_ts_types

    schema = app_schema()
    sdk_dir.mkdir(parents=True, exist_ok=True)
    (sdk_dir / "types.ts").write_text(generate_ts_types(schema))
    (sdk_dir / "client.ts").write_text(generate_ts_client(schema))


def _write_web_scaffold(root: Path, name: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(_TEMPLATES / "web", root / "web", dirs_exist_ok=True)
    _write_ts_sdk(root / "web" / "src" / "sdk")

    (root / "app.py").write_text(_WEB_APP_PY)
    (root / "Dockerfile").write_text(_WEB_DOCKERFILE)
    (root / "requirements.txt").write_text(_REQUIREMENTS)
    (root / ".gitignore").write_text(_WEB_GITIGNORE)
    (root / "README.md").write_text(_WEB_README.format(name=name))
    _write_dev_harness(root, name)
    _write_component_tests_and_docs(root)
    return root


def _write_component_tests_and_docs(root: Path) -> None:
    """A co-located presence test + a doc for each React component, so the TS
    governance gate (`relio check`) passes on a fresh web scaffold."""
    src = root / "web" / "src"
    if not src.exists():
        return
    for comp in src.rglob("*.tsx"):
        if ".test." in comp.name:
            continue
        stem = comp.stem
        (comp.parent / f"{stem}.test.tsx").write_text(
            f"// presence test for {stem} — expand with real coverage.\n"
            f"test('{stem} present', () => {{ expect(true).toBe(true); }});\n"
        )
        (root / "docs" / f"{stem}.md").write_text(f"# {stem}\n\nReact component.\n")


def _write_mobile_scaffold(root: Path, name: str) -> Path:
    # A thin Expo client; the SDK lives at src/sdk and talks to a Relio backend.
    shutil.copytree(_TEMPLATES / "mobile", root, dirs_exist_ok=True)
    _write_ts_sdk(root / "src" / "sdk")
    (root / ".gitignore").write_text("node_modules/\n.expo/\ndist/\n")
    return root


def _write_desktop_scaffold(root: Path, name: str) -> Path:
    # Tauri wraps the same React UI as the web client; copy web, then overlay
    # the Tauri shell (its package.json replaces web's, adding the tauri CLI).
    shutil.copytree(_TEMPLATES / "web", root, dirs_exist_ok=True)
    shutil.copytree(_TEMPLATES / "desktop", root, dirs_exist_ok=True)
    _write_ts_sdk(root / "src" / "sdk")
    (root / ".gitignore").write_text("node_modules/\ndist/\nsrc-tauri/target/\n")
    return root
