# relio/logs.py
"""Relio's logging: one logger tree under `relio`, an opt-in configurator, and a
structured audit channel for the governance surface (tool calls).

Library etiquette: importing Relio attaches only a `NullHandler` and never
configures the root logger — apps own their logging. Call `configure_logging()`
(or set your own handlers on the `relio` logger) to see output.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

ROOT = "relio"

# Never emit "No handlers could be found" and never hijack the app's logging.
logging.getLogger(ROOT).addHandler(logging.NullHandler())


def get_logger(name: str = "") -> logging.Logger:
    """A child of the `relio` logger — `get_logger("agents")` -> `relio.agents`,
    so apps can tune levels per subsystem (`logging.getLogger("relio.audit")`)."""
    return logging.getLogger(f"{ROOT}.{name}" if name else ROOT)


# The audit channel: every governed tool invocation is logged here with
# structured `extra` (tool / scope / outcome). Route it wherever compliance needs.
audit_log = get_logger("audit")


class JsonFormatter(logging.Formatter):
    """One JSON object per line: standard fields + any structured `extra` passed
    under the reserved `relio` key (e.g. `logger.info(msg, extra={"relio": {...}})`)."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra = getattr(record, "relio", None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(
    level: Optional[str] = None,
    *,
    json: bool = False,
    stream: Optional[Any] = None,
) -> logging.Logger:
    """Opt-in console logging for the `relio` tree. `level` falls back to the
    `RELIO_LOG_LEVEL` env var, then `INFO`; `RELIO_LOG_JSON=1` forces JSON. Safe to
    call repeatedly — it replaces only the handler it previously installed."""
    level = (level or os.environ.get("RELIO_LOG_LEVEL") or "INFO").upper()
    as_json = json or os.environ.get("RELIO_LOG_JSON") in ("1", "true", "True")

    logger = logging.getLogger(ROOT)
    logger.setLevel(level)
    handler = logging.StreamHandler(stream)
    handler.setFormatter(
        JsonFormatter()
        if as_json
        else logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    handler._relio_handler = True  # type: ignore[attr-defined]
    # Idempotent: drop a handler we installed on a prior call, keep the app's.
    logger.handlers = [h for h in logger.handlers if not getattr(h, "_relio_handler", False)]
    logger.addHandler(handler)
    logger.propagate = False  # our handler is terminal; don't double-log via root
    return logger
