# relio/studio/actions.py
"""Map a Studio UI action to a concrete command run in a project's directory.

Almost every action shells out to ``python -m relio <sub>`` so Studio reuses the
installed CLI's logic (npm resolution, uvicorn, docker, sdkgen). ``check`` is not
here — it's called via ``check_project()`` directly for structured results.
"""
from __future__ import annotations

import sys
from typing import Optional

from .process import relio_command

# Long-running actions keep a server alive; the rest run once and exit.
LONG_RUNNING = {"dev", "serve"}
ONE_SHOT = {"build", "test", "deploy", "sdk", "dockerfile", "install"}
ACTIONS = LONG_RUNNING | ONE_SHOT

# Default vite dev-server port used by scaffolded web apps.
_DEV_PORT = 5173
_DEFAULT_SERVE_PORT = 8000


def action_command(action: str, params: Optional[dict] = None) -> list[str]:
    """Build the command list for `action`. Raises ValueError for unknown actions."""
    params = params or {}
    if action not in ACTIONS:
        raise ValueError(f"unknown action: {action!r}")
    if action == "install":
        # Install the project's Python deps so Test/SDK/serve work from the GUI
        # (the DX gap: Studio never bootstrapped a freshly-created project).
        return [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]
    if action == "serve":
        port = int(params.get("port", _DEFAULT_SERVE_PORT))
        return relio_command("serve", "--port", str(port))
    if action == "deploy":
        name = str(params.get("name", "relio-app"))
        cmd = relio_command("deploy", "--name", name)
        target = params.get("target")
        if target:
            cmd += ["--target", str(target)]
        return cmd
    if action == "sdk":
        out = str(params.get("out", "sdk"))
        return relio_command("sdk", "--out", out)
    return relio_command(action)


def app_url(action: str, params: Optional[dict] = None) -> Optional[str]:
    """The URL where the running app can be opened, or None for non-server actions."""
    params = params or {}
    if action == "dev":
        return f"http://localhost:{_DEV_PORT}"
    if action == "serve":
        port = int(params.get("port", _DEFAULT_SERVE_PORT))
        return f"http://localhost:{port}"
    return None
