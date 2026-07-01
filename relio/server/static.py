# relio/server/static.py
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger("relio")


def mount_frontend(app: FastAPI, dist_dir: str) -> None:
    """Serve a built SPA from `dist_dir`: assets + an index.html catch-all.

    Call AFTER including the API routers so `/api/*` always wins. If the frontend
    hasn't been built yet (`dist_dir` absent), serve the API only rather than
    failing to start — so `uvicorn app:app` works before `relio build`.
    """
    dist = Path(dist_dir)
    if not dist.is_dir():
        logger.warning(
            "frontend dist not found at %r; serving API only. Run `relio build`.",
            dist_dir,
        )
        return
    index = dist / "index.html"
    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str) -> FileResponse:
        # An unknown /api/* path is a real 404 (JSON), not the SPA shell — so
        # missing/typo'd API routes don't silently return index.html.
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="not found")
        candidate = dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(index))
