# tests/server/test_auth_default.py — the wildcard-scope default must warn.
import logging

from relio.embedding.base import DeterministicEmbedder
from relio.memory import Memory
from relio.server.app import create_app
from relio.server.auth import anonymous_auth
from relio.server.llm.fake import FakeProvider


def _mem(tmp_path):
    return Memory(path=str(tmp_path / "m.db"), embedder=DeterministicEmbedder(dim=16))


def test_no_auth_hook_warns(tmp_path, caplog):
    with caplog.at_level(logging.WARNING, logger="relio.server.app"):
        create_app(_mem(tmp_path), FakeProvider())
    assert any("no auth" in r.message.lower() for r in caplog.records)


def test_explicit_anonymous_auth_is_silent(tmp_path, caplog):
    with caplog.at_level(logging.WARNING, logger="relio.server.app"):
        create_app(_mem(tmp_path), FakeProvider(), auth=anonymous_auth)
    assert not any("no auth" in r.message.lower() for r in caplog.records)
