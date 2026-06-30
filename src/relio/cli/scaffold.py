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
