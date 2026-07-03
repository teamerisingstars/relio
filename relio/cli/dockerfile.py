# relio/cli/dockerfile.py
"""The single source of truth for a Relio app's production Dockerfile.

Two shapes, both serving the API + frontend on one port:
- `web=True`  — multi-stage: build the React app in `web/` → `web/dist`, then run.
- `web=False` — single-stage: a zero-build HTML app served from `web/`.

The scaffold, `relio dockerfile`, and `relio deploy` all render from here so the
Dockerfile can't drift from the directory convention the scaffold establishes
(the app's `app.py` uses `frontend_dir="web/dist"` for web, `"web"` otherwise).
"""
from __future__ import annotations

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

_PLAIN_DOCKERFILE = """\
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . ./
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
"""


def render_dockerfile(web: bool = True) -> str:
    """The production Dockerfile. `web=True` (default) is the multi-stage React
    build (`web/` → `web/dist`); `web=False` is the single-stage HTML app.

    The app's `app.py` must expose `app = create_app(..., frontend_dir="web/dist")`
    (web) or `"web"` (plain)."""
    return _WEB_DOCKERFILE if web else _PLAIN_DOCKERFILE
