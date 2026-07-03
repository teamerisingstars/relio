# relio/studio/launch.py
"""Uvicorn entrypoint for Relio Studio.

`relio gui` runs ``uvicorn relio.studio.launch:app`` — this module builds the
Studio app with the default (real) registry, process manager, and bundled web
frontend. Kept tiny and side-effect-free at import time so uvicorn can load it.
"""
from __future__ import annotations

import secrets

from .app import create_studio_app

# A fresh per-process token, injected into the served page and required on every
# /api call — so only this browser session (not a random web page or a
# DNS-rebinding attacker) can drive Studio's process-spawning endpoints.
app = create_studio_app(token=secrets.token_urlsafe(32))
