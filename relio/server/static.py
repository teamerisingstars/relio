# relio/server/static.py
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
