# relio/cli/dockerfile.py
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
