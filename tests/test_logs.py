# tests/test_logs.py
import json
import logging

from relio import RelioAI, configure_logging, get_logger
from relio.embedding.base import DeterministicEmbedder
from relio.logs import ROOT, JsonFormatter
from relio.memory import Memory
from relio.record import Scope


def _ai(tmp_path):
    m = Memory(path=str(tmp_path / "l.db"), embedder=DeterministicEmbedder(dim=16))
    return RelioAI(memory=m)


def test_get_logger_is_a_child_of_relio():
    assert get_logger().name == ROOT
    assert get_logger("agents").name == "relio.agents"


def test_root_logger_has_a_null_handler_by_default():
    # Importing Relio must not emit "no handlers" or configure the root logger.
    handlers = logging.getLogger(ROOT).handlers
    assert any(isinstance(h, logging.NullHandler) for h in handlers)


def test_configure_logging_is_idempotent_and_reads_env(monkeypatch):
    monkeypatch.setenv("RELIO_LOG_LEVEL", "WARNING")
    logger = configure_logging()
    assert logger.level == logging.WARNING
    ours = [h for h in logger.handlers if getattr(h, "_relio_handler", False)]
    assert len(ours) == 1
    # calling again replaces (not duplicates) our handler
    configure_logging(level="INFO")
    ours = [h for h in logging.getLogger(ROOT).handlers if getattr(h, "_relio_handler", False)]
    assert len(ours) == 1
    assert logging.getLogger(ROOT).level == logging.INFO
    # reset so we don't leak config into other tests
    logging.getLogger(ROOT).handlers = [
        h for h in logging.getLogger(ROOT).handlers if not getattr(h, "_relio_handler", False)
    ]
    logging.getLogger(ROOT).propagate = True


def test_json_formatter_emits_structured_extra():
    rec = logging.LogRecord("relio.audit", logging.INFO, __file__, 1, "hi", None, None)
    rec.relio = {"tool": "pay", "outcome": "called"}
    out = json.loads(JsonFormatter().format(rec))
    assert out["logger"] == "relio.audit" and out["message"] == "hi"
    assert out["tool"] == "pay" and out["outcome"] == "called"


def test_tool_call_is_audited(tmp_path, caplog):
    ai = _ai(tmp_path)

    @ai.tool
    def lookup(who: str, scope: Scope = None) -> str:
        return "ok"

    with caplog.at_level(logging.INFO, logger="relio.audit"):
        ai.call_tool("lookup", scope=Scope(tenant="acme"), who="x")
    rec = next(r for r in caplog.records if r.name == "relio.audit")
    assert rec.relio["tool"] == "lookup" and rec.relio["outcome"] == "called"
    assert rec.relio["tenant"] == "acme"           # principal captured
    ai.close()


def test_request_logging_middleware(tmp_path, caplog):
    from fastapi.testclient import TestClient

    from relio.server.app import create_app

    m = Memory(path=str(tmp_path / "r.db"), embedder=DeterministicEmbedder(dim=16))
    app = create_app(m, request_logging=True)
    with caplog.at_level(logging.INFO, logger="relio.server.request"):
        with TestClient(app) as c:
            assert c.get("/api/health").status_code == 200
    rec = next(r for r in caplog.records if r.name == "relio.server.request")
    assert rec.relio["path"] == "/api/health" and rec.relio["status"] == 200
    m.close()


def test_destructive_block_is_audited(tmp_path, caplog):
    import pytest

    ai = _ai(tmp_path)

    @ai.tool(destructive=True)
    def wipe() -> str:
        return "gone"

    with caplog.at_level(logging.WARNING, logger="relio.audit"):
        with pytest.raises(PermissionError):
            ai.call_tool("wipe")   # not confirmed
    rec = next(r for r in caplog.records if r.name == "relio.audit")
    assert rec.relio["outcome"] == "blocked" and rec.relio["destructive"] is True
    ai.close()
