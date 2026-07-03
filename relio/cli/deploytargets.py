# relio/cli/deploytargets.py
"""Config generators for deploying a Relio app to free hosting platforms.

A Relio app is a single Docker image serving the API + built frontend on one
port, so any host that runs a container works. These generators emit the small
per-platform config file each one wants; the app itself picks up ``DATABASE_URL``
(managed Postgres) and ``ANTHROPIC_API_KEY`` from the environment, so state lives
off the ephemeral container disk. See ``docs/deploying.md``.
"""
from __future__ import annotations

# Serverless ("non-instance") targets: no long-running process. They need a
# pooled DATABASE_URL and a hosted embedder, and SSE chat degrades — use the
# non-streaming POST /api/chat/complete endpoint. See docs/deploying.md.
SERVERLESS_TARGETS = {"vercel", "lambda", "netlify"}
TARGETS = {"docker", "fly", "render", "hf"} | SERVERLESS_TARGETS

_FLY_TOML = """\
# fly.toml — deploy this Relio app to Fly.io (Docker-native).
#   fly launch --copy-config --no-deploy --name {name}
#   fly secrets set ANTHROPIC_API_KEY=sk-... DATABASE_URL=postgres://...
#   fly deploy
app = "{name}"
primary_region = "iad"

[build]
  dockerfile = "Dockerfile"

[env]
  # A hosted embedder keeps memory small on tiny VMs; "local" needs ~512MB RAM.
  # Options: openai | gemini | local | deterministic. Secrets go via `fly secrets`.
  RELIO_EMBEDDER = "deterministic"

[http_service]
  internal_port = {port}
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 0

# Secrets (never commit): ANTHROPIC_API_KEY, DATABASE_URL — set via `fly secrets set`.
"""

_RENDER_YAML = """\
# render.yaml — Render Blueprint. Push to GitHub, then New + > Blueprint.
# Free managed Postgres: create a Neon project and paste its URL into DATABASE_URL.
services:
  - type: web
    name: {name}
    runtime: docker
    plan: free
    healthCheckPath: /api/health
    envVars:
      - key: ANTHROPIC_API_KEY
        sync: false          # set in the Render dashboard (secret)
      - key: DATABASE_URL
        sync: false          # your Neon/Supabase postgres:// URL
      - key: RELIO_EMBEDDER
        value: deterministic  # or openai / gemini (hosted) / local (needs RAM)
"""

_HF_README = """\
---
title: {name}
emoji: 🧠
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: {port}
pinned: false
---

# {name}

A memory-native Relio app, deployed as a Hugging Face **Docker Space** (free).

Set these under **Settings > Variables and secrets**:

- `ANTHROPIC_API_KEY` — the chat LLM
- `DATABASE_URL` — a managed Postgres URL (e.g. Neon) so memory persists
- `RELIO_EMBEDDER` — `openai` / `gemini` (hosted) or `deterministic` (demo)
"""


_VERCEL_INDEX = '''\
# Vercel serverless entry — Vercel's @vercel/python runtime serves the ASGI `app`
# exported here. It imports your project's app.py (one dir up), which serves both
# /api and the built frontend.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402  (your FastAPI app = ASGI callable Vercel runs)
'''

_VERCEL_JSON = """\
{{
  "version": 2,
  "builds": [
    {{ "src": "api/index.py", "use": "@vercel/python" }}
  ],
  "routes": [
    {{ "src": "/(.*)", "dest": "api/index.py" }}
  ]
}}
"""
# ^ Everything routes to the ASGI app; it serves /api and the frontend. Set
#   DATABASE_URL (use Neon's *pooled* URL), ANTHROPIC_API_KEY, RELIO_EMBEDDER
#   (openai|gemini — never `local`) as Project env vars in the Vercel dashboard.

_LAMBDA_HANDLER = '''\
# AWS Lambda entry — Mangum adapts the ASGI `app` to the Lambda event model.
# `pip install mangum` (add it to requirements.txt).
from app import app
from mangum import Mangum

handler = Mangum(app)
'''

_SERVERLESS_YML = """\
# serverless.yml — deploy the Relio backend to AWS Lambda (Serverless Framework).
#   npm i -g serverless && serverless deploy
service: {name}

provider:
  name: aws
  runtime: python3.12
  environment:
    # Use a POOLED Postgres URL (e.g. Neon -pooler) — serverless opens many conns.
    DATABASE_URL: ${{env:DATABASE_URL}}
    ANTHROPIC_API_KEY: ${{env:ANTHROPIC_API_KEY}}
    RELIO_EMBEDDER: ${{env:RELIO_EMBEDDER, 'deterministic'}}

functions:
  api:
    handler: lambda_handler.handler
    url: true            # Lambda Function URL (supports response streaming)
    timeout: 29

plugins:
  - serverless-python-requirements
"""

_NETLIFY_TOML = """\
# netlify.toml — Netlify hosts the STATIC frontend. Netlify Functions don't run
# Python natively, so deploy the Relio backend elsewhere (Vercel/Lambda/a
# container) and point the frontend at it here.
[build]
  publish = "web/dist"
  command = "cd web && npm install && npm run build"

[[redirects]]
  from = "/api/*"
  to = "https://YOUR-BACKEND-HOST/api/:splat"
  status = 200
  force = true
"""


def render_fly_toml(name: str, port: int = 8000) -> str:
    return _FLY_TOML.format(name=name, port=port)


def render_vercel_index() -> str:
    return _VERCEL_INDEX


def render_vercel_json(name: str) -> str:
    return _VERCEL_JSON.format(name=name)


def render_lambda_handler() -> str:
    return _LAMBDA_HANDLER


def render_serverless_yml(name: str) -> str:
    return _SERVERLESS_YML.format(name=name)


def render_netlify_toml(name: str) -> str:
    return _NETLIFY_TOML.format(name=name)


def render_render_yaml(name: str, port: int = 8000) -> str:
    return _RENDER_YAML.format(name=name, port=port)


def render_hf_space(name: str, port: int = 8000) -> str:
    return _HF_README.format(name=name, port=port)


def files_for(target: str, name: str, port: int = 8000) -> dict[str, str]:
    """Return ``{filename: content}`` config files to write for `target`.

    ``docker`` returns nothing (it uses the existing Dockerfile flow).
    """
    if target == "fly":
        return {"fly.toml": render_fly_toml(name, port)}
    if target == "render":
        return {"render.yaml": render_render_yaml(name, port)}
    if target == "hf":
        return {"README.md": render_hf_space(name, port)}
    if target == "vercel":
        return {
            "api/index.py": render_vercel_index(),
            "vercel.json": render_vercel_json(name),
        }
    if target == "lambda":
        return {
            "lambda_handler.py": render_lambda_handler(),
            "serverless.yml": render_serverless_yml(name),
        }
    if target == "netlify":
        return {"netlify.toml": render_netlify_toml(name)}
    return {}
